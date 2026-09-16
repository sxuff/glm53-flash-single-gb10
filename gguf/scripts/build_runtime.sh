#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_MANIFEST="${RUNTIME_MANIFEST:-$REPO_ROOT/manifests/runtime.json}"
SOURCE_DIR="${SOURCE_DIR:-$REPO_ROOT/runtime/llama.cpp}"
BUILD_DIR="${BUILD_DIR:-$SOURCE_DIR/build-gb10}"
readarray -t runtime < <(python3 - "$RUNTIME_MANIFEST" "$REPO_ROOT" <<'PY'
import json, pathlib, sys
m=json.load(open(sys.argv[1]))
patch=m.get("patch")
print(m["repository"])
print(m["commit"])
print((pathlib.Path(sys.argv[2]) / patch) if patch else "")
print(m.get("patch_sha256", ""))
print(" ".join(m["build"]["targets"]))
PY
)
RUNTIME_REPO="${runtime[0]}"
RUNTIME_REV="${runtime[1]}"
PATCH="${runtime[2]}"
PATCH_SHA256="${runtime[3]}"
TARGETS="${runtime[4]}"

if [[ ! -d "$SOURCE_DIR/.git" ]]; then
  mkdir -p "$(dirname "$SOURCE_DIR")"
  git clone --filter=blob:none --no-checkout "$RUNTIME_REPO" "$SOURCE_DIR"
fi

git -C "$SOURCE_DIR" fetch --no-tags origin "$RUNTIME_REV"
test "$(git -C "$SOURCE_DIR" rev-parse FETCH_HEAD)" = "$RUNTIME_REV"
git -C "$SOURCE_DIR" checkout --detach "$RUNTIME_REV"
git -C "$SOURCE_DIR" reset --hard "$RUNTIME_REV"
git -C "$SOURCE_DIR" clean -ffd
if [[ -n "$PATCH" ]]; then
  test "$(sha256sum "$PATCH" | cut -d' ' -f1)" = "$PATCH_SHA256"
  git -C "$SOURCE_DIR" apply --check "$PATCH"
  git -C "$SOURCE_DIR" apply "$PATCH"
fi

git -C "$SOURCE_DIR" diff --check

export PATH="${CUDA_HOME:-/usr/local/cuda-13.0}/bin:$PATH"
export CUDACXX="${CUDACXX:-${CUDA_HOME:-/usr/local/cuda-13.0}/bin/nvcc}"

cmake -S "$SOURCE_DIR" -B "$BUILD_DIR" \
  -DCMAKE_BUILD_TYPE=Release \
  -DGGML_NATIVE=ON \
  -DGGML_CUDA=ON \
  -DGGML_CURL=ON \
  -DLLAMA_BUILD_UI=OFF \
  -DCMAKE_CUDA_COMPILER="$CUDACXX" \
  -DCMAKE_CUDA_ARCHITECTURES=121
cmake --build "$BUILD_DIR" --config Release --target $TARGETS -j"${JOBS:-2}"
for target in $TARGETS; do
  binary="$BUILD_DIR/bin/$target"
  test -x "$binary" || { printf 'missing built target: %s\n' "$binary" >&2; exit 1; }
  stat --printf='%n %s bytes\n' "$binary"
  sha256sum "$binary"
done
if [[ " $TARGETS " == *" llama-server "* ]]; then
  "$BUILD_DIR/bin/llama-server" --version
  "$BUILD_DIR/bin/llama-server" --list-devices
fi
