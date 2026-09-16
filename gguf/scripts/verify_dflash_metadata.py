#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct


SCALARS = {
    0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i",
    6: "f", 7: "?", 10: "Q", 11: "q", 12: "d",
}


def read_exact(handle, size: int) -> bytes:
    value = handle.read(size)
    if len(value) != size:
        raise ValueError("truncated GGUF header")
    return value


def unpack(handle, fmt: str):
    return struct.unpack("<" + fmt, read_exact(handle, struct.calcsize("<" + fmt)))[0]


def read_string(handle) -> str:
    size = unpack(handle, "Q")
    if size > 64 * 1024**2:
        raise ValueError(f"unreasonable GGUF string length: {size}")
    return read_exact(handle, size).decode("utf-8")


def read_value(handle, value_type: int):
    if value_type in SCALARS:
        return unpack(handle, SCALARS[value_type])
    if value_type == 8:
        return read_string(handle)
    if value_type == 9:
        element_type = unpack(handle, "I")
        count = unpack(handle, "Q")
        if count > 10_000_000:
            raise ValueError(f"unreasonable GGUF array length: {count}")
        return [read_value(handle, element_type) for _ in range(count)]
    raise ValueError(f"unsupported GGUF metadata type: {value_type}")


def read_header(path: Path) -> tuple[int, dict, list[str]]:
    with path.open("rb") as handle:
        if read_exact(handle, 4) != b"GGUF":
            raise ValueError("not a GGUF file")
        version = unpack(handle, "I")
        if version not in (2, 3):
            raise ValueError(f"unsupported GGUF version: {version}")
        tensor_count = unpack(handle, "Q")
        kv_count = unpack(handle, "Q")
        metadata = {}
        for _ in range(kv_count):
            key = read_string(handle)
            metadata[key] = read_value(handle, unpack(handle, "I"))
        tensors = []
        for _ in range(tensor_count):
            name = read_string(handle)
            n_dims = unpack(handle, "I")
            for _ in range(n_dims):
                unpack(handle, "Q")
            unpack(handle, "I")
            unpack(handle, "Q")
            tensors.append(name)
    return tensor_count, metadata, tensors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify DFlash2 GGUF architecture metadata")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    expected = manifest["metadata_expected"]
    tensor_count, metadata, tensors = read_header(args.model)
    actual = {
        "architecture": metadata.get("general.architecture"),
        "tensor_count": tensor_count,
        "vocab_size": metadata.get("dflash.vocab_size", metadata.get("tokenizer.ggml.vocab_size")),
        "block_size": metadata.get("dflash.block_size"),
        "conv_kernel_size": metadata.get("dflash.conv_kernel_size"),
        "conv_group_size": metadata.get("dflash.conv_group_size"),
        "selector_rank": metadata.get("dflash.selector_rank"),
        "selector_top_k": metadata.get("dflash.selector_top_k"),
        "target_layers": metadata.get("dflash.target_layers"),
    }
    if actual["vocab_size"] is None:
        tokens = metadata.get("tokenizer.ggml.tokens")
        actual["vocab_size"] = len(tokens) if isinstance(tokens, list) else None
    mismatches = {key: {"expected": value, "actual": actual.get(key)} for key, value in expected.items() if actual.get(key) != value}
    required_tensors = {"selector_hidden.weight", "selector_predecessor.weight", "selector_successor.weight"}
    missing_tensors = sorted(required_tensors - set(tensors))
    if mismatches or missing_tensors:
        raise SystemExit(json.dumps({"status": "failed", "mismatches": mismatches, "missing_tensors": missing_tensors}, sort_keys=True))
    print(
        "DFlash2 conv kernel = "
        f"{actual['conv_kernel_size']}, group = {actual['conv_group_size']}, "
        f"selector rank = {actual['selector_rank']}, top-k = {actual['selector_top_k']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())