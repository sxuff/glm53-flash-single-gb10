"""Checks the /metrics hook against stand-ins with TabbyAPI's module names and signatures.

    python3 -m unittest exllamav3/metrics/test_sitecustomize.py

Needs fastapi and httpx (for TestClient); skips the route test without them.
"""
import importlib
import pathlib
import subprocess
import sys
import tempfile
import textwrap
import unittest

HERE = pathlib.Path(__file__).resolve().parent

# Same shape as TabbyAPI f07131c: backends import log_metrics by name, main calls
# setup_app through the module.
STAND_INS = {
    'common/__init__.py': '',
    'common/gen_logging.py': '''
        CALLS = []
        def log_metrics(label, metrics, context_len, max_seq_len):
            CALLS.append(label)
    ''',
    'backends/__init__.py': '',
    'backends/model.py': '''
        from common.gen_logging import log_metrics
        def finish(label, metrics):
            log_metrics(label, metrics, 10, 262144)
    ''',
    'endpoints/__init__.py': '',
    'endpoints/server.py': '''
        from fastapi import FastAPI
        def setup_app(host=None, port=None):
            app = FastAPI()
            @app.get('/v1/model')
            def model():
                return {'id': 'glm53'}
            return app
    ''',
}

PROGRAM = '''
import sitecustomize  # what Python does at startup when it is on PYTHONPATH
from backends import model
from common import gen_logging
model.finish('a', {'gen_tokens': 400, 'gen_time': 13.5, 'prompt': 'never counted'})
model.finish('b', {'gen_tokens': 100, 'gen_time': 3.5})
model.finish('c', {'gen_tokens': 'junk'})
model.finish('d', None)
assert gen_logging.CALLS == ['a', 'b', 'c', 'd'], gen_logging.CALLS  # TabbyAPI's own logging still runs
text = sitecustomize.render()
assert 'tabbyapi_generated_tokens_total 500' in text, text
assert 'tabbyapi_generation_seconds_total 17.000000' in text, text
assert 'tabbyapi_requests_total 2' in text, text
assert 'never counted' not in text
try:
    from fastapi.testclient import TestClient
except ImportError:
    print('route: skipped (no fastapi/httpx)')
else:
    from endpoints import server
    client = TestClient(server.setup_app())
    response = client.get('/metrics')
    assert response.status_code == 200 and 'tabbyapi_generated_tokens_total 500' in response.text, response.text
    assert client.get('/v1/model').json() == {'id': 'glm53'}, 'existing routes untouched'
    print('route: ok')
print('ok')
'''


class MetricsHookTest(unittest.TestCase):
    def test_counts_finished_requests_and_serves_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            for name, body in STAND_INS.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(textwrap.dedent(body))
            env = {'PYTHONPATH': f'{HERE}{":" if sys.platform != "win32" else ";"}{root}', 'PATH': ''}
            result = subprocess.run([sys.executable, '-c', PROGRAM], cwd=root, env={**__import__('os').environ, **env}, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn('ok', result.stdout)
            print(result.stdout.strip())

    def test_a_broken_hook_never_stops_tabbyapi(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'common').mkdir()
            (root / 'common/__init__.py').write_text('')
            (root / 'common/gen_logging.py').write_text('x = 1\n')  # no log_metrics to wrap
            env = {**__import__('os').environ, 'PYTHONPATH': f'{HERE}{":" if sys.platform != "win32" else ";"}{root}'}
            result = subprocess.run([sys.executable, '-c', 'import sitecustomize\nfrom common import gen_logging\nprint(gen_logging.x)'], cwd=root, env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), '1')
            self.assertIn('not patched', result.stderr)


if __name__ == '__main__':
    unittest.main()
