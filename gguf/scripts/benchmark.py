#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import threading
import time
import urllib.request
import re

GIB = 1024**3
PROMPTS = {
    "prose": "Write a self-contained technical explanation of how unified CPU/GPU memory changes large-language-model inference on a single workstation. Use complete paragraphs, include benefits and bottlenecks, and do not use a table. Continue for at least 500 tokens.",
    "structured": "Output the integers from 1 through 260 in order. Put exactly one space between integers. Do not omit, repeat, explain, or add any other text.",
    "code": "Implement a production-quality Python module that parses a stream of Server-Sent Events from an iterable of bytes, yields decoded JSON data objects, handles comments and multi-line data fields, and stops on [DONE]. Include type hints, a docstring, validation, and focused unit tests. Continue until the implementation and tests are complete.",
    "math": "Solve this carefully and show the full derivation: a decoder produces one verified token per base-model step without speculation. A speculative method proposes k tokens; position i is accepted only if all earlier positions were accepted. Derive expected verified tokens per step from conditional acceptance probabilities, then evaluate k=4 for p=[0.82,0.61,0.40,0.20]. Discuss proposal overhead, the break-even condition, and two numerical edge cases in at least 500 tokens.",
}


def request(url: str, payload: dict | None = None, timeout: int = 60):
    data = None if payload is None else json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read())


def mem_available() -> int:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    raise RuntimeError("MemAvailable missing")


def swap_used() -> int:
    rows = Path("/proc/swaps").read_text().splitlines()[1:]
    return sum(int(row.split()[3]) * 1024 for row in rows if row.split())


def service_swap(unit: str | None) -> int | None:
    if not unit:
        return None
    output = subprocess.check_output(["systemctl", "--user", "show", unit, "-p", "ControlGroup"], text=True).strip()
    control_group = output.split("=", 1)[1]
    path = Path("/sys/fs/cgroup") / control_group.lstrip("/") / "memory.swap.current"
    return int(path.read_text()) if path.is_file() else 0


def digest(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect one GLM-5.3 Flash speed arm")
    parser.add_argument("--arm", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--unit", help="optional systemd user unit for service-swap telemetry and emergency stop")
    parser.add_argument("--warmups", type=int, default=1)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", args.arm):
        parser.error("--arm must be a lowercase filesystem-safe label")

    base = args.base_url.rstrip("/")
    props = request(base + "/props")
    baseline_swap = swap_used()
    telemetry = {
        "minimum_mem_available_bytes": mem_available(),
        "maximum_host_swap_growth_bytes": 0,
        "maximum_service_swap_bytes": 0 if args.unit else None,
        "samples": 0,
        "breach": None,
        "monitor_error": None,
    }
    stop = threading.Event()

    def monitor() -> None:
        try:
            while not stop.wait(0.5):
                available = mem_available()
                host_growth = max(0, swap_used() - baseline_swap)
                owned_swap = service_swap(args.unit)
                telemetry["minimum_mem_available_bytes"] = min(telemetry["minimum_mem_available_bytes"], available)
                telemetry["maximum_host_swap_growth_bytes"] = max(telemetry["maximum_host_swap_growth_bytes"], host_growth)
                if owned_swap is not None:
                    telemetry["maximum_service_swap_bytes"] = max(telemetry["maximum_service_swap_bytes"], owned_swap)
                telemetry["samples"] += 1
                if available < 6 * GIB:
                    telemetry["breach"] = f"MemAvailable below 6 GiB: {available}"
                elif host_growth > 512 * 1024**2:
                    telemetry["breach"] = f"host swap growth above 512 MiB: {host_growth}"
                elif owned_swap:
                    telemetry["breach"] = f"service swap nonzero: {owned_swap}"
                if not telemetry["breach"]:
                    continue
                if args.unit:
                    subprocess.run(["systemctl", "--user", "stop", args.unit], check=False)
                stop.set()
        except Exception as exc:
            telemetry["monitor_error"] = f"{type(exc).__name__}: {exc}"
            telemetry["breach"] = "safety telemetry monitor failed"
            if args.unit:
                subprocess.run(["systemctl", "--user", "stop", args.unit], check=False)
            stop.set()

    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    rows: list[dict] = []
    warmups: list[dict] = []
    failure = None
    try:
        for case, prompt in PROMPTS.items():
            payload = {
                "model": "glm",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
                "top_p": 1.0,
                "seed": 42,
                "max_tokens": 400,
                "ignore_eos": True,
                "chat_template_kwargs": {"enable_thinking": False},
            }
            for ordinal in range(args.warmups + 1):
                started = time.perf_counter()
                response = request(base + "/v1/chat/completions", payload, timeout=900)
                elapsed = time.perf_counter() - started
                if not isinstance(response, dict) or not response.get("choices"):
                    raise RuntimeError("server returned no completion choice")
                timings = response.get("timings") or {}
                usage = response.get("usage") or {}
                choice = response["choices"][0]
                message = choice.get("message") or {}
                content = message.get("content")
                reasoning = message.get("reasoning_content")
                if not isinstance(content, str):
                    raise RuntimeError("server returned no text content")
                if reasoning is not None and not isinstance(reasoning, str):
                    raise RuntimeError("server returned non-text reasoning content")
                if args.arm != "no-mtp" and ("draft_n" not in timings or "draft_n_accepted" not in timings):
                    raise RuntimeError("speculative arm did not return draft acceptance timings")
                output_channels = {"reasoning_content": reasoning, "content": content}
                record = {
                    "arm": args.arm,
                    "case": case,
                    "warmup": ordinal < args.warmups,
                    "request_sha256": digest(payload),
                    "response_sha256": digest(response),
                    "output_text_sha256": digest(output_channels),
                    "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
                    "reasoning_content_sha256": hashlib.sha256(reasoning.encode()).hexdigest() if reasoning is not None else None,
                    "wall_seconds": elapsed,
                    "finish_reason": choice.get("finish_reason"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "whole_request_completion_tokens_per_second": usage.get("completion_tokens", 0) / elapsed,
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "predicted_tokens": timings.get("predicted_n"),
                    "predicted_seconds": (timings.get("predicted_ms") or 0) / 1000,
                    "server_decode_tokens_per_second": timings.get("predicted_per_second"),
                    "draft_tokens": timings.get("draft_n", 0),
                    "accepted_draft_tokens": timings.get("draft_n_accepted", 0),
                    "system_fingerprint": response.get("system_fingerprint"),
                }
                if record["completion_tokens"] != 400 or record["finish_reason"] != "length":
                    raise RuntimeError(f"invalid completion denominator: tokens={record['completion_tokens']} finish={record['finish_reason']}")
                (warmups if record["warmup"] else rows).append(record)
                if telemetry["breach"]:
                    raise RuntimeError(telemetry["breach"])
    except Exception as exc:
        failure = f"{type(exc).__name__}: {exc}"
    finally:
        stop.set()
        thread.join(timeout=5)
    if thread.is_alive():
        telemetry["monitor_error"] = "monitor thread did not terminate"
        telemetry["breach"] = "safety telemetry monitor failed"
    if telemetry["samples"] == 0:
        telemetry["monitor_error"] = telemetry["monitor_error"] or "no safety telemetry samples collected"
        telemetry["breach"] = "safety telemetry monitor failed"
    if telemetry["monitor_error"] and not failure:
        failure = f"RuntimeError: {telemetry['monitor_error']}"

    report = {
        "schema_version": 1,
        "arm": args.arm,
        "status": "passed" if not failure and not telemetry["breach"] and telemetry["samples"] > 0 and len(rows) == 4 else "failed",
        "failure": failure,
        "runtime": {
            "build_info": props.get("build_info"),
            "context_tokens": (props.get("default_generation_settings") or {}).get("n_ctx"),
            "model_ftype": props.get("model_ftype"),
        },
        "rows": rows,
        "warmups": warmups,
        "telemetry": telemetry,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"arm": args.arm, "status": report["status"], "rows": len(rows), "telemetry": telemetry}, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
