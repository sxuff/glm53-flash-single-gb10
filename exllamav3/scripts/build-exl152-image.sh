#!/usr/bin/env bash
# Build the tested ARM64 exllamav3 1.5.2 layer without changing the 1.4.9 rollback image.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source_commit='12414d0af7b3beeabdda5990f6b554b996fa1416'
base_image='local/glm53-tabbyapi:f07131c-kda'
base_id='sha256:f3843891b30c4329bb502b959a18a5182cc8fc18a8f7c74f811c526f55696029'
result_image='local/glm53-tabbyapi:exl152-20260927'
result_id='sha256:1f626b72bd7b20a470dae03ae18039049d50a0d496de20bf818b3b612c8699ee'
[[ "$(docker image inspect "$base_image" --format '{{.Id}}')" == "$base_id" ]] || { printf 'base image pin mismatch\n' >&2; exit 3; }

# CHECK_ONLY=1 exercises the installed image pins without recompiling CUDA.
if [[ "${CHECK_ONLY:-0}" == 1 ]]; then
  [[ "$(docker image inspect "$result_image" --format '{{.Id}}')" == "$result_id" ]] || { printf 'candidate image pin mismatch\n' >&2; exit 4; }
  docker run --rm --entrypoint /opt/sglang/bin/python3 "$result_image" -c 'import importlib.metadata as m, exllamav3_ext; assert m.version("exllamav3") == "1.5.2"; print(m.version("exllamav3"), exllamav3_ext.__file__)'
  exit
fi

build_root="${BUILD_ROOT:-$HOME/.cache/glm53-exl152-image}"
mkdir -p "$build_root"
if [[ ! -d "$build_root/exllamav3-src/.git" ]]; then
  [[ ! -e "$build_root/exllamav3-src" ]] || { printf 'occupied source path; refusing to overwrite\n' >&2; exit 5; }
  git clone --depth 1 --branch v1.5.2 https://github.com/turboderp-org/exllamav3.git "$build_root/exllamav3-src"
fi
[[ "$(git -C "$build_root/exllamav3-src" rev-parse HEAD)" == "$source_commit" ]] || { printf 'source commit mismatch\n' >&2; exit 6; }
[[ -z "$(git -C "$build_root/exllamav3-src" status --porcelain)" ]] || { printf 'source tree is dirty\n' >&2; exit 7; }
cp "$here/../Dockerfile.exl152" "$build_root/Dockerfile"
docker build --progress=plain -f "$build_root/Dockerfile" --build-arg "BASE_IMAGE=$base_image" -t "$result_image" "$build_root"
actual="$(docker image inspect "$result_image" --format '{{.Id}}')"
printf 'image ID: %s\n' "$actual"
[[ "$actual" == "$result_id" ]] || { printf 'rebuild differs from tested image; do not serve until pin and canaries are revalidated\n' >&2; exit 8; }
