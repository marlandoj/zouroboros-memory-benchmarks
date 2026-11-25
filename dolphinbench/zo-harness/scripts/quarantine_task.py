"""Quarantine one task's crashed attempt so the benchmark Runner re-runs it fresh.

    python quarantine_task.py <run out dir> <task id NNN> <quarantine dir>

Run one's disclosed policy for a grading crash on the exact-match guard
(harness/submission.py grading_calls) that the null-key repair does not cover: set the
task's evidence, attempt journal, cost records and Hermes profile aside, and re-run
that task fresh. Nothing is deleted: everything is moved under <quarantine dir> (fenced
run directory). The task's entry in app-call-repairs.json moves with it. The agent relay's
tag log is kept, so the crashed attempt's cash stays in the run's cost.
"""
import json
import shutil
import sys
from pathlib import Path

out, task, dest = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
persona = sys.argv[4] if len(sys.argv) > 4 else "morgan"  # optional 4th arg: persona id
if not persona.isalpha() or not persona.islower():
    sys.exit(f"bad persona {persona!r}")
grade = out / "grades" / persona / f"{task}.json"
if grade.exists():
    sys.exit(f"{task} already has a grade; refusing to quarantine a graded task")
dest.mkdir(parents=True, exist_ok=False)
moved = []
candidates = [
    out / "tests" / persona / f"{task}.json",
    out / "tests" / persona / f"{task}.returned",
    out / "tests" / persona / f"{task}.inflight",
    out / "hermes" / "attempts" / "tests" / persona / f"{task}.json",
    *sorted((out / "hermes" / "costs" / "tests" / persona).glob(f"{task}-*.json")),
    *sorted((out / "hermes" / "profiles").glob(f"{persona}-test-{task}-a*")),
    out / "hermes" / "test-traces" / persona / f"{task}.jsonl",
]
for path in candidates:
    if path.exists():
        target = dest / path.relative_to(out)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(target))
        moved.append(str(path.relative_to(out)))
repairs = out / "app-call-repairs.json"
if repairs.exists():
    log = json.loads(repairs.read_text())
    if task in log:
        (dest / "app-call-repairs.json").write_text(json.dumps({task: log.pop(task)}, indent=2) + "\n")
        repairs.write_text(json.dumps(log, indent=2) + "\n")
        moved.append(f"app-call-repairs.json[{task}]")
print(json.dumps({"task": task, "moved": moved}, indent=2))
