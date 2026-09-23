#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:8] != bytes.fromhex("89504e470d0a1a0a"):
        raise ValueError(f"not a PNG: {path}")
    return struct.unpack(">II", data[16:24])


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the public GLM-5.3 deployment-comparison receipt")
    parser.add_argument("--previous", type=Path, default=ROOT.parent / "results" / "mtp-k2.json")
    parser.add_argument("--new", type=Path, default=ROOT / "results" / "dflash2-q4km-n3-p030.json")
    parser.add_argument(
        "--card",
        type=Path,
        default=None,
        help="Optional result-card PNG. Omit to build the receipt without a result_card block.",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "deployment-comparison.json")
    args = parser.parse_args()

    previous = json.loads(args.previous.read_text())
    new = json.loads(args.new.read_text())
    if previous.get("status") != "passed" or new.get("status") != "passed":
        raise ValueError("both source receipts must have status=passed")

    old_rows = previous["cases"]
    old_tokens = sum(int(row["output_tokens"]) for row in old_rows)
    old_decode_seconds = sum(float(row["server_decode_seconds"]) for row in old_rows)
    old_wall_seconds = sum(float(row["wall_seconds"]) for row in old_rows)
    old_decode = old_tokens / old_decode_seconds
    old_whole = old_tokens / old_wall_seconds

    new_aggregate = new["aggregate"]
    new_decode = float(new_aggregate["weighted_server_decode_tokens_per_second"])
    new_whole = float(new_aggregate["aggregate_whole_request_tokens_per_second"])
    workloads = new["workloads"]
    old_by_case = {row["case"]: row for row in old_rows}
    if set(old_by_case) != set(workloads):
        raise ValueError("workload sets differ")

    width, height = (None, None)
    if args.card is not None:
        width, height = png_size(args.card)
    result = {
        "schema_version": 1,
        "status": "passed",
        "evidence_label": "tested",
        "comparison_type": "deployment-to-deployment",
        "metric_definitions": {
            "weighted_server_decode_tokens_per_second": "sum of measured completion tokens divided by summed server decode seconds",
            "aggregate_whole_request_tokens_per_second": "sum of measured completion tokens divided by summed client wall seconds",
        },
        "protocol": {
            "hardware": "one NVIDIA GB10",
            "workloads": 4,
            "completion_tokens_per_request": 400,
            "warmups_per_workload": 1,
            "measured_requests_per_workload": 1,
            "temperature": 0.0,
            "seed": 42,
        },
        "previous": {
            "label": "Previous deployment",
            "profile": "EXL3 K2 with native MTP k=2",
            "context_tokens": int(previous["design"]["context_tokens"]),
            "weighted_server_decode_tokens_per_second": old_decode,
            "aggregate_whole_request_tokens_per_second": old_whole,
            "per_workload_server_decode_tokens_per_second": {
                case: float(row["server_decode_tokens_per_second"])
                for case, row in old_by_case.items()
            },
            "source_receipt": "../../results/mtp-k2.json",
            "source_sha256": hashlib.sha256(args.previous.read_bytes()).hexdigest(),
        },
        "new": {
            "label": "New DFlash2 deployment",
            "profile": "UD-IQ2_XXS with DFlash2 Q4_K_M, n=3, p_min=0.30",
            "context_tokens": int(new["design"]["context_tokens"]),
            "weighted_server_decode_tokens_per_second": new_decode,
            "aggregate_whole_request_tokens_per_second": new_whole,
            "per_workload_server_decode_tokens_per_second": {
                case: float(row["server_decode_tokens_per_second"])
                for case, row in workloads.items()
            },
            "draft_acceptance_rate": float(new_aggregate["draft_acceptance_rate"]),
            "source_receipt": "dflash2-q4km-n3-p030.json",
            "source_sha256": hashlib.sha256(args.new.read_bytes()).hexdigest(),
        },
        "delta": {
            "weighted_server_decode_ratio": new_decode / old_decode,
            "weighted_server_decode_increase_percent": (new_decode / old_decode - 1) * 100,
            "aggregate_whole_request_ratio": new_whole / old_whole,
            "aggregate_whole_request_increase_percent": (new_whole / old_whole - 1) * 100,
            "per_workload_server_decode_increase_percent": {
                case: (
                    float(workloads[case]["server_decode_tokens_per_second"])
                    / float(old_by_case[case]["server_decode_tokens_per_second"])
                    - 1
                )
                * 100
                for case in workloads
            },
        },
        "scope_note": "The deployments use different artifacts, runtimes, and context allocations. This is not an isolated component A/B test.",
    }
    if args.card is not None:
        result["result_card"] = {
            "path": os.path.relpath(args.card, args.output.parent),
            "sha256": hashlib.sha256(args.card.read_bytes()).hexdigest(),
            "width": width,
            "height": height,
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps(result["delta"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
