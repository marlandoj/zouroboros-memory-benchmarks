"""DolphinBench x Zouroboros driver: one persona per run directory; first 25 tests (smoke) or all.

Persona and test count come from run.conf (ZO_BENCH_PERSONA, default morgan; ZO_TEST_COUNT,
default 25, or "all" for every test of the persona in benchmark order). With the defaults the
run identity is the smoke's, unchanged. A full run uses one run directory per persona.

Persisted copy (zouroboros-memory-benchmarks/dolphinbench/zo-harness). Same stages, same
release filter, same Runner and grading as the first smoke (2026-11-23); what changed is
where things come from and how credentials reach the processes that need them:

- Paths come from the environment (scripts/stage.sh sets them), so one copy serves any run
  directory. The run directory holds the scratch store and all evidence.
- This process never holds a provider credential. It refuses to start if one is in its
  environment (see FORBIDDEN_ENV): the benchmark's container launcher copies provider
  variables into `docker create --env NAME=VALUE` arguments, which an error dump can print.
  The zo adapter server gets OPENAI_API_KEY (embeddings) through `bun --env-file=<0600 file>`,
  so the value is never in this process, a command line, or a log. The judge relay capability
  (AZURE_OPENAI_API_KEY, a random per-run loopback password the runner's judge client needs)
  is loaded from an env-file by stage.sh for the evaluate stage only, and the zo harness
  unsets it for every agent interaction.
- The Hermes source must carry plugins/memory/zo byte-identical to this repository's
  hermes-plugin/ copy; the runner adapter (zo_harness.py) is imported from this directory.

Stages (each resumable; completed work is never repeated):

  prepare   Local checks: release validates, adapter identity builds, plugin identity
            matches the persisted copy, zo adapter server answers. No paid calls.
  ingest    Export Morgan's history and push it through the Zouroboros adapter server (the
            memory system's standard ingest path), then record the embedding cost.
  freeze    Freeze + checkpoint the store (adapter /freeze, v2 content hash, and Hermes
            profile), verify the checkpoint once, write the runner checkpoint, collect the
            ingestion cost.
  evaluate  Run the first 25 Morgan tests through the benchmark's own Runner and grading
            (deterministic checks + the fixed gpt-5.6-sol judge via the local judge relay).
  summary   Aggregate per-task check pass counts (no dataset content) to summary.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1]
RUNNER_DIR = HARNESS / "runner"
PLUGIN_COPY = HARNESS / "hermes-plugin"


def required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Set {name} (scripts/stage.sh sets the run environment)")
    return value


REPO = Path(os.environ.get("DOLPHINBENCH_REPO", "/opt/zouroboros/benchmark-data/dolphinbench/repo"))
RUN = Path(required("ZO_RUN_DIR"))
OUT = RUN / "out"
WORKSPACE = Path(required("ZO_WORKSPACE"))
HERMES_SOURCE = Path(required("ZO_HERMES_SOURCE"))
HERMES_PYTHON = str(HERMES_SOURCE / ".venv/bin/python")
APP_PYTHON = os.environ.get("ZO_APP_PYTHON",
                            "/opt/zouroboros/benchmark-data/dolphinbench/apps-venv/bin/python")
VENV_PYTHON = REPO / ".venv/bin/python"
ZO_SERVER_TS = WORKSPACE / "packages/memory/src/dolphinbench/server.ts"
ZO_ENV_FILE = Path(required("ZO_ENV_FILE"))
PERSONA = os.environ.get("ZO_BENCH_PERSONA", "morgan")
if not re.fullmatch(r"[a-z]+", PERSONA):
    raise SystemExit(f"Bad ZO_BENCH_PERSONA {PERSONA!r}")
_COUNT = os.environ.get("ZO_TEST_COUNT", "25")
TEST_COUNT = None if _COUNT == "all" else int(_COUNT)  # None = every test, benchmark order
ZO_DB = RUN / f"dolphinbench-{PERSONA}.db"
ZO_URL = "http://127.0.0.1:8764"
# OpenAI list prices; the model is read from the store, never assumed.
EMBEDDING_PRICES_PER_TOKEN = {"text-embedding-3-small": 0.02 / 1_000_000,
                              "text-embedding-3-large": 0.13 / 1_000_000}
PLUGIN_FILES = ("plugins/memory/zo/__init__.py", "plugins/memory/zo/plugin.yaml")

# Real provider credentials: never in this process (they would reach `docker create` argv).
FORBIDDEN_ENV = {
    "OPENAI_API_KEY", "ZO_OPENAI_API_KEY", "CUSTOM_API_KEY", "OPENROUTER_API_KEY",
    "MINIMAX_OPENROUTER_API_KEY", "AZURE_FOUNDRY_API_KEY", "ANTHROPIC_API_KEY", "MEM0_API_KEY",
    "HONCHO_API_KEY", "HINDSIGHT_API_KEY", "SUPERMEMORY_API_KEY", "GITHUB_TOKEN", "GH_TOKEN",
}
CREDENTIAL_SHAPE = re.compile(r"(sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|xox[abp]-)")

sys.path.insert(0, str(REPO))
sys.path.insert(0, str(RUNNER_DIR))


def assert_no_credentials(stage: str) -> None:
    present = sorted(name for name in FORBIDDEN_ENV if os.environ.get(name))
    shaped = sorted(name for name, value in os.environ.items() if CREDENTIAL_SHAPE.search(value))
    if stage != "evaluate" and os.environ.get("AZURE_OPENAI_API_KEY"):
        present.append("AZURE_OPENAI_API_KEY")
    if present or shaped:
        # Names only, never values.
        raise SystemExit(f"Refusing to run with credentials in the environment: {present + shaped}")
    mode = ZO_ENV_FILE.stat().st_mode
    if mode & 0o077:
        raise SystemExit(f"{ZO_ENV_FILE} must be mode 0600")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_plugin_from_persisted_copy() -> dict:
    identity = {}
    for name in PLUGIN_FILES:
        source, copy = sha(HERMES_SOURCE / name), sha(PLUGIN_COPY / name)
        if source != copy:
            raise SystemExit(f"{HERMES_SOURCE / name} differs from the persisted copy {PLUGIN_COPY / name}")
        identity[name] = source
    return identity


def environment() -> dict:
    env = {
        "DOLPHINBENCH_HERMES_SOURCE": str(HERMES_SOURCE),
        "DOLPHINBENCH_HERMES_PYTHON": HERMES_PYTHON,
        "DOLPHINBENCH_APP_PYTHON": APP_PYTHON,
        "ZO_ADAPTER_URL": ZO_URL,
        # Container-reachable addresses (Docker bridge gateway): the agent
        # container cannot use controller loopback.
        "ZO_AGENT_URL": "http://172.17.0.1:8764",
        "AZURE_OPENAI_BASE_URL": "http://172.17.0.1:8766/openai/v1",
        "AGENT_RELAY_TOKENS": str(RUN / "relay-tokens"),
        "AGENT_RELAY_LOG": str(OUT / "agent-relay.jsonl"),
        "AGENT_RELAY_TAGS": str(OUT / "agent-relay-tags"),
        "JUDGE_RELAY_LOG": str(OUT / "judge-relay.jsonl"),
        "PYTHONPATH": os.pathsep.join((str(REPO), str(RUNNER_DIR))),
    }
    image_file = RUN / "image-id.txt"
    if image_file.exists():
        env["DOLPHINBENCH_AGENT_IMAGE"] = image_file.read_text().strip()
    return env


def http_json(method: str, url: str, body: dict | None = None, timeout: float = 600.0) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        return json.loads(raw) if raw else {}


class ZoServer:
    """Owns the bun adapter-server process for one stage. OPENAI_API_KEY reaches it only
    through `bun --env-file` (the file's path is on the command line, never its content)."""

    def __init__(self, locked: bool):
        self.locked = locked
        self.process = None

    def __enter__(self):
        OUT.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        env.pop("AZURE_OPENAI_API_KEY", None)
        env.update({
            "ZO_DB_PATH": str(ZO_DB),
            "ZO_PERSONA": PERSONA,
            "ZO_EMBED_PROVIDER": "openai",
            "ZO_DOLPHINBENCH_PORT": "8764",
            "ZO_LOCKED": "1" if self.locked else "0",
            # Task phase: the containerised agent recalls through the bridge.
            "ZO_BIND_HOST": "0.0.0.0" if self.locked else "127.0.0.1",
        })
        log = (OUT / "zo-server.log").open("ab")
        self.process = subprocess.Popen(
            ["bun", f"--env-file={ZO_ENV_FILE}", str(ZO_SERVER_TS)], cwd=str(WORKSPACE), env=env,
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        deadline = time.time() + 60
        while time.time() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError("zo adapter server exited on startup; see zo-server.log")
            try:
                http_json("GET", f"{ZO_URL}/stats", timeout=5)
                return self
            except Exception:
                time.sleep(0.5)
        raise RuntimeError("zo adapter server did not start in 60s")

    def __exit__(self, *exc):
        if self.process and self.process.poll() is None:
            self.process.send_signal(signal.SIGTERM)
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
        return False


def make_adapter():
    from zo_harness import build
    options = {
        "source_env": "DOLPHINBENCH_HERMES_SOURCE",
        "python_env": "DOLPHINBENCH_HERMES_PYTHON",
        "app_python_env": "DOLPHINBENCH_APP_PYTHON",
        "base_url_env": "AZURE_OPENAI_BASE_URL",
        "zo_url_env": "ZO_ADAPTER_URL",
        "relay_tokens_env": "AGENT_RELAY_TOKENS",
    }
    for name in options.values():
        if not os.environ.get(name):
            raise SystemExit(f"Set {name} (see environment() / stage setup)")
    import zo_harness
    if Path(zo_harness.__file__).resolve().parent != RUNNER_DIR:
        raise SystemExit(f"zo_harness imported from {zo_harness.__file__}, not {RUNNER_DIR}")
    return build(options, OUT)


def filtered_release():
    from harness.submission import read_release
    release = read_release(REPO)
    persona = release[PERSONA]
    if TEST_COUNT is None:
        return {PERSONA: persona}
    return {PERSONA: {**persona, "tests": persona["tests"][:TEST_COUNT]}}


def make_runner(adapter, allow_paid: bool):
    from harness.runner import Runner
    release = filtered_release()
    if TEST_COUNT is None:
        config = {"release": str(REPO), "output": str(OUT), "adapter": "zo_harness:build",
                  "subset": f"{PERSONA}:all", "smoke": False}
    else:  # the smoke's identity, unchanged
        config = {"release": str(REPO), "output": str(OUT), "adapter": "zo_harness:build",
                  "subset": f"{PERSONA}:1-{TEST_COUNT}", "smoke": True}
    identity = {
        "config": config,
        "code": {},
        "adapter": adapter.identity(),
    }
    return Runner(release, OUT, adapter, identity=identity, release_root=REPO,
                  allow_paid=allow_paid)


def stage_prepare() -> None:
    from harness.submission import read_release
    release = read_release(REPO)
    sessions = len(release[PERSONA]["sessions"])
    tests = len(release[PERSONA]["tests"])
    selected = len(filtered_release()[PERSONA]["tests"])
    print(f"release ok: {PERSONA} sessions={sessions} tests={tests} selected={selected}")
    print("plugin matches persisted copy:", json.dumps(assert_plugin_from_persisted_copy()))
    adapter = make_adapter()
    identity = adapter.identity()
    print("adapter identity ok:")
    print(json.dumps(identity["zo"], indent=2))
    print(f"hermes binary: {identity['binary_sha256'][:16]}…")
    print("source:", json.dumps(adapter.source_identity))
    with ZoServer(locked=False):
        stats = http_json("GET", f"{ZO_URL}/stats", timeout=10)
        print("zo server:", json.dumps(stats))
    print("prepare complete (no paid calls)")


def stage_ingest() -> None:
    assert_plugin_from_persisted_copy()
    # Establish the run identity before any evidence files exist (the Runner
    # refuses to adopt a directory that already holds JSON evidence). The adapter's
    # constructor writes its controller-side config (hermes/zo.json, not evidence) first,
    # so set it aside while the Runner writes run.json, then put it back unchanged.
    if not (OUT / "run.json").exists():
        adapter = make_adapter()
        config = OUT / "hermes" / "zo.json"
        content = config.read_bytes()
        config.unlink()
        make_runner(adapter, allow_paid=False)
        config.write_bytes(content)
    history = RUN / f"history-{PERSONA}.jsonl"
    if not history.exists():
        subprocess.run([str(VENV_PYTHON), str(RUNNER_DIR / "export_history.py"), PERSONA, str(history)],
                       check=True)
    messages = [json.loads(line) for line in history.read_text().splitlines() if line.strip()]
    (OUT / "hermes/accounting").mkdir(parents=True, exist_ok=True)
    started = time.time()
    totals = {"messagesIngested": 0, "messagesResumed": 0, "messagesSkipped": 0,
              "embeddingTokens": 0, "embeddingRequests": 0, "batches": 0}
    with ZoServer(locked=False):
        batch_size = 200
        for offset in range(0, len(messages), batch_size):
            batch = messages[offset:offset + batch_size]
            stats = http_json("POST", f"{ZO_URL}/ingest", {"messages": batch}, timeout=1800)
            for key in ("messagesIngested", "messagesResumed", "messagesSkipped",
                        "embeddingTokens", "embeddingRequests"):
                totals[key] += stats[key]
            totals["batches"] += 1
            print(f"ingest {offset + len(batch)}/{len(messages)}: "
                  f"+{stats['messagesIngested']} ({stats['embeddingTokens']} tokens)", flush=True)
        stats = http_json("GET", f"{ZO_URL}/stats", timeout=10)
    model = stats.get("embeddingModel")
    if model not in EMBEDDING_PRICES_PER_TOKEN:
        raise SystemExit(f"No list price recorded for embedding model {model!r}")
    cost = totals["embeddingTokens"] * EMBEDDING_PRICES_PER_TOKEN[model]
    record = {
        "persona": PERSONA,
        "sessions": len(messages),
        **totals,
        "store": stats,
        "embedding_model": model,
        "embedding_price_per_token_usd": EMBEDDING_PRICES_PER_TOKEN[model],
        "embedding_cost_usd": cost,
        "wall_clock_seconds": round(time.time() - started, 1),
    }
    (OUT / "hermes/accounting/ingestion.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


def stage_freeze() -> None:
    assert_plugin_from_persisted_copy()
    adapter = make_adapter()
    if not (OUT / "run.json").exists():
        make_runner(adapter, allow_paid=False)
    with ZoServer(locked=False):
        checkpoint = adapter.freeze(PERSONA)
        (OUT / "checkpoints").mkdir(parents=True, exist_ok=True)
        from harness.durable_json import save_json
        save_json(OUT / "checkpoints" / f"{PERSONA}.json", checkpoint)
        print("checkpoint:", json.dumps(checkpoint["zo"], indent=2)[:800])
        runner = make_runner(adapter, allow_paid=False)
        cost = runner._collect_cost("ingestion")
        print(f"ingestion cost: ${cost:.6f}")
    # Verify across a fresh, locked server process (the task-phase configuration).
    with ZoServer(locked=True):
        adapter.verify_checkpoint(PERSONA, checkpoint)
        print("checkpoint verified by a fresh locked server process")


def stage_evaluate() -> None:
    assert_plugin_from_persisted_copy()
    if not os.environ.get("AZURE_OPENAI_API_KEY") or not os.environ.get("AZURE_OPENAI_ENDPOINT"):
        raise SystemExit("The judge relay capability is missing (stage.sh loads it for evaluate)")
    adapter = make_adapter()
    runner = make_runner(adapter, allow_paid=True)
    with ZoServer(locked=True):
        runner.evaluate()
    print("evaluate complete")


def stage_summary() -> None:
    import yaml
    grades = OUT / "grades" / PERSONA
    tasks = {}
    for path in sorted(grades.glob("*.json")):
        checks = json.loads(path.read_text())["checks"]
        spec = yaml.safe_load((REPO / "tests" / PERSONA / f"{path.stem}.yaml").read_text())
        types = [a.get("type") for a in spec["grade"]["config"]["assertions"]]
        tasks[path.stem] = {
            "checks": len(checks),
            "passed": sum(1 for c in checks if c.get("passed")),
            "check_results": [{"check": c.get("check"), "passed": bool(c.get("passed")),
                               "type": types[c["check"]], "judge_called": "messages" in c}
                              for c in checks],
        }
    summary = {
        "tasks_graded": len(tasks),
        "tasks_fully_passed": sum(1 for t in tasks.values() if t["passed"] == t["checks"]),
        "checks": sum(t["checks"] for t in tasks.values()),
        "checks_passed": sum(t["passed"] for t in tasks.values()),
        "tasks": tasks,
    }
    (RUN / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "tasks"}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "ingest", "freeze", "evaluate", "summary"))
    args = parser.parse_args()
    assert_no_credentials(args.stage)
    os.environ.update({k: v for k, v in environment().items() if k not in os.environ})
    {"prepare": stage_prepare, "ingest": stage_ingest, "freeze": stage_freeze,
     "evaluate": stage_evaluate, "summary": stage_summary}[args.stage]()


if __name__ == "__main__":
    main()
