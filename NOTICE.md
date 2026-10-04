# Dependency boundary

This repository contains two independent deployment and validation lanes for GLM-5.3 Flash on one NVIDIA GB10.

## GGUF lane

The GGUF lane pins and builds:

- Runtime: https://github.com/unslothai/llama.cpp
- Commit: `629b50552801912b3e2078f9799e4d77213197d7`
- Model repository: `unsloth/GLM-5.3-Flash-GGUF`
- Model revision: `2975ab414d30340466d8c51533c6e91f0cca64c1`

The repository carries a two-line compatibility patch that maps the rewritten artifact's canonical text architecture and projector type to the names expected by the pinned runtime. The patch is stored in `gguf/patches/gguf-canonical-naming.patch`.

### Optional DFlash2 drafter

The measured external-drafter profile additionally pins:

- Drafter source: `incoai/GLM-5.3-Flash-DFlash2` at `bf582e4eacc1810f76656d1811693ff6c6737d2a`
- GGUF conversion: `vcruz305/GLM-5.3-Flash-DFlash2-GGUF` at `caf6ef0cedd0dc4ac1183c4110266c2e4f58e17c`
- Exercised local quantizer: `vcruz305/llama.cpp` at `4a06ec6187b72313754f5f0c7a394ca5522ad8a2`
- DFlash-capable serving runtime: `unslothai/llama.cpp` at `d94f44e79aa219d8057e8de21f95360a187ebf41`

The DFlash2 drafter weights are licensed **CC BY-NC-ND 4.0**. They are not included in this repository. The downloader requires the operator to set `ACCEPT_DFLASH2_NC_LICENSE=1` explicitly before obtaining them. The target GLM-5.3 Flash artifact remains under its existing MIT terms.

## EXL3 lane

The EXL3 lane pins and invokes the MIT-licensed upstream recipe:

- Repository: https://github.com/vcruz305/GLM-5.3-Flash-EXL3-K2-DGX-Spark-recipe
- Commit: `0b8dd0d6c7b186076f2e61d1b99a6289f8006c3c`
- Model repository: `vcruz305/GLM-5.3-Flash-EXL3-K2`
- Model revision: `ca0bcdae265f7df1e346c57a2b53b8b8f632ee0b`

## Licenses

Model weights are not redistributed. They remain subject to their model repositories' terms and the source GLM-5.3 Flash license.

llama.cpp, vLLM, ExLlamaV3, FlashInfer, PyTorch, Hugging Face tooling, the pinned EXL3 recipe, and their transitive dependencies retain their own licenses. This repository's MIT license applies only to the scripts, tests, patches, and notes authored here.

This project is independent and is not endorsed by the referenced projects or vendors.

## TensorFold lane

The TensorFold lane carries two patches against the MIT-licensed upstream runtime:

- Runtime: https://github.com/ashhart/TensorFold
- Tag `v0.5.0`, commit `9cd52ab4daba68ddd09be89be8f23ad43175e821`

`tensorfold/patches/` holds modifications to that source and new files written for this recipe. TensorFold's own code is not copied here beyond the context lines of the patches. The checkpoint is the one the EXL3 lane pins.
