#!/usr/bin/env python3
"""Stop before load unless host swap is stable and CUDA has fit headroom.

Environment:
  REPORT_DIR  where the JSON receipt is written (default $HOME/.hermes/reports)

Exits 0 on pass, 7 on abort.
"""
import ctypes, datetime, json, os, time
from pathlib import Path
REPORT_DIR = Path(os.environ.get('REPORT_DIR', str(Path.home() / '.hermes' / 'reports')))
REPORT_DIR.mkdir(parents=True, exist_ok=True)
OUT = REPORT_DIR / 'prelaunch-gate.json'

REQUIRED_CUDA_FREE_GIB = float(os.environ.get('REQUIRED_CUDA_FREE_GIB', '100'))
REQUIRED_AVAILABLE_GIB = float(os.environ.get('REQUIRED_AVAILABLE_GIB', '20'))
REQUIRED_CONSECUTIVE = int(os.environ.get('REQUIRED_CONSECUTIVE', '3'))
TIMEOUT_S = int(os.environ.get('GATE_TIMEOUT_S', '120'))

cu = ctypes.CDLL('libcudart.so')
if cu.cudaFree(ctypes.c_void_p(0)) != 0:
    raise RuntimeError('cuda init failed')


def sample():
    free = ctypes.c_size_t(); total = ctypes.c_size_t()
    if cu.cudaMemGetInfo(ctypes.byref(free), ctypes.byref(total)) != 0:
        raise RuntimeError('cudaMemGetInfo failed')
    d = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith(('MemAvailable:', 'SwapTotal:', 'SwapFree:')):
            k, v = line.split(':', 1); d[k] = int(v.split()[0]) * 1024
    return {'at': time.time(), 'cuda_free': free.value, 'cuda_total': total.value,
            'mem_available': d['MemAvailable'], 'swap_used': d['SwapTotal'] - d['SwapFree']}


r = {'started': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'samples': [],
     'required_cuda_free_gib': REQUIRED_CUDA_FREE_GIB,
     'required_consecutive': REQUIRED_CONSECUTIVE, 'timeout_s': TIMEOUT_S}
base = None
consecutive = 0
for i in range(max(5, TIMEOUT_S // 5)):
    s = sample(); r['samples'].append(s)
    if base is None:
        base = s['swap_used']
    print('GATE', i, 'cuda_free_GiB', round(s['cuda_free'] / 2 ** 30, 2),
          'available_GiB', round(s['mem_available'] / 2 ** 30, 2),
          'swap_delta', s['swap_used'] - base, flush=True)
    if s['mem_available'] < REQUIRED_AVAILABLE_GIB * 2 ** 30 or s['swap_used'] > base:
        r['status'] = 'abort'; r['reason'] = 'host reserve or swap growth'; break
    consecutive = consecutive + 1 if s['cuda_free'] >= REQUIRED_CUDA_FREE_GIB * 2 ** 30 else 0
    if consecutive >= REQUIRED_CONSECUTIVE:
        r['status'] = 'pass'; break
    time.sleep(5)
else:
    r['status'] = 'abort'
    r['reason'] = f'CUDA free below {REQUIRED_CUDA_FREE_GIB} GiB for {TIMEOUT_S} seconds'

r['completed'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
OUT.write_text(json.dumps(r, indent=2) + '\n')
print('RESULT', r['status'], r.get('reason'), flush=True)
raise SystemExit(0 if r['status'] == 'pass' else 7)
