# exllamav3 + MTP-1 serving recipe

The default GLM recipe: GLM-5.3 Flash EXL3 2.05 bpw served by TabbyAPI on exllamav3 1.5.2 with MTP n=1, at 262,144 tokens of configured context with vision enabled. The older 1.4.9 image remains an explicit rollback. This is a recipe, not a claim that the host currently serves GLM.

## Why this lane

The same checkpoint under SGLang with the EXL3 adapter measured 11.63 tok/s mean decode on a four-workload protocol. **The 1.4.9 lane** measured 29.97 tok/s on that protocol. SGLang held 9.04 GB of fused linears as a BF16 fallback and ran FP8 KV with no speculation, while exllamav3 uses native EXL3 kernels, an FP16 cache, and a one-token MTP drafter. This is a deployment-to-deployment comparison, not an isolated kernel result; the 29.97 figure was **not rerun on 1.5.2**.

The [1.5.2 quick screen](results/glm53-exl152-quick-ab-20260927.json) compares the same 262K + vision configuration and checkpoint against 1.4.9 on two 256-output-token prompts and one 84,865-token long prompt: mean decode **28.13 → 29.00 tok/s (+3.1%)**, prefill **326.73 → 356.34 tok/s (+9.1%)**, and long-prompt TTFT **260.56 → 238.99 s (−8.3%)**. One measured request per decode case and one per long-prompt arm make this a screen, not a full performance promotion. The [functional canaries](results/glm53-exl152-functional-canaries-20260927.json) passed arithmetic 2/2, forced tool 1/1 and vision 1/1, with zero candidate service swap.

## Pins

| Component | Value |
|---|---|
| Checkpoint | `turboderp/GLM-5.3-Flash-exl3` @ `51058cd551c7e570d87bd32a4adee720edce2349`, 2.05 bpw |
| TabbyAPI | `f07131cd8fe34e449fe87cdd3a066b52b96d3cac` |
| exllamav3 | `1.5.2` at `12414d0af7b3beeabdda5990f6b554b996fa1416`; rollback `1.4.9` |
| Candidate image | `sha256:1f626b72bd7b20a470dae03ae18039049d50a0d496de20bf818b3b612c8699ee` |
| Rollback/base image | `sha256:f3843891b30c4329bb502b959a18a5182cc8fc18a8f7c74f811c526f55696029` |
| Config | `config/glm53-tabbyapi-vision-262k.yml` |

The 1.4.9 base image bundles a local ARM64 compatibility patch moving a KDA Triton `next_power_of_2` calculation to the host. The separate 1.5.2 layer is compiled from upstream source at the exact tag commit over that pinned base. Upstream 1.5.2 no longer requires the older KDA patch in its installed source; the image ID pins the tested combination. See [`Dockerfile.exl152`](Dockerfile.exl152) and [`scripts/build-exl152-image.sh`](scripts/build-exl152-image.sh). The base image is retained locally; there is no publicly pullable image in this repository.

## Serve

```bash
./scripts/build-exl152-image.sh
MODEL_DIR="$HOME/models/glm53-flash-exl3-2.05bpw" ./scripts/start-tabbyapi.sh primary
```

The launcher defaults to 1.5.2. For a rollback, set `ENGINE=1.4.9` on the same command or in the unit environment, then verify model identity and a real generation. A fresh build with an image ID different from the receipt is not the tested binary and must be revalidated and repinned.

What the launcher does, in order:

1. Confirms the image ID matches the selected pin, and that the engine inside it reports the selected version.
2. Refuses to start if another GPU runtime is holding the device.
3. Runs `pagecache-hint.py`, which issues `POSIX_FADV_DONTNEED` against exactly the twelve EXL3 shards and checks the resulting CUDA headroom.
4. Runs `prelaunch-gate.py`, which requires three consecutive readings with at least 100 GiB CUDA-free, at least 20 GiB `MemAvailable`, and no host swap growth.
5. Starts the container with `--memory-swap` equal to `--memory`, which makes container swap impossible rather than merely unlikely.

The endpoint is published on `127.0.0.1:8002`. Set `REPORT_DIR` (default `$HOME/.hermes/reports`) to move the JSON receipts the gate scripts write.

## Preflight, to reproduce the numbers

The 262K + vision profile needs headroom before it loads. On the earlier 1.4.9 launch, the hint moved CUDA-free from 64.43 GiB to 112.05 GiB. Re-running it immediately afterwards is a no-op, which is the expected behaviour once the pages are gone. This recorded example is not a 1.5.2 launch receipt.

Both scripts print a single line and exit non-zero on failure, so they are safe to use as launch guards:

```
targeted_cache_hint pass cuda_free_GiB_before 64.43 after 112.05 host_free_GiB_before 64.43 after 112.05 swap_delta -20480
GATE 0 cuda_free_GiB 113.07 available_GiB 114.46 swap_delta 0
RESULT pass None
```

## Reasoning effort

`model.template_vars_default: {reasoning_effort: high}` sets the chat template default to High. It is the lowest-precedence source in TabbyAPI's merge order:

```
template_vars_default  <  request reasoning.effort  <  request reasoning_effort  <  request template_vars  <  template_vars_force
```

The upstream template only treats `low` and `high` as explicit values and sends everything else, including an unspecified request, to `max`. Max drove unbounded planning on long prompts: the same prompt returned no answer in three of three runs at a 4,096-token cap and again at 12,288 tokens. Defaulting to High fixed it without removing Max as an option.

Check the render without generating a token:

```bash
GLM_BASE=http://127.0.0.1:8002 python3 scripts/apply-template-probe.py
```

## Historical 1.4.9 promotion verification

| Check | Result |
|---|---|
| Looping prompt, 8K cap, temp 0.6 / top-p 0.95, 3 seeds | 3/3 delivered a final answer with `finish_reason=stop` |
| 15 deterministic known-answer tasks, thinking on at High | 15/15, all `stop` |
| Same 15 tasks, thinking disabled | 15/15 |
| External canary through the authenticated bridge and the Tailscale path | 7/7, including a forced tool call and a vision request |
| 30-minute loaded soak, per-service cgroup swap | `memory.swap.current` 0 throughout, minimum `MemAvailable` 24.32 GiB |

Scripts for those checks are not vendored here; the receipts in `results/` are.

The 1.5.2 canary receipt is narrower: it verifies two arithmetic outputs, a forced tool call, and a real image request on the configured 262K + vision profile. The historical 15-task panel, repeated looping-prompt trials, teacher-forced top-1 test, full-depth prompt and 30-minute soak have **not** been rerun on 1.5.2. Its quick screen includes a successful 84,865-token prompt, not a full 262,144-token prompt. Outputs differ by hash across quick-screen arms, so do not infer deterministic parity from throughput.

## Metrics

Stock TabbyAPI has no token counters. The launcher mounts [`metrics/sitecustomize.py`](metrics/sitecustomize.py), which adds a loopback `GET /metrics` without touching the pinned image:

```text
tabbyapi_generated_tokens_total      tokens generated by finished requests
tabbyapi_generation_seconds_total    seconds spent generating them
tabbyapi_requests_total              finished generation requests
```

Decode speed is the change in the first divided by the change in the second. The counts come from the `gen_tokens` and `gen_time` TabbyAPI already passes to its own request log; nothing else about a request is kept. `METRICS=0` turns it off. If the hook can't attach to a future TabbyAPI, the server starts unchanged and logs `tabby-metrics: ... not patched`.

If you run the lane from a copy (the systemd unit uses `~/exllamav3`), copy `metrics/` next to `scripts/`. Check it after a restart and one request:

```bash
curl -s localhost:8002/metrics
```

Test: `python3 -m unittest exllamav3/metrics/test_sitecustomize.py` (the route check needs `fastapi` and `httpx`).

## Rollback

Both exllamav3 images publish the same loopback port. The 1.4.9 image is retained as a cold fallback:

```bash
systemctl --user stop glm53-tabbyapi-primary.service
# Set ENGINE=1.4.9 in the unit environment, then start the same GLM unit.
systemctl --user start glm53-tabbyapi-primary.service
```

Trigger a rollback on any canary failure, any host swap growth, or `MemAvailable` below 20 GiB.
