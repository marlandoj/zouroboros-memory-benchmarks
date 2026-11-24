"""DolphinBench x Zouroboros smoke driver: one persona, first 25 tests.

Stages (each resumable; completed work is never repeated):

  prepare   Local checks: release validates, adapter identity builds, MCP app
            server starts, zo adapter server answers. No paid calls.
  ingest    Export Morgan's history and push it through the Zouroboros adapter
            server (the memory system's standard ingest path), then record the
            embedding cost. Requires OPENAI_API_KEY (embeddings only).
  freeze    Freeze + checkpoint the store (adapter /freeze and Hermes profile),
            write the runner checkpoint, collect the ingestion cost.
  evaluate  Run the first 25 Morgan tests through the benchmark's own Runner
            and grading (deterministic checks + the fixed gpt-5.6-sol judge,
            reached through the local judge relay). Requires the agent relay
            and judge relay running.

The zo adapter server (bun) is started and stopped by this script for the
stages that need it. Relays are long-lived and managed outside (see README /
PROGRESS.md in the workspace).
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path("/opt/zouroboros/benchmark-data/dolphinbench/repo")
RUN = Path("/opt/zouroboros/benchmark-data/dolphinbench/zo-run")
OUT = RUN / "tmp/zo-smoke-morgan"
WORKSPACE = Path("/opt/zouroboros/factory-workspaces/t_baa4f1d6")
VENV_PYTHON = REPO / ".venv/bin/python"
APP_PYTHON = "/opt/zouroboros/benchmark-data/dolphinbench/apps-venv/bin/python"
HERMES_PYTHON = "/opt/zouroboros/benchmark-data/dolphinbench/hermes-reference/.venv/bin/python"
HERMES_SOURCE = "/opt/zouroboros/benchmark-data/dolphinbench/hermes-reference"
ZO_SERVER_TS = WORKSPACE / "packages/memory/src/dolphinbench/server.ts"
ZO_DB = RUN / "dolphinbench-morgan.db"
ZO_URL = "http://127.0.0.1:8764"
PERSONA = "morgan"
TEST_COUNT = 25
EMBEDDING_PRICE_PER_TOKEN = 0.02 / 1_000_000  # text-embedding-3-small, OpenAI list

sys.path.insert(0, str(REPO))
sys.path.insert(0, str(RUN))


def environment() -> dict:
    env = dict(os.environ)
    env.update({
        "DOLPHINBENCH_HERMES_SOURCE": HERMES_SOURCE,
        "DOLPHINBENCH_HERMES_PYTHON": HERMES_PYTHON,
        "DOLPHINBENCH_APP_PYTHON": APP_PYTHON,
        "ZO_ADAPTER_URL": ZO_URL,
        # Container-reachable addresses (Docker bridge gateway): the agent
        # container cannot use controller loopback.
        "ZO_AGENT_URL": "http://172.17.0.1:8764",
        "AZURE_OPENAI_BASE_URL": "http://172.17.0.1:8766/openai/v1",
        "AGENT_RELAY_LOG": str(OUT / "agent-relay.jsonl"),
        "AGENT_RELAY_TAGS": str(OUT / "agent-relay-tags"),
        "JUDGE_RELAY_LOG": str(OUT / "judge-relay.jsonl"),
        "PYTHONPATH": os.pathsep.join((str(REPO), str(RUN))),
    })
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
    """Owns the bun adapter-server process for one stage."""

    def __init__(self, locked: bool):
        self.locked = locked
        self.process = None

    def __enter__(self):
        OUT.mkdir(parents=True, exist_ok=True)
        env = environment()
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
            ["bun", str(ZO_SERVER_TS)], cwd=str(WORKSPACE), env=env,
            stdout=log, stderr=subprocess.STDOUT)
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
        "relay_password_env": "AGENT_RELAY_PASSWORD",
    }
    for name in options.values():
        if not os.environ.get(name):
            raise SystemExit(f"Set {name} (see environment() / stage setup)")
    return build(options, OUT)


def filtered_release():
    from harness.submission import read_release
    release = read_release(REPO)
    morgan = release[PERSONA]
    return {PERSONA: {**morgan, "tests": morgan["tests"][:TEST_COUNT]}}


def make_runner(adapter, allow_paid: bool):
    from harness.runner import Runner
    release = filtered_release()
    identity = {
        "config": {"release": str(REPO), "output": str(OUT),
                   "adapter": "zo_harness:build", "subset": f"{PERSONA}:1-{TEST_COUNT}",
                   "smoke": True},
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
    print(f"release ok: {PERSONA} sessions={sessions} tests={tests}")
    adapter = make_adapter()
    identity = adapter.identity()
    print("adapter identity ok:")
    print(json.dumps(identity["zo"], indent=2))
    print(f"hermes binary: {identity['binary_sha256'][:16]}…")
    print("source:", json.dumps(adapter.source_identity["plugin"]))
    with ZoServer(locked=False):
        stats = http_json("GET", f"{ZO_URL}/stats", timeout=10)
        print("zo server:", json.dumps(stats))
    print("prepare complete (no paid calls)")


def stage_ingest() -> None:
    # Establish the run identity before any evidence files exist (the Runner
    # refuses to adopt a directory that already holds JSON evidence).
    if not (OUT / "run.json").exists():
        make_runner(make_adapter(), allow_paid=False)
    history = RUN / "history-morgan.jsonl"
    if not history.exists():
        subprocess.run([str(VENV_PYTHON), str(RUN / "export_history.py"), PERSONA, str(history)],
                       check=True)
    messages = [json.loads(line) for line in history.read_text().splitlines() if line.strip()]
    accounting = OUT / "hermes/accounting/ingestion.json"
    OUT.mkdir(parents=True, exist_ok=True)
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
    cost = totals["embeddingTokens"] * EMBEDDING_PRICE_PER_TOKEN
    record = {
        "persona": PERSONA,
        "sessions": len(messages),
        **totals,
        "store": stats,
        "embedding_model": "text-embedding-3-small",
        "embedding_price_per_token_usd": EMBEDDING_PRICE_PER_TOKEN,
        "embedding_cost_usd": cost,
        "wall_clock_seconds": round(time.time() - started, 1),
    }
    (OUT / "hermes/accounting/ingestion.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


def stage_freeze() -> None:
    adapter = make_adapter()
    if not (OUT / "run.json").exists():
        make_runner(adapter, allow_paid=False)
    with ZoServer(locked=False):
        checkpoint = adapter.freeze(PERSONA)  # noqa: F841
        (OUT / "checkpoints").mkdir(parents=True, exist_ok=True)
        from harness.durable_json import save_json
        save_json(OUT / "checkpoints" / f"{PERSONA}.json", checkpoint)
        print("checkpoint:", json.dumps(checkpoint["zo"], indent=2)[:800])
        runner = make_runner(adapter, allow_paid=False)
        cost = runner._collect_cost("ingestion")
        print(f"ingestion cost: ${cost:.6f}")


def stage_evaluate() -> None:
    adapter = make_adapter()
    runner = make_runner(adapter, allow_paid=True)
    with ZoServer(locked=True):
        runner.evaluate()
    print("evaluate complete")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "ingest", "freeze", "evaluate"))
    args = parser.parse_args()
    os.environ.update({k: v for k, v in environment().items() if k not in os.environ})
    {"prepare": stage_prepare, "ingest": stage_ingest,
     "freeze": stage_freeze, "evaluate": stage_evaluate}[args.stage]()


if __name__ == "__main__":
    main()
