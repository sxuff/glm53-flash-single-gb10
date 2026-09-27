#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(message: str) -> None:
    raise AssertionError(message)


def close(actual: float, expected: float, label: str) -> None:
    if abs(actual - expected) > 1e-12:
        fail(f"{label} mismatch: {actual} != {expected}")


def check_links(path: Path) -> None:
    pattern = re.compile(r"\[[^]]+\]\((?!https?://|#)([^)]+)\)")
    for link in pattern.findall(path.read_text()):
        if not (path.parent / link).resolve().exists():
            fail(f"broken relative link in {path.relative_to(REPO)}: {link}")


def main() -> int:
    target = json.loads((ROOT / "manifests/target.json").read_text())
    dflash = json.loads((ROOT / "manifests/dflash2.json").read_text())
    derived = json.loads((ROOT / "manifests/dflash2-derived.json").read_text())
    runtime = json.loads((ROOT / "manifests/runtime-dflash2.json").read_text())
    quantizer = json.loads((ROOT / "manifests/runtime-dflash2-quantizer.json").read_text())
    arm = json.loads((ROOT / "results/dflash2-q4km-n3-p030.json").read_text())
    summary = json.loads((ROOT / "results/deployment-comparison.json").read_text())
    previous = json.loads((REPO / "results/mtp-k2.json").read_text())

    if target["revision"] != "2975ab414d30340466d8c51533c6e91f0cca64c1":
        fail("target revision changed")
    if dflash["revision"] != "caf6ef0cedd0dc4ac1183c4110266c2e4f58e17c":
        fail("drafter revision changed")
    if runtime["commit"] != "d94f44e79aa219d8057e8de21f95360a187ebf41":
        fail("DFlash runtime revision changed")
    if sha256(ROOT / runtime["patch"]) != runtime["patch_sha256"]:
        fail("DFlash runtime patch hash mismatch")
    if derived["runtime"]["commit"] != quantizer["commit"]:
        fail("quantizer lineage mismatch")
    draft_rows = {row["quantization"]: row for row in derived["files"]}
    if set(draft_rows) != {"Q8_0", "Q4_K_M"}:
        fail("derived draft set changed")
    if draft_rows["Q4_K_M"]["bytes"] != 697017248:
        fail("Q4_K_M byte count changed")

    measured = list(arm["workloads"].values())
    tokens = sum(int(row["completion_tokens"]) for row in measured)
    weighted_decode = tokens / sum(float(row["server_decode_seconds"]) for row in measured)
    whole_request = tokens / sum(float(row["wall_seconds"]) for row in measured)
    close(weighted_decode, float(arm["aggregate"]["weighted_server_decode_tokens_per_second"]), "new weighted decode")
    close(whole_request, float(arm["aggregate"]["aggregate_whole_request_tokens_per_second"]), "new whole-request")
    accepted = int(arm["aggregate"]["accepted_draft_tokens"])
    proposed = int(arm["aggregate"]["proposed_draft_tokens"])
    close(accepted / proposed, float(arm["aggregate"]["draft_acceptance_rate"]), "draft acceptance")

    old_rows = previous["cases"]
    old_tokens = sum(int(row["output_tokens"]) for row in old_rows)
    old_decode = old_tokens / sum(float(row["server_decode_seconds"]) for row in old_rows)
    old_whole = old_tokens / sum(float(row["wall_seconds"]) for row in old_rows)
    close(old_decode, float(summary["previous"]["weighted_server_decode_tokens_per_second"]), "previous weighted decode")
    close(old_whole, float(summary["previous"]["aggregate_whole_request_tokens_per_second"]), "previous whole-request")
    close(weighted_decode, float(summary["new"]["weighted_server_decode_tokens_per_second"]), "summary new weighted decode")
    close(whole_request, float(summary["new"]["aggregate_whole_request_tokens_per_second"]), "summary new whole-request")
    close(weighted_decode / old_decode, float(summary["delta"]["weighted_server_decode_ratio"]), "decode ratio")
    close(whole_request / old_whole, float(summary["delta"]["aggregate_whole_request_ratio"]), "whole-request ratio")

    if "result_card" in summary:
        card = REPO / summary["result_card"]["path"]
        if sha256(card) != summary["result_card"]["sha256"]:
            fail("result-card hash mismatch")

    removed = (
        "assets/glm53-mtp-result-card.html",
        "assets/glm53-mtp-result-card.png",
        "assets/glm53-mtp-result-card.svg",
        "assets/glm53-dflash2-result-card.png",
        "gguf/CARD_VALUES.md",
        "gguf/REPORT.md",
        "gguf/results/summary.json",
    )
    for relative in removed:
        if (REPO / relative).exists():
            fail(f"obsolete artifact still exists: {relative}")

    docs = [REPO / "README.md", ROOT / "README.md", ROOT / "RESULT.md", ROOT / "RESULT_CARD.md"]
    for path in docs:
        check_links(path)
    archive_narrative = "\n".join(path.read_text() for path in docs[1:])
    for value in ("15.96", "28.95", "1.8136", "81.3650107666", "15.65", "28.37", "113.99%",
                  "not an isolated component A/B"):
        if value not in archive_narrative:
            fail(f"archived result value missing: {value}")
    current = docs[0].read_text()
    for value in ("1.5.2", "29.00", "356.34", "238.99", "quick screen"):
        if value not in current:
            fail(f"current result value missing: {value}")
    for stale_headline in ("29.97 tok/s", "96.97%", "26.1 GB"):
        if stale_headline in current:
            fail(f"historical result advertised as current: {stale_headline}")

    serve = (ROOT / "scripts/serve.sh").read_text()
    for token in (
        'MODE="${MODE:-dflash2}"',
        'DFLASH_N_MAX="${DFLASH_N_MAX:-3}"',
        'DFLASH_P_MIN="${DFLASH_P_MIN:-0.30}"',
        "--spec-type draft-dflash",
        "--spec-draft-n-min 0",
        "--cache-type-k q8_0",
        "--cache-type-v q8_0",
        "--no-kv-unified",
        "--fit off",
        "verify_launch_artifacts.py",
    ):
        if token not in serve:
            fail(f"serve contract missing: {token}")

    private_literals = (
        "/home/" + "sxuf",
        "gx10" + "-fe09",
        "cache/" + "images",
        "proxy" + ".key",
        "api" + "_key=",
        "0x" + "Sero",
        "Victor " + "Cruz",
    )
    roots = [REPO / "README.md", REPO / "NOTICE.md", REPO / "assets", ROOT]
    for item in roots:
        paths = [item] if item.is_file() else list(item.rglob("*"))
        for path in paths:
            if not path.is_file() or "__pycache__" in path.parts or "runtime" in path.parts or "local" in path.parts:
                continue
            data = path.read_bytes()
            for literal in private_literals:
                if literal.encode() in data:
                    fail(f"private literal found in {path.relative_to(REPO)}")

    print(json.dumps({
        "status": "passed",
        "weighted_decode_previous": old_decode,
        "weighted_decode_new": weighted_decode,
        "weighted_decode_ratio": weighted_decode / old_decode,
        "whole_request_previous": old_whole,
        "whole_request_new": whole_request,
        "draft_acceptance": accepted / proposed,
        "result_card_sha256": summary.get("result_card", {}).get("sha256"),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
