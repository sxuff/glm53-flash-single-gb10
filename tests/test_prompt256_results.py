"""Publication contracts for the optional prompt-only experiment and its card."""
import hashlib
import json
import math
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
receipt = json.loads((ROOT / 'results/glm53-mosaic-prefill-prompt256-20261012.json').read_text())
runs = json.loads((ROOT / receipt['artifacts']['runs']).read_text())
card = json.loads((ROOT / 'results/glm53-mosaic-prefill-prompt256-card.json').read_text())
assert receipt['recommended_for_production'] is False
assert receipt['performance_screen'] == 'positive'
assert receipt['serving_qualification'] == 'indeterminate'
assert receipt['runtime']['context_slots'] == 262144
assert receipt['protocol']['measured_sweeps_per_arm'] == 1
assert receipt['protocol']['fresh_prefix_reuse_tokens'] == 0
assert receipt['protocol']['page_cold_residency_verified'] is False
for artifact, key in [('patch', 'patch_sha256'), ('runs', 'runs_sha256')]:
    assert hashlib.sha256((ROOT / receipt['artifacts'][artifact]).read_bytes()).hexdigest() == receipt['artifacts'][key]
assert len(receipt['pairs']) == 20
rows = {arm: {r['id']: r for r in raw} for arm, raw in runs['arms'].items()}
assert all(len(v) == 20 for v in rows.values())
for pair in receipt['pairs']:
    a, b = rows['A'][pair['id']], rows['B'][pair['id']]
    assert a['token_ids'] == b['token_ids']
    assert a['prompt_ids_sha256'] == b['prompt_ids_sha256']
    assert a['request_sha256'] == b['request_sha256']
    for arm, raw in [('A', a), ('B', b)]:
        assert len(raw['token_ids']) == raw['completion_tokens']
        assert raw['cached_tokens'] == 0
        assert math.isclose(raw['native_prefill_proxy_tok_s'], raw['prompt_tokens'] / raw['native_prefill_s'], rel_tol=1e-12)
        for metric in ['native_prefill_proxy_tok_s', 'ttft_s', 'callback_decode_tok_s', 'total_s']:
            assert raw[metric] == pair[metric + '_' + arm]
    if pair['phase'] == 'decode':
        assert a['completion_tokens'] == b['completion_tokens'] == 400
        assert abs(pair['callback_decode_tok_s_change_percent']) <= 3
        for key in ['accepted', 'drafted', 'rounds']:
            assert a['stats'][key] == b['stats'][key]
    if pair['phase'] == 'fresh_prefill':
        assert math.isclose(pair['native_prefill_proxy_tok_s_change_percent'], 100 * (b['native_prefill_proxy_tok_s'] / a['native_prefill_proxy_tok_s'] - 1), abs_tol=1e-10)
assert receipt['correctness']['module_gate']['passed'] is True
assert receipt['correctness']['module_gate']['tests'] == 21
assert all(row['slot_exact'] and row['combine_exact'] for row in receipt['correctness']['module_gate']['rows'])
for checks in receipt['correctness']['same_runtime_mtp_exactness'].values():
    assert len(checks) == 4 and all(c['exact'] for c in checks)
assert all(s['content_equal'] and s['reasoning_equal'] and s['token_ids_equal'] for s in receipt['correctness']['feature_behavior_comparison'])
assert runs['feature_smokes']['A'][0]['checks']['answer'] is False
assert runs['feature_smokes']['B'][0]['checks']['answer'] is False
assert runs['feature_smokes']['A'][1]['checks']['thinking_present'] is False
assert runs['feature_smokes']['B'][1]['checks']['thinking_present'] is False
asset = ROOT / card['card']
raw = asset.read_bytes()
assert raw[:8] == b'\x89PNG\r\n\x1a\n'
assert struct.unpack('>II', raw[16:24]) == (card['width_px'], card['height_px']) == (1240, 650)
assert hashlib.sha256(raw).hexdigest() == card['sha256']
assert (ROOT / card['source_receipt']).exists()
by_id = {p['id']: p for p in receipt['pairs']}
assert len(card['rows']) == 4
for row in card['rows']:
    p = by_id[row['id']]
    assert row['display_values'][1:] == [f"{p['ttft_s_A']:.2f}", f"{p['ttft_s_B']:.2f}", f"{p['native_prefill_proxy_tok_s_A']:.0f}", f"{p['native_prefill_proxy_tok_s_B']:.0f}", f"{p['native_prefill_proxy_tok_s_change_percent']:+.1f}%"]
assert receipt['safety']['minimum_reserve_bytes'] >= 7 * 1024**3
assert receipt['safety']['maximum_host_swap_growth_bytes'] <= 1024**3
assert receipt['safety']['maximum_experiment_cgroup_swap_bytes'] == 0
files = [ROOT / 'experiments/prompt256/README.md', ROOT / 'experiments/prompt256/test_policy.py', ROOT / receipt['artifacts']['patch']]
files += list((ROOT / 'results').glob('glm53-mosaic-prefill-prompt256*.json'))
for p in files:
    for token in [b'/home/', b'/opt/data/', b'172.17.', b'Bearer ', b'proxy.key', b'filicroval', b'gx10-fe09']:
        assert token not in p.read_bytes(), (p, token)
print('prompt256 receipt/card/publication contracts passed')
