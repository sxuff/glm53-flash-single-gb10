"""CPU-only prompt-role and source contracts. Never loads Torch or a model."""
import argparse
import importlib.util
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

parser = argparse.ArgumentParser()
parser.add_argument('--runtime', required=True, type=Path)
args, remaining = parser.parse_known_args()
G = args.runtime / 'src/tensorfold/families/glm5_next/cuda'
spec = importlib.util.spec_from_file_location('prompt_policy', G / 'prompt_policy.py')
assert spec is not None and spec.loader is not None
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)

class PolicyContracts(unittest.TestCase):
    def test_off_matches_incumbent(self):
        with patch.dict(os.environ, GLM_PROMPT_WIDE='0'):
            self.assertEqual(policy.prompt_rows(), 128)
            for rows in (1, 2, 127, 128, 129, 255, 256, 257):
                for role in (True, False):
                    self.assertEqual(policy.routed_window_rows(rows, prefill=role), min(rows, 128))

    def test_prompt_only_boundaries(self):
        with patch.dict(os.environ, GLM_PROMPT_WIDE='1'):
            self.assertEqual(policy.prompt_rows(), 256)
            for rows in (1, 2, 127, 128, 129, 255, 256, 257):
                self.assertEqual(policy.routed_window_rows(rows, prefill=True), min(rows, 256))
                self.assertEqual(policy.routed_window_rows(rows, prefill=False), min(rows, 128))

    def test_one_row_role_not_inferred(self):
        with patch.dict(os.environ, GLM_PROMPT_WIDE='1'):
            for role in (True, False):
                self.assertEqual(policy.routed_window_rows(1, prefill=role), 1)
            for role in (0, 1, None, 'prompt'):
                with self.assertRaises(ValueError):
                    policy.routed_window_rows(1, prefill=role)

    def test_invalid_switch_fails_closed(self):
        with patch.dict(os.environ, GLM_PROMPT_WIDE='true'):
            with self.assertRaises(ValueError):
                policy.prompt_rows()

    def test_real_buffer_role_dispatch(self):
        forward = (G / 'forward.py').read_text()
        decode = (G / 'decode.py').read_text()
        self.assertIn('routed_window_rows(rows, prefill=prefill)', forward)
        self.assertIn('self.pbuf = Buffers(w, prefill_rows, capacity, prefill=True)', decode)
        self.assertIn('self.mbuf = Buffers(w, max_rows, capacity)', decode)

    def test_dense_staging_and_admission_scope(self):
        text = (G / 'packed.py').read_text()
        self.assertIn('pr=min(r,128)', text)
        self.assertIn('one(prefill_rows,prompt=True)', text)

    def test_no_torch_loaded(self):
        self.assertNotIn('torch', sys.modules)

if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]] + remaining, verbosity=2)
