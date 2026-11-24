#!/bin/bash
# Run one run_smoke.py stage with an environment built from scratch. launch.sh invokes this
# inside a systemd --user unit, so it is outside any caller's process group and cgroup.
#
#   bash stage.sh <run.conf> <prepare|ingest|freeze|evaluate|summary>
#
# The inherited environment is cleared except for a few basics; run.conf supplies paths (no
# secrets). Only the evaluate stage loads judge.env (the per-run judge relay password), by
# `source`, so no value is ever on a command line. Provider keys are never loaded here.
set -euo pipefail
CONF="${1:?run.conf}"; STAGE="${2:?stage}"
HERE="$(cd "$(dirname "$0")" && pwd)"
if ! id -nG | grep -qw docker; then exec sg docker -c "exec bash '$HERE/stage.sh' '$CONF' '$STAGE'"; fi
UNIT_INFO="$(cat /proc/self/cgroup)"
for name in $(compgen -e); do
  case "$name" in PATH|HOME|USER|LOGNAME|LANG|XDG_RUNTIME_DIR) ;; *) unset "$name" ;; esac
done
set -a
. "$CONF"
set +a
export PATH="$HOME/.bun/bin:$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
export PYTHONDONTWRITEBYTECODE=1
if [ "$STAGE" = evaluate ]; then
  set -a
  . "$ZO_SECRETS_DIR/judge.env"
  set +a
  export AZURE_OPENAI_ENDPOINT=http://127.0.0.1:8765
  umask 000   # the agent container runs --cap-drop=ALL; the staged payload must be writable
else
  umask 022
fi
cd "$HERE/../runner"
echo "stage $STAGE start $(date -u +%FT%TZ) pid $$ pgid $(ps -o pgid= $$ | tr -d ' ') sid $(ps -o sid= $$ | tr -d ' ') cgroup $UNIT_INFO"
set +e
"$DOLPHINBENCH_REPO/.venv/bin/python" run_smoke.py "$STAGE"
rc=$?
set -e
echo "stage $STAGE exit $rc $(date -u +%FT%TZ)"
echo "$rc" > "$ZO_RUN_DIR/logs/$STAGE.exit"
exit "$rc"
