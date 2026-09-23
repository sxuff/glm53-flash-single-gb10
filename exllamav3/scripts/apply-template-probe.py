#!/usr/bin/env python3
"""Render the chat template for a fixed request without generating anything.

TabbyAPI's POST /v1/apply-template returns the fully templated prompt, so this
proves what reasoning effort a request actually resolves to. Cheaper and more
direct than enabling prompt logging, and it costs no GPU time.

Environment:
  GLM_BASE     endpoint (default http://127.0.0.1:8002)
  REPORT_DIR   where the JSON receipt is written (default $HOME/.hermes/reports)
"""
import datetime, json, os, urllib.error, urllib.request
from pathlib import Path
BASE = os.environ.get('GLM_BASE', 'http://127.0.0.1:8002')
REPORT_DIR = Path(os.environ.get('REPORT_DIR', str(Path.home() / '.hermes' / 'reports')))
REPORT_DIR.mkdir(parents=True, exist_ok=True)
OUT = REPORT_DIR / 'tabbyapi-template-effort-probe.json'


def post(path, payload):
    q = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                               headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(q, timeout=60) as v:
            return v.status, json.loads(v.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:2000]


r = {'started': datetime.datetime.now(datetime.timezone.utc).isoformat(),
     'base': BASE, 'cases': []}


def run(label, extra):
    payload = {'model': 'glm53',
               'messages': [{'role': 'user', 'content': 'What is 9 times 6? Reply with only the integer.'}],
               'max_tokens': 16}
    payload.update(extra)
    status, body = post('/v1/apply-template', payload)
    prompt = body.get('prompt') if isinstance(body, dict) else str(body)
    line = [x for x in (prompt or '').split('<|') if 'Reasoning Effort' in x]
    r['cases'].append({'label': label, 'status': status, 'extra': extra,
                       'effort_line': line[0].strip() if line else None})
    print('CASE', label, status, repr(line[0].strip() if line else None), flush=True)


run('default_no_field', {})
run('flat_reasoning_effort_max', {'reasoning_effort': 'max'})
run('flat_reasoning_effort_low', {'reasoning_effort': 'low'})
run('flat_reasoning_effort_high', {'reasoning_effort': 'high'})
run('template_vars_max', {'template_vars': {'reasoning_effort': 'max'}})
run('reasoning_object_max', {'reasoning': {'effort': 'max'}})

r['ended'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
r['status'] = 'completed'
OUT.write_text(json.dumps(r, indent=2) + '\n')
print('STATUS', r['status'], flush=True)
