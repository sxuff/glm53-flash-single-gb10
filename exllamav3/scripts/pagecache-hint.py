#!/usr/bin/env python3
"""Evict only the clean EXL3 shard page cache, then verify CUDA fit headroom.

Environment:
  MODEL_DIR   checkpoint directory (required)
  REPORT_DIR  where the JSON receipt is written (default $HOME/.hermes/reports)

Exits 0 on pass, 7 on abort.
"""
import ctypes, datetime, json, os, time
from pathlib import Path
MODEL_DIR = Path(os.environ.get('MODEL_DIR') or (_ for _ in ()).throw(SystemExit('MODEL_DIR is required')))
REPORT_DIR = Path(os.environ.get('REPORT_DIR', str(Path.home() / '.hermes' / 'reports')))
REPORT_DIR.mkdir(parents=True, exist_ok=True)
OUT = REPORT_DIR / 'exl3-targeted-pagecache.json'
EXPECTED_SHARDS = int(os.environ.get('EXPECTED_SHARDS', '12'))

shards = sorted(MODEL_DIR.glob('model-*-of-*.safetensors'))
assert len(shards) == EXPECTED_SHARDS, f'expected {EXPECTED_SHARDS} shards, found {len(shards)}'
assert all(p.is_file() and not p.is_symlink() for p in shards), 'unexpected shard set'
cu = ctypes.CDLL('libcudart.so')
assert cu.cudaFree(ctypes.c_void_p(0)) == 0


def snapshot():
    free = ctypes.c_size_t(); total = ctypes.c_size_t()
    assert cu.cudaMemGetInfo(ctypes.byref(free), ctypes.byref(total)) == 0
    m = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith(('MemFree:', 'MemAvailable:', 'Cached:', 'SwapTotal:', 'SwapFree:')):
            k, v = line.split(':', 1); m[k] = int(v.split()[0]) * 1024
    return {'at': time.time(), 'cuda_free_bytes': free.value, 'cuda_total_bytes': total.value,
            'mem_free_bytes': m['MemFree'], 'mem_available_bytes': m['MemAvailable'],
            'cached_bytes': m['Cached'], 'swap_used_bytes': m['SwapTotal'] - m['SwapFree']}


r = {'started': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'model_dir': str(MODEL_DIR),
     'shard_count': len(shards), 'shard_bytes': sum(p.stat().st_size for p in shards),
     'before': snapshot(), 'shards': [p.name for p in shards]}

# Only clean, read-only pages of these files are hinted. Never run this while a
# consumer has the checkpoint mapped: DONTNEED on a live mapping thrashes the loader.
for p in shards:
    fd = os.open(p, os.O_RDONLY)
    try:
        os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
    finally:
        os.close(fd)

r['after_hint'] = snapshot()
for _ in range(5):
    time.sleep(1)
    r['after'] = snapshot()
    if r['after']['cuda_free_bytes'] >= 100 * 2 ** 30:
        break

r['status'] = 'pass' if (r['after']['cuda_free_bytes'] >= 100 * 2 ** 30
                         and r['after']['mem_available_bytes'] >= 20 * 2 ** 30
                         and r['after']['swap_used_bytes'] <= r['before']['swap_used_bytes']) else 'abort'
r['completed'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
OUT.write_text(json.dumps(r, indent=2) + '\n')
print('targeted_cache_hint', r['status'],
      'cuda_free_GiB_before', round(r['before']['cuda_free_bytes'] / 2 ** 30, 2),
      'after', round(r['after']['cuda_free_bytes'] / 2 ** 30, 2),
      'host_free_GiB_before', round(r['before']['mem_free_bytes'] / 2 ** 30, 2),
      'after', round(r['after']['mem_free_bytes'] / 2 ** 30, 2),
      'swap_delta', r['after']['swap_used_bytes'] - r['before']['swap_used_bytes'], flush=True)
raise SystemExit(0 if r['status'] == 'pass' else 7)
