#!/usr/bin/env python3
import json
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_REVISION = "ca0bcdae265f7df1e346c57a2b53b8b8f632ee0b"
UPSTREAM_COMMIT = "0b8dd0d6c7b186076f2e61d1b99a6289f8006c3c"
CHECKPOINT_REVISION = "51058cd551c7e570d87bd32a4adee720edce2349"
TABBYAPI_COMMIT = "f07131cd8fe34e449fe87cdd3a066b52b96d3cac"
ENGINE_VERSION = "1.5.2"
ENGINE_COMMIT = "12414d0af7b3beeabdda5990f6b554b996fa1416"
IMAGE_SHA = "sha256:1f626b72bd7b20a470dae03ae18039049d50a0d496de20bf818b3b612c8699ee"
ROLLBACK_IMAGE_SHA = "sha256:f3843891b30c4329bb502b959a18a5182cc8fc18a8f7c74f811c526f55696029"
TARGET_REVISION = "2975ab414d30340466d8c51533c6e91f0cca64c1"
DFLASH_RUNTIME = "d94f44e79aa219d8057e8de21f95360a187ebf41"

manifest = json.loads((ROOT / "manifests/glm53-exl3-k2.json").read_text())
assert manifest["revision"] == MODEL_REVISION
assert manifest["weight_shards"] == len(manifest["files"]) == 120
assert manifest["weight_bytes"] == sum(row["bytes"] for row in manifest["files"]) == 97_728_721_536
assert all(len(row["sha256"]) == 64 for row in manifest["files"])

artifact = json.loads((ROOT / "results/artifact-verification.json").read_text())
assert artifact["status"] == "passed"
assert artifact["resolved_revision"] == MODEL_REVISION
assert artifact["all_sha256_verified"] is True

functional = json.loads((ROOT / "results/functional-validation.json").read_text())
assert functional["status"] == "passed"
assert functional["summary"]["passed"] == functional["summary"]["total"] == 9

previous = json.loads((ROOT / "results/mtp-k2.json").read_text())
assert previous["status"] == "passed"
assert previous["model"]["revision"] == MODEL_REVISION
assert previous["aggregate"]["completion_tokens"] == 1600
assert all(row["output_tokens"] == 400 for row in previous["cases"])

new = json.loads((ROOT / "gguf/results/dflash2-q4km-n3-p030.json").read_text())
comparison = json.loads((ROOT / "gguf/results/deployment-comparison.json").read_text())
assert new["status"] == comparison["status"] == "passed"
assert new["deployment"]["target_revision"] == TARGET_REVISION
assert new["deployment"]["runtime_commit"] == DFLASH_RUNTIME
assert new["deployment"]["draft_n_max"] == 3
assert new["design"]["context_tokens"] == 8192
assert new["aggregate"]["measured_completion_tokens"] == 1600
assert abs(new["aggregate"]["weighted_server_decode_tokens_per_second"] - 28.94797399552837) < 1e-12
assert abs(comparison["previous"]["weighted_server_decode_tokens_per_second"] - 15.961167963529409) < 1e-12
assert abs(comparison["delta"]["weighted_server_decode_ratio"] - 1.8136501076658837) < 1e-12
assert comparison["comparison_type"] == "deployment-to-deployment"

readme = (ROOT / "README.md").read_text()
for value in (
    CHECKPOINT_REVISION, TABBYAPI_COMMIT, ENGINE_VERSION, ENGINE_COMMIT, IMAGE_SHA,
    "29.00", "+3.1%", "356.34", "+9.1%", "238.99", "−8.3%",
):
    assert value in readme, value
for historical in ("29.97 tok/s", "96.97%", "26.1 GB", "exllamav3 1.4.9"):
    assert historical not in readme, historical

exl_root = ROOT / "exllamav3"
quick = json.loads((exl_root / "results/glm53-exl152-quick-ab-20260927.json").read_text())
checks = json.loads((exl_root / "results/glm53-exl152-functional-canaries-20260927.json").read_text())
card = json.loads((exl_root / "results/glm53-exl152-card-asset-20260927.json").read_text())
asset = ROOT / card["card"]
assert quick["status"] == checks["status"] == "completed"
assert quick["evidence_label"] == "quick_screen_not_full_promotion"
assert quick["runtime"]["exllamav3_1_5_2_commit"] == ENGINE_COMMIT
assert quick["runtime"]["context_capacity_tokens"] == 262144
assert quick["protocol"]["long_prefill_input_tokens"] == 84865
assert quick["protocol"]["decode_measured_requests_per_case"] == 1
assert set(quick["arms"]) == {"old-149", "new-152-legacy-kda", "new-152-default-kda"}
assert quick["arms"]["old-149"]["image_id"] == ROLLBACK_IMAGE_SHA
assert quick["arms"]["new-152-default-kda"]["image_id"] == IMAGE_SHA
assert all(arm["safety"]["peak_service_swap_bytes"] == arm["safety"]["breach_count"] == 0 for arm in quick["arms"].values())
assert round(quick["display"]["decode_old_tok_s"], 2) == 28.13
assert round(quick["display"]["decode_new_tok_s"], 2) == 29.00
assert round(quick["display"]["decode_percent_change"], 1) == 3.1
assert round(quick["display"]["prefill_percent_change"], 1) == 9.1
assert round(quick["display"]["ttft_new_s"], 2) == 238.99
assert checks["candidate_image_id"] == IMAGE_SHA
assert set(checks["checks"]) == {"arithmetic_zero_budget", "arithmetic_default_effort", "forced_tool", "vision_red_square"}
assert all(item["passed"] and item["service_swap_bytes"] == 0 for item in checks["checks"].values())
assert checks["checks"]["forced_tool"]["tool_calls"][0]["function"]["name"] == "lookup_order"
assert checks["checks"]["vision_red_square"]["content"].strip() == "Red"
assert card["sha256"] == hashlib.sha256(asset.read_bytes()).hexdigest()
assert (card["width_px"], card["height_px"]) == (1472, 1968)
assert "1.5.2 quick-screen candidate metrics only" in card["lineage"]
assert b"\x89PNG\r\n\x1a\n" == asset.read_bytes()[:8]
for filename in re.findall(r"`(glm53-[\w-]+\.(?:json|md))`", readme):
    assert (exl_root / "results" / filename).exists(), filename
start_script = (exl_root / "scripts/start-tabbyapi.sh").read_text()
build_script = (exl_root / "scripts/build-exl152-image.sh").read_text()
for pinned in (IMAGE_SHA, ROLLBACK_IMAGE_SHA, ENGINE_VERSION):
    assert pinned in start_script
assert ENGINE_COMMIT in build_script

# Archived lanes document their own pins and figures in their own trees. The current
# README describes the deployment that replaced them.
archived = "\n".join(
    (ROOT / relative).read_text()
    for relative in (
        "gguf/README.md",
        "gguf/RESULT.md",
        "results/mtp-k2.json",
        "results/artifact-verification.json",
    )
)
for value in (
    "15.96", "28.95", "1.8136", "81.3650107666", "15.65", "28.37", "113.99%",
    TARGET_REVISION, DFLASH_RUNTIME, MODEL_REVISION,
):
    assert value in archived, value

launcher = (ROOT / "scripts/run_server.sh").read_text()
for value in ("127.0.0.1", "MAX_MODEL_LEN", "65536", "SPEC_METHOD", "MTP_TOKENS", "GPU_MEM_UTIL", "0.87", "EXL3_FUSED_MOE"):
    assert value in launcher

serve = (ROOT / "gguf/scripts/serve.sh").read_text()
for value in ('MODE="${MODE:-dflash2}"', 'DFLASH_N_MAX="${DFLASH_N_MAX:-3}"', "--spec-type draft-dflash", "--spec-draft-n-min 0"):
    assert value in serve

for relative in (
    "assets/glm53-mtp-result-card.html",
    "assets/glm53-mtp-result-card.png",
    "assets/glm53-mtp-result-card.svg",
    "assets/glm53-dflash2-result-card.png",
    "gguf/CARD_VALUES.md",
    "gguf/REPORT.md",
    "gguf/results/summary.json",
):
    assert not (ROOT / relative).exists(), relative

public_files = [ROOT / "README.md", ROOT / "NOTICE.md"]
for directory in (ROOT / "assets", ROOT / "gguf", ROOT / "exllamav3"):
    public_files.extend(
        path for path in directory.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and "runtime" not in path.parts and "local" not in path.parts
    )
all_public = b"\n".join(path.read_bytes() for path in public_files)
for forbidden in (
    "/home/" + "sxuf",
    "gx10" + "-fe09",
    "proxy" + ".key",
    "api" + "_key=",
    "cache/" + "images",
    "0x" + "Sero",
    "Victor " + "Cruz",
):
    assert forbidden.encode() not in all_public, forbidden

print("recipe tests passed")
