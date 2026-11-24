#!/bin/bash
# Launch the run's long-lived processes as transient systemd --user units, detached from the
# caller: a unit belongs to the user manager (user@<uid>.service), not to the caller's session,
# process group or cgroup, so a caller's timeout, SIGHUP or cgroup reap cannot reach it.
#
#   bash launch.sh <run.conf> relays            agent relay (0.0.0.0:8766) + judge relay (127.0.0.1:8765)
#   bash launch.sh <run.conf> stage <name>      one run_smoke.py stage (stage.sh)
#   bash launch.sh <run.conf> image             build the agent image (build_image.sh)
#   bash launch.sh <run.conf> stop              stop the relays
#
# Credentials reach the relays only through EnvironmentFile= (systemd reads the file; the
# value is never on a command line or in a unit property). Output goes to $ZO_RUN_DIR/logs.
set -euo pipefail
CONF="$(readlink -f "${1:?run.conf}")"; WHAT="${2:?what}"
. "$CONF"
HERE="$(cd "$(dirname "$0")" && pwd)"
RUNNER="$(dirname "$HERE")/runner"
PY="$DOLPHINBENCH_REPO/.venv/bin/python"
LOGS="$ZO_RUN_DIR/logs"
OUT="$ZO_RUN_DIR/out"
U="dolphinbench-$ZO_RUN_NAME"
mkdir -p "$LOGS" "$OUT/agent-relay-tags"
mkdir -p -m 700 "$ZO_RUN_DIR/relay-tokens"
chmod 700 "$ZO_RUN_DIR/relay-tokens"

case "$WHAT" in
relays)
  systemd-run --user --quiet --collect --unit="$U-agent-relay" \
    -p Restart=on-failure -p RestartSec=2 \
    -p EnvironmentFile="$ZO_SECRETS_DIR/relay.env" \
    --setenv=AGENT_RELAY_HOST=0.0.0.0 \
    --setenv=AGENT_RELAY_TOKENS="$ZO_RUN_DIR/relay-tokens" \
    --setenv=AGENT_RELAY_LOG="$OUT/agent-relay.jsonl" \
    --setenv=AGENT_RELAY_TAGS="$OUT/agent-relay-tags" \
    --working-directory="$RUNNER" \
    -p StandardOutput=append:"$LOGS/agent-relay.out" -p StandardError=append:"$LOGS/agent-relay.out" \
    "$PY" agent_relay.py
  systemd-run --user --quiet --collect --unit="$U-judge-relay" \
    -p Restart=on-failure -p RestartSec=2 \
    -p EnvironmentFile="$ZO_SECRETS_DIR/relay.env" \
    -p EnvironmentFile="$ZO_SECRETS_DIR/judge.env" \
    --setenv=JUDGE_RELAY_LOG="$OUT/judge-relay.jsonl" \
    --working-directory="$RUNNER" \
    -p StandardOutput=append:"$LOGS/judge-relay.out" -p StandardError=append:"$LOGS/judge-relay.out" \
    "$PY" judge_relay.py
  sleep 2
  systemctl --user is-active "$U-agent-relay" "$U-judge-relay"
  ;;
stage)
  NAME="${3:?stage name}"
  rm -f "$LOGS/$NAME.exit"
  systemd-run --user --quiet --collect --unit="$U-$NAME" \
    --working-directory="$RUNNER" \
    -p StandardOutput=append:"$LOGS/$NAME.log" -p StandardError=append:"$LOGS/$NAME.log" \
    /bin/bash "$HERE/stage.sh" "$CONF" "$NAME"
  systemctl --user is-active "$U-$NAME" || true
  ;;
image)
  systemd-run --user --quiet --collect --unit="$U-image" \
    -p StandardOutput=append:"$LOGS/image-build.log" -p StandardError=append:"$LOGS/image-build.log" \
    /bin/bash "$HERE/build_image.sh" "$CONF"
  ;;
stop)
  systemctl --user stop "$U-agent-relay" "$U-judge-relay" || true
  ;;
*) echo "unknown: $WHAT" >&2; exit 2 ;;
esac
