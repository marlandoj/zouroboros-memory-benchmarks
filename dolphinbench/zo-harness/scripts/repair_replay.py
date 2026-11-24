"""Replay the zo harness's app-call repair offline on saved evidence and run the benchmark's
own guard (harness.submission.grading_calls) on the result. No paid calls, no writes to the
run directory (repairs are logged to a temp dir). Prints tool names and dropped keys only.

    python repair_replay.py <harness runner dir> <evidence.json> [...]
"""
import copy
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, "/opt/zouroboros/benchmark-data/dolphinbench/repo")
sys.path.insert(0, sys.argv[1])
import zo_harness  # noqa: E402
from harness.submission import SubmissionError, grading_calls  # noqa: E402

print("zo_harness", zo_harness.ADAPTER_VERSION, "from", zo_harness.__file__)
print("declared defaults list_open_prs:", zo_harness.declared_defaults("list_open_prs"))
for name in sys.argv[2:]:
    row = json.loads(Path(name).read_text())["row"]
    record = SimpleNamespace(messages=row["messages"], app_calls=copy.deepcopy(row.get("app_calls")))
    with tempfile.TemporaryDirectory() as raw:
        fake = SimpleNamespace(home=Path(raw) / "hermes")
        zo_harness.ZoHermesAdapter._repair_app_call_args(fake, SimpleNamespace(interaction_id="x"), record)
        log = Path(raw) / "app-call-repairs.json"
        repairs = json.loads(log.read_text())["x"] if log.exists() else []
    changed = record.app_calls != row.get("app_calls")
    try:
        before = "pass"
        grading_calls(row, "before")
    except SubmissionError:
        before = "ABORT"
    try:
        grading_calls({**row, "app_calls": record.app_calls}, "after")
        after = "pass"
    except SubmissionError:
        after = "ABORT"
    print(f"{name.split('/run2/')[-1]}: guard before={before} after={after} changed={changed} "
          f"repairs={json.dumps(repairs)}")
