#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

GIB = 1024**3
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "manifests" / "target.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(16 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect(path: Path, item: dict) -> dict:
    actual_bytes = path.stat().st_size if path.is_file() else None
    actual_hash = sha256(path) if actual_bytes == item["bytes"] else None
    return {
        "name": item["final_name"],
        "actual_bytes": actual_bytes,
        "expected_bytes": item["bytes"],
        "actual_sha256": actual_hash,
        "expected_sha256": item["sha256"],
        "ok": actual_bytes == item["bytes"] and actual_hash == item["sha256"],
    }


def validate_manifest(manifest: dict) -> None:
    required = ("repository", "revision", "variant", "files")
    if any(not manifest.get(key) for key in required) or not isinstance(manifest["files"], list):
        raise ValueError("manifest is missing required identity fields")
    names: set[str] = set()
    for item in manifest["files"]:
        for key in ("source_path", "final_name", "bytes", "sha256"):
            if key not in item:
                raise ValueError(f"manifest file is missing {key}")
        for key in ("source_path", "final_name"):
            value = Path(item[key])
            if value.is_absolute() or ".." in value.parts or str(value) in ("", "."):
                raise ValueError(f"unsafe manifest path: {item[key]}")
        if item["final_name"] in names:
            raise ValueError(f"duplicate final filename: {item['final_name']}")
        names.add(item["final_name"])
        if not isinstance(item["bytes"], int) or item["bytes"] < 1:
            raise ValueError(f"invalid byte count for {item['final_name']}")
        if not isinstance(item["sha256"], str) or len(item["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in item["sha256"]):
            raise ValueError(f"invalid SHA-256 for {item['final_name']}")


def require_license_acceptance(manifest: dict) -> None:
    license_info = manifest.get("license")
    if not license_info:
        return
    name = license_info.get("acceptance_environment_variable")
    value = license_info.get("acceptance_value")
    if not name or not value:
        raise ValueError("license acceptance manifest is incomplete")
    if os.environ.get(name) != value:
        raise PermissionError(license_info.get("notice") or f"set {name}={value} to accept the artifact license")


def main() -> int:
    parser = argparse.ArgumentParser(description="Download and verify a pinned GLM-5.3 Flash GGUF artifact")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--reserve-gib", type=int, default=10)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    validate_manifest(manifest)
    require_license_acceptance(manifest)
    destination = args.destination.expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    report_path = args.report or destination / "verification.json"

    final_rows = [inspect(destination / item["final_name"], item) for item in manifest["files"]]
    missing = [item for item, row in zip(manifest["files"], final_rows) if not row["ok"]]

    for item, row in zip(manifest["files"], final_rows):
        final = destination / item["final_name"]
        if final.exists() and not row["ok"]:
            raise RuntimeError(f"refusing to overwrite invalid final file: {final}")

    if missing:
        required = sum(item["bytes"] for item in missing) + args.reserve_gib * GIB
        available = shutil.disk_usage(destination).free
        print(json.dumps({"available_bytes": available, "required_bytes": required, "margin_bytes": available - required}))
        if available < required:
            raise RuntimeError(f"disk reserve gate failed: available={available} required={required}")

        command = [
            "hf", "download", manifest["repository"],
            "--revision", manifest["revision"],
            "--local-dir", os.fspath(destination),
        ]
        for item in missing:
            command.extend(["--include", item["source_path"]])
        subprocess.run(command, check=True)

        staged = []
        for item in missing:
            source = destination / item["source_path"]
            row = inspect(source, {**item, "final_name": item["source_path"]})
            staged.append(row)
        if not all(row["ok"] for row in staged):
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps({"status": "staging_failed", "files": staged}, indent=2, sort_keys=True) + "\n")
            return 1

        for item in missing:
            os.replace(destination / item["source_path"], destination / item["final_name"])

    rows = [inspect(destination / item["final_name"], item) for item in manifest["files"]]
    report = {
        "schema_version": 1,
        "status": "passed" if all(row["ok"] for row in rows) else "failed",
        "repository": manifest["repository"],
        "revision": manifest["revision"],
        "variant": manifest["variant"],
        "verified_files": sum(row["ok"] for row in rows),
        "verified_bytes": sum((row["actual_bytes"] or 0) for row in rows if row["ok"]),
        "free_bytes_after": shutil.disk_usage(destination).free,
        "files": rows,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in ("status", "repository", "revision", "variant", "verified_files", "verified_bytes", "free_bytes_after")}, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
