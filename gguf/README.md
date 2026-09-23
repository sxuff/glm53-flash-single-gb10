# GLM-5.3 Flash UD-IQ2_XXS + DFlash2 on one GB10

This directory contains the pinned recipe behind the repository's **28.95 tok/s weighted server-decode** result.

## Measured profile

- Target: `UD-IQ2_XXS`
- Drafter: `DFlash2 Q4_K_M`
- DFlash settings: `n_max=3`, `n_min=0`, `p_min=0.30`
- Context allocation: 8,192 tokens
- Parallel slots: one
- Target KV: `q8_0`
- Flash Attention: enabled
- Full GPU offload

Measured results:

| Metric | Value |
|---|---:|
| Weighted server decode | **28.9479739955 tok/s** |
| Mean per-workload server decode | 30.2772655365 tok/s |
| Aggregate whole-request | **28.3719040665 tok/s** |
| Draft acceptance | **63.9149468418%** |

Per-workload server decode:

| Workload | tok/s |
|---|---:|
| Prose | 22.0494091339 |
| Structured | 39.9207548004 |
| Code | 27.0730602152 |
| Math | 32.0658379965 |

The public receipt is [`results/dflash2-q4km-n3-p030.json`](results/dflash2-q4km-n3-p030.json).

## Pinned stack

### Target

- Repository: `unsloth/GLM-5.3-Flash-GGUF`
- Revision: `2975ab414d30340466d8c51533c6e91f0cca64c1`
- Variant: `UD-IQ2_XXS`
- Files: four text shards plus one BF16 projector

Exact filenames, byte counts, and SHA-256 values are in [`manifests/target.json`](manifests/target.json).

### DFlash2 drafter

- GGUF revision: `caf6ef0cedd0dc4ac1183c4110266c2e4f58e17c`
- BF16 source file: 2,352,022,432 bytes
- Derived `Q4_K_M`: 697,017,248 bytes
- Derived `Q8_0`: 1,254,335,392 bytes

Lineage, metadata fields, hashes, and quantizer provenance are in:

- [`manifests/dflash2.json`](manifests/dflash2.json)
- [`manifests/dflash2-derived.json`](manifests/dflash2-derived.json)
- [`manifests/runtime-dflash2-quantizer.json`](manifests/runtime-dflash2-quantizer.json)

The drafter weights are CC BY-NC-ND 4.0. The downloader requires explicit acceptance through `ACCEPT_DFLASH2_NC_LICENSE=1`.

### Runtime

- Repository: `unslothai/llama.cpp`
- Commit: `d94f44e79aa219d8057e8de21f95360a187ebf41`
- Effective CUDA architecture: `121a`
- Patch: [`patches/dflash2-glm5next-architecture.patch`](patches/dflash2-glm5next-architecture.patch)

The complete runtime receipt is [`manifests/runtime-dflash2.json`](manifests/runtime-dflash2.json).

## Download

Download and verify the target:

```bash
python3 scripts/download.py \
  --destination "$HOME/models/GLM-5.3-Flash-UD-IQ2_XXS-2975ab41"
```

Download and verify the BF16 drafter after accepting its license:

```bash
ACCEPT_DFLASH2_NC_LICENSE=1 python3 scripts/download.py \
  --manifest manifests/dflash2.json \
  --destination "$HOME/models/GLM-5.3-Flash-DFlash2"
```

## Build

Build the pinned quantizer:

```bash
RUNTIME_MANIFEST=manifests/runtime-dflash2-quantizer.json \
SOURCE_DIR="$PWD/runtime/llama.cpp-dflash2-quantizer" \
BUILD_DIR="$PWD/runtime/llama.cpp-dflash2-quantizer/build-gb10" \
JOBS=2 ./scripts/build_runtime.sh
```

Create and verify the local draft quantizations:

```bash
BUILD_DIR="$PWD/runtime/llama.cpp-dflash2-quantizer/build-gb10" \
DRAFT_DIR="$HOME/models/GLM-5.3-Flash-DFlash2" \
./scripts/quantize_dflash2.sh
```

Build the exercised DFlash-capable server:

```bash
RUNTIME_MANIFEST=manifests/runtime-dflash2.json \
SOURCE_DIR="$PWD/runtime/llama.cpp-dflash2" \
BUILD_DIR="$PWD/runtime/llama.cpp-dflash2/build-gb10" \
JOBS=2 ./scripts/build_runtime.sh
```

## Serve

Start the measured profile:

```bash
MODEL_DIR="$HOME/models/GLM-5.3-Flash-UD-IQ2_XXS-2975ab41" \
DRAFT_DIR="$HOME/models/GLM-5.3-Flash-DFlash2" \
./scripts/serve.sh
```

The endpoint binds to `http://127.0.0.1:8001/v1`.

Optional overrides:

```bash
CTX=65536                    # context allocation
DFLASH_N_MAX=3               # draft depth
DFLASH_P_MIN=0.30            # confidence threshold
MMPROJ="$MODEL_DIR/mmproj-BF16-glm5next-621d456e.gguf"  # image input
```

Alternative modes remain available:

```bash
MODE=dflash2-control  # same DFlash-capable runtime and target KV, no drafter
MODE=mtp              # retained native-MTP runtime
MODE=no-mtp           # retained no-spec runtime
```

Before launch, `serve.sh` verifies the target and drafter against their manifests and validates the DFlash2 GGUF metadata.

## Reproduce the measured arm

Start a fresh measured-profile server, then run:

```bash
python3 scripts/benchmark.py \
  --arm dflash2-q4km-n3-p030 \
  --base-url http://127.0.0.1:8001 \
  --output local/dflash2-q4km-n3-p030.json
```

The benchmark uses four fixed workloads, one warm-up and one measured request per workload, 400 generated tokens, temperature 0, top-p 1, seed 42, and thinking disabled.

Regenerate the public comparison receipt:

```bash
python3 scripts/analyze.py \
  --previous ../results/mtp-k2.json \
  --new results/dflash2-q4km-n3-p030.json \
  --output results/deployment-comparison.json
```

Run the repository checks:

```bash
./scripts/ci.sh
```

## Scope

This is a one-repetition operational sweep on one GB10. The previous and new deployments use different artifacts, runtimes, and context allocations, so the headline is a deployment comparison rather than an isolated component A/B test. The measured DFlash2 result used an 8K allocation and must not be presented as a 128K measurement.
