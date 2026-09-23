# GLM-5.3 Flash EXL3 on one NVIDIA GB10

A pinned, reproducible recipe for serving GLM-5.3 Flash EXL3 2.05 bpw with exllamav3 1.4.9 and MTP n=1 behind TabbyAPI on one NVIDIA GB10, at 262,144 tokens of context with vision enabled.

![GLM-5.3 Flash EXL3 deployment comparison on one NVIDIA GB10](assets/glm53-exllamav3-tabbyapi-result-card.png)

## Result

Deployment to deployment on the same checkpoint (`51058cd`). The previous lane was SGLang with an EXL3 adapter; the new lane is TabbyAPI on exllamav3.

| Metric | Previous deployment | New deployment | Change |
|---|---:|---:|---:|
| Decode | 11.63 tok/s | **29.97 tok/s** | **2.58x, +157.7%** |
| Decode, temperature 0.6 / top-p 0.95 | not measured | 29.51 tok/s | — |
| Min free memory under load | ≈ 8 GB | **26.1 GB** | ≈ 3.3x |
| MTP draft acceptance (n=1, greedy) | off | 78.0% | — |
| Long-context prefill | ≈ 425 tok/s | 395 tok/s | ≈ −7% |
| Known-answer tasks | — | 15 / 15 | — |
| Top-1 agreement vs previous | — | 96.97% | — |
| Service swap during a 30-minute loaded soak | — | 0 B | — |

What the new lane changes:

- TabbyAPI `f07131c` with exllamav3 1.4.9 (ARM64, local patch)
- native EXL3 kernels and an FP16 cache
- MTP n=1, with reasoning effort defaulting to High
- 262,144-token context with vision
- a page-cache prelaunch gate

The previous lane ran SGLang with the EXL3 adapter (`PR #2`, `4e3ffc7`), 9.04 GB of fused linears held as a BF16 fallback, FP8 KV, DSA sparse MLA, and no speculation.

## Measurement contract

- Hardware: one NVIDIA GB10
- Decode: four fixed prompts, 400 forced output tokens, temperature 0, one slot. Previous: one warm-up plus one measured run per prompt. New: one warm-up plus three measured runs, taken with a 16K cache.
- Memory: a 30-minute loaded soak on the promoted 262K + vision profile, one live generation per minute. Minimum `MemAvailable` 24.32 GiB.
- Prefill: previous is the retired lane's reported figure at 262,016 tokens; new is 241,998 tokens in 612.7 s.
- Top-1: teacher-forced, 4,096 scored positions across four workloads, mean KL 0.0072.
- Determinism: outputs are not bit-reproducible run to run. Repeated greedy runs of one frozen prompt show identical argmax with directed KL around 1e-4 and maximum absolute logit differences of 1.6 to 1.9.

Decode, memory, and top-1 are matched-protocol measurements. The comparison is deployment to deployment, not an isolated component A/B: the previous lane and the new lane use different runtimes, different cache precisions, and different context allocations.

## Deployment

### Pins

- Checkpoint: `turboderp/GLM-5.3-Flash-exl3`, revision `51058cd551c7e570d87bd32a4adee720edce2349`, 2.05 bpw, 12 shards
- TabbyAPI: `f07131cd8fe34e449fe87cdd3a066b52b96d3cac`
- exllamav3: `1.4.9`
- Image: `sha256:f3843891b30c4329bb502b959a18a5182cc8fc18a8f7c74f811c526f55696029`
- Profile: 262,144-token context, FP16 cache, 256-token chunks, one slot, vision on, MTP n=1

Model weights and runtime binaries are not stored in this repository.

### Serve

```bash
cd exllamav3

MODEL_DIR="$HOME/models/glm53-flash-exl3-2.05bpw" ./scripts/start-tabbyapi.sh primary
```

The launcher pins the image ID and the engine version, refuses to start while another GPU runtime is active, runs the page-cache hint, and enforces the memory gate before `docker run`. It publishes the endpoint on `127.0.0.1:8002`.

For a user unit instead of a foreground run:

```bash
cp systemd/glm53-tabbyapi-primary.service "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable --now glm53-tabbyapi-primary.service
```

### Verify

```bash
# endpoint is up and reports the model id
curl -s localhost:8002/v1/models

# a deterministic known-answer request; thinking disabled for a direct answer
curl -s localhost:8002/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"glm53","messages":[{"role":"user","content":"What is 9 times 6? Reply with only the integer."}],"temperature":0,"max_tokens":64,"reasoning_budget_tokens":0}'
# -> "54"

# render the chat template without generating anything, to confirm the reasoning default
python3 scripts/apply-template-probe.py
# -> default request renders "Reasoning Effort: High"; reasoning_effort max/low override it
```

Reasoning effort defaults to **High** through `model.template_vars_default`. Per-request overrides use the flat `reasoning_effort` field (`low`, `high`, `max`), `template_vars` / `chat_template_kwargs`, or an OpenRouter-style `reasoning.effort` object. `reasoning_budget_tokens: 0` disables thinking for a request.

Full recipe detail, including the prelaunch gate parameters: [`exllamav3/README.md`](exllamav3/README.md).

## Receipts

Under [`exllamav3/results/`](exllamav3/results/):

| Receipt | Backs |
|---|---|
| `glm53-exllama-matched-mtp1-16k-20260923.json` | New-lane decode at 16K, MTP n=1, four workloads, warm-up plus three measured runs |
| `glm53-exllama-matched-nospec-16k-20260923.json` | Same-protocol no-speculation arm for the MTP delta |
| `glm53-exllama-matched-mtp2-16k-20260923.json` | MTP n=2 retest; it measured slower, which is why n=1 ships |
| `glm53-quality-cross-runtime-top1-kl-20260923.json` | Top-1 agreement and KL over 4,096 teacher-forced positions |
| `glm53-promotion-cgroup-swap-soak-20260923.json` | 30-minute loaded soak with per-service cgroup swap counters |
| `glm53-phase0-2026-09-22.md` | Previous-lane decode baseline and its four-workload protocol |

The result card renders the MTP-1 receipt as `glm53-exllama-matched-mtp-1-16k-20260923.json`; the committed filename omits that hyphen.

## Superseded lanes

Earlier deployments are kept in-tree for reproducibility and are not current:

- `gguf/`: a llama.cpp UD-IQ2_XXS lane with a DFlash2 Q4_K_M drafter
- `scripts/`, `systemd/`, `manifests/`, `results/`: an earlier EXL3 K2 lane

Neither is running. The endpoint served by this repository is the TabbyAPI + exllamav3 profile described above.

## License

Repository scripts and documentation are MIT licensed. Model weights are not redistributed and retain their upstream terms. The DFlash2 drafter weights referenced by the archived lane are CC BY-NC-ND 4.0 and require explicit acceptance before download. See [`NOTICE.md`](NOTICE.md).
