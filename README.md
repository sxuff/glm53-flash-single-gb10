# GLM-5.3 Flash EXL3 on one NVIDIA GB10

A pinned TabbyAPI recipe for GLM-5.3 Flash EXL3 2.05 bpw with exllamav3 1.5.2 and MTP n=1 on one NVIDIA GB10. The serving profile configures 262,144 tokens and vision. These settings are not a claim that a full-depth prompt was benchmarked.

## Measured quick screen

Same checkpoint, TabbyAPI commit, FP16 cache, MTP n=1 and 262K + vision configuration on one GB10. Deltas use a matched prior engine run, **not** the older four-prompt deployment benchmark.

| Metric | exllamav3 1.5.2 | Change vs matched run |
|---|---:|---:|
| Mean decode, prose and code | **29.00 tok/s** | **+3.1%** |
| Prefill, 84,865-token prompt | **356.34 tok/s** | **+9.1%** |
| Time to first token, same prompt | **238.99 s** | **−8.3%** |
| Functional canaries | **4/4** | Two arithmetic, one forced tool call, one image |
| Candidate service cgroup swap | **0 B** | During observed loads and requests |

Decode used 256 output tokens at temperature 0, one warm-up and **one measured request per prompt**. The long prompt was measured once, with 24 output tokens. This is a quick screen, not a variance estimate, full-depth 262K test, or full quality sweep. Output hashes differed across arms. [Measurements and protocol](exllamav3/results/glm53-exl152-quick-ab-20260927.json) · [functional checks](exllamav3/results/glm53-exl152-functional-canaries-20260927.json) · [card hash](exllamav3/results/glm53-exl152-card-asset-20260927.json).

## Deployment card

The full-suite **29.97 tok/s** headline below belongs to an earlier deployment. Only the separate quick-screen section reports 1.5.2 measurements.

![GLM-5.3 Flash EXL3 deployment history and 1.5.2 quick-screen results on one NVIDIA GB10](assets/glm53-exllamav3-tabbyapi-result-card.png)

## Pinned recipe

- Checkpoint: `turboderp/GLM-5.3-Flash-exl3`, revision `51058cd551c7e570d87bd32a4adee720edce2349`, 2.05 bpw, 12 shards
- TabbyAPI: `f07131cd8fe34e449fe87cdd3a066b52b96d3cac`
- exllamav3: `1.5.2`, source commit `12414d0af7b3beeabdda5990f6b554b996fa1416`
- Tested image: `sha256:1f626b72bd7b20a470dae03ae18039049d50a0d496de20bf818b3b612c8699ee`
- Profile: 262,144-token configured context, FP16 cache, 256-token chunks, one slot, vision on, MTP n=1

Model weights and runtime binaries are not stored here. The build requires a retained local base image; it is not a public registry pull. [`build-exl152-image.sh`](exllamav3/scripts/build-exl152-image.sh) verifies the base and source pins. If a fresh build has a different image ID, revalidate it before serving rather than silently substituting it.

### Serve

```bash
cd exllamav3
./scripts/build-exl152-image.sh
# Or verify the already tested local image without recompiling:
# CHECK_ONLY=1 ./scripts/build-exl152-image.sh
MODEL_DIR="$HOME/models/glm53-flash-exl3-2.05bpw" ./scripts/start-tabbyapi.sh primary
```

The launcher checks the image ID and engine version, then runs the page-cache hint and memory gate before binding `127.0.0.1:8002`. Stop other model services before switching. This repository does not claim GLM is the currently live host endpoint.

For a user service, see [`exllamav3/systemd/glm53-tabbyapi-primary.service`](exllamav3/systemd/glm53-tabbyapi-primary.service). [Configuration and operations detail](exllamav3/README.md).

### Verify a running GLM endpoint

```bash
curl -s localhost:8002/v1/models
curl -s localhost:8002/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"glm53","messages":[{"role":"user","content":"What is 9 times 6? Reply with only the integer."}],"temperature":0,"max_tokens":64,"reasoning_budget_tokens":0}'
# -> "54"
```

Reasoning effort defaults to **High** through `model.template_vars_default`. Per-request overrides use the flat `reasoning_effort` field (`low`, `high`, `max`), `template_vars` / `chat_template_kwargs`, or an OpenRouter-style `reasoning.effort` object. `reasoning_budget_tokens: 0` disables thinking for a request.

## Archived experiments

Older deployment receipts remain under [`exllamav3/results/`](exllamav3/results/) for audit and rollback. The `gguf/` and root-level `scripts/`, `systemd/`, `manifests/` and `results/` trees are superseded lanes, not the default recipe.

## License

Repository scripts and documentation are MIT licensed. Model weights retain their upstream terms. The archived DFlash2 drafter weights are CC BY-NC-ND 4.0 and require explicit acceptance before download. See [`NOTICE.md`](NOTICE.md).
