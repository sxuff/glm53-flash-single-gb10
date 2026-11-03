# Experimental: up to three MTP drafts a round

On four greedy prompts at 262,144 slots, three drafts with the `"auto"` policy averaged **33.79 tok/s against 31.69** at one draft (**+6.6%**): +18.6% on structured output, −5.9% on prose. Output matched the one-draft arm on all five prompts run.

**Experimental, not the default recipe.** This is one pass per arm, on prompts other than the ones behind the recipe's 30.73 tok/s. The thinking cap, long prompts and agent sessions have not been run with it. The default recipe still drafts one token a round, and with `mtp_drafts` at 1 this patch serves exactly as before.

## Measured

Receipts: [results](../../results/glm53-mosaic-mtp-depth-20261103.json) · [complete replies and token IDs](../../results/glm53-mosaic-mtp-depth-20261103-runs.json)

| Prompt | 1 draft | 3 drafts | Change | Acceptance, 1 → 3 drafts | Tokens a round, 1 → 3 drafts | Rounds at 1 / 2 / 3 drafts |
|---|---:|---:|---:|---:|---:|---:|
| Structured | 33.91 tok/s | 40.24 tok/s | +18.6% | 0.951 → 0.887 | 1.95 → 3.00 | 28 / 43 / 62 |
| Math | 32.78 tok/s | 35.67 tok/s | +8.8% | 0.900 → 0.778 | 1.90 → 2.66 | 24 / 82 / 44 |
| Code | 32.67 tok/s | 33.46 tok/s | +2.4% | 0.886 → 0.703 | 1.88 → 2.46 | 30 / 89 / 43 |
| Prose | 27.40 tok/s | 25.79 tok/s | −5.9% | 0.559 → 0.507 | 1.56 → 1.61 | 199 / 48 / 1 |
| **Mean** | **31.69 tok/s** | **33.79 tok/s** | **+6.6%** | | | |
| Math prompt, server defaults | 31.97 tok/s | 34.02 tok/s | +6.4% | 0.912 → 0.741 | 1.91 → 2.53 | 23 / 193 / 40 |

The first four rows are 400 tokens at temperature 0 with the thinking guard off. The last is the server's default sampling (temperature 0.3) with the guard on: 649 tokens, one seed. The server was restarted between arms with only `mtp_drafts` changed, and the loader was at 4 rows in both. An earlier three-draft pass came within 0.4% on all four greedy prompts. There were no repeats at one draft.

- **Exactness.** Token IDs matched the one-draft arm on the four greedy prompts. On the default-sampling prompt, the server's token hash and the text matched. No MTP-off serial arm was run on these prompts.
- **Cost of a draft.** Rounds took 57 to 60 ms at one draft and about 74 to 75 ms at 2.1 to 2.3 drafts, so a further draft costs about 14 to 15 ms against the 13 assumed below.
- **Why the gains stop short.** Chained drafts are accepted less often, and the confidence gate often stops a chain early: structured output used all three drafts in 62 of 133 rounds.
- **Prose still loses.** The greedy gate kept 199 of 248 rounds at one draft, but the extra drafts mostly missed: 1.61 tokens a round against 1.56, for 62 ms a round against 57.
- **Memory.** Peak GPU reservation barely moved, 95.77 against 95.75 GiB, but host memory free at ready fell from 9.92 to 8.75 GiB: about 1.2 GiB for the 3- and 4-row graphs. The lowest seen while serving these checks was 8.39 GiB, above the 5 GiB reserve. Host swap grew by at most 12 MB.
- **Load time.** 50 to 55 s at three drafts, 46 s at one.

## Why it might help

The server drafts one token with the MTP layer and verifies two rows a round: the pending token and the draft. Most of a verify pass's bytes are read once however many rows it has. From the tensor sizes of turboderp's SC 2.10 pack, which has the 2.05 base's layout:

- about 5.5 GB a pass for attention, the three dense layers, shared weights and the head;
- about 2.0 GB more for each extra row, mostly its own 8 routed experts in each of 42 layers;
- about 7.7 GB for one row, about 29 tok/s at the 225 GB/s the EXL3 kernels reach.

One draft a round costs 57.4 ms for 1.763 tokens (30.73 tok/s), against 44.0 ms for a serial token. Taking about 13 ms for each further draft (one more verify row and one more MTP step), with per-draft acceptance `p` from the [decode receipt](../../results/glm53-mosaic-decode-20261005.json):

| Prompt | Acceptance | 1 draft, measured | 1 draft, model | 2 drafts, model | 3 drafts, model |
|---|---:|---:|---:|---:|---:|
| Structured | 0.99 | 33.67 tok/s | 34.7 | 42.2 | 47.2 |
| Math | 0.84 | 31.82 tok/s | 32.1 | 36.2 | 37.6 |
| Code | 0.75 | 30.64 tok/s | 30.5 | 32.8 | 32.8 |
| Prose | 0.53 | 26.77 tok/s | 26.7 | 25.7 | 23.5 |

The model reproduces the measured one-draft rates. It treats every draft as accepted with the same `p`, so its gains are an upper bound: a chained draft is usually accepted less often than the first. Prose loses with more drafts, which is why the depth adapts. This table uses the recipe's fixed prompts, so it can't be compared line by line with the measured table above.

## What the patch changes

[`06-experimental-mtp-depth.patch`](../../patches/06-experimental-mtp-depth.patch), on top of patches 01 to 04. It applies with or without 05. SHA-256: `de9148226a27d2c4def7d7a03cdb51caea2a697e176a0adaadcb46e693e98007`.

```bash
git apply ../patches/06-experimental-mtp-depth.patch
```

Then set `"mtp_drafts": 3` in `serving/serving_defaults.json`.

- **`serving/serving_defaults.json`** takes `mtp_drafts` (1 to 7, default 1) and `mtp_depth` (`"auto"` or `"fixed"`, default `"auto"`).
- **`"auto"`** is the policy upstream TensorFold v0.6.5 uses for GLM (`engine.py`, `DepthPolicy(3, fixed=True, confidence=0.35) if greedy else DepthPolicy(3, low=0.6, high=0.85)`):
  - a greedy request chains up to `mtp_drafts` drafts while their joint confidence stays at 0.35 or more;
  - a sampled request, the server default at temperature 0.3, adapts to its running acceptance: one draft below 0.6, two below 0.85, otherwise three.
- **`"fixed"`** always asks for `mtp_drafts`, for sweeps.
- **Verification is unchanged in kind.** Target rows are still sampled one at a time under the thinking guard's simulation. The window stops at the first draft its row did not sample, at EOS, and before any row that would follow a closed reasoning block, a landing trigger or a stop. Every kept token is the target's own sample at its position, so greedy output should match serial output token for token, as it does with one draft.
- **Graph capture** covers verify windows of 1 to `mtp_drafts + 1` rows for the main model, the MTP layer and every sparse pool bucket. With 1 it captures the same (1, 2) as before.
- **Each reply's stats** gain `draft_depths`, rounds by number of drafts. The ready line reports `mtp_drafts` and `mtp_depth`.

## Loader change needed

The unpublished host loader allocates the decode and MTP buffers and the hidden-row scratch for two rows. Three drafts need four. Set `max_rows`, the scratch rows and the rows passed to `workspace_bytes` to at least `mtp_drafts + 1`. Otherwise the server refuses to start with `mtp_drafts 3 needs 4-row verify windows; this runtime allocates 2`. Prompt buffers are separate and unchanged.

## Checks

`tests/test_landing_mtp.py` runs the server's decode loops on CPU, with doubles for the forward pass and caches and the real `draft`, `absorb`, `Engine.sample` and `DepthPolicy` code. The patch adds 11 tests for two and three drafts:

- output identical to serial decoding on the thinking-guard path and the plain path;
- a missed draft keeps only the matched prefix and realigns the MTP cache; the double checks every MTP row's position;
- no reply goes past `max_tokens`;
- a closing `</think>`, a landing trigger and the real thinking guard inside a window end it as serial decoding would;
- the auto policy settles on 2 to 3 drafts when every draft lands and drops to 1 when none do; a greedy request stops chaining at low confidence;
- the policy learns from every drafted round, including those between the thinking guard's serial rounds.

All 33 tests in the file pass, and the 22 earlier ones also pass against the unpatched server. With the 5 other landing and GLM contract suites, 184 tests pass. 3 fail identically without the patch on the machine they were run on: one reads a file from the original host, and two look for a shard file that isn't there.

## Still to measure

1. Run the four-prompt decode harness at temperature 0, 3 repeats a prompt, with `mtp_drafts` 1, 2 and 3, both `"fixed"` and `"auto"`. Check that drafted and MTP-off serial tokens match on all four prompts, and record tok/s, `accepted / drafted` and `draft_depths` per prompt.
2. Run the same at the server's default sampling (temperature 0.3) with more than one prompt and seed, to exercise the adaptive policy.
3. Try a higher greedy confidence than 0.35 on prose.
4. Reach the thinking cap on the GPU. No reply here got near it, so the serial rounds and MTP resumes have only run on CPU.
5. Repeat the serving checks: the 75K retrieval, JSON replies, vision and the agent session.
