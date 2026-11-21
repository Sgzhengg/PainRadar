/* PainRadar UI — talks to /api/*, no build step. */
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const money = (v) => (v >= 1e8 ? `$${(v / 1e8).toFixed(2)} 亿` : v >= 1e4 ? `$${(v / 1e4).toFixed(1)} 万` : `$${Math.round(v ?? 0)}`);
const baseScene = (t) => String(t).split(" · ")[0];

const FACTORS = {
  frequency: "频次", breadth: "人群广度", intensity: "情绪强度", cost_clarity: "代价清晰度",
  persistence: "持续性", supply_gap: "供给缺口", wtp: "付费信号", serviceability: "可服务性",
  timing: "时机", competition: "竞争密度",
};

const state = {
  runs: [], detail: null, category: null, runId: null,
  scenes: new Set(), members: [], total: 0, cluster: null, loading: false,
};

async function api(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (el.hidden = true), 2600);
}

function categories() {
  const seen = new Map();
  for (const r of state.runs) {
    if (r.latest_for_category && !seen.has(r.category)) seen.set(r.category, r);
  }
  for (const r of state.runs) {
    if (!seen.has(r.category)) seen.set(r.category, r);
  }
  return [...seen.values()];
}

function runsFor(category) {
  return state.runs.filter((r) => r.category === category)
    .sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
}

function renderTabs() {
  const discoverTab = `<button class="tab ${state.mode === "discover" ? "on" : ""}" data-discover="1">发现</button>`;
  const catTabs = categories().map((r) =>
    `<button class="tab ${state.mode === "category" && r.category === state.category ? "on" : ""}" data-cat="${esc(r.category)}">${esc(r.category_name)}</button>`
  ).join("");
  $("#tabs").innerHTML = discoverTab + catTabs;
  $("#tabs").querySelectorAll(".tab").forEach((el) =>
    el.addEventListener("click", () => {
      if (el.dataset.discover) { showDiscovery(); return; }
      const cat = el.dataset.cat;
      const latest = runsFor(cat)[0];
      if (latest) selectRun(latest.run_id);
    })
  );
}

function renderRunPick() {
  const list = runsFor(state.category);
  $("#runpick").innerHTML = list.map((r) =>
    `<option value="${esc(r.run_id)}" ${r.run_id === state.runId ? "selected" : ""}>
      ${esc(r.created_at.slice(0, 16))} · ${esc(r.extractor)} · ${r.items} 条
    </option>`
  ).join("");
}

function renderStats() {
  const d = state.detail;
  if (!d) return;
  $("#meta").textContent = `运行 ${d.run_id} · 生成 ${d.created_at}`;
  const s = d.stats;
  const cells = [
    ["扫描评论", s.items], ["痛点原子", s.atoms], ["机会簇", s.clusters],
    ["噪声率", `${(s.noise_rate * 100).toFixed(0)}%`], ["L2+ 证据", `${(s.l2_share * 100).toFixed(0)}%`],
    ["抽取器", s.extractor],
  ];
  $("#stats").innerHTML = cells.map(([k, v]) => `<div class="stat">${k}<b>${esc(v)}</b></div>`).join("");
}

function renderScenes() {
  if (!state.detail) return;
  const names = [...new Set(state.detail.opportunities.map((o) => baseScene(o.title)))];
  for (const n of [...state.scenes]) if (!names.includes(n)) state.scenes.delete(n);
  $("#scenes").innerHTML = names.map((n) =>
    `<label class="chk"><input type="checkbox" value="${esc(n)}" ${state.scenes.has(n) ? "checked" : ""}>${esc(n)}</label>`
  ).join("");
  $("#scenes").querySelectorAll("input").forEach((el) =>
    el.addEventListener("change", () => {
      el.checked ? state.scenes.add(el.value) : state.scenes.delete(el.value);
      renderCards();
    })
  );
}

function filtered() {
  if (!state.detail) return [];
  const tier = $("#tier").value;
  const minPain = +$("#pain").value;
  const q = $("#q").value.trim().toLowerCase();
  return state.detail.opportunities.filter((o) => {
    if (tier && o.opportunity_tier !== tier) return false;
    if (o.pain !== null && o.pain < minPain) return false;
    if (state.scenes.size && !state.scenes.has(baseScene(o.title))) return false;
    if (q && !(o.members.some((m) => m.quote.toLowerCase().includes(q)) ||
      (o.one_liner || "").toLowerCase().includes(q))) return false;
    return true;
  });
}

function renderCards() {
  const list = filtered();
  $("#painv").textContent = $("#pain").value;
  if (!list.length) {
    $("#cards").innerHTML = `<div class="empty">没有符合筛选的机会卡</div>`;
    return;
  }
  $("#cards").innerHTML = list.map((o) => `
    <article class="card" data-cluster="${esc(o.cluster_id)}">
      <div class="row"><h2>${esc(o.title)}</h2><span class="tier ${esc(o.opportunity_tier)}">机会 ${esc(o.opportunity_tier)}</span></div>
      <div class="line">${esc(o.one_liner)}</div>
      <div class="nums">
        <span><b>${o.pain ?? "—"}</b>痛感</span>
        <span><b>${o.opportunity ?? "—"}</b>机会</span>
        <span><b>${o.member_count}</b>证据</span>
        <span><b>${money(o.market_mid)}</b>SOM 中值</span>
      </div>
      ${o.solo_fit && o.solo_fit.level
        ? `<div class="solo ${o.solo_fit.level === "低" ? "ok" : o.solo_fit.level === "中" ? "mid" : "hard"}">⚡ ${esc(o.solo_fit.mvp_days)} 可做 · ${esc(o.solo_fit.form)} · ${esc(o.solo_fit.monetization)}</div>`
        : ""}
    </article>`).join("");
  $("#cards").querySelectorAll(".card").forEach((el) =>
    el.addEventListener("click", () => openCard(el.dataset.cluster))
  );
}

function factorBars(o) {
  return Object.entries(FACTORS)
    .filter(([k]) => o.factors[k] !== undefined && k !== "wtp_coverage")
    .map(([k, label]) => {
      const v = o.factors[k];
      return `<div class="factor"><span class="n">${label}</span>
        <span class="t"><span class="f" style="width:${Math.round(v * 100)}%"></span></span>
        <span class="v">${v.toFixed(2)}</span></div>`;
    }).join("");
}

function quoteHtml(m) {
  return `<div class="quote">${esc(m.quote)}
    <div class="m">${esc(m.platform)} · ${esc(m.app)} · ${esc(m.published_at)} · 置信度 ${m.confidence} · ${esc(m.level)}${m.likes ? ` · 👍 ${m.likes}` : ""}
    ${m.url ? ` · <a href="${esc(m.url)}" target="_blank" rel="noreferrer">原文</a>` : ""}</div></div>`;
}

function drawerShell(o) {
  const warn = o.members.length && (o.ladder.L2 || 0) + (o.ladder.L3 || 0) + (o.ladder.L4 || 0) < o.members.length * 0.2
    ? `<div class="warn">该簇以纯抱怨（L1）为主，先做人群验证，不要直接立项。</div>` : "";
  return `<button class="close" id="close">×</button>
    <h2>${esc(o.title)}</h2>
    <div class="line">${esc(o.one_liner)}</div>
    <div class="nums"><span><b>${o.pain ?? "—"}</b>痛感</span><span><b>${o.opportunity ?? "—"}</b>机会</span>
      <span><b>${o.member_count}</b>证据</span></div>
    ${warn}
    <div class="kv">
      <span class="k">人群</span><span>${esc(o.persona || "待补")}</span>
      <span class="k">现有替代</span><span>${esc(o.workaround || "未观察到明确替代")}</span>
      <span class="k">梯子</span><span>${Object.entries(o.ladder).map(([k, v]) => k + " " + v).join(" / ") || "—"}</span>
      <span class="k">一人开发</span><span>${o.solo_fit && o.solo_fit.level
        ? `${esc(o.solo_fit.level)}难度 · ${esc(o.solo_fit.mvp_days)} · ${esc(o.solo_fit.form)} · ${esc(o.solo_fit.monetization)}（${esc(o.solo_fit.note || "")}）`
        : "未评估"}</span>
      <span class="k">SOM</span><span>${money(o.market_low)} – ${money(o.market_high)}（中值 ${money(o.market_mid)}）</span>
      <span class="k">证伪条件</span><span>${esc(o.falsifier)}</span>
    </div>
    <h3 class="sec">评分因子</h3>${factorBars(o)}
    <div class="outreach"><a class="btn" href="/api/runs/${state.runId}/clusters/${encodeURIComponent(o.cluster_id)}/outreach.csv">⬇ 导出种子用户外联表 (CSV)</a></div>
    <h3 class="sec">证据（<span id="mcount">${state.members.length}</span>/${state.total}）</h3>
    <div id="quotes">${state.members.map(quoteHtml).join("")}</div>
    <div id="morewrap">${state.members.length < state.total ? `<button class="more" id="more">加载更多证据</button>` : ""}</div>`;
}

async function loadMore() {
  const o = state.detail.opportunities.find((x) => x.cluster_id === state.cluster);
  if (!o) return;
  const data = await api(`/api/runs/${state.runId}/members?cluster_id=${encodeURIComponent(state.cluster)}&offset=${state.members.length}&limit=50`);
  state.members = state.members.concat(data.items);
  state.total = data.total;
  $("#quotes").innerHTML = state.members.map(quoteHtml).join("");
  $("#mcount").textContent = state.members.length;
  if (state.members.length >= state.total) $("#morewrap").innerHTML = "";
  else $("#more").addEventListener("click", loadMore);
}

function openCard(clusterId) {
  const o = state.detail.opportunities.find((x) => x.cluster_id === clusterId);
  if (!o) return;
  state.cluster = clusterId;
  state.members = o.members.slice();
  state.total = o.member_count;
  $("#sheet").innerHTML = drawerShell(o);
  $("#drawer").hidden = false;
  $("#close").addEventListener("click", closeCard);
  const more = $("#more");
  if (more) more.addEventListener("click", loadMore);
  const hash = new URLSearchParams({ run: state.runId, cluster: clusterId });
  history.replaceState(null, "", `#${hash}`);
}

function closeCard() {
  $("#drawer").hidden = true;
  state.cluster = null;
  history.replaceState(null, "", `#run=${state.runId}`);
}

async function selectRun(runId, clusterId = null) {
  state.mode = "category";
  document.body.classList.remove("discover");
  state.runId = runId;
  toast("加载中…");
  try {
    state.detail = await api(`/api/runs/${encodeURIComponent(runId)}?max_members=12`);
  } catch (err) {
    toast(`加载失败：${err.message}`);
    return;
  }
  state.category = state.detail.category;
  $("#toast").hidden = true;
  renderTabs();
  renderRunPick();
  renderStats();
  renderScenes();
  renderCards();
  if (clusterId) openCard(clusterId);
  else history.replaceState(null, "", `#run=${runId}`);
}

async function refreshRuns() {
  const data = await api("/api/runs");
  state.runs = data.runs || [];
}

async function openRunModal() {
  $("#runstate").textContent = "";
  $("#runstate").className = "runstate";
  $("#runstart").disabled = false;
  $("#runmodal").hidden = false;
  const sel = $("#runcat");
  sel.innerHTML = `<option value="">加载中…</option>`;
  try {
    const { categories } = await api("/api/categories");
    const usable = categories.filter((c) => c.items > 0);
    sel.innerHTML = (usable.length ? usable : categories).map((c) =>
      `<option value="${esc(c.category)}" ${c.items ? "" : "disabled"}>
        ${esc(c.name)}${c.items ? `（${c.items} 条）` : "（无数据）"}
      </option>`
    ).join("") || `<option value="">没有可用品类</option>`;
    const desired = state.pendingCategory || state.category;
    const current = desired && usable.some((c) => c.category === desired) ? desired : "";
    if (current) sel.value = current;
    state.pendingCategory = null;
  } catch (err) {
    sel.innerHTML = `<option value="">品类加载失败</option>`;
    $("#runstate").className = "runstate err";
    $("#runstate").textContent = `无法读取品类：${err.message}`;
  }
}

function closeRunModal() {
  $("#runmodal").hidden = true; // a running job keeps polling in the background
}

function fmtElapsed(iso) {
  const ms = Date.now() - new Date(iso).getTime();
  const s = Math.max(0, Math.round(ms / 1000));
  return s < 60 ? `${s} 秒` : `${Math.floor(s / 60)} 分 ${s % 60} 秒`;
}

async function pollJob(jobId) {
  const btn = $("#runstart");
  btn.disabled = true;
  const tick = setInterval(() => {
    const el = $("#runstate");
    if (el.dataset.started) el.textContent = `运行中… 已用 ${fmtElapsed(el.dataset.started)}`;
  }, 1000);
  try {
    for (;;) {
      const { job } = await api(`/api/run/${jobId}`);
      const el = $("#runstate");
      if (job.status === "queued" || job.status === "running") {
        el.dataset.started = job.started_at;
        el.textContent = job.status === "queued" ? "排队中…" : `运行中… 已用 ${fmtElapsed(job.started_at)}`;
        await new Promise((r) => setTimeout(r, 1500));
        continue;
      }
      clearInterval(tick);
      if (job.status === "done") {
        el.className = "runstate ok";
        el.textContent = `完成：${job.atoms ?? (job.stats && job.stats.atoms) ?? "?"} 个原子，${job.run_id}`;
        await refreshRuns();
        renderTabs();
        renderRunPick();
        setTimeout(async () => {
          $("#runmodal").hidden = true;
          btn.disabled = false;
          await selectRun(job.run_id);
        }, 600);
      } else {
        el.className = "runstate err";
        el.textContent = `失败：${job.error || "未知错误"}`;
        btn.disabled = false;
      }
      return;
    }
  } catch (err) {
    clearInterval(tick);
    const el = $("#runstate");
    el.className = "runstate err";
    el.textContent = `状态查询失败：${err.message}`;
    btn.disabled = false;
  }
}

async function startRun() {
  const category = $("#runcat").value;
  const extractor = document.querySelector('input[name="extractor"]:checked').value;
  const el = $("#runstate");
  if (!category) {
    el.className = "runstate err";
    el.textContent = "没有可用品类：先抓取或导入评论。";
    return;
  }
  el.className = "runstate";
  el.textContent = "提交中…";
  el.dataset.started = new Date().toISOString();
  await Promise.resolve();
  try {
    const res = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category, extractor }),
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail || res.status);
    pollJob(body.job.job_id);
  } catch (err) {
    el.className = "runstate err";
    el.textContent = `无法启动：${err.message}`;
  }
}

async function restoreActiveJob() {
  try {
    const { job } = await api("/api/run/active");
    if (!job) return;
    openRunModal();
    $("#runcat").value = job.category;
    document.querySelector(`input[name="extractor"][value="${job.extractor}"]`).checked = true;
    pollJob(job.job_id);
  } catch {
    /* ignore */
  }
}

$("#runbtn").addEventListener("click", openRunModal);
$("#runclose").addEventListener("click", closeRunModal);
$("#runstart").addEventListener("click", startRun);
$("#runmodal").addEventListener("click", (e) => { if (e.target.id === "runmodal") closeRunModal(); });

function openNewCat() {
  $("#newcatstate").textContent = "";
  $("#newcatstate").className = "runstate";
  $("#newcatstart").disabled = false;
  $("#newcatname").value = "";
  $("#newcatterm").value = "";
  $("#newcatmodal").hidden = false;
  $("#newcatname").focus();
}

function closeNewCat() {
  $("#newcatmodal").hidden = true;
}

async function searchNewCatApps() {
  const term = $("#newcatterm").value.trim();
  const el = $("#newcatstate");
  if (!term) {
    el.className = "runstate err";
    el.textContent = "先填英文搜索词，再搜索候选 App。";
    return;
  }
  el.className = "runstate";
  el.textContent = "搜索中…";
  $("#newcatstart").disabled = true;
  try {
    const { apps } = await api(`/api/apps/search?term=${encodeURIComponent(term)}&limit=8`);
    state.newcatApps = apps || [];
    if (!state.newcatApps.length) {
      el.textContent = "没有搜到 App，换个英文词试试。";
      $("#newcatapps").innerHTML = "";
      return;
    }
    $("#newcatapps").innerHTML = state.newcatApps.map((a, i) => `
      <label class="chk appchk">
        <input type="checkbox" value="${i}" checked>
        <span>${esc(a.name)} <span class="muted">· ${esc(a.genre || "未分类")} · ${a.rating_count || 0} 评分</span></span>
      </label>`).join("");
    el.className = "runstate ok";
    el.textContent = `找到 ${state.newcatApps.length} 个候选，请确认哪些属于「${$("#newcatname").value.trim() || "该品类"}」。`;
    $("#newcatstart").disabled = false;
  } catch (err) {
    el.className = "runstate err";
    el.textContent = `搜索失败：${err.message}`;
  }
}

async function startNewCat() {
  const name = $("#newcatname").value.trim();
  const term = $("#newcatterm").value.trim();
  const pages = +$("#newcatpages").value;
  const el = $("#newcatstate");
  if (!name || !term) {
    el.className = "runstate err";
    el.textContent = "品类名和搜索词都要填。";
    return;
  }
  const picked = [...document.querySelectorAll("#newcatapps input:checked")]
    .map((el) => state.newcatApps[+el.value])
    .filter(Boolean);
  if (!picked.length) {
    el.className = "runstate err";
    el.textContent = "至少勾选一个属于该品类的 App。";
    return;
  }
  el.className = "runstate";
  el.textContent = "正在创建品类并抓取评论…";
  $("#newcatstart").disabled = true;
  try {
    const res = await fetch("/api/categories/custom", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name, term, pages,
        apps: picked.map((a) => ({ app_id: String(a.app_id), name: a.name })),
      }),
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail || res.status);
    const apps = (body.apps || []).map((a) => a.name).join("、");
    el.textContent = `已确认：${apps}。正在抓取评论…`;
    let job = body.job;
    for (;;) {
      const polled = await api(`/api/run/${job.job_id}`);
      job = polled.job;
      if (job.status === "queued" || job.status === "running") {
        const secs = Math.max(0, Math.round((Date.now() - new Date(job.started_at).getTime()) / 1000));
        el.textContent = `抓取中… ${secs} 秒（${apps}）`;
        await new Promise((r) => setTimeout(r, 1500));
        continue;
      }
      break;
    }
    if (job.status === "done") {
      const n = job.stats ? job.stats.inserted : "?";
      el.className = "runstate ok";
      el.textContent = `完成：抓取 ${n} 条评论。现在可以运行「${name}」。`;
      state.pendingCategory = body.category;
      await refreshRuns();
      setTimeout(() => {
        closeNewCat();
        $("#newcatstart").disabled = false;
        openRunModal();
      }, 800);
    } else {
      el.className = "runstate err";
      el.textContent = `抓取失败：${job.error || "未知错误"}`;
      $("#newcatstart").disabled = false;
    }
  } catch (err) {
    el.className = "runstate err";
    el.textContent = `失败：${err.message}`;
    $("#newcatstart").disabled = false;
  }
}

$("#newcatbtn").addEventListener("click", openNewCat);
$("#ddbtn").addEventListener("click", ddOpen);
$("#ddclose").addEventListener("click", ddClose);
$("#ddplan").addEventListener("click", ddPlan);
$("#ddrun").addEventListener("click", ddRun);
$("#newcatclose").addEventListener("click", closeNewCat);
$("#newcatstart").addEventListener("click", startNewCat);
$("#newcatsearch").addEventListener("click", searchNewCatApps);
$("#newcatmodal").addEventListener("click", (e) => { if (e.target.id === "newcatmodal") closeNewCat(); });

async function showDiscovery(corpus) {
  state.mode = "discover";
  document.body.classList.add("discover");
  state.discoveryCorpus = corpus || state.discoveryCorpus || "main";
  toast("加载发现结果…");
  try {
    state.discovery = await api(`/api/discovery?corpus=${encodeURIComponent(state.discoveryCorpus)}`);
  } catch (err) {
    $("#discbar").hidden = false;
    $("#discbar").innerHTML = `<span class="state">语料 ${esc(state.discoveryCorpus)}：${esc(err.message)}</span>`;
    $("#cards").innerHTML = `<div class="empty">这个语料还没有快照。点“生成快照”，或运行<br><code>python run.py discover --canonical --db var\llm_full.db</code></div>`;
    await renderCorpusBar();
    renderTabs();
    return;
  }
  $("#toast").hidden = true;
  await renderCorpusBar();
  renderTabs();
  const snap = state.discovery;
  $("#meta").textContent = `需求发现快照 · 来源 ${snap.source ?? "?"} · 生成于 ${snap.generated_at} · 需求表 v${snap.taxonomy_version ?? "?"} · 覆盖 ${Math.round((snap.coverage ?? 0) * 100)}%`;
  const chips = [
    ["需求数", snap.demands.length],
    ["证据总量", snap.demands.reduce((a, d) => a + d.size, 0)],
    ["跨域需求", snap.demands.filter((d) => Object.keys(d.domains || {}).length > 1).length],
    ["语料", snap.source || ""],
  ];
  if (snap.coverage !== null && snap.coverage !== undefined) {
    chips.splice(3, 0, ["需求表覆盖率", `${Math.round(snap.coverage * 100)}%（${snap.unassigned ?? "?"} 簇未归类）`]);
  }
  $("#stats").innerHTML = chips.map(([k, v]) => `<div class="stat">${k}<b>${esc(v)}</b></div>`).join("");
  renderDiscoveryCards();
  const dparams = new URLSearchParams(location.hash.slice(1));
  if (dparams.has("demand")) openDemand(+dparams.get("demand"));
  history.replaceState(null, "", "#discover");
}


async function renderCorpusBar() {
  const bar = $("#discbar");
  bar.hidden = false;
  let corpora = state.corpora;
  if (!corpora) {
    try {
      corpora = (await api("/api/discovery/corpora")).corpora;
      state.corpora = corpora;
    } catch (err) {
      corpora = [];
    }
  }
  const options = corpora
    .map((c) => `<option value="${esc(c.name)}"${c.name === state.discoveryCorpus ? " selected" : ""}>${esc(c.label)}${c.ready ? "" : "（未生成）"}</option>`)
    .join("");
  bar.innerHTML =
    `<label>语料 <select id="corpuspick">${options}</select></label>` +
    `<button id="corpusbuild">生成快照</button>` +
    `<span class="state" id="corpusstate"></span>`;
  $("#corpuspick").addEventListener("change", (e) => showDiscovery(e.target.value));
  $("#corpusbuild").addEventListener("click", buildCorpus);
}

async function buildCorpus() {
  const corpus = state.discoveryCorpus;
  const el = $("#corpusstate");
  el.textContent = "生成中，可能需要 1–3 分钟…";
  try {
    const job = await api("/api/discovery/build", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ corpus }),
    });
    for (;;) {
      const s = await api(`/api/discovery/build/${job.job_id}`);
      if (s.status !== "running") {
        if (s.status === "done") {
          el.textContent = `完成：${s.demands} 个需求`;
          state.corpora = null;
          await showDiscovery(corpus);
        } else {
          el.textContent = `失败：${s.error || "未知错误"}`;
        }
        break;
      }
      await new Promise((r) => setTimeout(r, 3000));
    }
  } catch (err) {
    el.textContent = `失败：${err.message}`;
  }
}

function renderDiscoveryCards() {
  const list = state.discovery ? state.discovery.demands : [];
  if (!list.length) {
    $("#cards").innerHTML = `<div class="empty">没有需求</div>`;
    return;
  }
  $("#cards").innerHTML = list.map((d, i) => {
    const domains = Object.keys(d.domains || {});
    return `<article class="card" data-demand="${i}">
      <div class="row"><h2>${esc(d.label)}</h2><span class="tier ${d.score >= 55 ? "强" : "中"}">${d.score} 分</span></div>
      <div class="line">${esc(d.definition || "")}</div>
      <div class="nums">
        <span><b>${d.size}</b>证据</span>
        <span><b>${domains.length}</b>个域</span>
        <span><b>${(d.l2_share * 100).toFixed(0)}%</b>L2+</span>
        <span>${domains.map((x) => `<span class="dom">${esc(x)}</span>`).join(" ")}</span>
      </div>
      ${trendLine(d)}
      ${soloLine(d)}
    </article>`;
  }).join("");
  $("#cards").querySelectorAll(".card").forEach((el) =>
    el.addEventListener("click", () => openDemand(+el.dataset.demand))
  );
}

function trendLine(d) {
  const tr = d.market_trend;
  if (!tr || tr.change_pct === null || tr.change_pct === undefined) return "";
  const v = tr.change_pct;
  const cls = v >= 5 ? "up" : v <= -5 ? "down" : "";
  const sign = v > 0 ? "+" : "";
  const terms = (tr.terms || []).map((x) => esc(x.term)).join(" / ");
  return `<div class="trend ${cls}">市场趋势 ${sign}${v.toFixed(1)}%（Google Trends${terms ? "：" + terms : ""}）</div>`;
}

function soloLine(d) {
  const fit = d.solo_fit;
  if (!fit || fit.total === undefined) return "";
  const cls = fit.total >= 70 ? "good" : fit.total >= 55 ? "mid" : "low";
  return `<div class="solo ${cls}">单人可交付 ${fit.total} ／ 100${fit.summary ? "：" + esc(fit.summary) : ""}</div>`;
}

function openDemand(i) {
  const d = state.discovery.demands[i];
  const domains = Object.entries(d.domains || {}).map(([k, v]) => {
    const who = (d.buyer_by_domain || {})[k] || d.buyer || "买家待补";
    return `<div class="kv"><span class="k">${esc(k)}</span><span>${esc(who)}（${v} 条）</span></div>`;
  }).join("");
  const quotes = (d.examples || []).map((e) => `<div class="quote">${esc(e.quote)}
    <div class="m">${esc(e.domain)} · ${esc(e.app)} · ${esc(e.level)}</div></div>`).join("");
  $("#sheet").innerHTML = `<button class="close" onclick="closeCard()">×</button>
    <h2>${esc(d.label)}</h2>
    <div class="line">${esc(d.definition || "")}</div>
    <div class="nums"><span><b>${d.score}</b>分数</span><span><b>${d.size}</b>证据</span>
      <span><b>${Object.keys(d.domains || {}).length}</b>个域</span></div>
    <h3 class="sec">买家分布</h3>${domains || "<div class='empty'>无</div>"}
    <h3 class="sec">证据</h3>${quotes || "<div class='empty'>无</div>"}
    <h3 class="sec">单人可交付性</h3>${soloBlock(d)}
    <h3 class="sec">解决方案</h3><div id="solbox" class="empty">加载中…</div>`;
  $("#drawer").hidden = false;
  fillSolutions(d.label);
}

function soloBlock(d) {
  const fit = d.solo_fit;
  if (!fit || !fit.scores) return "<div class='empty'>未评分（python run.py solo-fit --attach）</div>";
  const labels = {
    third_party_actionable: "第三方可介入",
    leverage: "能否真解决",
    competition_gap: "竞争空隙",
    software_only: "纯软件",
    zero_onboarding: "零配置",
    no_docs: "无文档依赖",
    low_ops: "少运维",
    frequency: "使用频率",
    self_serve_pay: "自助付费",
  };
  const rows = Object.entries(fit.scores).map(([k, v]) => {
    const width = (v / 5) * 100;
    const cls = v >= 4 ? "good" : v >= 3 ? "mid" : "low";
    return `<div class="fitrow"><span class="fitlabel">${labels[k] || k}</span>
      <span class="fitbar"><i class="${cls}" style="width:${width}%"></i></span>
      <span class="fitval">${v}</span></div>
      <div class="fitwhy">${esc((fit.reasons || {})[k] || "")}</div>`;
  }).join("");
  return `<div class="fithead">总分 <b>${fit.total}</b> / 100</div>${rows}
    <div class="fitwhy">${esc(fit.summary || "")}</div>`;
}

async function fillSolutions(label) {
  const box = document.getElementById("solbox");
  if (!box) return;
  try {
    if (!state.solutions) state.solutions = await api("/api/solutions");
    const entry = state.solutions[label];
    if (!entry || !(entry.solutions || []).length) {
      box.className = "empty";
      box.textContent = "这条需求还没有生成方案（python run.py solve）。";
      return;
    }
    box.className = "";
    const rec = entry.recommended || {};
    const recNote = rec.name
      ? `<div class="recnote">建议先做：<b>${esc(rec.name)}</b> —— ${esc(rec.reason || "")}</div>`
      : "";
    box.innerHTML = recNote + entry.solutions.map((s) => {
      const isRec = rec.name && s.name === rec.name;
      return `
      <div class="sol${isRec ? " rec" : ""}">
        <div class="solhead"><b>${esc(s.name)}</b>
          <span class="solfit">${isRec ? '<span class="badge-rec">建议先做</span> ' : ""}可行性 ${s.feasibility}/5</span></div>
        <div class="solpitch">${esc(s.pitch)}</div>
        <div class="solmeta">${esc(s.buyer)} ｜ ${esc(s.pricing)}</div>
        <div class="solmech">${esc(s.mechanism)}</div>
        <details><summary>MVP 与验证</summary>
          <ul>${(s.mvp || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
          <div class="solval">
            假设：${esc((s.validation || {}).hypothesis || "")}<br>
            实验：${esc((s.validation || {}).experiment || "")}<br>
            阈值：${esc((s.validation || {}).threshold || "")}
          </div>
        </details>
      </div>`;}).join("");
  } catch (err) {
    box.className = "empty";
    box.textContent = `方案加载失败：${err.message}`;
  }
}

async function init() {
  try {
    const data = await api("/api/runs");
    state.runs = data.runs || [];
  } catch (err) {
    toast(`无法连接 API：${err.message}`);
    return;
  }
  if (!state.runs.length) {
    $("#cards").innerHTML = `<div class="empty">数据库里还没有运行记录，先执行 <code>run.py run</code></div>`;
    $("#runbtn").disabled = false;
  $("#newcatbtn").disabled = false;
    return;
  }
  const params = new URLSearchParams(location.hash.slice(1));
  const latest = categories()[0];
  const runId = params.get("run") || latest.run_id;
  if (params.has("discover")) {
    $("#runbtn").disabled = false;
    await showDiscovery();
    return;
  }
  await selectRun(runId, params.get("cluster"));
  $("#runbtn").disabled = false;
  $("#newcatbtn").disabled = false;
  if (params.has("runmodal")) openRunModal();
  if (params.has("deepdive")) {
    ddOpen();
    if (params.get("demo") === "compare") {
      $("#ddmsg").value = "对比 Apple Watch、Kindle 和 VR 头显的弃用原因";
      ddRenderReport({ spec: { product: "Apple Watch vs Kindle vs VR" }, markdown: DD_COMPARE, count: 57, cached: false, series: [] });
      $("#ddstate").className = "runstate ok";
      $("#ddstate").textContent = "示例对比报告（演示用）";
    } else if (params.has("demo")) {
      $("#ddmsg").value = "我想研究 Apple Watch 用户为什么买了之后不用了";
      ddRenderReport({ spec: { product: "Apple Watch" }, markdown: DD_SAMPLE, count: 17, cached: false, series: DD_DEMO_SERIES });
      $("#ddstate").className = "runstate ok";
      $("#ddstate").textContent = "示例报告（演示用）";
    }
    const preset = params.get("msg");
    if (preset) {
      $("#ddmsg").value = preset;
      await ddPlan();
      await ddPreview();
    }
  }
  if (params.has("newcat")) openNewCat();
  restoreActiveJob();
}

["tier", "pain", "q"].forEach((id) =>
  document.getElementById(id).addEventListener("input", renderCards)
);
$("#runpick").addEventListener("change", (e) => selectRun(e.target.value));
$("#drawer").addEventListener("click", (e) => { if (e.target.id === "drawer") closeCard(); });
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") { closeCard(); closeRunModal(); closeNewCat(); }
});
window.addEventListener("hashchange", () => {
  const p = new URLSearchParams(location.hash.slice(1));
  if (p.get("run") && p.get("run") !== state.runId) selectRun(p.get("run"), p.get("cluster"));
  else if (p.get("cluster")) openCard(p.get("cluster"));
});
init();


function mdInline(s) {
  let x = esc(s);
  x = x.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  x = x.replace(/`([^`]+)`/g, "<code>$1</code>");
  return x;
}

function renderMarkdown(md) {
  const lines = String(md || "").split(/\r?\n/);
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (/^\s*\|/.test(line) && i + 1 < lines.length && /^\s*\|?[\s:|-]+\|?\s*$/.test(lines[i + 1])) {
      const head = line.split("|").slice(1, -1).map((c) => c.trim());
      i += 2;
      const rows = [];
      while (i < lines.length && /^\s*\|/.test(lines[i])) {
        rows.push(lines[i].split("|").slice(1, -1).map((c) => c.trim()));
        i++;
      }
      out.push(
        `<table class="mdtable"><thead><tr>${head.map((h) => `<th>${mdInline(h)}</th>`).join("")}</tr></thead>` +
        `<tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${mdInline(c)}</td>`).join("")}</tr>`).join("")}</tbody></table>`
      );
      continue;
    }
    if (/^#{1,3}\s/.test(line)) {
      const lvl = line.match(/^(#{1,3})/)[1].length;
      out.push(`<h${lvl + 2}>${mdInline(line.replace(/^#+\s*/, ""))}</h${lvl + 2}>`);
      i++;
      continue;
    }
    if (/^\s*>\s?/.test(line)) {
      const q = [];
      while (i < lines.length && /^\s*>\s?/.test(lines[i])) {
        q.push(lines[i].replace(/^\s*>\s?/, ""));
        i++;
      }
      out.push(`<blockquote>${q.map(mdInline).join("<br>")}</blockquote>`);
      continue;
    }
    if (/^\s*[-*]\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*]\s+/, ""));
        i++;
      }
      out.push(`<ul>${items.map((x) => `<li>${mdInline(x)}</li>`).join("")}</ul>`);
      continue;
    }
    if (!line.trim()) {
      i++;
      continue;
    }
    out.push(`<p>${mdInline(line)}</p>`);
    i++;
  }
  return out.join("");
}

const DD_DEMO_SERIES = [
  { date: "2026-10-07", counts: { value_not_realized: 7, redundancy: 1, discomfort: 3 } },
  { date: "2026-10-21", counts: { value_not_realized: 11, redundancy: 2, discomfort: 2 } },
  { date: "2026-11-04", counts: { value_not_realized: 10, redundancy: 3, discomfort: 2 } },
  { date: "2026-11-18", counts: { value_not_realized: 9, redundancy: 4, discomfort: 2 } },
];
const DD_COMPARE = `# 多产品对比：Apple Watch vs Kindle vs VR 头显

| 产品 | 有效证据 | 首要触发 | 触发总数 |
|---|---|---|---|
| Apple Watch | 17 | value_not_realized | 17 |
| Kindle | 13 | value_not_realized | 13 |
| VR 头显 | 27 | value_not_realized | 27 |

## 触发分布（占各自总数比例）

| 触发 | Apple Watch | Kindle | VR 头显 |
|---|---|---|---|
| value_not_realized | 53% | 62% | 41% |
| redundancy | 24% | 8% | 7% |
| discomfort | 12% | 8% | 11% |
| hardware_failure | 12% | 8% | 7% |
`;const DD_SAMPLE = `# 专项挖掘：Apple Watch

> 平台：Reddit ｜ 系统：watchOS ｜ 口径：价值衰减 ｜ 样本：17 条

## 衰减触发

| 触发 | 条数 | 占比 |
|---|---|---|
| value_not_realized | 9 | 53% |
| redundancy | 4 | 24% |
| discomfort | 2 | 12% |

## 处置动作

- shelved：7
- sold：4
- still_using：4

## 与上次对比（2026-11-04）

| 触发 | 上次 | 本次 | 变化 |
|---|---|---|---|
| value_not_realized | 11 | 9 | -2 |
| redundancy | 2 | 4 | +2 |
| discomfort | 2 | 2 | +0 |

## 典型叙述

**为长途徒步和旅行提供可靠续航**

> I have the Ultra exclusively for travel and long hikes... Otherwise though I barely use it.

- 触发：\`redundancy\`　处置：\`shelved\`　替代：普通款 Apple Watch
`;

function ddOpen() {
  $("#ddmodal").hidden = false;
  $("#ddstate").textContent = "";
}
function ddClose() {
  $("#ddmodal").hidden = true;
}

async function ddPlan() {
  const message = $("#ddmsg").value.trim();
  const el = $("#ddstate");
  if (!message) {
    el.className = "runstate err";
    el.textContent = "先描述你想研究什么。";
    return;
  }
  el.className = "runstate";
  el.textContent = "正在理解你的需求…";
  $("#ddrun").hidden = true;
  try {
    const res = await api("/api/deepdive/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    state.ddSession = res.session_id;
    const spec = res.spec || {};
    state.ddSpec = spec;
    const product = spec.product || "";
    $("#ddqs").innerHTML =
      `<div class="line">将研究：<b>${esc(product || "（还没识别出产品）")}</b>` +
      ` · 数据来自：Reddit${spec.app_store ? " 和 App Store" : ""}</div>` +
      (product ? "" : `<div class="q"><label>产品叫什么？</label><input id="ddproduct" placeholder="例如 Apple Watch、Kindle"></div>`) +
      `<div class="q"><label>1. 你最想知道什么？</label><div class="chips" data-q="0">` +
      ["为什么买了不用", "哪里难用", "值不值得买"].map((v) => `<button type="button" data-v="${v}">${v}</button>`).join("") +
      `</div></div>` +
      `<div class="q"><label>2. 主要看谁？</label><div class="chips" data-q="1">` +
      ["普通用户", "重度用户", "已经不用的人"].map((v) => `<button type="button" data-v="${v}">${v}</button>`).join("") +
      `</div></div>` +
      `<div class="q"><label>3. 看多久？</label><div class="chips" data-q="2">` +
      ["最近一年", "不限时间"].map((v) => `<button type="button" data-v="${v}">${v}</button>`).join("") +
      `</div></div>` +
      `<details class="adv"><summary>高级设置（可选）</summary>` +
      `<div class="q"><label><input type="checkbox" id="ddapp" checked> 同时抓 App Store 评论</label></div>` +
      `<div class="q"><label><input type="checkbox" id="ddforce"> 忽略缓存，强制重新抓取</label></div>` +
      `<div class="q"><label>Reddit 板块（逗号分隔）</label>` +
      `<input id="ddsubs" value="${esc((spec.subreddits || []).join(","))}"></div>` +
      `<div class="q"><label>关键词（逗号分隔）</label>` +
      `<input id="ddkw" value="${esc((spec.keywords || []).join(","))}"></div>` +
      `<div class="q"><label><input type="checkbox" id="ddmulti"> 多产品对比（每行：产品 | 板块 | 关键词）</label>` +
      `<textarea id="ddproducts" rows="3" placeholder="Apple Watch | AppleWatch | stopped,sold&#10;Kindle | kindle,ereader | dust,sold"></textarea></div>` +
      `<button class="runsync" id="ddpreview">预检样本</button>` +
      `<div id="ddpreviewout"></div>` +
      `</details>` +
      `<button class="runsync" id="ddreplan">按这些回答重新理解</button>`;
    document.querySelectorAll("#ddqs .chips").forEach((group) => {
      group.addEventListener("click", (e) => {
        const btn = e.target.closest("button[data-v]");
        if (!btn) return;
        group.querySelectorAll("button").forEach((b) => b.classList.remove("on"));
        btn.classList.add("on");
      });
    });
    $("#ddpreview")?.addEventListener("click", ddPreview);
    $("#ddreplan").addEventListener("click", ddReplan);
    $("#ddrun").hidden = false;
    el.className = "runstate ok";
    el.textContent = "补充回答（可留空）后开始挖掘。";
  } catch (err) {
    el.className = "runstate err";
    el.textContent = `失败：${err.message}`;
  }
}


async function ddReplan() {
  const base = $("#ddmsg").value.trim();
  const answers = [...document.querySelectorAll("#ddqs .chips")]
    .map((g) => g.querySelector("button.on")?.dataset.v)
    .filter(Boolean);
  const product = $("#ddproduct") ? $("#ddproduct").value.trim() : "";
  if (!answers.length && !product) {
    $("#ddstate").className = "runstate err";
    $("#ddstate").textContent = "先选一个答案，或填上产品名。";
    return;
  }
  const extra = [];
  if (product) extra.push(`产品是 ${product}`);
  if (answers[0]) extra.push(`我最想知道：${answers[0]}`);
  if (answers[1]) extra.push(`主要看：${answers[1]}`);
  if (answers[2]) extra.push(`时间范围：${answers[2]}`);
  $("#ddmsg").value = base + "\n补充：" + extra.join("；");
  await ddPlan();
}

async function ddPreview() {
  const el = $("#ddstate");
  const out = $("#ddpreviewout");
  const spec = ddSpecOverride();
  el.className = "runstate";
  el.textContent = "正在预检（每个板块抓 1 页）…";
  try {
    const res = await api("/api/deepdive/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: state.ddSession, spec }),
    });
    const rows = (res.rows || []).map((r) =>
      `<tr><td>r/${esc(r.subreddit)}</td><td>${r.scanned}</td><td>${r.matched}</td></tr>`).join("");
    const suggest = (res.suggested_keywords || []);
    const suggestBtn = suggest.length
      ? `<div class="line"><a href="#" id="ddsuggest">→ 采用建议关键词（${suggest.length} 个）</a></div>` : "";
    out.innerHTML = `<table class="ddtable"><thead><tr><th>板块</th><th>抓到</th><th>匹配</th></tr></thead>` +
      `<tbody>${rows}</tbody></table>` +
      `<div class="line">Reddit ${res.scanned} 条，匹配 ${res.matched} 条（命中率 ${(res.hit_rate * 100).toFixed(1)}%）` +
      `${res.app_scanned ? `；App Store ${res.app_scanned} 条` : ""}。${esc(res.advice || "")}</div>` +
      ((res.app_store || []).length
        ? `<div class="line">App Store：${res.app_store.map((a) => `${esc(a.app)}（${a.rating_count} 评分）`).join("、")}</div>`
        : "") +
      (suggest.length ? `<div class="line">建议：${suggest.map(esc).join("、")}</div>` : "") + suggestBtn;
    if (suggest.length) {
      $("#ddsuggest").addEventListener("click", async (e) => {
        e.preventDefault();
        $("#ddkw").value = suggest.join(",");
        await ddPreview();
      });
    }
    el.className = res.hit_rate < 0.05 ? "runstate err" : "runstate ok";
    el.textContent = res.hit_rate < 0.05 ? "命中率偏低，建议放宽关键词。" : "预检通过，可以开始挖掘。";
  } catch (err) {
    el.className = "runstate err";
    el.textContent = `预检失败：${err.message}`;
  }
}

function ddSpecOverride() {
  const subs = $("#ddsubs") ? $("#ddsubs").value.split(",").map((x) => x.trim().replace(/^r\//, "")).filter(Boolean) : [];
  const kw = $("#ddkw") ? $("#ddkw").value.split(",").map((x) => x.trim()).filter(Boolean) : [];
  const appStore = $("#ddapp") ? $("#ddapp").checked : false;
  return { subreddits: subs, keywords: kw, app_store: appStore };
}

async function ddRun() {
  const el = $("#ddstate");
  const chips = [...document.querySelectorAll("#ddqs .chips")]
    .map((g) => g.querySelector("button.on")?.dataset.v)
    .filter(Boolean);
  const answers = chips;
  const multi = $("#ddmulti") && $("#ddmulti").checked;
  const focusOverride = chips[0] === "为什么买了不用" ? "decay" : chips[0] ? "pain" : "";
  const specOverride = ddSpecOverride();
  if (focusOverride) specOverride.focus = focusOverride;
  el.className = "runstate";
  $("#ddrun").disabled = true;
  try {
    let res;
    if (multi) {
      const products = ($("#ddproducts") ? $("#ddproducts").value : "")
        .split("\n")
        .map((line) => {
          const parts = line.split("|").map((x) => x.trim());
          const subs = (parts[1] || "").split(",").map((x) => x.trim()).filter(Boolean);
          const kw = (parts[2] || "").split(",").map((x) => x.trim()).filter(Boolean);
          return { product: parts[0] || "", subreddits: subs, keywords: kw };
        })
        .filter((x) => x.product);
      if (products.length < 2) {
        el.className = "runstate err";
        el.textContent = "对比模式至少填两个产品，用逗号分隔。";
        return;
      }
      el.textContent = `开始对比 ${products.length} 个产品，可能需要 2–5 分钟…`;
      const spec = specOverride;
      res = await api("/api/deepdive/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          products,
          subreddits: spec.subreddits,
          keywords: spec.keywords,
          app_store: spec.app_store,
          force: $("#ddforce") ? $("#ddforce").checked : false,
          focus: spec.focus || "decay",
        }),
      });
    } else {
      el.textContent = "开始挖掘，可能需要 1–3 分钟…";
      res = await api("/api/deepdive/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: state.ddSession,
          answers,
          spec: specOverride,
          force: $("#ddforce") ? $("#ddforce").checked : false,
        }),
      });
    }
    let job = null;
    for (;;) {
      job = await api(`/api/deepdive/${res.job_id}`);
      if (job.status !== "running") break;
      await new Promise((r) => setTimeout(r, 2000));
    }
    if (job.status === "done") {
      el.className = "runstate ok";
      el.textContent = `完成：${job.report.count} 条有效证据${job.report.cached ? "（来自缓存）" : ""}。`;
      const rep = $("#ddreport");
      rep.hidden = false;
      ddRenderReport(job.report);
    } else {
      el.className = "runstate err";
      el.textContent = `失败：${job.error || "未知错误"}`;
    }
  } catch (err) {
    el.className = "runstate err";
    el.textContent = `失败：${err.message}`;
  } finally {
    $("#ddrun").disabled = false;
  }
}


function ddTrendChart(series) {
  if (!series || series.length < 2) return "";
  const last = series[series.length - 1].counts || {};
  const top = Object.keys(last)
    .sort((a, b) => (last[b] || 0) - (last[a] || 0))
    .slice(0, 3);
  if (!top.length) return "";
  const W = 680;
  const H = 150;
  const pad = 26;
  const max = Math.max(1, ...series.flatMap((s) => top.map((k) => s.counts[k] || 0)));
  const x = (i) => pad + ((W - 2 * pad) * i) / (series.length - 1);
  const y = (v) => H - pad - ((H - 2 * pad) * v) / max;
  const colors = ["#0f766e", "#7c3aed", "#f59e0b"];
  const lines = top
    .map((k, idx) => {
      const color = colors[idx % colors.length];
      const pts = series.map((s, i) => `${x(i).toFixed(1)},${y(s.counts[k] || 0).toFixed(1)}`).join(" ");
      const dots = series
        .map((s, i) => `<circle cx="${x(i).toFixed(1)}" cy="${y(s.counts[k] || 0).toFixed(1)}" r="2.5" fill="${color}"/>`)
        .join("");
      return `<polyline fill="none" stroke="${color}" stroke-width="2" points="${pts}"/>${dots}`;
    })
    .join("");
  const legend = top
    .map((k, idx) => `<span style="color:${colors[idx % colors.length]}">● ${esc(k)}</span>`)
    .join(" ");
  const labels = series
    .map(
      (s, i) =>
        `<text x="${x(i).toFixed(1)}" y="${H - 6}" font-size="9" fill="#6b7280" text-anchor="middle">${esc(
          String(s.date || "").slice(5)
        )}</text>`
    )
    .join("");
  return (
    `<div class="ddtrend"><div class="ddlegend">${legend}</div>` +
    `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}">` +
    `<line x1="${pad}" y1="${H - pad}" x2="${W - pad}" y2="${H - pad}" stroke="#e5e7eb"/>` +
    lines +
    labels +
    `</svg></div>`
  );
}

function ddAddChart(root) {
  const table = root.querySelector("table.mdtable");
  if (!table) return;
  const rows = [...table.querySelectorAll("tbody tr")];
  if (rows.length < 2) return;
  const data = rows
    .map((tr) => {
      const cells = [...tr.children].map((td) => td.textContent.trim());
      return { label: cells[0] || "", value: parseFloat(cells[1]), raw: cells[1] || "" };
    })
    .filter((d) => !isNaN(d.value) && d.value > 0);
  if (!data.length) return;
  const max = Math.max(...data.map((d) => d.value));
  const chart = document.createElement("div");
  chart.className = "ddchart";
  chart.innerHTML = data
    .map(
      (d) =>
        `<div class="ddrow"><span class="ddlabel">${esc(d.label)}</span>` +
        `<span class="ddtrack"><i style="width:${Math.round((d.value / max) * 100)}%"></i></span>` +
        `<span class="ddval">${esc(d.raw)}</span></div>`
    )
    .join("");
  table.parentNode.insertBefore(chart, table);
}

function ddRenderReport(report) {
  const rep = $("#ddreport");
  rep.hidden = false;
  rep.innerHTML = renderMarkdown((report && report.markdown) || "");
  ddAddChart(rep);
  if (report && report.series && report.series.length > 1) {
    const anchor = rep.querySelector("blockquote") || rep.firstElementChild;
    const chart = ddTrendChart(report.series);
    if (anchor) anchor.insertAdjacentHTML("afterend", chart);
    else rep.insertAdjacentHTML("afterbegin", chart);
  }
  state.ddReport = report;
  const bar = document.getElementById("ddbar");
  if (bar) {
    bar.removeAttribute("hidden");
    bar.style.display = "flex";
  }
}

document.getElementById("ddmd")?.addEventListener("click", ddDownloadMd);
document.getElementById("ddprint")?.addEventListener("click", ddPrint);

function ddFileName(ext) {
  const product = (state.ddReport && state.ddReport.spec && state.ddReport.spec.product) || "report";
  const safe = String(product).replace(/[^\w\u4e00-\u9fa5-]+/g, "_").slice(0, 40);
  const d = new Date();
  const stamp = `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}`;
  return `deepdive-${safe}-${stamp}.${ext}`;
}

function ddDownloadMd() {
  const md = (state.ddReport && state.ddReport.markdown) || "";
  const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = ddFileName("md");
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

function ddPrint() {
  const html = ($("#ddreport") && $("#ddreport").innerHTML) || "";
  const w = window.open("", "_blank");
  if (!w) {
    $("#ddstate").className = "runstate err";
    $("#ddstate").textContent = "浏览器拦截了弹窗，请允许后重试。";
    return;
  }
  w.document.write(
    `<!doctype html><html><head><meta charset="utf-8"><title>${esc(ddFileName("pdf"))}</title>` +
    `<style>body{font:14px/1.6 -apple-system,"PingFang SC",sans-serif;margin:32px;color:#111}` +
    `table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid #ddd;padding:6px 8px;text-align:left}` +
    `blockquote{border-left:3px solid #99f6e4;background:#f0fdfa;margin:8px 0;padding:8px 12px}` +
    `code{background:#f1f5f9;padding:1px 4px}</style></head><body>${html}</body></html>`
  );
  w.document.close();
  w.focus();
  setTimeout(() => w.print(), 300);
}