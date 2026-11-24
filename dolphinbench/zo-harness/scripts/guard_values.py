"""Value-level guard diagnosis WITHOUT printing values: for each unmatched app call, compare it
key by key with each transcript call of the same tool and report only the KIND of difference
(equal / missing / type differs / numeric-equal-but-repr-differs / string length & case / other).

    python guard_values.py <tests/<persona>/NNN.json>
"""
import json
import sys
from collections import Counter

sys.path.insert(0, "/opt/zouroboros/benchmark-data/dolphinbench/repo")
from harness.submission import check_messages  # noqa: E402

row = json.load(open(sys.argv[1]))["row"]
transcript = check_messages(row["messages"], "t")
calls = row["app_calls"]


def key(tool, args):
    return json.dumps([tool, args], sort_keys=True, allow_nan=False)


def kind(a, b):
    if a == b and type(a) is type(b):
        return "equal"
    if a == b:
        return f"equal-value-type-differs({type(a).__name__}/{type(b).__name__})"
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return f"number-differs(ratio={'%.4f' % (a / b) if b else 'n/a'})"
    if isinstance(a, str) and isinstance(b, str):
        if a.strip() == b.strip():
            return "string-whitespace"
        if a.lower() == b.lower():
            return "string-case"
        return f"string-differs(len {len(a)}/{len(b)}, common-prefix {len(__import__('os').path.commonprefix([a, b]))})"
    if isinstance(a, str) or isinstance(b, str):
        return f"type({type(a).__name__}/{type(b).__name__}) str-equal={str(a) == str(b)}"
    return f"differs({type(a).__name__}/{type(b).__name__})"


available = Counter(key(c["tool"], c["args"]) for c in transcript)
for i, call in enumerate(calls):
    k = key(call["tool"], call["args"])
    if available[k] > 0:
        available[k] -= 1
        print(f"app #{i} {call['tool']}: exact match")
        continue
    print(f"app #{i} {call['tool']}: UNMATCHED")
    for j, t in enumerate(transcript):
        if t["tool"] != call["tool"]:
            continue
        keys = sorted(set(call["args"]) | set(t["args"]))
        diff = {}
        for name in keys:
            if name not in t["args"]:
                diff[name] = "only-app"
            elif name not in call["args"]:
                diff[name] = "only-transcript"
            else:
                diff[name] = kind(call["args"][name], t["args"][name])
        print(f"   vs transcript #{j}: {diff}")
