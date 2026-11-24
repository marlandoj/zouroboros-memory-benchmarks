"""Diagnose a grading_calls guard failure structurally: which app calls have no exact
transcript match, and how they differ (keys and value types only; no values printed).

    python guard_diag.py <tests/morgan/NNN.json>
"""
import json
import sys
from collections import Counter

sys.path.insert(0, "/opt/zouroboros/benchmark-data/dolphinbench/repo")
from harness.submission import check_messages  # noqa: E402

row = json.load(open(sys.argv[1]))["row"]
transcript = check_messages(row["messages"], "transcript")
calls = row["app_calls"]


def key(tool, args):
    return json.dumps([tool, args], sort_keys=True)


available = Counter(key(c["tool"], c["args"]) for c in transcript)
print(f"app_calls={len(calls)} transcript_calls={len(transcript)}")
print("app tools:", [c["tool"] for c in calls])
print("transcript tools:", [c["tool"] for c in transcript])


def shape(value):
    if isinstance(value, dict):
        return {k: shape(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [shape(v) for v in value[:3]] + (["..."] if len(value) > 3 else [])
    return type(value).__name__


for index, call in enumerate(calls):
    k = key(call["tool"], call["args"])
    if available[k] > 0:
        available[k] -= 1
        continue
    print(f"UNMATCHED app call #{index} tool={call['tool']} args shape={shape(call['args'])}")
    for t in transcript:
        if t["tool"] != call["tool"]:
            continue
        a, b = call["args"], t["args"]
        keys = sorted(set(a) | set(b))
        diff = {}
        for name in keys:
            if name not in a:
                diff[name] = f"only in transcript ({type(b[name]).__name__})"
            elif name not in b:
                diff[name] = f"only in app log ({type(a[name]).__name__}{', null' if a[name] is None else ''})"
            elif a[name] != b[name]:
                diff[name] = (f"differs: app {type(a[name]).__name__} vs transcript {type(b[name]).__name__}"
                              f"; equal as strings: {str(a[name]) == str(b[name])}"
                              f"; equal stripped: {str(a[name]).strip() == str(b[name]).strip()}")
        print("   vs transcript call of same tool:", diff or "identical")
