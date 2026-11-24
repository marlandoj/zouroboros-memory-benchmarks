#!/bin/bash
# Build the run's Hermes source: the pinned reference base, the benchmark's own evaluation
# patch, and the zo plugin copied from THIS repository (never from an untracked directory).
#
#   bash prepare_hermes_source.sh <run.conf>
#
# Commits: (1) examples/reference/hermes-evaluation.patch applied on 935c1e8, whose SHA-256 must
# equal the release spec's patch_sha256; (2) plugins/memory/zo from hermes-plugin/. Then a
# frozen uv sync (python 3.11, extras mcp + honcho, as the reference spec pins).
set -euo pipefail
. "${1:?run.conf}"
HERE="$(cd "$(dirname "$0")" && pwd)"
HARNESS="$(dirname "$HERE")"
SRC="$ZO_HERMES_SOURCE"
BASE=935c1e8962d43de3ef0adde30e80dda55d0247db
PATCH="$DOLPHINBENCH_REPO/examples/reference/hermes-evaluation.patch"
want="$(grep -o '"patch_sha256": *"[0-9a-f]*"' "$DOLPHINBENCH_REPO/examples/reference/hermes-builtin.json" | grep -o '[0-9a-f]\{64\}')"
have="$(sha256sum "$PATCH" | cut -d' ' -f1)"
[ "$want" = "$have" ] || { echo "benchmark patch sha mismatch" >&2; exit 1; }

if [ ! -d "$SRC/.git" ]; then
  # Objects come from the local reference clone (fetched from upstream in the first run).
  git clone -q --no-checkout "${ZO_HERMES_OBJECTS:?}" "$SRC"
  git -C "$SRC" remote set-url origin https://github.com/NousResearch/hermes-agent.git
  git -C "$SRC" checkout -q --detach "$BASE"
  git -C "$SRC" apply --binary "$PATCH"
  git -C "$SRC" add -A
  git -C "$SRC" -c user.name=zo-smoke -c user.email=smoke@zouroboros.local commit -q \
    -m "Apply DolphinBench examples/reference/hermes-evaluation.patch (sha256 $have)"
  mkdir -p "$SRC/plugins/memory/zo"
  cp "$HARNESS/hermes-plugin/plugins/memory/zo/__init__.py" "$HARNESS/hermes-plugin/plugins/memory/zo/plugin.yaml" \
     "$SRC/plugins/memory/zo/"
  harness_rev="$(git -C "$HARNESS" rev-parse HEAD)"
  git -C "$SRC" add plugins/memory/zo
  git -C "$SRC" -c user.name=zo-smoke -c user.email=smoke@zouroboros.local commit -q \
    -m "Add plugins/memory/zo from marlandoj/zouroboros-memory-benchmarks@$harness_rev (dolphinbench/zo-harness/hermes-plugin)"
fi
cd "$SRC"
uv sync --frozen --python 3.11 --extra mcp --extra honcho > "$ZO_RUN_DIR/logs/uv-sync.log" 2>&1
git log --oneline -3
git status --porcelain --untracked-files=all | head -5
sha256sum plugins/memory/zo/__init__.py plugins/memory/zo/plugin.yaml
