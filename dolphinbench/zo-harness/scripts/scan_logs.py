"""Scan every file a run produced for credential material; print counts and paths, never values.

    python scan_logs.py <run.conf-dir-or-run-dir> [--secrets DIR] [--extra PATH ...]

Checks, per file (text and binary alike, read as bytes):

1. exact  - the run's actual secret values (read from the env-files in --secrets): the
            OpenAI and OpenRouter keys and the judge relay password. Any hit is a leak.
2. token  - every 32-hex-char run is hashed and looked up in issued-token-hashes.txt (the
            SHA-256 of every per-interaction relay token the harness minted). A hit means a
            (revoked, single-interaction) relay capability was written somewhere.
3. shape  - credential-shaped strings: OpenAI/OpenRouter-style sk- keys, GitHub tokens,
            Slack tokens, AWS access key ids, PEM private keys, and Authorization: Bearer /
            api-key headers carrying a long value.

Output: one line per (check, file) with a hit count, then a JSON summary. Matched text is
never printed. The secrets directory itself is skipped.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SHAPES = {
    "openai_or_openrouter_sk_key": re.compile(rb"sk-(?:or-v1-|proj-|svcacct-|ant-)?[A-Za-z0-9_-]{20,}"),
    "github_token": re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}"),
    "slack_token": re.compile(rb"xox[abprs]-[A-Za-z0-9-]{10,}"),
    "aws_access_key_id": re.compile(rb"AKIA[0-9A-Z]{16}"),
    "pem_private_key": re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "bearer_header": re.compile(rb"(?i)authorization[\"']?\s*[:=]\s*[\"']?bearer\s+[A-Za-z0-9._~+/-]{20,}"),
    "api_key_header": re.compile(rb"(?i)[\"']?api-key[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9._-]{20,}"),
}
HEX32 = re.compile(rb"(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])")


def load_secrets(directory: Path | None) -> dict[str, bytes]:
    values = {}
    if directory is None:
        return values
    for path in sorted(directory.glob("*.env")):
        for line in path.read_text().splitlines():
            name, _, value = line.partition("=")
            if value:
                values[f"{path.name}:{name}"] = value.encode()
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--secrets", type=Path)
    parser.add_argument("--extra", type=Path, nargs="*", default=[])
    parser.add_argument("--exclude", type=Path, nargs="*", default=[],
                        help="trees that are not run output (e.g. a Hermes source checkout + venv)")
    args = parser.parse_args()
    secrets = load_secrets(args.secrets)
    ledger = args.run_dir / "issued-token-hashes.txt"
    issued = set()
    if ledger.exists():
        issued = {line.split()[0] for line in ledger.read_text().splitlines() if line.strip()}
    roots = [args.run_dir, *args.extra]
    files = []
    for root in roots:
        if root.is_file():
            files.append(root)
            continue
        for path in root.rglob("*"):
            if args.secrets and args.secrets in path.parents:
                continue
            if any(excluded == path or excluded in path.parents for excluded in args.exclude):
                continue
            if path.is_file() and not path.is_symlink():
                files.append(path)
    hits: dict[str, dict[str, int]] = {}
    scanned_bytes = 0

    def record(check: str, path: Path, count: int) -> None:
        if count:
            hits.setdefault(check, {})[str(path)] = hits.get(check, {}).get(str(path), 0) + count

    for path in files:
        try:
            data = path.read_bytes()
        except OSError as error:
            print(f"unreadable {path}: {error.strerror}", file=sys.stderr)
            continue
        scanned_bytes += len(data)
        for name, value in secrets.items():
            record(f"exact:{name}", path, data.count(value))
        if issued:
            record("token:issued_relay_token", path,
                   sum(1 for m in HEX32.finditer(data) if hashlib.sha256(m.group()).hexdigest() in issued))
        for name, pattern in SHAPES.items():
            record(f"shape:{name}", path, len(pattern.findall(data)))
    for check, per_file in sorted(hits.items()):
        for file, count in sorted(per_file.items()):
            print(f"HIT {check} {count} {file}")
    summary = {
        "files_scanned": len(files),
        "bytes_scanned": scanned_bytes,
        "exact_secret_values_checked": len(secrets),
        "issued_relay_tokens_checked": len(issued),
        "hits": {check: sum(per_file.values()) for check, per_file in sorted(hits.items())},
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
