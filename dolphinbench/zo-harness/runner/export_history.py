"""Export a persona's DolphinBench history to JSONL for the Zouroboros adapter ingest.

Reads the benchmark's registry/personas/<persona>/life_sim.yaml and writes one
{"id", "date", "text"} object per line, in benchmark order. Stays outside the
gated workspace; the output is dataset content and must not be copied elsewhere.
"""

import json
import sys
from pathlib import Path

import yaml

REPO = Path("/opt/zouroboros/benchmark-data/dolphinbench/repo")


def main() -> None:
    persona, output = sys.argv[1], Path(sys.argv[2])
    data = yaml.safe_load((REPO / "registry/personas" / persona / "life_sim.yaml").read_text())
    sessions = data["sessions"]
    with output.open("w") as stream:
        for session in sessions:
            stream.write(json.dumps({
                "id": session["id"],
                "date": session["narrative_date"],
                "text": session["messages"][0].strip(),
            }) + "\n")
    print(f"{persona}: {len(sessions)} sessions -> {output}")


if __name__ == "__main__":
    main()
