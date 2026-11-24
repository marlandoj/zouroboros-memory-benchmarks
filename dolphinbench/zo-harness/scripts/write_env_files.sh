#!/bin/bash
# Write the run's credential env-files into a private tmpfs directory (never on disk, never echoed).
#
#   ZO_SECRETS_DIR=/run/user/$(id -u)/<run> bash write_env_files.sh
#
# Reads OPENAI_API_KEY and OPENROUTER_API_KEY from the invoking environment and writes:
#   zo.env     OPENAI_API_KEY        -> zo adapter server only (bun --env-file)
#   relay.env  OPENROUTER_API_KEY    -> agent + judge relays only (systemd EnvironmentFile=)
#   judge.env  AZURE_OPENAI_API_KEY  -> a fresh random loopback password shared by the runner's
#                                       judge client and the judge relay (evaluate stage only)
# printf is a shell builtin, so no value ever appears in a process command line. Prints only
# file names and modes.
set -euo pipefail
umask 077
S="${ZO_SECRETS_DIR:?set ZO_SECRETS_DIR}"
case "$S" in /run/user/*) ;; *) echo "ZO_SECRETS_DIR must be under /run/user (tmpfs)" >&2; exit 2 ;; esac
[ -n "${OPENAI_API_KEY:-}" ] || { echo "OPENAI_API_KEY is not set" >&2; exit 2; }
[ -n "${OPENROUTER_API_KEY:-}" ] || { echo "OPENROUTER_API_KEY is not set" >&2; exit 2; }
mkdir -p "$S"
chmod 700 "$S"
printf 'OPENAI_API_KEY=%s\n' "$OPENAI_API_KEY" > "$S/zo.env"
printf 'OPENROUTER_API_KEY=%s\n' "$OPENROUTER_API_KEY" > "$S/relay.env"
judge="$(od -An -N24 -tx1 /dev/urandom | tr -d ' \n')"
printf 'AZURE_OPENAI_API_KEY=%s\n' "$judge" > "$S/judge.env"
unset judge
chmod 600 "$S/zo.env" "$S/relay.env" "$S/judge.env"
stat -c '%A %n' "$S" "$S"/*.env
