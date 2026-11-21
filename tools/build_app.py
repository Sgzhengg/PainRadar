"""Build a single-file interactive UI from one or more databases.

    python tools/build_app.py --db var/gold200.db --db var/gold.db --out reports/app.html

The output embeds the run payload as JSON, so it works offline and can be
screenshotted headlessly. No server, no external assets.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from painradar.appdata import build_payload  # noqa: E402
from painradar.store import Store  # noqa: E402

TEMPLATE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PainRadar · 机会雷达</title>
<style>
:root{--ink:#111827;--muted:#6b7280;--line:#e5e7eb;--bg:#f3f4f6;--card:#fff;--brand:#4f46e5}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
.top{background:linear-gradient(120deg,#1e1b4b,#4338ca 60%,#6366f1);color:#fff;padding:22px 28px}
.top h1{margin:0;font-size:22px}
.top .meta{opacity:.8;font-size:12px;margin-top:4px}
.tabs{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}
.tab{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.25);color:#fff;
border-radius:999px;padding:6px 14px;cursor:pointer;font-size:13px}
.tab.on{background:#fff;color:#3730a3;font-weight:600}
.stats{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}
.stat{background:rgba(255,255,255,.12);border-radius:10px;padding:6px 12px;font-size:12px}
.stat b{font-size:15px;margin-left:4px}
.wrap{display:grid;grid-template-columns:250px 1fr;gap:18px;padding:20px 24px 60px;max-width:1400px;margin:0 auto}
.side{position:sticky;top:16px;align-self:start}
.panel{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px}
.panel h3{margin:0 0 10px;font-size:13px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}
.field{margin-bottom:14px}
.field label{display:block;font-size:12px;color:var(--muted);margin-bottom:6px}
select,input[type=search]{width:100%;padding:8px 10px;border:1px solid var(--line);border-radius:9px;font-size:13px;background:#fff}
input[type=range]{width:100%}
.chk{display:flex;align-items:center;gap:8px;font-size:13px;padding:3px 0;cursor:pointer}
.cards{display:grid;gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px;cursor:pointer;transition:.15s}
.card:hover{border-color:#c7d2fe;box-shadow:0 6px 18px rgba(79,70,229,.10)}
.card .row{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}
.card h2{margin:0;font-size:17px}
.tier{font-size:12px;font-weight:700;padding:3px 10px;border-radius:999px;white-space:nowrap}
.tier.强{background:#ccfbf1;color:#0f766e}.tier.中{background:#fef3c7;color:#b45309}.tier.弱{background:#eef2ff;color:#6b7280}
.line{color:#374151;margin:8px 0 10px}
.nums{display:flex;gap:18px;color:var(--muted);font-size:12px}
.nums b{color:var(--ink);font-size:16px;margin-right:3px}
.empty{padding:40px;text-align:center;color:var(--muted)}
.drawer{position:fixed;inset:0;background:rgba(17,24,39,.45);display:none;z-index:20}
.drawer.open{display:block}
.sheet{position:absolute;right:0;top:0;bottom:0;width:min(620px,92vw);background:#fff;overflow:auto;padding:24px 26px}
.sheet h2{margin:0 0 4px;font-size:20px}
.close{position:absolute;right:18px;top:14px;border:none;background:none;font-size:22px;cursor:pointer;color:var(--muted)}
.quote{border-left:3px solid #c7d2fe;background:#f8fafc;padding:10px 14px;border-radius:0 8px 8px 0;margin:10px 0}
.quote .m{color:var(--muted);font-size:12px}
.factor{display:flex;gap:10px;align-items:center;margin:4px 0;font-size:12px}
.factor .n{width:76px;color:var(--muted)}
.factor .t{flex:1;height:6px;background:#eef0f5;border-radius:999px;overflow:hidden}
.factor .f{height:100%;background:linear-gradient(90deg,#6366f1,#22d3ee);display:block}
.factor .v{width:30px;text-align:right;color:var(--muted)}
.kv{display:grid;grid-template-columns:88px 1fr;gap:6px 14px;font-size:13px;margin:12px 0}
.kv .k{color:var(--muted)}
a{color:#4338ca}
.warn{background:#fef2f2;color:#b91c1c;border-radius:8px;padding:8px 12px;font-size:12px;margin:10px 0}
@media(max-width:860px){.wrap{grid-template-columns:1fr}.side{position:static}}
</style></head><body>
<div class="top">
  <h1>PainRadar · 机会雷达</h1>
  <div class="meta" id="meta"></div>
  <div class="tabs" id="tabs"></div>
  <div class="stats" id="stats"></div>
</div>
<div class="wrap">
  <div class="side"><div class="panel">
    <h3>筛选</h3>
    <div class="field"><label>机会等级</label>
      <select id="tier"><option value="">全部</option><option>强</option><option>中</option><option>弱</option></select>
    </div>
    <div class="field"><label>最低痛感 <span id="painv">0</span></label>
      <input type="range" id="pain" min="0" max="100" value="0" step="5">
    </div>
    <div class="field"><label>场景</label><div id="scenes"></div></div>
    <div class="field"><label>搜索证据</label>
      <input type="search" id="q" placeholder="关键词，如 pump / 噪音">
    </div>
  </div></div>
  <div><div class="cards" id="cards"></div></div>
</div>
<div class="drawer" id="drawer"><div class="sheet" id="sheet"></div></div>
<script id="payload" type="application/json">__PAYLOAD__</script>
<script>
const DATA = JSON.parse(document.getElementById('payload').textContent);
let current = 0, activeScenes = new Set();
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const money = v => v >= 1e8 ? `$${(v/1e8).toFixed(2)} 亿` : v >= 1e4 ? `$${(v/1e4).toFixed(1)} 万` : `$${Math.round(v)}`;
function run() { return DATA.runs[current]; }
function renderTabs() {
  $('#tabs').innerHTML = DATA.runs.map((r,i) =>
    `<div class="tab ${i===current?'on':''}" onclick="selectRun(${i})">${esc(r.category_name)}</div>`).join('');
}
function selectRun(i){ current=i; activeScenes.clear(); $('#pain').value=0; $('#tier').value=''; $('#q').value=''; renderAll(); }
function renderStats() {
  const s = run().stats;
  $('#meta').textContent = `运行 ${run().run_id} · ${run().created_at}`;
  $('#stats').innerHTML = [
    ['扫描评论', s.items], ['痛点原子', s.atoms], ['机会簇', s.clusters],
    ['噪声率', (s.noise_rate*100).toFixed(0)+'%'], ['L2+ 证据', (s.l2_share*100).toFixed(0)+'%'],
    ['抽取器', s.extractor]
  ].map(([k,v]) => `<div class="stat">${k}<b>${esc(v)}</b></div>`).join('');
}
function baseScene(t){ return String(t).split(' · ')[0]; }
function renderScenes() {
  const names = [...new Set(run().opportunities.map(o => baseScene(o.title)))];
  $('#scenes').innerHTML = names.map(n =>
    `<label class="chk"><input type="checkbox" value="${esc(n)}" ${activeScenes.has(n)?'checked':''}
     onchange="toggleScene(this)">${esc(n)}</label>`).join('');
}
function toggleScene(el){ el.checked ? activeScenes.add(el.value) : activeScenes.delete(el.value); renderCards(); }
function filtered() {
  const tier = $('#tier').value, minPain = +$('#pain').value, q = $('#q').value.trim().toLowerCase();
  return run().opportunities.filter(o => {
    if (tier && o.opportunity_tier !== tier) return false;
    if (o.pain !== null && o.pain < minPain) return false;
    if (activeScenes.size && !activeScenes.has(baseScene(o.title))) return false;
    if (q && !(o.members.some(m => m.quote.toLowerCase().includes(q)) ||
               (o.one_liner||'').toLowerCase().includes(q))) return false;
    return true;
  });
}
function renderCards() {
  const list = filtered();
  $('#painv').textContent = $('#pain').value;
  if (!list.length) { $('#cards').innerHTML = '<div class="empty">没有符合筛选的机会卡</div>'; return; }
  $('#cards').innerHTML = list.map(o => {
    const idx = run().opportunities.indexOf(o);
    return `<div class="card" onclick="openCard(${idx})">
      <div class="row"><h2>${esc(o.title)}</h2><span class="tier ${esc(o.opportunity_tier)}">机会 ${esc(o.opportunity_tier)}</span></div>
      <div class="line">${esc(o.one_liner)}</div>
      <div class="nums">
        <span><b>${o.pain ?? '—'}</b>痛感</span>
        <span><b>${o.opportunity ?? '—'}</b>机会</span>
        <span><b>${o.member_count}</b>证据</span>
        <span><b>${money(o.market_mid)}</b>SOM 中值</span>
      </div></div>`;
  }).join('');
}
const FACTORS = {frequency:'频次',breadth:'人群广度',intensity:'情绪强度',cost_clarity:'代价清晰度',
persistence:'持续性',supply_gap:'供给缺口',wtp:'付费信号',serviceability:'可服务性',timing:'时机',competition:'竞争密度'};
function openCard(i) {
  const o = run().opportunities[i];
  const bars = Object.entries(FACTORS).filter(([k]) => o.factors[k] !== undefined && k !== 'wtp_coverage')
    .map(([k,label]) => { const v = o.factors[k];
      return `<div class="factor"><span class="n">${label}</span><span class="t"><span class="f" style="width:${Math.round(v*100)}%"></span></span><span class="v">${v.toFixed(2)}</span></div>`; }).join('');
  const warn = (o.members.length && (o.ladder.L2||0)+(o.ladder.L3||0)+(o.ladder.L4||0) < o.members.length*0.2)
    ? '<div class="warn">该簇以纯抱怨（L1）为主，先做人群验证，不要直接立项。</div>' : '';
  const quotes = o.members.map(m => `<div class="quote">${esc(m.quote)}
    <div class="m">${esc(m.platform)} · ${esc(m.app)} · ${esc(m.published_at)} · 置信度 ${m.confidence} · ${esc(m.level)}
    ${m.url ? ` · <a href="${esc(m.url)}" target="_blank" rel="noreferrer">原文</a>` : ''}</div></div>`).join('') || '<div class="empty">无证据</div>';
  $('#sheet').innerHTML = `<button class="close" onclick="closeCard()">×</button>
    <h2>${esc(o.title)}</h2><div class="line">${esc(o.one_liner)}</div>
    <div class="nums"><span><b>${o.pain ?? '—'}</b>痛感</span><span><b>${o.opportunity ?? '—'}</b>机会</span>
    <span><b>${o.member_count}</b>证据</span></div>
    ${warn}
    <div class="kv"><span class="k">人群</span><span>${esc(o.persona || '待补')}</span>
      <span class="k">现有替代</span><span>${esc(o.workaround || '未观察到明确替代')}</span>
      <span class="k">梯子</span><span>${Object.entries(o.ladder).map(([k,v])=>k+' '+v).join(' / ') || '—'}</span>
      <span class="k">SOM</span><span>${money(o.market_low)} – ${money(o.market_high)}（中值 ${money(o.market_mid)}）</span>
      <span class="k">证伪条件</span><span>${esc(o.falsifier)}</span></div>
    <h3 style="margin:18px 0 6px;font-size:13px;color:#6b7280">评分因子</h3>${bars}
    <h3 style="margin:18px 0 6px;font-size:13px;color:#6b7280">证据（${o.member_count}）</h3>${quotes}`;
  $('#drawer').classList.add('open');
}
function closeCard(){ $('#drawer').classList.remove('open'); }
$('#drawer').addEventListener('click', e => { if (e.target.id === 'drawer') closeCard(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeCard(); });
['tier','pain','q'].forEach(id => document.getElementById(id).addEventListener('input', renderCards));
function renderAll(){ renderTabs(); renderStats(); renderScenes(); renderCards(); }
window.addEventListener('hashchange', () => {
  const p = new URLSearchParams(location.hash.slice(1));
  if (p.has('cat')) selectRun(+p.get('cat'));
  if (p.has('scene')) { activeScenes.add(p.get('scene')); renderScenes(); renderCards(); }
  if (p.has('card')) openCard(+p.get('card'));
});
renderAll();
const init = new URLSearchParams(location.hash.slice(1));
if (init.has('cat')) selectRun(+init.get('cat'));
if (init.has('scene')) { activeScenes.add(init.get('scene')); renderScenes(); renderCards(); }
if (init.has('card')) openCard(+init.get('card'));
</script></body></html>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", action="append", required=True)
    ap.add_argument("--out", default="reports/app.html")
    args = ap.parse_args()

    stores = [Store(p) for p in args.db]
    payload = build_payload([(s, None) for s in stores])
    text = (
        TEMPLATE.replace("__PAYLOAD__", json.dumps(payload, ensure_ascii=False))
        .replace("__GENERATED__", datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M"))
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"written {out} ({len(text) / 1024:.0f} KB, {len(payload['runs'])} runs)")
    for s in stores:
        s.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
