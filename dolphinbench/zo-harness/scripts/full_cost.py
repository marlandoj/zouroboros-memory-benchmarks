"""Cash spent so far across a full run's persona run directories, and the checkpoint projection.

    python full_cost.py spent <run dir> [<run dir> ...]
        -> prints the total cash in USD (agent relay + judge relay + embeddings) of every
           run directory given, counting a leg only once its records exist.
    python full_cost.py project <release root> <done run dir> <remaining persona> [...]
        -> prints a JSON projection: the done persona's measured rates (embedding cash per
           ingested history message, agent+judge cash per graded task, wall-clock per stage)
           applied to the remaining personas' history and test counts.

Aggregate numbers only; no dataset content is read beyond counting sessions and tests.
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path


def lines(path):
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def legs(run: Path) -> dict:
    out = run / "out"
    agent = sum(float(r.get("cost_usd") or 0) for r in lines(out / "agent-relay.jsonl")
                if r.get("event") == "end")
    judge = sum(float(r.get("cost_usd") or 0) for r in lines(out / "judge-relay.jsonl"))
    accounting = out / "hermes/accounting/ingestion.json"
    embed = json.loads(accounting.read_text())["embedding_cost_usd"] if accounting.exists() else 0.0
    return {"embeddings": embed, "agent": agent, "judge": judge, "total": embed + agent + judge}


def stage_seconds(run: Path, stage: str) -> float | None:
    log = run / "logs" / f"{stage}.log"
    if not log.exists():
        return None
    starts = re.findall(rb"stage \w+ start (\S+Z)", log.read_bytes())
    ends = re.findall(rb"stage \w+ exit 0 (\S+Z)", log.read_bytes())
    if not starts or not ends:
        return None
    parse = lambda b: datetime.strptime(b.decode(), "%Y-%m-%dT%H:%M:%SZ")
    # First start to last successful exit: resumed attempts are included in the wall-clock.
    return (parse(ends[-1]) - parse(starts[0])).total_seconds()


def counts(release_root: Path, persona: str) -> tuple[int, int]:
    sys.path.insert(0, str(release_root))
    from harness.submission import read_release
    release = read_release(release_root)[persona]
    return len(release["sessions"]), len(release["tests"])


def main():
    if sys.argv[1] == "spent":
        print(f"{sum(legs(Path(p))['total'] for p in sys.argv[2:]):.6f}")
        return
    root, done, remaining = Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4:]
    persona = json.loads((done / "out/hermes/accounting/ingestion.json").read_text())["persona"]
    sessions, tests = counts(root, persona)
    spent = legs(done)
    seconds = {s: stage_seconds(done, s) for s in ("prepare", "ingest", "freeze", "evaluate", "summary")}
    per_session_embed = spent["embeddings"] / sessions
    per_task_cash = (spent["agent"] + spent["judge"]) / tests
    per_task_seconds = (seconds["evaluate"] or 0) / tests
    other_seconds = sum(v or 0 for k, v in seconds.items() if k != "evaluate")
    projection = {"basis_persona": persona, "basis_sessions": sessions, "basis_tests": tests,
                  "basis_cash_usd": spent, "basis_stage_seconds": seconds,
                  "rates": {"embedding_usd_per_history_message": per_session_embed,
                            "agent_plus_judge_usd_per_task": per_task_cash,
                            "evaluate_seconds_per_task": per_task_seconds},
                  "remaining": {}}
    total_cash, total_seconds = spent["total"], sum(v or 0 for v in seconds.values())
    for other in remaining:
        s, t = counts(root, other)
        cash = s * per_session_embed + t * per_task_cash
        secs = other_seconds * s / sessions + t * per_task_seconds
        projection["remaining"][other] = {"sessions": s, "tests": t, "cash_usd": cash,
                                          "wall_clock_seconds": secs}
        total_cash += cash
        total_seconds += secs
    projection["projected_total_cash_usd"] = total_cash
    projection["projected_total_wall_clock_seconds"] = total_seconds
    # Superseded attempts (FULL_PRIOR_RUNS, space-separated run dirs) are sunk cash: counted
    # against the cap, not used for the rates.
    import os
    prior = [Path(p) for p in os.environ.get("FULL_PRIOR_RUNS", "").split()]
    if prior:
        sunk = sum(legs(p)["total"] for p in prior)
        projection["prior_attempts"] = {str(p): legs(p) for p in prior}
        projection["projected_total_cash_usd"] = total_cash + sunk
    print(json.dumps(projection, indent=2))


if __name__ == "__main__":
    main()
