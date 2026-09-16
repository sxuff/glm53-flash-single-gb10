#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${MODE:-dflash2}"
if [[ -z "${LLAMA_ROOT:-}" ]]; then
  case "$MODE" in
    dflash2|dflash2-control) LLAMA_ROOT="$REPO_ROOT/runtime/llama.cpp-dflash2" ;;
    *) LLAMA_ROOT="$REPO_ROOT/runtime/llama.cpp" ;;
  esac
fi
BUILD_DIR="${BUILD_DIR:-$LLAMA_ROOT/build-gb10}"
MODEL_DIR="${MODEL_DIR:?set MODEL_DIR to the verified UD-IQ2_XXS directory}"
MODEL="${MODEL:-$MODEL_DIR/GLM-5.3-Flash-UD-IQ2_XXS-00001-of-00004.gguf}"
TARGET_MANIFEST="${TARGET_MANIFEST:-$REPO_ROOT/manifests/target.json}"
DRAFT_DIR="${DRAFT_DIR:-}"
DRAFT_MODEL="${DRAFT_MODEL:-$DRAFT_DIR/GLM-5.3-Flash-DFlash2-Q4_K_M.gguf}"
DFLASH_MANIFEST="${DFLASH_MANIFEST:-$REPO_ROOT/manifests/dflash2.json}"
DFLASH_DERIVED_MANIFEST="${DFLASH_DERIVED_MANIFEST:-$REPO_ROOT/manifests/dflash2-derived.json}"
DFLASH_N_MAX="${DFLASH_N_MAX:-3}"
DFLASH_P_MIN="${DFLASH_P_MIN:-0.30}"
MMPROJ="${MMPROJ:-}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8001}"
CTX="${CTX:-8192}"

args=(
  --model "$MODEL"
  --host "$HOST"
  --port "$PORT"
  --ctx-size "$CTX"
  --parallel 1
  --n-gpu-layers 99
  --flash-attn on
  --jinja
  --metrics
  --no-webui
)

if [[ -n "$MMPROJ" ]]; then
  args+=(--mmproj "$MMPROJ")
fi

case "$MODE" in
  mtp)
    args+=(--spec-type draft-mtp --spec-draft-n-max 2 --spec-draft-n-min 0)
    ;;
  no-mtp)
    args+=(--spec-type none)
    ;;
  dflash2-control)
    args+=(
      --spec-type none
      --cache-type-k q8_0
      --cache-type-v q8_0
      --no-kv-unified
      --fit off
    )
    ;;
  dflash2)
    test -n "$DRAFT_DIR" || { printf 'set DRAFT_DIR for MODE=dflash2\n' >&2; exit 2; }
    test -f "$DRAFT_MODEL" || { printf 'missing DFlash2 draft: %s\n' "$DRAFT_MODEL" >&2; exit 2; }
    python3 "$REPO_ROOT/scripts/verify_dflash_metadata.py" \
      --manifest "$DFLASH_MANIFEST" \
      --model "$DRAFT_MODEL"
    args+=(
      --model-draft "$DRAFT_MODEL"
      --spec-type draft-dflash
      --spec-draft-n-max "$DFLASH_N_MAX"
      --spec-draft-n-min 0
      --spec-draft-p-min "$DFLASH_P_MIN"
      --spec-draft-ngl 99
      --cache-type-k q8_0
      --cache-type-v q8_0
      --no-kv-unified
      --fit off
    )
    ;;
  *)
    printf 'MODE must be mtp, no-mtp, dflash2-control, or dflash2\n' >&2
    exit 2
    ;;
esac

verify_args=(
  --target-manifest "$TARGET_MANIFEST"
  --model-dir "$MODEL_DIR"
  --model "$MODEL"
)
if [[ -n "$MMPROJ" ]]; then
  verify_args+=(--mmproj "$MMPROJ")
fi
if [[ "$MODE" == dflash2 ]]; then
  verify_args+=(
    --draft-manifest "$DFLASH_MANIFEST"
    --derived-manifest "$DFLASH_DERIVED_MANIFEST"
    --draft-model "$DRAFT_MODEL"
  )
fi
python3 "$REPO_ROOT/scripts/verify_launch_artifacts.py" "${verify_args[@]}"

exec "$BUILD_DIR/bin/llama-server" "${args[@]}"
