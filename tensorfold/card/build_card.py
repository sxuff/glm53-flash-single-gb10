"""Build the TensorFold result card HTML from the depth-check receipt.

    python build_card.py depth-check.json card.html
"""
import json,sys

def fmt_tokens(n):return f'{n:,}'
def fmt_seconds(s):return f'{s:.1f} s' if s<10 else (f'{s:.0f} s' if s<120 else f'{s/60:.1f} min')

def main(src,dst):
 data=json.load(open(src));rows=data['depths']
 body=''.join(f"""<tr><td>{fmt_tokens(r['prompt_tokens'])}</td><td class="n">{r['decode_tok_s_weighted']:.1f} tok/s</td>
<td class="n">{r['needles_correct']} / {r['needles_total']}</td><td class="n">{fmt_seconds(r['fresh_prefill_s'])}</td></tr>""" for r in rows)
 deepest=rows[-1];lo=min(r['decode_tok_s_weighted'] for r in rows);hi=max(r['decode_tok_s_weighted'] for r in rows)
 html=f"""<!doctype html><html><head><meta charset="utf-8"><title>GLM-5.3-Flash TensorFold card</title><style>
*{{box-sizing:border-box;margin:0}}
body{{background:#0d0d0d;font-family:"DejaVu Sans","Segoe UI",Verdana,sans-serif;color:#eaeaea;width:1472px}}
.card{{background:#191919;border:1px solid #333;border-radius:26px;padding:56px 52px 48px;width:1472px}}
h1{{font-size:30px;font-weight:700;letter-spacing:.2px}}
.sub{{color:#b9b9b9;font-size:18px;margin-top:10px}}
.hero{{display:grid;grid-template-columns:1fr 88px 1fr;align-items:center;margin-top:34px}}
.box{{background:#121212;border-radius:14px;padding:38px 32px 30px;height:240px}}
.box.new{{background:#06225c}}
.box .lab{{color:#a9a9a9;font-size:20px}}.box.new .lab{{color:#e6ecff}}
.box .big{{font-family:"DejaVu Serif",Georgia,serif;font-size:76px;margin-top:10px}}.box.new .big{{color:#5b9bff}}
.box .unit{{font-size:20px;margin-top:12px}}.box.new .unit{{color:#5b9bff}}
.arrow{{text-align:center;color:#8a8a8a;font-size:40px}}
table{{width:100%;border-collapse:collapse;margin-top:38px;font-size:20px}}
th{{text-align:left;color:#a9a9a9;font-weight:700;padding:14px 16px;border-bottom:1px solid #4a4a4a}}
td{{padding:19px 16px;border-bottom:1px solid #303030}}
th.n,td.n{{text-align:right}}
.tiles{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:24px;margin-top:34px}}
.tile{{background:#121212;border-radius:14px;padding:26px 28px}}
.tile .lab{{color:#b9b9b9;font-size:18px}}.tile .val{{font-size:32px;font-weight:700;margin-top:8px}}.tile .note{{color:#8f8f8f;font-size:16px;margin-top:8px}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:48px;margin-top:38px}}
.cols h2{{font-size:22px;padding-bottom:14px;border-bottom:1px solid #4a4a4a;margin-bottom:10px}}
.cols h2.old{{color:#a9a9a9}}
.cols p{{font-size:20px;padding:9px 16px}}
.foot{{color:#a3a3a3;font-size:18.5px;line-height:1.75;margin-top:34px}}
.receipts{{color:#7f7f7f;font-size:16.5px;line-height:1.7;margin-top:22px}}
.up{{color:#5b9bff}}.down{{color:#f0a04b}}
</style></head><body><div class="card">
<h1>GLM-5.3-Flash EXL3 2.05 bpw · TensorFold on one GB10</h1>
<div class="sub">Same checkpoint as the ExLlamaV3 recipe · 262,144-token context · one NVIDIA GB10</div>
<div class="hero">
 <div class="box"><div class="lab">ExLlamaV3 1.5.2 + TabbyAPI · decode</div><div class="big">28.56</div><div class="unit">tok/s</div></div>
 <div class="arrow">→</div>
 <div class="box new"><div class="lab">TensorFold · decode</div><div class="big">32.03</div><div class="unit">tok/s · 1.12× · +12.1%</div></div>
</div>
<table><tr><th>Prompt tokens · TensorFold, greedy, 512 tokens × 3</th><th class="n">Decode</th><th class="n">Planted codes found</th><th class="n">First token, fresh prompt</th></tr>
{body}</table>
<div class="tiles">
 <div class="tile"><div class="lab">Next turn · 11,272-token conversation</div><div class="val">2.1 s <span style="color:#8f8f8f;font-weight:400;font-size:22px">was 47.6 s</span></div><div class="note">prompt state reused · 1,321 reply tokens identical</div></div>
 <div class="tile"><div class="lab">Prompt fill · ~85K tokens</div><div class="val"><span class="down">245 tok/s</span></div><div class="note">ExLlamaV3 1.5.2: 356 tok/s</div></div>
 <div class="tile"><div class="lab">Free memory · 262K slots</div><div class="val">21.4 GiB</div><div class="note">17.4 GiB lowest during load · swap 0 B</div></div>
</div>
<div class="cols">
 <div><h2 class="old">ExLlamaV3 recipe</h2><p>TabbyAPI f07131c + exllamav3 1.5.2</p><p>native EXL3 kernels · FP16 cache</p><p>MTP n=1 · reasoning effort High</p><p>262,144 context + vision</p></div>
 <div><h2>TensorFold recipe</h2><p>TensorFold 0.5.0 + packed-EXL3 single-GPU port</p><p>sparse attention past 2,051 tokens · MTP n=1</p><p>prompt state reused between turns</p><p>262,144 slots · thinking capped at 3,000 tokens</p></div>
</div>
<div class="foot">Headline: four fixed workloads, 400 forced output tokens, greedy and temperature 0.6 / top-p 0.95 pooled, one warm-up + three measured per cell, both runtimes on the same checkpoint (ExLlamaV3 at its 262K + vision profile, TensorFold at a 2,051-token window). Depth table: one conversation per depth on the served build; a document of numbered records with five planted six-digit codes, then three identical 512-token turns resumed from that prompt state, reasoning tokens counted; decode ranged {lo:.1f} to {hi:.1f} tok/s. First token is a prompt filled from an engine reset. Next-turn tile: same seed, resumed against refilled. Prompt fill: {fmt_tokens(next(r for r in rows if 80000<r['prompt_tokens']<90000)['prompt_tokens'])} tokens here, 84,865 for ExLlamaV3. No ExLlamaV3 run in this block: its figures are the earlier receipts. Not measured: answer quality beyond code retrieval, tool calls or images at depth.</div>
<div class="receipts">receipts · glm53-tensorfold-depth-check-20261004.json · glm53-tensorfold-cache-equivalence-20261004.json · glm53-tabby-vs-tensorfold-fixed-work-20261001.json · glm53-exl152-quick-ab-20260927.json</div>
</div></body></html>"""
 open(dst,'w',encoding='utf-8').write(html)
if __name__=='__main__':main(sys.argv[1],sys.argv[2])
