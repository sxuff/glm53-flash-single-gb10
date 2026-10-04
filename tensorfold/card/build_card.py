"""Build the TensorFold result card (1600x900) from the depth-check receipt.

    python build_card.py glm53-tensorfold-depth-check-20261004.json card.html

Render card.html at 1600x900 to get the PNG. The two headline figures are constants
with their receipts named beside them; the bars come from the depth-check receipt.
"""
import json,sys

BASELINE=11.63   # exllamav3/results/glm53-phase0-2026-09-22.md: SGLang + EXL3 adapter, mean decode, four prompts, temperature 0
TENSORFOLD=32.32 # tensorfold/results/glm53-tabby-vs-tensorfold-fixed-work-20261001.json: pooled greedy decode, same four prompts
SCALE=35.0       # tok/s at the full bar width
SKIP=(80000,90000)  # the ~85K row is left off the card; it stays in the receipt and the README

def main(src,dst):
 rows=[r for r in json.load(open(src))['depths'] if not SKIP[0]<r['prompt_tokens']<SKIP[1]]
 assert all(r['needles_correct']==r['needles_total'] for r in rows)
 bars=''.join(f"""<div class="row"><div class="size">{r['prompt_tokens']:,}</div>
<div class="track"><div class="bar" style="width:{100*r['decode_tok_s_weighted']/SCALE:.2f}%"></div><div class="val">{r['decode_tok_s_weighted']:.1f}</div></div></div>""" for r in rows)
 ratio=TENSORFOLD/BASELINE
 html=f"""<!doctype html><html><head><meta charset="utf-8"><title>GLM-5.3 Flash on one GB10</title><style>
*{{box-sizing:border-box;margin:0}}
:root{{--surface:#1a1a19;--panel:#121211;--ink:#f3f2ee;--ink2:#c2c1bc;--muted:#8d8c87;--rule:#34342f;--blue:#3987e5}}
body{{width:1600px;height:900px;background:var(--surface);color:var(--ink);font-family:"Segoe UI","Inter","Helvetica Neue",Arial,sans-serif;padding:58px 72px 0;overflow:hidden}}
header{{display:flex;justify-content:space-between;align-items:baseline}}
h1{{font-size:40px;font-weight:650;letter-spacing:-.3px}}
header span{{font-size:21px;color:var(--muted)}}
.top{{display:grid;grid-template-columns:372px 44px 520px 1fr;gap:20px;align-items:stretch;margin-top:38px;height:250px}}
.box{{border-radius:18px;padding:30px 34px;display:flex;flex-direction:column;justify-content:space-between}}
.box .lab{{font-size:20px}}
.old{{background:var(--panel)}}.old .lab{{color:var(--muted)}}
.old .num{{font-size:84px;font-weight:600;color:var(--ink2);letter-spacing:-2px;line-height:1}}
.old .unit{{font-size:20px;color:var(--muted)}}
.new{{background:linear-gradient(135deg,#0b2a66,#17479c)}}.new .lab{{color:#dbe7ff}}
.new .num{{font-size:122px;font-weight:650;letter-spacing:-4px;line-height:.92;color:#fff}}
.new .unit{{font-size:21px;color:#dbe7ff}}
.arrow{{align-self:center;text-align:center;color:var(--muted);font-size:34px}}
.tiles{{display:grid;grid-template-rows:1fr 1fr;gap:20px;margin-left:16px}}
.tile{{background:var(--panel);border-radius:18px;padding:20px 28px;display:flex;flex-direction:column;justify-content:center}}
.tile .lab{{font-size:18px;color:var(--muted)}}
.tile .v{{font-size:38px;font-weight:650;margin-top:4px;letter-spacing:-.5px}}
.tile .v small{{font-size:20px;font-weight:400;color:var(--muted);letter-spacing:0;margin-left:8px}}
.depth{{background:var(--panel);border-radius:18px;margin-top:28px;padding:26px 34px 22px}}
.depth .head{{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:12px}}
.depth .head b{{font-size:21px;font-weight:600}}
.depth .head span{{font-size:19px;color:var(--ink2)}}
.row{{display:grid;grid-template-columns:150px 1fr;align-items:center;height:56px}}
.size{{font-size:21px;color:var(--ink2);font-variant-numeric:tabular-nums;text-align:right;padding-right:22px}}
.track{{display:flex;align-items:center;border-left:1px solid var(--rule);height:100%}}
.bar{{height:18px;background:var(--blue);border-radius:0 4px 4px 0}}
.val{{font-size:21px;font-weight:600;margin-left:12px;font-variant-numeric:tabular-nums}}
footer{{position:absolute;left:72px;right:72px;bottom:26px;font-size:16.5px;color:var(--muted);display:flex;justify-content:space-between}}
</style></head><body>
<header><h1>GLM-5.3 Flash on one GB10</h1><span>EXL3 2.05 bpw · TensorFold · 262K context</span></header>
<div class="top">
 <div class="box old"><div class="lab">Previous deployment · decode</div><div class="num">{BASELINE:.2f}</div><div class="unit">tok/s</div></div>
 <div class="arrow">→</div>
 <div class="box new"><div class="lab">TensorFold · decode</div><div class="num">{TENSORFOLD:.2f}</div><div class="unit">tok/s · {ratio:.2f}× · +{100*(ratio-1):.0f}%</div></div>
 <div class="tiles">
  <div class="tile"><div class="lab">Context</div><div class="v">262,144 <small>tokens</small></div></div>
  <div class="tile"><div class="lab">Next turn · 11K-token chat</div><div class="v">2.1 s <small>was 47.6 s</small></div></div>
 </div>
</div>
<div class="depth">
 <div class="head"><b>Decode by prompt size · tok/s</b><span>5 of 5 planted codes found at every size</span></div>
 {bars}
</div>
<footer><span>same checkpoint · four fixed prompts, 400 tokens, temperature 0 · prompt sizes: 512 tokens × 3</span><span>github.com/sxuff/glm53-flash-single-gb10</span></footer>
</body></html>"""
 open(dst,'w',encoding='utf-8',newline='\n').write(html)
if __name__=='__main__':main(sys.argv[1],sys.argv[2])
