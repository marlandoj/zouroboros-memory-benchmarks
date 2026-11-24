#!/bin/bash
# Build the agent image from the run's Hermes source (tracked files only, the benchmark's own
# builder), add the two runtime packages the first run pre-installed, record the image id.
# Runs inside a systemd --user unit via launch.sh (needs the docker group: sg docker).
set -euo pipefail
. "${1:?run.conf}"
if ! id -nG | grep -qw docker; then exec sg docker -c "exec bash '$0' '$1'"; fi
cd "$DOLPHINBENCH_REPO"
.venv/bin/python -m reference.execution.build_agent_image --source "$ZO_HERMES_SOURCE" \
  --memory builtin --tag "$ZO_IMAGE_TAG"
ctx="$(mktemp -d)"
printf 'FROM %s\nRUN python -m pip install --no-cache-dir boto3==1.42.89 edge-tts==7.2.7\n' "$ZO_IMAGE_TAG" > "$ctx/Dockerfile"
docker build --tag "$ZO_IMAGE_TAG-preinstalled" "$ctx"
rm "$ctx/Dockerfile"
rmdir "$ctx"
docker image inspect --format '{{.Id}}' "$ZO_IMAGE_TAG-preinstalled" > "$ZO_RUN_DIR/image-id.txt"
cat "$ZO_RUN_DIR/image-id.txt"
