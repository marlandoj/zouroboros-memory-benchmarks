#!/bin/bash
# Full DolphinBench run: personas in sequence, each in its own run directory (its own run.conf),
# each ingested, frozen (v2 checkpoint), then evaluated on all its tests, with a cash cap.
# Run it detached (launch it with systemd-run --user; see the README "Full run"):
#
#   bash full_run.sh <cap USD> <run.conf> [<run.conf> ...]
#
# Per persona: relays up, stages prepare -> ingest -> freeze -> evaluate -> summary (a stage
# whose logs/<stage>.exit is 0 is skipped, so the script resumes), relays down, costs.json.
# After the FIRST persona: full_cost.py projects the total from its measured rates into
# <first run dir>/projection.json; if the projection exceeds the cap, stop there.
# During evaluate, the cumulative cash of all persona runs is checked every 60 s; at the cap
# the stage is stopped (status cap-stop).
#
# Guard-crash policy (unchanged from the smoke, uniform): if evaluate exits non-zero on the
# benchmark's exact-match guard ("app call has no matching conversation tool call"), the one
# task with evidence but no grade is quarantined (quarantine_task.py) and evaluate resumes,
# i.e. the task re-runs fresh; at most 2 fresh re-runs per task, then stop. Every re-run is
# appended to <run dir>/guard-reruns.jsonl. Any other failure stops the script.
#
# Status: <first run dir>/../full-status.txt, one line per event.
set -uo pipefail
CAP="${1:?cap}"; shift
HERE="$(cd "$(dirname "$0")" && pwd)"
CONFS=("$@")
FIRST_RUN="$(. "${CONFS[0]}"; echo "$ZO_RUN_DIR")"
STATUS="$(dirname "$FIRST_RUN")/full-status.txt"
log() { echo "$(date -u +%FT%TZ) $*" >> "$STATUS"; }
PYB() { (. "${CONFS[0]}"; "$DOLPHINBENCH_REPO/.venv/bin/python" "$@"); }
GUARD='app call has no matching conversation tool call'
run_dirs=(); for c in "${CONFS[@]}"; do run_dirs+=("$(. "$c"; echo "$ZO_RUN_DIR")"); done
spent() { PYTHONDONTWRITEBYTECODE=1 PYB "$HERE/full_cost.py" spent "${run_dirs[@]}"; }
over_cap() { awk -v s="$(spent)" -v c="$CAP" 'BEGIN { exit !(s >= c) }'; }

run_stage() {  # conf stage -> rc   (each stage is its own transient systemd --user unit)
  local conf="$1" stage="$2" run name; run="$(. "$conf"; echo "$ZO_RUN_DIR")"; name="$(. "$conf"; echo "$ZO_RUN_NAME")"
  if [ "$(cat "$run/logs/$stage.exit" 2>/dev/null)" = 0 ]; then log "$(basename "$run") $stage already done"; return 0; fi
  bash "$HERE/launch.sh" "$conf" stage "$stage" >> "$run/logs/launch.log" 2>&1
  local unit="dolphinbench-$name-$stage" ticks=0
  sleep 5
  while systemctl --user is-active --quiet "$unit"; do
    sleep 15; ticks=$((ticks + 1))
    if [ "$stage" = evaluate ] && [ $((ticks % 4)) = 0 ] && over_cap; then
      log "CAP reached during $name evaluate (spent $(spent)); stopping the unit"
      systemctl --user stop "$unit"
      return 99
    fi
  done
  local rc; rc="$(cat "$run/logs/$stage.exit" 2>/dev/null || echo 98)"
  return "$rc"
}

evaluate_with_policy() {  # conf -> rc
  local conf="$1" run persona; run="$(. "$conf"; echo "$ZO_RUN_DIR")"; persona="$(. "$conf"; echo "$ZO_BENCH_PERSONA")"
  while true; do
    run_stage "$conf" evaluate; local rc=$?
    [ "$rc" = 0 ] && return 0
    [ "$rc" = 99 ] && return 99
    if ! tail -n 60 "$run/logs/evaluate.log" | grep -q "$GUARD"; then
      log "$persona evaluate failed rc=$rc (not the exact-match guard); stopping"; return "$rc"
    fi
    local ungraded=()
    for f in "$run/out/tests/$persona"/*.json; do
      [ -e "$f" ] || continue
      local id; id="$(basename "$f" .json)"
      [ -e "$run/out/grades/$persona/$id.json" ] || ungraded+=("$id")
    done
    if [ "${#ungraded[@]}" != 1 ]; then
      log "$persona guard crash but ${#ungraded[@]} ungraded tasks (${ungraded[*]}); stopping"; return 3
    fi
    local id="${ungraded[0]}" n
    n="$(ls -d "$run/quarantine/$id-attempt"* 2>/dev/null | wc -l)"
    if [ "$n" -ge 2 ]; then
      log "$persona task $id: guard crash after 2 fresh re-runs (bound reached); stopping"; return 4
    fi
    mkdir -p "$run/quarantine"
    PYTHONDONTWRITEBYTECODE=1 PYB "$HERE/quarantine_task.py" "$run/out" "$id" \
      "$run/quarantine/$id-attempt$((n + 1))" "$persona" >> "$run/logs/quarantine.log" 2>&1 || {
        log "$persona task $id: quarantine failed; stopping"; return 5; }
    echo "{\"task\": \"$id\", \"crashed_attempt\": $((n + 1)), \"at\": \"$(date -u +%FT%TZ)\"}" >> "$run/guard-reruns.jsonl"
    log "$persona task $id: exact-match guard crash, attempt $((n + 1)) quarantined; fresh re-run"
  done
}

log "full run start cap=$CAP personas=${#CONFS[@]}"
index=0
for conf in "${CONFS[@]}"; do
  run="${run_dirs[$index]}"; persona="$(. "$conf"; echo "$ZO_BENCH_PERSONA")"
  if over_cap; then log "cap reached before $persona (spent $(spent)); stopping"; exit 10; fi
  log "$persona start (spent so far $(spent))"
  bash "$HERE/launch.sh" "$conf" relays >> "$run/logs/launch.log" 2>&1 || { log "$persona relays failed"; exit 11; }
  for stage in prepare ingest freeze; do
    run_stage "$conf" "$stage" || { log "$persona $stage failed"; bash "$HERE/launch.sh" "$conf" stop; exit 12; }
    log "$persona $stage done"
  done
  evaluate_with_policy "$conf"; rc=$?
  if [ "$rc" != 0 ]; then bash "$HERE/launch.sh" "$conf" stop; log "$persona evaluate stopped rc=$rc"; exit 13; fi
  log "$persona evaluate done"
  run_stage "$conf" summary || log "$persona summary failed"
  bash "$HERE/launch.sh" "$conf" stop >> "$run/logs/launch.log" 2>&1
  PYTHONDONTWRITEBYTECODE=1 PYB "$HERE/costs.py" "$run/out" > "$run/costs.json" 2>> "$run/logs/launch.log"
  log "$persona complete (spent so far $(spent))"
  if [ "$index" = 0 ] && [ "${#CONFS[@]}" -gt 1 ]; then
    rest=(); for c in "${CONFS[@]:1}"; do rest+=("$(. "$c"; echo "$ZO_BENCH_PERSONA")"); done
    PYTHONDONTWRITEBYTECODE=1 PYB "$HERE/full_cost.py" project "$(. "$conf"; echo "$DOLPHINBENCH_REPO")" "$run" "${rest[@]}" \
      > "$run/projection.json" 2>> "$run/logs/launch.log" || { log "projection failed; stopping"; exit 14; }
    projected="$(grep -o '"projected_total_cash_usd": [0-9.e+-]*' "$run/projection.json" | awk '{print $2}')"
    log "checkpoint projection: total cash $projected USD (cap $CAP)"
    if awk -v p="$projected" -v c="$CAP" 'BEGIN { exit !(p > c) }'; then
      log "projection exceeds the cap; stopping after $persona"; exit 20
    fi
  fi
  index=$((index + 1))
done
log "full run complete (spent $(spent))"
