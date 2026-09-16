#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="${MANIFEST:-$REPO_ROOT/manifests/dflash2.json}"
DERIVED_MANIFEST="${DERIVED_MANIFEST:-$REPO_ROOT/manifests/dflash2-derived.json}"
LLAMA_ROOT="${LLAMA_ROOT:-$REPO_ROOT/runtime/llama.cpp}"
BUILD_DIR="${BUILD_DIR:-$LLAMA_ROOT/build-gb10}"
DRAFT_DIR="${DRAFT_DIR:?set DRAFT_DIR to the verified DFlash2 directory}"
BF16="$DRAFT_DIR/GLM-5.3-Flash-DFlash2-BF16.gguf"
QUANTIZE="$BUILD_DIR/bin/llama-quantize"

expected=$(python3 - "$MANIFEST" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))["files"][0]["sha256"])
PY
)
actual=$(sha256sum "$BF16" | cut -d' ' -f1)
test "$actual" = "$expected" || { echo "BF16 SHA-256 mismatch" >&2; exit 1; }
test -x "$QUANTIZE" || { echo "missing llama-quantize: $QUANTIZE" >&2; exit 1; }

for type in Q8_0 Q4_K_M; do
  readarray -t expected_row < <(python3 - "$DERIVED_MANIFEST" "$type" <<'PY'
import json, sys
row = next(item for item in json.load(open(sys.argv[1]))["files"] if item["quantization"] == sys.argv[2])
print(row["name"])
print(row["bytes"])
print(row["sha256"])
PY
  )
  output="$DRAFT_DIR/${expected_row[0]}"
  if [[ -e "$output" ]]; then
    bytes=$(stat -c %s "$output")
    hash=$(sha256sum "$output" | cut -d' ' -f1)
    if [[ "$bytes" == "${expected_row[1]}" && "$hash" == "${expected_row[2]}" ]]; then
      printf 'verified existing %s %s bytes %s\n' "$output" "$bytes" "$hash"
      continue
    fi
    printf 'refusing to overwrite invalid derived artifact: %s\n' "$output" >&2
    exit 1
  fi
  "$QUANTIZE" "$BF16" "$output" "$type"
  bytes=$(stat -c %s "$output")
  hash=$(sha256sum "$output" | cut -d' ' -f1)
  test "$bytes" = "${expected_row[1]}" || { echo "$type byte count mismatch" >&2; exit 1; }
  test "$hash" = "${expected_row[2]}" || { echo "$type SHA-256 mismatch" >&2; exit 1; }
  printf 'verified %s %s bytes %s\n' "$output" "$bytes" "$hash"
done
