#!/usr/bin/env bash
# run.sh - one-command setup and launch for this recipe on one NVIDIA GB10.
#
#   git clone https://github.com/sxuff/glm53-flash-single-gb10 && cd glm53-flash-single-gb10 && ./run.sh
#
# Every pin and flag below is copied from this repo's README, patches or
# receipts; the comment next to each value names its source. Nothing here
# tunes, "improves" or changes a measured setting.
set -euo pipefail
cd "$(dirname "$0")"
REPO_DIR="$(pwd)"

# ===================== recipe config (per repo) =============================
RECIPE_NAME="glm53-flash-single-gb10"
PORT=8002                                        # fixed: serving/server.py (patches/02) binds 127.0.0.1:8002; not configurable
MODELS_DIR="${MODELS_DIR:-$HOME/models}"
SRC_DIR="${SRC_DIR:-$HOME/src}"
STATE_DIR="${STATE_DIR:-$HOME/.local/state/glm53-flash-single-gb10}"
NEEDS_TOOLS="git curl sha256sum docker python3 nvidia-smi ss numfmt"
# The loader admits the load only while host MemAvailable >= planned peak + 5 GiB
# (serving/loader_mosaic.py, patches/07); the planned peak is server.py's PEAK_ESTIMATE, 98.5 GiB.
NEED_MEM_BYTES=$(( 985 * 1073741824 / 10 + 5 * 1073741824 ))   # 103.5 GiB
ENGINE_KIND=docker
CONTAINER_NAME="tfglm-mosaic-v59-pipeline"       # serving/server.py STAGE (patches/07); the container name the host supervisor used
READY_URL="http://127.0.0.1:${PORT}/v1/models"   # the host supervisor's readiness probe (serving/supervisor.py, patches/02)
READY_TIMEOUT=1200                               # serving/supervisor.py (patches/02): readiness timeout 1200 s
EXPECTED_LINE="30.73 tok/s decode, mean of four prompt medians, single stream (measured at 2,560 cache slots; ./run.sh serves the README's 262,144-slot profile)"
RECEIPT_PATH="results/glm53-mosaic-decode-20261005.json"

# Engine source: TensorFold v0.6.5 with this repo's patches 01-04 (README.md:61,65-83) and
# patches/07-portable-launcher.patch, which replaces server.py's three host-only imports.
TF_URL="https://github.com/ashhart/TensorFold"
TF_COMMIT="609ca419abecebdc5a059498a613680bd3aa847f"   # README.md:61
TF_DIR="$SRC_DIR/glm53-tensorfold-${TF_COMMIT:0:12}"
PATCHES="
eba18758e5152c378bc698f7fc0a52ff2c6154fc9e53b57df4c9096743f39ea4 01-exl3-single-gpu-port.patch
9137cfdda8d57fa7702179608404c732d3f318dc4266c4fe1ce01d01ab69040d 02-serving.patch
6dc8437c9c9c81d13969587bd5a3cdd88a1e62d6b166bb95c283fa089bfe5d80 03-mosaic-mixed-width-experts.patch
629afcadb9bb833975f5995f28e3cf15ac6856ce0bcd038336da7db87daf890b 04-stream-keepalive-content-delta.patch
acb9011ec342d359a51d65741e6350d4c1face7986a69d7d5ae7ebf683dada42 07-portable-launcher.patch
"   # README.md:79-82 (01-04) and the README "Run it" section (07)

# Runtime image: the exact image behind every mosaic receipt, pinned by image ID (README.md:62).
IMAGE_ID="sha256:1f626b72bd7b20a470dae03ae18039049d50a0d496de20bf818b3b612c8699ee"
# The same image on ghcr.io, by manifest digest. That manifest's config digest is IMAGE_ID, so with Docker's
# classic image store a pull shows IMAGE_ID; with the containerd image store Docker reports the manifest digest.
IMAGE_PULL="ghcr.io/sxuff/glm53-tensorfold-runtime@sha256:b9b29ebb48b11026e4ee278d8ee4c2c20f168fdcc433359e883c7a8c2dfb5e18"
IMAGE_BYTES=33600645222        # docker image inspect .Size of IMAGE_ID, uncompressed
image_local() {                # prints the reference to run: the image ID if present, else the pulled digest
  if docker image inspect "$IMAGE_ID" >/dev/null 2>&1; then echo "$IMAGE_ID"
  elif docker image inspect "$IMAGE_PULL" >/dev/null 2>&1; then echo "$IMAGE_PULL"; fi
}
IMAGE_RUN="$(image_local)"

# The overlay the host installed beside the image (its grammar-requirements.txt): transformers 5.17.0, hash-pinned.
DEPS_DIR="$STATE_DIR/deps-transformers-5.17.0"
DEPS_REQ="transformers==5.17.0 --hash=sha256:78ec1ce21579b38dfb83950a0658cd119f87212a2fcfdff478096ce9d6c03801"

MODEL_DIR="$MODELS_DIR/glm53-mosaic-12l-264285174"
ENGINE_DISK_BYTES=0
[ -n "$IMAGE_RUN" ] || ENGINE_DISK_BYTES=$IMAGE_BYTES

# Pinned weights: 0xSero/GLM-5.3-Flash-EXL3-Spark @ 2642851741fc (README.md:60), 27 files,
# 96,105,136,306 bytes (results/glm53-mosaic-artifact-census-20261005.json pack_total_bytes).
# SHA-256 per file. LFS files: the Hub's LFS metadata at the pinned revision (they also match the
# checkpoint's own sha256-manifest.txt). The 12 small files: hashed from the Hub at that revision on
# 2026-11-11 (their git blob IDs match the Hub tree). Columns: sha256 bytes repo revision path dest.
W_REPO="0xSero/GLM-5.3-Flash-EXL3-Spark"
W_REV="2642851741fc833764e77d03039117be559dc83e"
WEIGHTS="
d3b10d515fb2bb0da69e29ec07a1e44296bd0dc1a51d1388be703a189d470cab 1696 $W_REPO $W_REV .gitattributes glm53-mosaic-12l-264285174/.gitattributes
3b9b98e4b0d0c7494ffe0ececb570a6beb94d7588d5ea67f50ca3a9ae5165332 159 $W_REPO $W_REV DOWNLOAD-SEAL.json glm53-mosaic-12l-264285174/DOWNLOAD-SEAL.json
30b85b6b9659f2e78aa259f8faf5d920a68dee7c9ced3fa6dba1f19f2bc4fca1 1070 $W_REPO $W_REV LICENSE glm53-mosaic-12l-264285174/LICENSE
dcc332b8cf01ff05ced1544dc5fd6c41a519f71a06f762748d293c3301b669aa 3626 $W_REPO $W_REV PROVENANCE.json glm53-mosaic-12l-264285174/PROVENANCE.json
0b2fbcd899986ef69473917ad4a9b8bfa3b6c4e90a263902975811487cc79830 5033 $W_REPO $W_REV README.md glm53-mosaic-12l-264285174/README.md
41cff9af7b3a86c96751b107a8444f245fbda0bd5320b636a5bb1f7f4ba1a5c3 8617 $W_REPO $W_REV chat_template.jinja glm53-mosaic-12l-264285174/chat_template.jinja
43921c0b6dd51805a243649a647417230ef9cb9ba8e26ae06a461c3f7e08d037 86532 $W_REPO $W_REV config.json glm53-mosaic-12l-264285174/config.json
230c30609ecbbb9e6583bedde8e7bdda0c6eb8fe5fad0eaeb3d1b293d751cb4f 194 $W_REPO $W_REV generation_config.json glm53-mosaic-12l-264285174/generation_config.json
0c747ea520a74a3fce0b482ea4c2ad266761f1e1da5bee79624a005c03bae136 8338599140 $W_REPO $W_REV model-00001-of-00012.safetensors glm53-mosaic-12l-264285174/model-00001-of-00012.safetensors
fa59e1f5a50f87defe7b6ff71f76a0fcab320b606096155b474aef94271515da 7676876178 $W_REPO $W_REV model-00002-of-00012.safetensors glm53-mosaic-12l-264285174/model-00002-of-00012.safetensors
5b9464704a0fafdcbfbaf56d3e589c309aa38c38cf4e545145421f69659cb256 7676890170 $W_REPO $W_REV model-00003-of-00012.safetensors glm53-mosaic-12l-264285174/model-00003-of-00012.safetensors
022876be3d8fbb11216be5ce8758c4067c0e00c880c876395e6132ef7ce7ac2f 7676890170 $W_REPO $W_REV model-00004-of-00012.safetensors glm53-mosaic-12l-264285174/model-00004-of-00012.safetensors
87df348852f785bbb60003737a802cad059aea665d537d8c543991084a3de44a 7676890170 $W_REPO $W_REV model-00005-of-00012.safetensors glm53-mosaic-12l-264285174/model-00005-of-00012.safetensors
10777ced73454005836098cc39cafbcef6936172860705e0f5be7075b1b7136e 7676890170 $W_REPO $W_REV model-00006-of-00012.safetensors glm53-mosaic-12l-264285174/model-00006-of-00012.safetensors
bf3a8deb3189d57d2ef242a71398a9a8cffb6fc0cc7d4a7cca3e25df92c34037 7676890170 $W_REPO $W_REV model-00007-of-00012.safetensors glm53-mosaic-12l-264285174/model-00007-of-00012.safetensors
57a097001adc64da8041ab68c2a011780f16e43395a2bbf686dc1f265833a98d 9488829500 $W_REPO $W_REV model-00008-of-00012.safetensors glm53-mosaic-12l-264285174/model-00008-of-00012.safetensors
5edb8b52e9f2f20185d4b49aebf91ea6917a5723364878c892cede1c7d443331 9488829500 $W_REPO $W_REV model-00009-of-00012.safetensors glm53-mosaic-12l-264285174/model-00009-of-00012.safetensors
bd32555c618e9266cccd8f6bd4079bd4a868629c7bf1a14c731de09f9702f727 11300773364 $W_REPO $W_REV model-00010-of-00012.safetensors glm53-mosaic-12l-264285174/model-00010-of-00012.safetensors
73452e068d0db728c925eafd1142448a07d955a49fa82b7c0412876295af9bea 11298120632 $W_REPO $W_REV model-00011-of-00012.safetensors glm53-mosaic-12l-264285174/model-00011-of-00012.safetensors
c33e653466463e6bb081f3c4c50665e83f8bce36d4967c5e4a1270367b8a026a 44078468 $W_REPO $W_REV model-00012-of-00012.safetensors glm53-mosaic-12l-264285174/model-00012-of-00012.safetensors
9509363becd75ed23fc60fd678cd4dd3de214c4fa4df177f8d13ab7a09bc4ecb 16343097 $W_REPO $W_REV model.safetensors.index.json glm53-mosaic-12l-264285174/model.safetensors.index.json
aae38374c94b08cc9b0547c6e64f05b951bd9735cea571c6988f5ed552bed3ed 909 $W_REPO $W_REV processor_config.json glm53-mosaic-12l-264285174/processor_config.json
0fd462eec7938a4211bbe820cb49d7b4eb8f0e177da79e0e73286ea7e34bbf4c 1462 $W_REPO $W_REV pull.sh glm53-mosaic-12l-264285174/pull.sh
06c2613e02040d0036ef6ab98ecec292aadd0f2dec0219cfd6ba5cdd5ff4b3a0 47905720 $W_REPO $W_REV quantization_config.json glm53-mosaic-12l-264285174/quantization_config.json
b51fe40eb74fbf2f657bafa3efe9700af5022158d46dae7ecd23951913a2948f 2356 $W_REPO $W_REV sha256-manifest.txt glm53-mosaic-12l-264285174/sha256-manifest.txt
19e773648cb4e65de8660ea6365e10acca112d42a854923df93db4a6f333a82d 20217442 $W_REPO $W_REV tokenizer.json glm53-mosaic-12l-264285174/tokenizer.json
98b1271574f41abf89427ae2dda030d94dc9478f0edc5a8bd240db213c6fd5fc 761 $W_REPO $W_REV tokenizer_config.json glm53-mosaic-12l-264285174/tokenizer_config.json
"

engine_step() {
  # 1) the runtime image, by image ID
  if [ -n "$IMAGE_RUN" ]; then ok "image present: $IMAGE_RUN"
  elif [ "$CHECK" = 1 ]; then plan "docker pull $IMAGE_PULL  (14.9 GB compressed; its config digest is $IMAGE_ID)"
  else
    docker pull "$IMAGE_PULL"
    local id; id="$(docker image inspect "$IMAGE_PULL" --format '{{.Id}}')"
    case "$id" in "$IMAGE_ID"|"${IMAGE_PULL##*@}") ;; *) die "pulled image $id is neither $IMAGE_ID nor ${IMAGE_PULL##*@}" ;; esac
    IMAGE_RUN="$IMAGE_PULL"; ok "image pulled: $IMAGE_PULL"
  fi
  # 2) TensorFold at the pinned commit; every patch checked by SHA-256, then applied in order
  local mark="$TF_DIR/.glm53-patches-applied" want sha name
  want="$(printf '%s\n' "$PATCHES" | sed '/^$/d' | sha256sum | cut -d' ' -f1)"
  while read -r sha name; do
    [ -z "${sha:-}" ] && continue
    [ "$(sha256sum "$REPO_DIR/patches/$name" | cut -d' ' -f1)" = "$sha" ] || die "patches/$name SHA-256 differs from its pin"
  done <<< "$PATCHES"
  ok "patch SHA-256s match pins (01, 02, 03, 04, 07)"
  if [ -f "$mark" ] && [ "$(cat "$mark")" = "$TF_COMMIT $want" ]; then ok "TensorFold ${TF_COMMIT:0:12} + patches: $TF_DIR"
  elif [ "$CHECK" = 1 ]; then plan "clone $TF_URL to $TF_DIR, check out ${TF_COMMIT:0:12}, git apply patches 01, 02, 03, 04, 07"
  else
    [ ! -e "$TF_DIR" ] || die "$TF_DIR exists but is not a finished patched tree; move it away and re-run"
    mkdir -p "$SRC_DIR"; git_pin "$TF_URL" "$TF_COMMIT" "$TF_DIR"
    while read -r sha name; do
      [ -z "${sha:-}" ] && continue
      git -C "$TF_DIR" apply --whitespace=nowarn "$REPO_DIR/patches/$name"
    done <<< "$PATCHES"
    echo "$TF_COMMIT $want" > "$mark"; ok "patched: $TF_DIR"
  fi
  # 3) the transformers overlay, hash-pinned, installed by the image's own pip
  if [ -f "$DEPS_DIR/.ok" ]; then ok "overlay present: $DEPS_DIR"
  elif [ "$CHECK" = 1 ]; then plan "pip install --no-deps --require-hashes ${DEPS_REQ%% *} into $DEPS_DIR (with the image's pip)"
  else
    mkdir -p "$DEPS_DIR"; printf '%s\n' "$DEPS_REQ" > "$DEPS_DIR/requirements.txt"
    docker run --rm --network host --user "$(id -u):$(id -g)" -e HOME=/tmp -e PYTHONPATH= -v "$DEPS_DIR:/deps" \
      --entrypoint /opt/sglang/bin/python3 "${IMAGE_RUN:-$IMAGE_PULL}" \
      -m pip install --quiet --no-deps --require-hashes --target /deps -r /deps/requirements.txt
    touch "$DEPS_DIR/.ok"; ok "overlay installed: $DEPS_DIR"
  fi
}

serve_step() {   # the docker run of serving/supervisor.py (patches/02), without the host's own service hand-off
  local gib=1073741824 swap
  swap=$(awk '/SwapTotal/{t=$2} /SwapFree/{f=$2} END{print (t-f)*1024}' /proc/meminfo)   # host swap baseline, as the host launcher took it
  local argv=(docker run -d --pull never --name "$CONTAINER_NAME" --label "tfglm.stage=$CONTAINER_NAME" --gpus all --network host
    --memory $((95 * gib)) --memory-swap $((95 * gib)) --entrypoint python3
    -v "$TF_DIR:/work/TensorFold:ro" -v "$DEPS_DIR:/work/deps:ro" -v "$MODEL_DIR:/model:ro"
    -v "$STATE_DIR/torch_extensions:/work/torch_extensions"
    -e EXL3_INT8_GEMV=2 -e PYTHONDONTWRITEBYTECODE=1 -e "TFGLM_CONTROLLER_STAGE=$CONTAINER_NAME"
    -e TORCH_EXTENSIONS_DIR=/work/torch_extensions
    -e PYTHONPATH=/work/deps:/work/TensorFold/src:/opt/sglang/lib/python3.12/site-packages
    "${IMAGE_RUN:-$IMAGE_PULL}" -B -S /work/TensorFold/serving/server.py --model /model --host-swap-baseline-bytes "$swap")
  # supervisor.py: 95 GiB memory limit, zero container swap, EXL3_INT8_GEMV=2 (README.md:63), same env and entry point
  if [ "$CHECK" = 1 ]; then plan "${argv[*]}"; return; fi
  mkdir -p "$STATE_DIR/torch_extensions"
  docker rm "$CONTAINER_NAME" >/dev/null 2>&1 || true   # a stopped container left by an earlier run
  "${argv[@]}" >/dev/null
  nohup docker logs -f "$CONTAINER_NAME" >"$LOGFILE" 2>&1 &
}

stop_override() {
  if [ -n "$(docker ps -aq --filter "name=^${CONTAINER_NAME}\$" 2>/dev/null)" ]; then
    doit docker stop --time 30 "$CONTAINER_NAME"; doit docker rm "$CONTAINER_NAME"
    ok "stopped and removed $CONTAINER_NAME"
  else ok "nothing started by this script is running"; fi
}

curl_test() {      # served model id and request fields: README.md:89-94 and serving/server.py
  cat <<EOF
curl -s http://127.0.0.1:${PORT}/v1/chat/completions -H 'Content-Type: application/json' \\
  -d '{"model":"glm53","messages":[{"role":"user","content":"Return only the integer obtained by multiplying 12 by 17."}],"max_tokens":2000}'
curl -s http://127.0.0.1:${PORT}/health
EOF
}
# ===================== end of recipe config =================================

# ---------------------------------------------------------------------------
# Shared machinery (identical in every sxuff recipe repo).
# ---------------------------------------------------------------------------
CHECK=0; ACTION=run
usage() {
  cat <<EOF
Usage: ./run.sh [--check] [--stop] [--help]

Sets up and launches ${RECIPE_NAME} on one NVIDIA GB10 (SM121).

  (no flag)  check the machine, build or pull the pinned engine, download the
             pinned weights, verify SHA-256, start the server, print a test.
             Safe to re-run: finished steps are skipped.
  --check    print what would happen; change nothing.
  --stop     stop the server this script started.
  --help     show this text.

Environment:
  HF_TOKEN     Hugging Face token, read from the environment only, never saved.
  MODELS_DIR   weights        (default: ${MODELS_DIR})
  SRC_DIR      engine source  (default: ${SRC_DIR})
  STATE_DIR    pid and log    (default: ${STATE_DIR})
  PORT         server port    (default: ${PORT})

Expected: ${EXPECTED_LINE}
Receipt:  ${RECEIPT_PATH}
EOF
}
for a in "$@"; do
  case "$a" in
    --check) CHECK=1 ;;
    --stop)  ACTION=stop ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $a (see ./run.sh --help)" >&2; exit 2 ;;
  esac
done

say()  { printf '\n==> %s\n' "$*"; }
ok()   { printf '    ok    %s\n' "$*"; }
plan() { printf '    would %s\n' "$*"; }
die()  { printf '\nerror: %s\n' "$*" >&2; exit 1; }
CHECK_FAILED=0   # under --check, a failed pre-flight check is reported and the plan continues
fail() { if [ "$CHECK" = 1 ]; then printf '    FAIL  %s\n' "$*"; CHECK_FAILED=1; else die "$*"; fi; }
human(){ numfmt --to=iec --suffix=B "$1" 2>/dev/null || echo "$1 B"; }
doit() { if [ "$CHECK" = 1 ]; then plan "$*"; else "$@"; fi; }   # mutate, or describe under --check

PIDFILE="${STATE_DIR}/server.pid"
LOGFILE="${STATE_DIR}/server.log"
STOP_CMD="cd ${REPO_DIR} && ./run.sh --stop"

server_running() {
  if [ "$ENGINE_KIND" = docker ]; then
    [ -n "$(docker ps -q --filter "name=^${CONTAINER_NAME}\$" 2>/dev/null)" ]
  else
    [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null
  fi
}

stop_step() {   # may be overridden in the config block (e.g. to call scripts/stop.sh)
  if ! server_running; then ok "nothing started by this script is running"; return; fi
  if [ "$ENGINE_KIND" = docker ]; then doit docker stop "$CONTAINER_NAME"
  else
    local pid; pid="$(cat "$PIDFILE")"; doit kill "$pid"
    if [ "$CHECK" = 0 ]; then
      for _ in $(seq 1 60); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
      kill -0 "$pid" 2>/dev/null && kill -9 "$pid"; rm -f "$PIDFILE"
    fi
  fi
  ok "stopped"
}
declare -f stop_override >/dev/null && stop_step() { stop_override; }

if [ "$ACTION" = stop ]; then say "Stopping ${RECIPE_NAME}"; stop_step; exit 0; fi
[ "$CHECK" = 1 ] && say "--check: nothing will be changed"

# git checkout of an exact commit, idempotent. Usage: git_pin <url> <sha> <dir>
git_pin() {
  local url="$1" sha="$2" dir="$3"
  if [ -d "$dir/.git" ] && [ "$(git -C "$dir" rev-parse HEAD)" = "$sha" ]; then ok "source at ${sha:0:12}: $dir"; return; fi
  if [ ! -d "$dir/.git" ]; then doit git clone --quiet "$url" "$dir"; fi
  if [ "$CHECK" = 1 ]; then plan "check out $sha in $dir"; return; fi
  [ -z "$(git -C "$dir" status --porcelain)" ] || die "$dir has local changes; refusing to move it to $sha"
  git -C "$dir" fetch --quiet origin "$sha" 2>/dev/null || git -C "$dir" fetch --quiet origin
  git -C "$dir" checkout --quiet --detach "$sha"
  [ "$(git -C "$dir" rev-parse HEAD)" = "$sha" ] || die "could not check out $sha in $dir"
  ok "source at ${sha:0:12}: $dir"
}

# docker image by digest, idempotent. Usage: image_pin <repo@sha256:...>
image_pin() {
  if docker image inspect "$1" >/dev/null 2>&1; then ok "image present: $1"; else doit docker pull "$1"; fi
}

# --- 1. machine ------------------------------------------------------------
say "Machine"
[ "$(uname -m)" = aarch64 ] || die "expected aarch64 (GB10), got $(uname -m)"
command -v nvidia-smi >/dev/null || die "nvidia-smi not found"
GPU="$(nvidia-smi --query-gpu=name,compute_cap --format=csv,noheader | head -1)"
case "$GPU" in *GB10*", 12.1") ok "GPU: $GPU" ;; *) die "measured on an NVIDIA GB10 (SM121); found: ${GPU:-none}" ;; esac
MISSING=""; for t in $NEEDS_TOOLS; do command -v "$t" >/dev/null || MISSING="$MISSING $t"; done
if [ -n "$MISSING" ]; then fail "missing tool(s):$MISSING"; else ok "tools: $NEEDS_TOOLS"; fi
ALREADY=0; server_running && ALREADY=1
MEM_AVAIL=$(( $(awk '/MemAvailable/ {print $2}' /proc/meminfo) * 1024 ))
if [ "$ALREADY" = 1 ]; then ok "server already running; memory check skipped"
elif [ "$MEM_AVAIL" -lt "$NEED_MEM_BYTES" ]; then
  fail "need $(human "$NEED_MEM_BYTES") available memory, have $(human "$MEM_AVAIL"). Stop other models first (nvidia-smi, docker ps)."
else ok "memory: $(human "$MEM_AVAIL") available, need $(human "$NEED_MEM_BYTES")"; fi
if [ "$ALREADY" = 1 ]; then ok "port ${PORT}: served by this recipe"
else
  # The server binds 127.0.0.1 (or the host network). A listener on 127.0.0.1, a wildcard or ::1
  # blocks it; one bound to another interface address does not, and is only reported.
  PORT_ALL="$(ss -ltnH "sport = :${PORT}" 2>/dev/null || true)"
  PORT_CLASH="$(printf '%s\n' "$PORT_ALL" | awk '{print $4}' | grep -E '^(127\.0\.0\.1|0\.0\.0\.0|\*|\[::\]|\[::1\]|\[::ffff:127\.0\.0\.1\]):' || true)"
  PORT_DOCKER="$(docker ps --format '{{.Names}} {{.Ports}}' 2>/dev/null | grep -E "(127\.0\.0\.1|0\.0\.0\.0|\[::\]|:::?):${PORT}->" || true)"
  if [ -n "$PORT_CLASH$PORT_DOCKER" ]; then
    printf '    port %s is taken:\n%s\n%s\n' "$PORT" "$PORT_CLASH" "$PORT_DOCKER"
    fail "free port ${PORT} or run: PORT=<other> ./run.sh"
  elif [ -n "$PORT_ALL" ]; then
    ok "port ${PORT}: free on 127.0.0.1 (also bound elsewhere: $(printf '%s' "$PORT_ALL" | awk '{print $4}' | tr '\n' ' '))"
  else ok "port ${PORT}: free"; fi
fi

# --- 2. disk ---------------------------------------------------------------
say "Disk"
nearest_dir() { local d="$1"; while [ ! -d "$d" ]; do d="$(dirname "$d")"; done; echo "$d"; }
NEED_DISK=$ENGINE_DISK_BYTES
while read -r sha size repo rev rpath dest; do
  [ -z "${sha:-}" ] && continue
  have=0; [ -f "$MODELS_DIR/$dest" ] && have=$(stat -c %s "$MODELS_DIR/$dest")
  [ "$have" -lt "$size" ] && NEED_DISK=$(( NEED_DISK + size - have ))
done <<< "$WEIGHTS"
FREE_DISK=$(df -B1 --output=avail "$(nearest_dir "$MODELS_DIR")" | tail -1 | tr -d ' ')
if [ "$FREE_DISK" -ge "$NEED_DISK" ]; then ok "need $(human "$NEED_DISK") more, have $(human "$FREE_DISK")"
else fail "need $(human "$NEED_DISK") more disk under $MODELS_DIR, have $(human "$FREE_DISK"). Nothing was deleted."; fi

# --- 3. engine -------------------------------------------------------------
say "Engine"
engine_step

# --- 4. weights: pinned revision + SHA-256 -----------------------------------
hf_fetch() {   # repo rev path dest. The token reaches curl on stdin: never in argv or a file.
  { [ -n "${HF_TOKEN:-}" ] && printf 'header = "Authorization: Bearer %s"\n' "$HF_TOKEN"; true; } |
    curl --fail --location --retry 5 --retry-delay 5 --continue-at - --config - \
         --output "$4.part" "https://huggingface.co/$1/resolve/$2/$3"
  mv "$4.part" "$4"
}
default_weights_step() {
  while read -r sha size repo rev rpath dest; do
    [ -z "${sha:-}" ] && continue
    local f="$MODELS_DIR/$dest" mark="$MODELS_DIR/$dest.sha256-ok"
    if [ -f "$mark" ] && [ "$(cat "$mark")" = "$sha $size" ] && [ "$(stat -c %s "$f" 2>/dev/null)" = "$size" ]; then
      ok "verified earlier: $dest"; continue
    fi
    if [ "$(stat -c %s "$f" 2>/dev/null || echo 0)" != "$size" ]; then
      if [ "$CHECK" = 1 ]; then plan "download $repo@${rev:0:12} $rpath ($(human "$size"))"; continue; fi
      mkdir -p "$(dirname "$f")"; printf '    get   %s (%s)\n' "$rpath" "$(human "$size")"
      hf_fetch "$repo" "$rev" "$rpath" "$f"
    elif [ "$CHECK" = 1 ]; then plan "verify SHA-256 of $dest"; continue; fi
    local got; got="$(sha256sum "$f" | cut -d' ' -f1)"
    if [ "$got" != "$sha" ]; then mv "$f" "$f.sha256-mismatch"; die "SHA-256 mismatch for $dest: expected $sha, got $got (kept as $f.sha256-mismatch)"; fi
    echo "$sha $size" > "$mark"; ok "sha256 ok: $dest"
  done <<< "$WEIGHTS"
}
declare -f weights_step >/dev/null || weights_step() { default_weights_step; }
say "Weights"
weights_step

# --- 5. serve --------------------------------------------------------------
say "Server"
if [ "$ALREADY" = 1 ]; then ok "already running"
elif [ "$CHECK" = 1 ]; then serve_step
else
  mkdir -p "$STATE_DIR"; serve_step
  printf '    wait  for %s (up to %ss; log: %s)\n' "$READY_URL" "$READY_TIMEOUT" "$LOGFILE"
  t=0
  until curl -fsS -o /dev/null "$READY_URL" 2>/dev/null; do
    server_running || die "server exited during start-up; see $LOGFILE"
    [ "$t" -ge "$READY_TIMEOUT" ] && die "not ready after ${READY_TIMEOUT}s; see $LOGFILE"
    sleep 5; t=$((t + 5))
  done
  ok "ready after ${t}s"
fi

# --- 6. done ---------------------------------------------------------------
if [ "$CHECK" = 1 ]; then
  if [ "$CHECK_FAILED" = 1 ]; then say "Check finished with FAIL lines above; nothing was changed. ./run.sh would stop at the first one."; exit 1; fi
  say "Check finished; nothing was changed. Run ./run.sh to do it."; exit 0
fi
say "Test it"
curl_test
say "Stop it"
echo "$STOP_CMD"
echo
echo "Expected: ${EXPECTED_LINE} - receipt: ${RECEIPT_PATH}"
