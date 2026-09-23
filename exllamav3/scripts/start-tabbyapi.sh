#!/usr/bin/env bash
# Pinned TabbyAPI launcher for GLM-5.3-Flash EXL3 2.05bpw with MTP n=1.
#
#   MODEL_DIR=/path/to/glm53-flash-exl3-2.05bpw ./start-tabbyapi.sh
#
# Pins the image ID and the engine version, refuses to start while another GPU
# runtime is active, and runs the page-cache hint plus the memory gate before
# `docker run`. Environment overrides:
#   MODEL_DIR    checkpoint directory                      (default below)
#   PORT         host loopback port to publish             (default 8002)
#   NAME         container name                            (default glm53-tabbyapi-primary)
#   REPORT_DIR   where the gate scripts write their JSON   (default $HOME/.hermes/reports)
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_DIR="${MODEL_DIR:-$HOME/models/glm53-flash-exl3-2.05bpw}"
PORT="${PORT:-8002}"
NAME="${NAME:-glm53-tabbyapi-primary}"
REPORT_DIR="${REPORT_DIR:-$HOME/.hermes/reports}"
CONFIG="${CONFIG:-$here/../config/glm53-tabbyapi-vision-262k.yml}"

image='local/glm53-tabbyapi:f07131c-kda'
expected_id='sha256:f3843891b30c4329bb502b959a18a5182cc8fc18a8f7c74f811c526f55696029'
actual_id="$(docker image inspect "$image" --format '{{.Id}}')"
[[ "$actual_id" == "$expected_id" ]] || { printf 'image pin mismatch\n' >&2; exit 3; }

# Source revision plus the ARM64 compatibility patch are pinned by that immutable ID.
# exllamav3 1.4.9 is mandatory; never silently accept a different engine.
version="$(docker run --rm --entrypoint python3 "$image" -c 'import importlib.metadata;print(importlib.metadata.version("exllamav3"))' 2>/dev/null)"
[[ "$version" == '1.4.9' ]] || { printf 'engine pin mismatch: %s\n' "${version:-none}" >&2; exit 4; }

# One GPU runtime at a time. Refuse if anything else is already holding the device.
busy="$(docker ps --format '{{.Names}}' | grep -v "^${NAME}$" | grep -E 'glm53|llama|sglang|vllm|tabbyapi' || true)"
[[ -z "$busy" ]] || { printf 'another GPU runtime is active: %s\n' "$busy" >&2; exit 5; }
[[ -d "$MODEL_DIR" ]] || { printf 'model dir not found: %s\n' "$MODEL_DIR" >&2; exit 6; }

MODEL_DIR="$MODEL_DIR" REPORT_DIR="$REPORT_DIR" python3 -u "$here/pagecache-hint.py"
REPORT_DIR="$REPORT_DIR" python3 -u "$here/prelaunch-gate.py"

cleanup() { docker stop --time 3 "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT INT TERM

docker run --rm --name "$NAME" --gpus all --ipc=host --shm-size=8g \
  --memory=110000000000 --memory-swap=110000000000 \
  -p "127.0.0.1:${PORT}:5000" \
  -v "$MODEL_DIR":/models/glm53:ro \
  -v "$CONFIG":/cfg/config.yml:ro \
  "$image" --config /cfg/config.yml
