#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

CHUNK = 16 * 1024 * 1024
EVICT_WINDOW = 64 * 1024 * 1024


def sha256_and_evict(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        offset = 0
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
            offset += len(chunk)
            if hasattr(os, "posix_fadvise") and offset >= EVICT_WINDOW:
                os.posix_fadvise(
                    handle.fileno(),
                    offset - EVICT_WINDOW,
                    EVICT_WINDOW,
                    os.POSIX_FADV_DONTNEED,
                )
        if hasattr(os, "posix_fadvise"):
            os.posix_fadvise(handle.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
    return digest.hexdigest()


def verify(path: Path, expected: dict) -> dict:
    if path.name != expected["name"]:
        raise ValueError(f"unexpected artifact filename: {path.name}")
    if not path.is_file():
        raise FileNotFoundError(f"missing artifact: {path.name}")
    actual_bytes = path.stat().st_size
    if actual_bytes != expected["bytes"]:
        raise ValueError(
            f"artifact byte mismatch for {path.name}: "
            f"expected={expected['bytes']} actual={actual_bytes}"
        )
    actual_hash = sha256_and_evict(path)
    if actual_hash != expected["sha256"]:
        raise ValueError(f"artifact SHA-256 mismatch for {path.name}")
    return {"name": path.name, "bytes": actual_bytes, "sha256": actual_hash}


def target_rows(manifest: dict) -> dict[str, dict]:
    return {
        row["final_name"]: {
            "name": row["final_name"],
            "bytes": row["bytes"],
            "sha256": row["sha256"],
        }
        for row in manifest["files"]
    }


def draft_rows(hub_manifest: dict, derived_manifest: dict) -> dict[str, dict]:
    rows = {
        row["final_name"]: {
            "name": row["final_name"],
            "bytes": row["bytes"],
            "sha256": row["sha256"],
        }
        for row in hub_manifest["files"]
    }
    rows.update({
        row["name"]: {
            "name": row["name"],
            "bytes": row["bytes"],
            "sha256": row["sha256"],
        }
        for row in derived_manifest["files"]
    })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Hash-bind a llama.cpp launch to pinned artifacts")
    parser.add_argument("--target-manifest", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--mmproj", type=Path)
    parser.add_argument("--draft-manifest", type=Path)
    parser.add_argument("--derived-manifest", type=Path)
    parser.add_argument("--draft-model", type=Path)
    args = parser.parse_args()

    target_manifest = json.loads(args.target_manifest.read_text())
    expected_target = target_rows(target_manifest)
    model_dir = args.model_dir.expanduser().resolve()
    model = args.model.expanduser().resolve()
    if model.parent != model_dir:
        raise ValueError("target model must be inside MODEL_DIR")
    first_name = target_manifest["files"][0]["final_name"]
    if model.name != first_name:
        raise ValueError(f"target entry shard must be {first_name}")

    verified_target = []
    for row in target_manifest["files"]:
        expected = expected_target[row["final_name"]]
        verified_target.append(verify(model_dir / expected["name"], expected))

    if args.mmproj:
        mmproj = args.mmproj.expanduser().resolve()
        expected = expected_target.get(mmproj.name)
        if expected is None:
            raise ValueError(f"projector is not pinned by target manifest: {mmproj.name}")
        if mmproj.parent != model_dir:
            raise ValueError("projector must be inside MODEL_DIR")
        # It was already verified with the complete target set above.

    verified_draft = None
    if args.draft_model:
        if not args.draft_manifest or not args.derived_manifest:
            raise ValueError("draft verification requires both draft manifests")
        hub = json.loads(args.draft_manifest.read_text())
        derived = json.loads(args.derived_manifest.read_text())
        expected_drafts = draft_rows(hub, derived)
        draft = args.draft_model.expanduser().resolve()
        expected = expected_drafts.get(draft.name)
        if expected is None:
            raise ValueError(f"draft is not checksum-pinned: {draft.name}")
        verified_draft = verify(draft, expected)

    report = {
        "status": "passed",
        "target_repository": target_manifest["repository"],
        "target_revision": target_manifest["revision"],
        "target_files": len(verified_target),
        "target_bytes": sum(row["bytes"] for row in verified_target),
        "draft": verified_draft,
    }
    print(json.dumps(report, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
