# GLM-5.3 Flash EXL3 on TensorFold, one NVIDIA GB10

The same `turboderp/GLM-5.3-Flash-exl3` 2.05 bpw checkpoint as the [ExLlamaV3 lane](../exllamav3/README.md), served by TensorFold 0.5.0 with a single-GPU packed-EXL3 port and an OpenAI-compatible serving layer. It is an experimental lane: the source is published as patches, and the launcher has not been packaged for a clean machine yet.

![GLM-5.3 Flash on TensorFold, one NVIDIA GB10](../assets/glm53-tensorfold-result-card.png)

## Measured

Decode against ExLlamaV3 1.5.2 on the same checkpoint: four fixed workloads, 400 forced output tokens, greedy and temperature 0.6 / top-p 0.95, one warm-up and three measured requests per cell.

| | ExLlamaV3 1.5.2 + TabbyAPI | TensorFold | Change |
|---|---:|---:|---:|
| Pooled decode | 28.56 tok/s | **32.03 tok/s** | **+12.1%** |
| Greedy only | 28.64 tok/s | 32.32 tok/s | +12.9% |
| Temperature 0.6 | 28.49 tok/s | 31.75 tok/s | +11.5% |

That comparison ran TensorFold at a 2,051-token window and ExLlamaV3 at its 262K + vision profile. Receipt: [`results/glm53-tabby-vs-tensorfold-fixed-work-20261001.json`](results/glm53-tabby-vs-tensorfold-fixed-work-20261001.json).

Decode and retrieval by prompt depth on the served 262,144-slot build, greedy, one conversation per depth. Each document holds five planted six-digit codes; the decode figure is three identical 512-token turns resumed from that prompt state.

| Prompt tokens | Decode | Planted codes found | First token, fresh prompt | Prompt fill |
|---:|---:|---:|---:|---:|
| 123 | 30.0 tok/s | 5 / 5 | 0.5 s | 234 tok/s |
| 7,965 | 30.2 tok/s | 5 / 5 | 34 s | 234 tok/s |
| 32,078 | 29.0 tok/s | 5 / 5 | 134 s | 240 tok/s |
| 86,068 | 28.5 tok/s | 5 / 5 | 351 s | 245 tok/s |
| 130,502 | 30.6 tok/s | 5 / 5 | 531 s | 246 tok/s |
| 255,716 | 26.2 tok/s | 5 / 5 | 1,047 s | 244 tok/s |

Receipt: [`results/glm53-tensorfold-depth-check-20261004.json`](results/glm53-tensorfold-depth-check-20261004.json).

Prompt state is reused between turns. On an 11,272-token conversation the next turn reached its first token in 2.1 s instead of 47.6 s, and 1,321 reply tokens were identical to the refilled run with the same seed. Five cases, below, across and above the 2,051-token dense limit, all matched. Receipts: [`cache-equivalence`](results/glm53-tensorfold-cache-equivalence-20261004.json), [`long replies`](results/glm53-tensorfold-cache-equivalence-long-replies-20261004.json).

## Where it loses

- **Prompt fill is slower.** About 245 tok/s here against 356 tok/s for ExLlamaV3 1.5.2 on an 84,865-token prompt. A fresh 86K prompt waits 5.8 minutes for its first token; ExLlamaV3 measured 4.0.
- **One request at a time, one conversation cached.** A second conversation evicts the first one's prompt state, so parallel agents refill their whole prompt on every turn.
- **Recall at 2.05 bpw is unreliable.** On a physics formula the model gave a different wrong version across runs. Its own sanity checks caught the errors and it kept re-deriving until the output cap. The serving layer bounds that; it does not make the answers right.

## Not measured

- Answer quality at depth beyond retrieving planted codes. No long-form, tool-call or image test past 85K tokens.
- ExLlamaV3 decode at depth under this contract. The older depth comparison used 32 forced tokens and one run per arm, so it is not quoted here.
- Variance. The depth table is one conversation per depth.

## Pinned inputs

- Checkpoint: `turboderp/GLM-5.3-Flash-exl3`, revision `51058cd551c7e570d87bd32a4adee720edce2349`, 2.05 bpw
- TensorFold: `https://github.com/ashhart/TensorFold`, tag `v0.5.0`, commit `9cd52ab4daba68ddd09be89be8f23ad43175e821` (MIT)
- Container image: `sha256:1f626b72bd7b20a470dae03ae18039049d50a0d496de20bf818b3b612c8699ee`, the tested image of the ExLlamaV3 lane
- Environment: `EXL3_INT8_GEMV=2`

## Source

Two patches, applied in order to TensorFold 0.5.0. Together they reproduce the served source tree exactly; that was checked file by file.

```bash
git clone https://github.com/ashhart/TensorFold && cd TensorFold
git checkout 9cd52ab4daba68ddd09be89be8f23ad43175e821
git apply ../tensorfold/patches/tensorfold-0.5.0-glm-exl3-single-gpu-port.patch
git apply ../tensorfold/patches/serving-v58-over-port.patch
```

| Patch | SHA-256 | What it adds |
|---|---|---|
| [`tensorfold-0.5.0-glm-exl3-single-gpu-port.patch`](patches/tensorfold-0.5.0-glm-exl3-single-gpu-port.patch) | `a7c809f8f41c7bb6789b12b5242194819353d2e382f7fe1acaf268c2369739b3` | Loads the fully packed EXL3 checkpoint on one GPU: 19 files in the GLM family, with CPU tests |
| [`serving-v58-over-port.patch`](patches/serving-v58-over-port.patch) | `7ab55a79609e3536526c01946124553742dded60c894a4b02bef9a77f8900291` | The `serving/` layer, the thinking guard, prompt-state reuse, stream keep-alive and their tests |

`serving/server.py` and `serving/supervisor.py` are the files that ran. They import a memory guard, a loader and a service controller from the local experiment tree that produced these results, and they hard-code that host's model path. Those pieces are not in this repository, so the patches document the serving code; they are not a one-command launcher.

## Serving profile

- 262,144 cache slots, 262,016-token context, prompts up to 257,920 tokens, replies up to 16,384
- Sparse attention past 2,051 tokens, MTP n=1
- Defaults: temperature 0.3, top-p 0.95, min-p 0.05, reasoning effort high, a fresh seed per request unless one is sent
- Thinking is capped at 3,000 tokens. At the cap the server injects a short closing sentence and the close tag, then the answer is sampled normally. A window of near-identical filler ("Hmm, hmm.") lands the same way and blocks those tokens briefly
- Prompt state reuse is on by default; `"prefix_cache": false` on a request refills the prompt
- Streamed requests get an empty chunk every 15 seconds while queued or filling, and a client that has left is cancelled between 128-token prefill chunks
- Request fields: `thinking_budget`, `thinking_loop` (per-field overrides), `prefix_cache`, `seed`, `response_format: {"type": "json_object"}`

Two behaviours to know about:

- A request whose `max_tokens` is below 1,053 is refused while the thinking guard is on, because the guard reserves 1,024 tokens for the answer. Send `"thinking_loop": {"enabled": false}` with small caps.
- A turn that switches thinking off no longer extends the previous prompt as rendered, so it refills the whole prompt.

## Checks

`serving/cpu_json.py` and `serving/cpu_prepare.py` run the real request handling, prefill, snapshot and restore code over numerical doubles, with the checkpoint's tokenizer and no GPU. With the landing suites under `tests/` they pass on the served tree: 31, 12 and 146 tests. `serving/cache_equivalence.py` and `serving/depth_check.py` are the two live checks behind the tables above.

The card is built by [`card/build_card.py`](card/build_card.py) from the depth-check receipt.
