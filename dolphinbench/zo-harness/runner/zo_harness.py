"""DolphinBench's Hermes + Luna agent, with Zouroboros as its memory provider (smoke adapter).

Modelled on the past.dev adapter (pastdotdev-benchmarks/dolphin/hermes_past.py): the agent is
DolphinBench's pinned reference Hermes (NousResearch/hermes-agent 935c1e8 + the benchmark's
evaluation patch) with one added plugin, `plugins/memory/zo`, and nothing else changed.

Differences from the full-benchmark procedure, per the smoke commission:

- Ingestion is adapter-side and direct: every history message is ingested through the
  Zouroboros memory system's standard ingest path (packages/memory/src/dolphinbench) with its
  timestamp, not through per-message Hermes turns. The store is then locked (PRAGMA query_only
  plus an adapter lock) and checkpointed (v2: SHA-256 over the ordered dolphinbench-scoped
  rows plus row counts; the DB file hash is informational only).
- Tests run on the benchmark's official test-phase toolsets: dolphinbench-apps, memory,
  session_search (reference/artifacts.py MATRIX_TOOLSETS at 81cb6f8). The agent recalls through
  the plugin's zo_recall tool against the frozen store served by the adapter server.
- Cost. Agent model calls go through the agent relay (agent_relay.py) tagged per interaction;
  a phase costs what OpenRouter billed for its calls, retries included (Hermes records no price
  for a relayed endpoint). Ingestion cost is the embedding batch, recorded by the ingest step in
  the run's accounting file. Memory recall is self-hosted and bills nothing.

Environment (see run_smoke.py): DOLPHINBENCH_HERMES_SOURCE, DOLPHINBENCH_HERMES_PYTHON,
DOLPHINBENCH_APP_PYTHON, AZURE_OPENAI_BASE_URL (agent relay), ZO_ADAPTER_URL,
AGENT_RELAY_TOKENS, AGENT_RELAY_TAGS. AZURE_FOUNDRY_API_KEY is set per interaction.

Secret hygiene (0.3.0). The benchmark's container launcher passes the agent's provider
variables to `docker create` as `--env NAME=VALUE` arguments, and an error dump of that
command once wrote a real key into a log. So no provider credential is ever in this process's
environment (run_smoke.py refuses to start if one is). The only value the agent container
receives is AZURE_FOUNDRY_API_KEY = `<token>.<tag>`, where <token> is minted for one
interaction, registered with the agent relay by its SHA-256 only (AGENT_RELAY_TOKENS/<hash>,
content = the tag), and deregistered when the interaction ends. A copy of that value in any
log is a revoked, single-interaction relay capability, never a provider key; the post-run
scan (scripts/scan_logs.py) checks every log for it by hash.
"""

from __future__ import annotations

import ast
import functools
import hashlib
import json
import os
import secrets
import subprocess
import time
import urllib.request
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

import yaml

import harness
from harness.adapter import InteractionRecord
from harness.adapters import hermes as hermes_module
from harness.adapters.hermes import HermesAdapter, environment
from harness.adapters.hermes_profile import _load_personas
from harness.durable_json import save_json
from harness.submission import check_total_cost, load_json


@contextmanager
def env_overlay(values: dict):
    """Like harness.adapters.hermes.environment, but None unsets the variable."""
    previous = {key: os.environ.get(key) for key in values}
    for key, value in values.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

ADAPTER_VERSION = "0.5.0"  # 0.2.0: null-enrichment app-call evidence repair (disclosed)
# 0.3.0: persisted copy (zouroboros-memory-benchmarks/dolphinbench/zo-harness); per-interaction
# relay tokens instead of a shared relay password; repair logic unchanged from 0.2.0.
# 0.4.0: second disclosed repair rule, declared non-null defaults of omitted parameters.
# 0.5.0: third disclosed repair rule, int/float representation of equal numbers (full run).
ROOT = Path(harness.__file__).resolve().parents[1]
# The benchmark's official test-phase toolsets (reference/artifacts.py MATRIX_TOOLSETS @81cb6f8).
BENCH_TOOLSETS = ["dolphinbench-apps", "memory", "session_search"]
# The public Hermes adapter module constant drives the -t flag and profile checks.
hermes_module.TOOLSETS = BENCH_TOOLSETS

PLUGIN = Path("plugins/memory/zo")
PLUGIN_FILES = ("plugins/memory/zo/__init__.py", "plugins/memory/zo/plugin.yaml")
AGENT_SPEC = json.loads((ROOT / "examples/reference/hermes-builtin.json").read_text())["agent"]
DIFF_FLAGS = ["--binary", "--full-index", "--no-ext-diff", "--no-textconv", "--no-renames",
              "--src-prefix=a/", "--dst-prefix=b/", "--unified=3"]
OPTIONS = {"source_env", "python_env", "app_python_env", "base_url_env", "zo_url_env",
           "relay_tokens_env"}
EMBEDDING_PRICE_PER_TOKEN = 0.02 / 1_000_000  # text-embedding-3-small, OpenAI list


def sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


# Where the release's repair server (mock_mcp/repair_server.py build_server) finds each
# tool's implementation: the first owner class that defines it, else the base server
# module. Read with ast (no import side effects); only literal defaults are used.
DEFAULT_SOURCES = (("repair_server.py", "CandidateSlack"), ("repair_calendar.py", "CandidateCalendar"),
                   ("repair_records.py", "CandidateRecords"), ("repair_travel.py", "CandidateTravel"),
                   ("repair_engineering.py", "CandidateEngineering"),
                   ("repair_operations.py", "CandidateOperations"), ("repair_growth.py", "CandidateGrowth"),
                   ("server.py", None))


@functools.lru_cache(maxsize=None)
def declared_defaults(tool: str) -> dict:
    """{parameter: literal default} of the function the release's server runs for `tool`."""
    for file, owner in DEFAULT_SOURCES:
        tree = ast.parse((ROOT / "mock_mcp" / file).read_text())
        scope = tree.body
        if owner is not None:
            classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == owner]
            if not classes:
                continue
            scope = classes[0].body
        for node in scope:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == tool:
                values = {}
                positional = node.args.posonlyargs + node.args.args
                for arg, default in zip(positional[len(positional) - len(node.args.defaults):],
                                        node.args.defaults):
                    try:
                        values[arg.arg] = ast.literal_eval(default)
                    except ValueError:
                        pass
                for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
                    if default is not None:
                        try:
                            values[arg.arg] = ast.literal_eval(default)
                        except ValueError:
                            pass
                return values
    return {}


def align_numbers(value, reference, path, retyped):
    """0.5.0 rule helper: `value` with each number that equals the number at the same key
    path in `reference` but differs only in int/float type replaced by the reference's
    number; changed paths are appended to `retyped`. Everything else is returned as is."""
    def number(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if isinstance(value, dict) and isinstance(reference, dict):
        return {k: align_numbers(v, reference[k], f"{path}.{k}" if path else k, retyped)
                if k in reference else v for k, v in value.items()}
    if isinstance(value, list) and isinstance(reference, list) and len(value) == len(reference):
        return [align_numbers(v, r, f"{path}[{i}]", retyped)
                for i, (v, r) in enumerate(zip(value, reference))]
    if number(value) and number(reference) and type(value) is not type(reference) and value == reference:
        retyped.append(path)
        return reference
    return value


def post_json(url: str, body: dict, timeout: float = 120.0) -> dict:
    request = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        return json.loads(raw) if raw else {}


class ZoHermesAdapter(HermesAdapter):
    """HermesAdapter with the Zouroboros memory provider and direct ingestion."""

    def __init__(self, options, work_dir):
        if set(options) != OPTIONS:
            raise ValueError(f"zo harness options must be {sorted(OPTIONS)}")
        self.home = work_dir / "hermes"
        self.profiles = self.home / "profiles"
        self.reference = None
        self.templates = {}
        source = Path(os.environ[options["source_env"]]).resolve()
        python = str(Path(os.environ[options["python_env"]]).absolute())
        self.app_python = str(Path(os.environ[options["app_python_env"]]).absolute())
        base_url = os.environ[options["base_url_env"]].rstrip("/")
        self.zo_url = os.environ[options["zo_url_env"]].rstrip("/")
        self.relay_tokens = Path(os.environ[options["relay_tokens_env"]])
        if not self.relay_tokens.is_dir() or self.relay_tokens.stat().st_mode & 0o077:
            raise ValueError("The relay token directory must exist with mode 0700")
        self.binary = str(Path(python).parent / "hermes")
        if not Path(self.binary).is_file():
            raise ValueError(f"Hermes binary does not exist: {self.binary}")
        self.source_identity = self._verify_source(source)
        self.generated_templates = self._build_templates(base_url)
        # Controller-side copy of the plugin configuration (prepare checks).
        self.home.mkdir(parents=True, exist_ok=True)
        (self.home / "zo.json").write_text(json.dumps({"base_url": self.zo_url}) + "\n")

    # -- identity -----------------------------------------------------------

    def _verify_source(self, source: Path) -> dict:
        """The pinned Hermes base, the benchmark's evaluation patch, and only the zo plugin
        committed on top (the container image builder stages tracked files only)."""
        spec_path = ROOT / "examples/reference/hermes-builtin.json"
        spec = json.loads(spec_path.read_text())
        if sha((ROOT / "examples/reference/hermes-evaluation.patch").read_bytes()) != spec["patch_sha256"]:
            raise ValueError("Bundled Hermes reference patch changed")
        for file, key in (("uv.lock", "uv_lock_sha256"), ("pyproject.toml", "pyproject_sha256")):
            if sha((source / file).read_bytes()) != spec[key]:
                raise ValueError(f"Hermes {file} differs from the reference")

        def git(*args) -> bytes:
            return subprocess.run(["git", "-C", str(source), *args], check=True,
                                  capture_output=True, timeout=60).stdout

        if git("status", "--porcelain", "--untracked-files=all").strip():
            raise ValueError("The Hermes checkout has uncommitted changes")
        head = git("rev-parse", "HEAD").decode().strip()
        patch = git("diff", *DIFF_FLAGS, spec["source_base"], head, "--", ".",
                    f":(exclude){PLUGIN.as_posix()}")
        if sha(patch) != spec["patch_sha256"]:
            raise ValueError("Outside plugins/memory/zo, the Hermes checkout differs from the reference")
        return {"source_base": spec["source_base"], "evaluated_commit": spec["evaluated_commit"],
                "patch_sha256": spec["patch_sha256"], "head": head,
                "plugin": {name: sha((source / name).read_bytes()) for name in PLUGIN_FILES}}

    def _build_templates(self, base_url: str) -> dict:
        agent = dict(AGENT_SPEC)
        agent["base_url"] = base_url
        templates = {}
        for persona, name in _load_personas(ROOT).items():
            config = {
                "model": {
                    "provider": agent["provider"],
                    "default": agent["model"],
                    "base_url": agent["base_url"],
                    "api_mode": agent["api_mode"],
                    "context_length": agent["context_length"],
                },
                "memory": {
                    "memory_enabled": True,
                    "user_profile_enabled": True,
                    "flush_min_turns": 6,
                    "nudge_interval": 10,
                    "provider": "zo",
                },
                "toolsets": list(BENCH_TOOLSETS),
                "platform_toolsets": {
                    platform: list(BENCH_TOOLSETS)
                    for platform in ("cli", "slack", "discord", "telegram", "whatsapp", "signal",
                                     "homeassistant")
                },
                "mcp_servers": {
                    "dolphinbench-apps": {
                        "command": self.app_python,
                        "args": [str(ROOT / "mock_mcp" / "server.py")],
                        "tools": {"resources": False, "prompts": False},
                        "env": {},
                    }
                },
                "agent": {
                    "personalities": {
                        "default": "You are Hermes Agent. Be direct, helpful, concise, and use "
                                   "tools to complete requested actions.",
                    },
                    "api_max_retries": 8,
                    "retry_rate_limits_until_success": True,
                    "reasoning_effort": agent["reasoning_effort"],
                    "max_turns": agent["max_turns"],
                },
            }
            soul = (ROOT / "harness/benchmark_soul.md").read_text().replace("{{persona_name}}", name)
            # The container stages only the profile directory; the plugin finds
            # its config there. ZO_AGENT_URL is the adapter server as the agent
            # container reaches it (Docker bridge gateway).
            zo_config = {"base_url": os.environ.get("ZO_AGENT_URL", "http://172.17.0.1:8764"),
                         "identity": persona}
            templates[persona] = {"config.yaml": yaml.safe_dump(config, sort_keys=False),
                                  "SOUL.md": soul,
                                  "zo.json": json.dumps(zo_config) + "\n"}
        return templates

    def identity(self):
        value = super().identity()
        value["zo"] = {
            "adapter_version": ADAPTER_VERSION,
            "adapter_source_sha256": sha(Path(__file__).read_bytes()),
            "memory_provider": "zouroboros",
            "adapter_module": "packages/memory/src/dolphinbench",
            "toolsets": list(BENCH_TOOLSETS),
            "agent": {key: AGENT_SPEC[key] for key in
                      ("provider", "model", "api_mode", "context_length", "reasoning_effort", "max_turns")},
            "model_route": "openrouter:openai/gpt-5.6-luna(provider=azure) via local agent relay",
            "zo_url": self.zo_url,
        }
        return value

    # -- interactions --------------------------------------------------------

    def run_interaction(self, request):
        tag = f"{request.phase}.{request.persona}.{request.interaction_id}"
        token = secrets.token_hex(16)
        digest = hashlib.sha256(token.encode()).hexdigest()
        registration = self.relay_tokens / digest
        # Only the hash is stored; the issued-hash ledger lets the post-run
        # scan recognise a leaked token without ever recording its value.
        with open(self.relay_tokens.parent / "issued-token-hashes.txt", "a") as ledger:
            ledger.write(f"{digest} {tag}\n")
        fd = os.open(registration, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(tag)
        # The judge's relay settings are controller-only: the reference container
        # launcher rejects loopback provider URLs in the agent environment.
        try:
            with env_overlay({"AZURE_FOUNDRY_API_KEY": f"{token}.{tag}",
                              "DOLPHINBENCH_SEED_ITEM_ID": request.interaction_id,
                              "AZURE_OPENAI_ENDPOINT": None,
                              "AZURE_OPENAI_API_KEY": None}):
                record = super().run_interaction(request)
        finally:
            registration.unlink(missing_ok=True)  # revoke: the relay refuses it from now on
            del token
        if request.phase == "tests":
            self._repair_app_call_args(request, record)
        return record

    # The release's repair_server logs enriched call args (optional parameters
    # appear with their null defaults), while the conversation transcript
    # records the model's raw arguments, which may omit them. The benchmark's
    # submission guard (harness.submission.grading_calls) then aborts the whole
    # run on a representation mismatch that says nothing about the agent's
    # action. Repair the adapter-supplied app_calls to the transcript's
    # representation when they match exactly after dropping null-valued keys
    # from both sides; every repaired task is recorded in the run's
    # app-call-repairs.json (disclosed in the smoke report). Grading itself is
    # untouched.
    def _repair_app_call_args(self, request, record):
        from harness.submission import check_messages

        if not record.app_calls:
            return
        transcript = check_messages(record.messages, "transcript")

        def drop_nulls(value):
            if isinstance(value, dict):
                return {k: drop_nulls(v) for k, v in value.items() if v is not None}
            if isinstance(value, list):
                return [drop_nulls(v) for v in value]
            return value

        def key(tool, args):
            return json.dumps([tool, args], sort_keys=True, allow_nan=False)

        exact = Counter(key(c["tool"], c["args"]) for c in transcript)
        fuzzy = Counter(key(c["tool"], drop_nulls(c["args"])) for c in transcript)
        repaired = []
        for call in record.app_calls:
            if exact[key(call["tool"], call["args"])] > 0:
                exact[key(call["tool"], call["args"])] -= 1
                fuzzy[key(call["tool"], drop_nulls(call["args"]))] -= 1
                continue
            if fuzzy[key(call["tool"], drop_nulls(call["args"]))] > 0:
                fuzzy[key(call["tool"], drop_nulls(call["args"]))] -= 1
                before = dict(call["args"])
                call["args"] = drop_nulls(call["args"])
                repaired.append({"tool": call["tool"],
                                 "dropped_null_keys": sorted(set(before) - set(call["args"]))})
                continue
            # 0.4.0 rule (disclosed): the server also fills an OMITTED optional
            # parameter with its declared non-null default (list_open_prs status
            # -> "open"). Drop an app-log key only when the transcript call lacks
            # it and its value equals the default the release's server code
            # declares for that tool; then the same post-drop exact match applies.
            defaults = declared_defaults(call["tool"])
            for candidate in transcript:
                if candidate["tool"] != call["tool"] or not isinstance(candidate["args"], dict):
                    continue
                dropped = sorted(k for k, v in call["args"].items()
                                 if k not in candidate["args"] and k in defaults
                                 and v is not None and v == defaults[k])
                if not dropped:
                    continue
                trimmed = drop_nulls({k: v for k, v in call["args"].items() if k not in dropped})
                target = key(call["tool"], drop_nulls(candidate["args"]))
                if key(call["tool"], trimmed) == target and fuzzy[target] > 0:
                    fuzzy[target] -= 1
                    before = dict(call["args"])
                    call["args"] = trimmed
                    repaired.append({"tool": call["tool"], "rule": "declared-default",
                                     "dropped_default_keys": dropped,
                                     "dropped_null_keys": sorted(set(before) - set(trimmed) - set(dropped))})
                    break
            else:
                # 0.5.0 rule (disclosed, added mid-run in the 2026-11-24 full run): the
                # server coerces a number to its parameter's declared type before logging
                # (the model sends max_price_usd 900, the app log has 900.0), and the
                # guard's JSON key distinguishes 900 from 900.0. Only after the three
                # rules above fail: for a transcript call of the same tool, after the
                # same null and declared-default drops, replace an app-log number by the
                # transcript's number at the same key path when the two are numerically
                # equal and differ only in int/float type (bools excluded). Nothing else
                # is changed; the same exact post-repair match must hold, or the guard
                # still aborts.
                for candidate in transcript:
                    if candidate["tool"] != call["tool"] or not isinstance(candidate["args"], dict):
                        continue
                    dropped = sorted(k for k, v in call["args"].items()
                                     if k not in candidate["args"] and k in defaults
                                     and v is not None and v == defaults[k])
                    trimmed = drop_nulls({k: v for k, v in call["args"].items() if k not in dropped})
                    reference = drop_nulls(candidate["args"])
                    retyped = []
                    aligned = align_numbers(trimmed, reference, "", retyped)
                    if not retyped:
                        continue
                    target = key(call["tool"], reference)
                    if key(call["tool"], aligned) == target and fuzzy[target] > 0:
                        fuzzy[target] -= 1
                        before = dict(call["args"])
                        call["args"] = aligned
                        repaired.append({"tool": call["tool"], "rule": "numeric-representation",
                                         "retyped_keys": retyped,
                                         "dropped_default_keys": dropped,
                                         "dropped_null_keys": sorted(set(before) - set(aligned) - set(dropped))})
                        break
        if repaired:
            path = Path(self.home).parent / "app-call-repairs.json"
            log = json.loads(path.read_text()) if path.exists() else {}
            log.setdefault(request.interaction_id, []).extend(repaired)
            save_json(path, log)

    # -- memory lifecycle ------------------------------------------------------

    def freeze(self, persona):
        # The Hermes profile exists even though ingestion was adapter-side.
        self._initialize(persona)
        checkpoint = post_json(f"{self.zo_url}/freeze", {})
        save_json(self.home / "zo-checkpoints" / f"{persona}.json", checkpoint)
        profile_freeze = super().freeze(persona)
        return {"format": "zo-freeze-v1", "zo": checkpoint, **profile_freeze}

    def verify_checkpoint(self, persona, checkpoint):
        if checkpoint.get("format") != "zo-freeze-v1":
            raise ValueError(f"Unknown zo checkpoint: {checkpoint.get('format')}")
        post_json(f"{self.zo_url}/verify", {"checkpoint": checkpoint["zo"]})
        directory = self.profiles / f"{persona}-frozen"
        from harness.adapters.hermes import tree_identity
        if not directory.is_dir() or checkpoint.get("files") != tree_identity(directory):
            raise ValueError(f"Frozen Hermes profile changed: {persona}")

    # -- cost --------------------------------------------------------------------

    def total_cost_usd(self, phase):
        if phase not in {"ingestion", "tests"}:
            raise ValueError(f"Unknown phase: {phase}")
        total = 0.0
        tags_dir = Path(os.environ.get("AGENT_RELAY_TAGS", "."))
        found_any = False
        for path in sorted(tags_dir.glob(f"{phase}.*.jsonl")):
            found_any = True
            for line in path.read_text().splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                if record.get("event") == "end" and record.get("cost_usd"):
                    total += float(record["cost_usd"])
        if phase == "ingestion":
            accounting = self.home / "accounting" / "ingestion.json"
            if not accounting.is_file():
                raise ValueError("Missing ingestion accounting; run the ingest step first")
            record = load_json(accounting.read_bytes())
            total += check_total_cost(record["embedding_cost_usd"], "embeddings")
        elif not found_any:
            raise ValueError(f"No agent relay records for phase {phase}")
        return check_total_cost(total, phase)


def build(options, work_dir):
    return ZoHermesAdapter(options, work_dir)
