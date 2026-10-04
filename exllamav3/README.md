# GLM-5.3 Flash EXL3 serving recipe

TabbyAPI + exllamav3 1.5.2, EXL3 2.05 bpw, MTP n=1. The profile configures 262,144 tokens and vision on a single NVIDIA GB10. This is a repository recipe, not a claim that GLM is currently the live host endpoint.

## Measured evidence

The [quick-screen receipt](results/glm53-exl152-quick-ab-20260927.json) reports **29.00 tok/s** mean decode across two 256-output-token prompts, **356.34 tok/s** prefill on an 84,865-token prompt, and **238.99 s** time to first token on that prompt. Matched prior-engine deltas are +3.1%, +9.1%, and −8.3%, respectively. There was one measured request per decode prompt and one long-prompt request. The [candidate canaries](results/glm53-exl152-functional-canaries-20260927.json) passed two arithmetic tasks, a forced tool call and a real image request, with zero candidate service cgroup swap.

These are narrow checks, not a repeated 15-task quality panel, teacher-forced top-1 test, 30-minute loaded soak, or full 262K-prompt validation. Output hashes differed between benchmark arms; throughput alone does not establish output parity. Earlier deployment receipts remain under `results/` for audit, but their figures are not attributed to this release.

## Deployment card

The full-suite **29.97 tok/s** headline below belongs to an earlier deployment. Only the quick-screen figures above are 1.5.2 measurements.

![GLM-5.3 Flash EXL3 deployment history and 1.5.2 quick-screen results on one NVIDIA GB10](../assets/glm53-exllamav3-tabbyapi-result-card.png)

## Pins

| Component | Value |
|---|---|
| Checkpoint | `turboderp/GLM-5.3-Flash-exl3` @ `51058cd551c7e570d87bd32a4adee720edce2349`, 2.05 bpw |
| TabbyAPI | `f07131cd8fe34e449fe87cdd3a066b52b96d3cac` |
| exllamav3 | `1.5.2` at `12414d0af7b3beeabdda5990f6b554b996fa1416` |
| Tested image | `sha256:1f626b72bd7b20a470dae03ae18039049d50a0d496de20bf818b3b612c8699ee` |
| Config | `config/glm53-tabbyapi-vision-262k.yml` |

[`Dockerfile.exl152`](Dockerfile.exl152) and [`scripts/build-exl152-image.sh`](scripts/build-exl152-image.sh) layer the pinned source onto a retained local base image. The base is not publicly pullable. The launcher verifies the selected image's immutable ID and package version; a fresh build with a different ID must be revalidated before it is served.

## Serve

```bash
./scripts/build-exl152-image.sh
# Or verify the already tested image: CHECK_ONLY=1 ./scripts/build-exl152-image.sh
MODEL_DIR="$HOME/models/glm53-flash-exl3-2.05bpw" ./scripts/start-tabbyapi.sh primary
```

The launcher checks the image pin and package version, refuses another named GPU container, runs `pagecache-hint.py` against the twelve EXL3 shards, and requires three consecutive prelaunch readings with at least 100 GiB CUDA-free, 20 GiB `MemAvailable` and no host swap growth. It then runs the container with `--memory-swap` equal to `--memory` and binds `127.0.0.1:8002`. Stop other model services before switching. Set `REPORT_DIR` (default `$HOME/.hermes/reports`) to move gate receipts.

## Reasoning effort

`model.template_vars_default: {reasoning_effort: high}` sets the default to High. Request `reasoning.effort`, flat `reasoning_effort`, `template_vars`, then `template_vars_force` override it in that order. The upstream template treats `low` and `high` as explicit values and routes an unspecified value to `max`; Max previously exhausted long-answer caps without a final answer. A request can still opt into Max.

```bash
GLM_BASE=http://127.0.0.1:8002 python3 scripts/apply-template-probe.py
```

## Metrics

The launcher mounts [`metrics/sitecustomize.py`](metrics/sitecustomize.py) for a loopback `GET /metrics` endpoint with generated-token, generation-second and completed-request counters. Decode speed divides the change in generated tokens by the change in generation seconds. `METRICS=0` turns it off. If the hook cannot attach to a future TabbyAPI, the server starts unchanged and logs `tabby-metrics: ... not patched`. Copy `metrics/` beside `scripts/` when deploying from another directory.

```bash
curl -s localhost:8002/metrics
python3 -m unittest exllamav3/metrics/test_sitecustomize.py
```

The unit template is [`systemd/glm53-tabbyapi-primary.service`](systemd/glm53-tabbyapi-primary.service). A retained prior image is available for rollback through the launcher's `ENGINE` switch. Trigger rollback on a canary failure, host swap growth, or `MemAvailable` below 20 GiB; verify model identity and a real generation after a switch.
