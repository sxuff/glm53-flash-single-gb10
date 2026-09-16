from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.target = json.loads((ROOT / "manifests/target.json").read_text())
        cls.dflash = json.loads((ROOT / "manifests/dflash2.json").read_text())
        cls.derived = json.loads((ROOT / "manifests/dflash2-derived.json").read_text())
        cls.runtime = json.loads((ROOT / "manifests/runtime-dflash2.json").read_text())
        cls.arm = json.loads((ROOT / "results/dflash2-q4km-n3-p030.json").read_text())
        cls.summary = json.loads((ROOT / "results/deployment-comparison.json").read_text())

    def test_pinned_lineage(self) -> None:
        self.assertEqual(self.target["revision"], "2975ab414d30340466d8c51533c6e91f0cca64c1")
        self.assertEqual(self.dflash["revision"], "caf6ef0cedd0dc4ac1183c4110266c2e4f58e17c")
        self.assertEqual(self.runtime["commit"], "d94f44e79aa219d8057e8de21f95360a187ebf41")
        self.assertEqual(self.runtime["build"]["cuda_architectures_effective"], "121a")

    def test_derived_draft(self) -> None:
        rows = {row["quantization"]: row for row in self.derived["files"]}
        self.assertEqual(set(rows), {"Q8_0", "Q4_K_M"})
        self.assertEqual(rows["Q4_K_M"]["bytes"], 697017248)
        self.assertEqual(rows["Q4_K_M"]["sha256"], "0d7f33cb57a88d98d72e17c691a37f0f4ed8d97b71dc0cb8cc4f7da612b97e2e")

    def test_public_result_values(self) -> None:
        self.assertAlmostEqual(self.summary["previous"]["weighted_server_decode_tokens_per_second"], 15.961167963529409, places=12)
        self.assertAlmostEqual(self.summary["new"]["weighted_server_decode_tokens_per_second"], 28.94797399552837, places=12)
        self.assertAlmostEqual(self.summary["new"]["aggregate_whole_request_tokens_per_second"], 28.371904066514873, places=12)
        self.assertAlmostEqual(self.summary["delta"]["weighted_server_decode_ratio"], 1.8136501076658837, places=12)
        self.assertAlmostEqual(self.arm["aggregate"]["draft_acceptance_rate"], 2044 / 3198, places=12)

    def test_workload_values(self) -> None:
        expected = {
            "prose": 22.04940913385997,
            "structured": 39.92075480042074,
            "code": 27.07306021523558,
            "math": 32.065837996475004,
        }
        self.assertEqual(set(self.arm["workloads"]), set(expected))
        for name, value in expected.items():
            self.assertAlmostEqual(self.arm["workloads"][name]["server_decode_tokens_per_second"], value, places=12)

    def test_default_serve_contract(self) -> None:
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
        ):
            self.assertIn(token, serve)

    def test_download_requires_license_acceptance(self) -> None:
        module = load_module("download_for_test", ROOT / "scripts/download.py")
        previous = os.environ.pop("ACCEPT_DFLASH2_NC_LICENSE", None)
        try:
            with self.assertRaises(PermissionError):
                module.require_license_acceptance(self.dflash)
            os.environ["ACCEPT_DFLASH2_NC_LICENSE"] = "1"
            module.require_license_acceptance(self.dflash)
        finally:
            if previous is None:
                os.environ.pop("ACCEPT_DFLASH2_NC_LICENSE", None)
            else:
                os.environ["ACCEPT_DFLASH2_NC_LICENSE"] = previous

    def test_analyzer_reproduces_checked_in_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "summary.json"
            subprocess.run([
                sys.executable,
                os.fspath(ROOT / "scripts/analyze.py"),
                "--previous", os.fspath(REPO / "results/mtp-k2.json"),
                "--new", os.fspath(ROOT / "results/dflash2-q4km-n3-p030.json"),
                "--card", os.fspath(REPO / "assets/glm53-dflash2-result-card.png"),
                "--output", os.fspath(output),
            ], check=True, stdout=subprocess.DEVNULL)
            regenerated = json.loads(output.read_text())
        self.assertEqual(regenerated, self.summary)

    def test_old_result_artifacts_removed(self) -> None:
        for relative in (
            "assets/glm53-mtp-result-card.html",
            "assets/glm53-mtp-result-card.png",
            "assets/glm53-mtp-result-card.svg",
            "gguf/CARD_VALUES.md",
            "gguf/REPORT.md",
            "gguf/results/summary.json",
        ):
            self.assertFalse((REPO / relative).exists(), relative)


if __name__ == "__main__":
    unittest.main()
