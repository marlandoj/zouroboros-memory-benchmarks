"""Itemise a run's cash cost per leg from its relay logs and ingestion accounting.

    python costs.py <run out dir>

Agent: sum of OpenRouter-billed cost_usd over the agent relay's `end` events (retries
included), plus call/token counts. Judge: the judge relay's per-call cost_usd. Embeddings:
hermes/accounting/ingestion.json. Prints one JSON object; no dataset content involved.
"""
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])


def lines(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


agent = [r for r in lines(out / "agent-relay.jsonl") if r.get("event") == "end"]
agent_tests = [r for r in agent if str(r.get("tag") or "").startswith("tests.")]
judge = lines(out / "judge-relay.jsonl")
ingestion = json.loads((out / "hermes/accounting/ingestion.json").read_text())


def usage_sum(records, key):
    total = 0
    for r in records:
        usage = r.get("usage") or {}
        total += int(usage.get(key) or 0)
    return total


def cached(records):
    total = 0
    for r in records:
        details = (r.get("usage") or {}).get("input_tokens_details") or {}
        total += int(details.get("cached_tokens") or 0)
    return total


result = {
    "embeddings": {"model": ingestion["embedding_model"], "tokens": ingestion["embeddingTokens"],
                   "requests": ingestion["embeddingRequests"],
                   "cash_usd": round(ingestion["embedding_cost_usd"], 6)},
    "agent": {"calls": len(agent), "tests_phase_calls": len(agent_tests),
              "status_counts": {str(s): sum(1 for r in agent if r.get("status") == s)
                                for s in sorted({r.get("status") for r in agent}, key=str)},
              "input_tokens": usage_sum(agent, "input_tokens"),
              "cached_input_tokens": cached(agent),
              "output_tokens": usage_sum(agent, "output_tokens"),
              "calls_missing_cost": sum(1 for r in agent if r.get("cost_usd") is None),
              "cash_usd": round(sum(float(r.get("cost_usd") or 0) for r in agent), 6)},
    "judge": {"calls": len(judge),
              "prompt_tokens": sum(int(r.get("prompt_tokens") or 0) for r in judge),
              "completion_tokens": sum(int(r.get("completion_tokens") or 0) for r in judge),
              "providers": sorted({str(r.get("provider")) for r in judge}),
              "cash_usd": round(sum(float(r.get("cost_usd") or 0) for r in judge), 6)},
}
result["total_cash_usd"] = round(result["embeddings"]["cash_usd"] + result["agent"]["cash_usd"]
                                 + result["judge"]["cash_usd"], 6)
# 0.6.0 ingest legs (verbatim / extraction / consolidation), itemised when recorded.
if "legs" in ingestion:
    result["ingest_legs"] = {
        leg: {"embedding_tokens": int(v.get("embeddingTokens") or 0),
              "embedding_cash_usd": round(float(v.get("embedding_cost_usd") or 0), 6),
              "model_cash_usd": round(float(v.get("model_cost_usd") or 0), 6)}
        for leg, v in ingestion["legs"].items()
    }
print(json.dumps(result, indent=2))
