#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_REVISION = "ca0bcdae265f7df1e346c57a2b53b8b8f632ee0b"
UPSTREAM_COMMIT = "0b8dd0d6c7b186076f2e61d1b99a6289f8006c3c"
VLLM_COMMIT = "878631b6079d2cf9fb80830ef9cb41b43aded098"
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
    "15.96", "28.95", "1.81x", "+81.37%", "15.65", "28.37", "63.91%",
    "Deployment-to-deployment", TARGET_REVISION, DFLASH_RUNTIME, MODEL_REVISION, VLLM_COMMIT,
):
    assert value in readme, value

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
    "gguf/CARD_VALUES.md",
    "gguf/REPORT.md",
    "gguf/results/summary.json",
):
    assert not (ROOT / relative).exists(), relative

public_files = [ROOT / "README.md", ROOT / "NOTICE.md"]
for directory in (ROOT / "assets", ROOT / "gguf"):
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
