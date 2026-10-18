/* earnings-card web generator.
 * The cards are drawn by the same render.py the CLI uses, running in the browser through Pyodide.
 * Text is measured with canvas measureText (render.set_measurer), so layouts match the web fonts.
 * Data is precomputed nightly from SEC EDGAR into data/ (the browser can't call SEC directly). */
"use strict";
const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/";
const LOCAL_PYODIDE = new URL("pyodide/", location.href).href;
const CARD_ORDER = ["cover", "mix", "profit", "trend", "cash", "guide", "wide"];
const STYLES = [
  {id: "light", zh: "杂志米白", en: "Paper", bg: "#F4F1EA", ink: "#151515", hi: "#8C6A3F"},
  {id: "dark", zh: "墨黑", en: "Ink", bg: "#121212", ink: "#F2EFE8", hi: "#D9A65E"},
  {id: "mono", zh: "极简黑白", en: "Swiss", bg: "#FFFFFF", ink: "#000000", hi: "#E10600"},
  {id: "terminal", zh: "终端", en: "Terminal", bg: "#0A0A0A", ink: "#FFB000", hi: "#33C7FF"},
  {id: "salmon", zh: "财经报纸", en: "Salmon", bg: "#FFF1E5", ink: "#33302E", hi: "#0D7680"},
  {id: "pop", zh: "小红书色块", en: "Pop", bg: "#FFF5F3", ink: "#1B1B1B", hi: "#FF2442"},
];
// Google Fonts families behind the CSS font stacks render.py writes into the SVG.
const GFONTS = {
  "Inter": "Inter", "Noto Sans SC": "Noto+Sans+SC", "Source Serif 4": "Source+Serif+4",
  "Noto Serif SC": "Noto+Serif+SC", "JetBrains Mono": "JetBrains+Mono",
};
const WEIGHTS = [400, 500, 600, 700, 800];

const T = {
  zh: {
    brand: "财报卡生成器", gallery: "画廊", title: "输入代码，生成财报卡",
    lede: "选季报或年报、风格、比例和水印，卡片在浏览器里即时生成。数据来自 SEC EDGAR 官方财报。",
    ticker: "股票代码", period: "报告期", quarter: "季报", annual: "年报", ratio: "图片比例", style: "风格",
    customColors: "自定义颜色", cBg: "背景", cInk: "文字", cHi: "强调色", font: "字体", fAuto: "跟随风格",
    fSans: "无衬线", fSerif: "衬线", fMono: "等宽", cardLang: "卡片语言", headline: "一句话标题（可选）",
    headlinePh: "例如：营收同比翻倍，毛利率稳在 75%", headlineHint: "放在封面上，只写数据里看得到的事实。",
    watermark: "水印", handlePh: "@你的账号", avatar: "头像", remove: "移除", cards: "卡片",
    downloadAll: "下载全部（ZIP）", download: "下载 PNG",
    names: {cover: "封面", mix: "钱从哪里来", profit: "利润拆解", trend: "利润率趋势", cash: "现金流", guide: "管理层指引", wide: "横版封面"},
    noMix: "这期财报没有分业务数据", noGuide: "这只股票这一期没有整理好的指引", noGuideAnnual: "指引只有季报有",
    noWide: "16:9 下封面本身就是横版", r: {"4:5": "竖版 1080×1350：小红书、朋友圈", "1:1": "方图 1080×1080：微博、Instagram",
      "9:16": "长图 1080×1920：Stories、视频号封面", "16:9": "横版 1920×1080：X、公众号头图、PPT"},
    coverage: n => `已覆盖 ${n} 只美股（标普 100 起步），每晚自动更新。`,
    boot: "正在加载渲染引擎（Pyodide，首次约 10 MB，之后会缓存）…", loading: t => `正在读取 ${t} 的财报数据…`,
    drawing: "正在生成卡片…", notFound: (t, n) => `暂时没有 ${t} 的数据。目前覆盖 ${n} 只股票，想加更多可以在 GitHub 提 issue 或改 tools/tickers.txt。`,
    noPeriod: "这只股票没有这种报告期的数据，换一个试试。", bootFail: "渲染引擎加载失败，请检查网络后刷新页面。",
    zipping: "正在打包…", exportFail: "导出失败：", fontWarn: "（字体没能嵌入，PNG 会用系统字体）",
    meta: (d) => `${d.fiscal_label} · 截至 ${d.period_end} · ${d.form.replace(" (derived)", "")} ${d.filed} 披露`,
    foot: '数据来自 SEC EDGAR（GAAP 口径），不构成投资建议。卡片由开源项目 <a href="https://github.com/TTNAN/earnings-card">earnings-card</a> 生成，也可以在 Claude Code / Codex 里装上 skill：<code>npx skills add TTNAN/earnings-card</code>',
  },
  en: {
    brand: "Earnings card generator", gallery: "Gallery", title: "Type a ticker, get the cards",
    lede: "Pick quarterly or annual, a style, an aspect ratio and your watermark. Cards render instantly in your browser from official SEC filings.",
    ticker: "Ticker", period: "Report", quarter: "Quarterly", annual: "Annual", ratio: "Aspect ratio", style: "Style",
    customColors: "Custom colours", cBg: "Background", cInk: "Text", cHi: "Accent", font: "Font", fAuto: "Style's own",
    fSans: "Sans", fSerif: "Serif", fMono: "Mono", cardLang: "Card language", headline: "Headline (optional)",
    headlinePh: "e.g. Revenue doubled, margins held at 75%", headlineHint: "Goes on the cover. Stick to what the numbers show.",
    watermark: "Watermark", handlePh: "@your_handle", avatar: "Avatar", remove: "Remove", cards: "Cards",
    downloadAll: "Download all (ZIP)", download: "Download PNG",
    names: {cover: "Cover", mix: "Revenue mix", profit: "Profit", trend: "Margins", cash: "Cash flow", guide: "Outlook", wide: "Wide cover"},
    noMix: "No segment breakdown in this filing", noGuide: "No outlook prepared for this quarter", noGuideAnnual: "Outlook is quarterly only",
    noWide: "At 16:9 the cover already is landscape", r: {"4:5": "Portrait 1080×1350: Instagram, Xiaohongshu", "1:1": "Square 1080×1080",
      "9:16": "Story 1080×1920", "16:9": "Landscape 1920×1080: X, slides"},
    coverage: n => `${n} US stocks covered (starting with the S&P 100), refreshed nightly.`,
    boot: "Loading the renderer (Pyodide, ~10 MB the first time, cached after)…", loading: t => `Loading ${t} filings…`,
    drawing: "Drawing cards…", notFound: (t, n) => `No data for ${t} yet. ${n} tickers are covered; open an issue or edit tools/tickers.txt on GitHub to add more.`,
    noPeriod: "No data for this report type, try the other one.", bootFail: "The renderer failed to load. Check your connection and reload.",
    zipping: "Zipping…", exportFail: "Export failed: ", fontWarn: " (fonts could not be embedded; PNG uses system fonts)",
    meta: (d) => `${d.fiscal_label} · ${d.period === "annual" ? "fiscal year ended" : "quarter ended"} ${d.period_end} · ${d.form.replace(" (derived)", "")} filed ${d.filed}`,
    foot: 'Data from SEC EDGAR (GAAP). Not investment advice. Made with the open-source <a href="https://github.com/TTNAN/earnings-card">earnings-card</a>; agents can install it with <code>npx skills add TTNAN/earnings-card</code>',
  },
};

// ---------- state ----------
const $ = s => document.querySelector(s);
const q = new URLSearchParams(location.search);
const S = {
  ui: q.get("ui") || localStorage.ecui || "zh",
  ticker: (q.get("t") || "NVDA").toUpperCase(),
  period: q.get("p") === "annual" ? "annual" : "quarter",
  ratio: ["4:5", "1:1", "9:16", "16:9"].includes(q.get("r")) ? q.get("r") : "4:5",
  style: STYLES.some(s => s.id === q.get("s")) ? q.get("s") : "light",
  font: ["auto", "sans", "serif", "mono"].includes(q.get("f")) ? q.get("f") : "auto",
  lang: q.get("lang") === "en" ? "en" : (q.get("lang") === "zh" ? "zh" : null),
  headline: q.get("h") || "",
  handle: localStorage.echandle || "",
  avatar: localStorage.ecavatar || "",
  colors: {}, colorOn: {},
  off: new Set((q.get("hide") || "").split(",").filter(Boolean)),
};
if (!S.lang) S.lang = S.ui;
let py = null, webRender = null, tickers = [], dataCache = {}, current = null, rendered = [], seq = 0;
const tr = () => T[S.ui];

// ---------- UI text ----------
function applyUI() {
  const t = tr();
  document.documentElement.lang = S.ui === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i]").forEach(el => {
    const v = t[el.dataset.i];
    if (typeof v === "string") (el.dataset.i === "foot" ? el.innerHTML = v : el.textContent = v);
  });
  document.querySelectorAll("[data-ph]").forEach(el => el.placeholder = t[el.dataset.ph]);
  $("#avatarBtn").title = t.avatar;
  $("#ratiohint").textContent = t.r[S.ratio];
  if (tickers.length) $("#coverage").textContent = t.coverage(tickers.length);
  drawSwatches();
  drawChecks();
  setSeg("#uilang", S.ui);
  if (current) $("#meta").innerHTML = metaHTML();
  rendered.length && drawGrid(rendered);
}
function setSeg(sel, v) { document.querySelectorAll(sel + " button").forEach(b => b.classList.toggle("on", b.dataset.v === v)); }
function bindSeg(sel, key, after) {
  document.querySelectorAll(sel + " button").forEach(b => b.onclick = () => {
    S[key] = b.dataset.v; setSeg(sel, S[key]); after && after(); schedule();
  });
  setSeg(sel, S[key]);
}
function drawSwatches() {
  $("#styles").innerHTML = STYLES.map(s => `<button class="sw${s.id === S.style ? " on" : ""}" data-v="${s.id}">
    <i style="background:${s.bg}"><b style="background:${s.ink};height:22px"></b><b style="background:${s.hi};height:14px"></b><b style="background:${s.ink};height:9px;opacity:.35"></b></i>
    <em>${s[S.ui]}</em></button>`).join("");
  document.querySelectorAll(".sw").forEach(b => b.onclick = () => {
    S.style = b.dataset.v; drawSwatches(); syncColorInputs(); schedule();
  });
}
function syncColorInputs() {
  const st = STYLES.find(s => s.id === S.style);
  for (const k of ["bg", "ink", "hi"]) if (!S.colorOn[k]) $("#c-" + k).value = st[k].toLowerCase();
}

// ---------- which cards ----------
function availability() {
  const t = tr(), d = current && current.data, a = {};
  for (const c of CARD_ORDER) a[c] = "";
  if (d && !(d.segments && Object.keys(d.segments).length)) a.mix = t.noMix;
  if (S.period === "annual") a.guide = t.noGuideAnnual;
  else if (!(current && current.guide)) a.guide = t.noGuide;
  if (S.ratio === "16:9") a.wide = t.noWide;
  return a;
}
function drawChecks() {
  const t = tr(), av = availability();
  $("#cards").innerHTML = CARD_ORDER.map(c => `<label class="${av[c] ? "off" : ""}" title="${av[c]}">
    <input type="checkbox" value="${c}" ${av[c] ? "disabled" : ""} ${!av[c] && !S.off.has(c) ? "checked" : ""}>${t.names[c]}</label>`).join("");
  document.querySelectorAll("#cards input").forEach(i => i.onchange = () => {
    i.checked ? S.off.delete(i.value) : S.off.add(i.value); schedule();
  });
}

// ---------- status ----------
function status(msg, err) {
  const el = $("#status");
  el.hidden = !msg; el.classList.toggle("err", !!err);
  $("#statusText").textContent = msg || "";
}

// ---------- ticker search ----------
function setupSearch() {
  const inp = $("#ticker"), ul = $("#sugg");
  let hits = [], idx = 0;
  const show = () => {
    const v = inp.value.trim().toUpperCase();
    if (!v) { ul.hidden = true; return; }
    const lv = v.toLowerCase();
    hits = tickers.filter(([tk]) => tk.startsWith(v))
      .concat(tickers.filter(([tk, n]) => !tk.startsWith(v) && n.toLowerCase().includes(lv))).slice(0, 8);
    idx = 0;
    ul.innerHTML = hits.map(([tk, n], i) => `<li data-t="${tk}" class="${i === 0 ? "on" : ""}"><b>${tk}</b><span>${esc(n)}</span></li>`).join("");
    ul.hidden = !hits.length;
  };
  const pick = tk => {
    inp.value = tk; ul.hidden = true;
    if (tk !== S.ticker || !current) {
      if (tk !== S.ticker) { S.headline = ""; $("#headline").value = ""; }   // a headline is about one stock
      S.ticker = tk; saveURL(); loadTicker();
    }
  };
  inp.addEventListener("input", show);
  inp.addEventListener("focus", () => { inp.select(); });
  inp.addEventListener("keydown", e => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (ul.hidden) return; e.preventDefault();
      idx = (idx + (e.key === "ArrowDown" ? 1 : hits.length - 1)) % hits.length;
      ul.querySelectorAll("li").forEach((li, i) => li.classList.toggle("on", i === idx));
    } else if (e.key === "Enter") {
      e.preventDefault();
      pick(!ul.hidden && hits[idx] ? hits[idx][0] : inp.value.trim().toUpperCase());
      inp.blur();
    } else if (e.key === "Escape") ul.hidden = true;
  });
  ul.addEventListener("mousedown", e => { const li = e.target.closest("li"); if (li) { e.preventDefault(); pick(li.dataset.t); inp.blur(); } });
  inp.addEventListener("blur", () => setTimeout(() => { ul.hidden = true; if (!inp.value.trim()) inp.value = S.ticker; }, 120));
}
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
const file = tk => tk.replace(/\./g, "-");

// ---------- data ----------
async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(r.status + " " + url);
  return r.json();
}
let labelsZh = null;
async function loadTicker() {
  const tk = S.ticker, my = ++seq;
  status(tr().loading(tk));
  try {
    if (!dataCache[tk]) {
      const [rec, lab, gzh, gen] = await Promise.all([
        getJSON(`data/${file(tk)}.json`),
        getJSON(`data/labels/${file(tk)}.json`).catch(() => ({})),
        getJSON(`data/guide/${file(tk)}-guide-zh.json`).catch(() => null),
        getJSON(`data/guide/${file(tk)}-guide-en.json`).catch(() => null),
      ]);
      dataCache[tk] = {rec, labels: lab, guide: {zh: gzh, en: gen}};
    }
  } catch (e) {
    if (my !== seq) return;
    current = null; rendered = []; $("#grid").innerHTML = ""; $("#meta").innerHTML = ""; $("#zip").disabled = true;
    status(tr().notFound(tk, tickers.length), true);
    return;
  }
  if (my !== seq) return;
  pickPeriod();
  schedule(0);
}
function pickPeriod() {
  const c = dataCache[S.ticker];
  if (!c) { current = null; return; }
  let d = c.rec[S.period];
  if (!d) {   // only one report type for this stock (e.g. a bank whose quarterly tags we can't read): switch to it
    const other = S.period === "quarter" ? "annual" : "quarter";
    if (c.rec[other]) { S.period = other; setSeg("#period", S.period); d = c.rec[other]; }
  }
  // An outlook file belongs to one quarter: use it only while that quarter is the latest.
  const g = c.guide[S.lang];
  const guide = d && S.period === "quarter" && g && g.prior && g.prior.period === d.fiscal_label ? g : null;
  current = d ? {data: d, guide, labels: Object.assign({}, labelsZh || {}, c.labels)} : null;
}
function metaHTML() {
  const d = current.data;
  const name = d.company === d.company.toUpperCase() ? d.company.replace(/\w\S*/g, w => w[0] + w.slice(1).toLowerCase()) : d.company;
  return `<b>${esc(d.ticker)}</b>${esc(name)} · ${esc(tr().meta(d))}`;
}

// ---------- rendering ----------
let timer = null;
function schedule(ms = 140) { clearTimeout(timer); timer = setTimeout(render, ms); saveURL(); }
function options() {
  const cards = CARD_ORDER.filter(c => !S.off.has(c));
  const o = {lang: S.lang, style: S.style, font: S.font, ratio: S.ratio, cards, headline: S.headline.trim(),
    handle: S.handle.trim(), avatar: S.avatar, guidance: current.guide,
    labels: S.lang === "zh" ? current.labels : {}};
  for (const k of ["bg", "ink", "hi"]) if (S.colorOn[k]) o[k] = $("#c-" + k).value;
  return o;
}
let fontPass = 0;
async function render() {
  if (!webRender) return;
  pickPeriod();
  drawChecks();
  if (!dataCache[S.ticker]) return;
  if (!current) { status(tr().noPeriod, true); $("#grid").innerHTML = ""; rendered = []; $("#zip").disabled = true; return; }
  $("#meta").innerHTML = metaHTML();
  $("#grid").classList.add("busy");
  await new Promise(r => requestAnimationFrame(() => setTimeout(r)));
  let out;
  try {
    out = JSON.parse(webRender(JSON.stringify(current.data), JSON.stringify(options())));
  } catch (e) {
    console.error(e); status(String(e).slice(0, 300), true); $("#grid").classList.remove("busy"); return;
  }
  status("");
  rendered = out;
  drawGrid(out);
  $("#grid").classList.remove("busy");
  $("#zip").disabled = !out.length;
  // Web fonts load lazily (Chinese fonts in slices): once the glyphs on these cards are in, measure again.
  if (await ensureFonts(out) && fontPass < 3) { fontPass++; resetMeasurer(); render(); } else fontPass = 0;
}
function drawGrid(out) {
  const t = tr(), grid = $("#grid");
  grid.className = "grid r" + S.ratio.replace(":", "");
  grid.innerHTML = out.map((c, i) => `<figure class="tile${c.w > c.h && S.ratio !== "16:9" ? " wide" : ""}">
    <div class="img">${c.svg}</div>
    <figcaption><span>${i + 1} · ${t.names[c.name]} · ${c.w}×${c.h}</span><button data-k="${i}">${t.download}</button></figcaption></figure>`).join("");
  grid.querySelectorAll("figcaption button").forEach(b => b.onclick = () => downloadOne(+b.dataset.k, b));
}

// ---------- fonts ----------
function familiesIn(svg) {
  const fams = new Set();
  for (const f of Object.keys(GFONTS)) if (svg.includes(f)) fams.add(f);
  return fams;
}
function textOf(cards) {
  let s = "";
  for (const c of cards) s += c.svg.replace(/<[^>]+>/g, "");
  return s.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&").replace(/&quot;/g, '"').replace(/&#x27;/g, "'");
}
async function ensureFonts(cards) {
  if (!document.fonts) return false;
  const text = [...new Set(textOf(cards))].join("");
  const fams = new Set();
  cards.forEach(c => familiesIn(c.svg).forEach(f => fams.add(f)));
  const specs = [];
  for (const f of fams) for (const w of WEIGHTS) specs.push(`${w} 20px "${f}"`);
  const missing = specs.filter(s => { try { return !document.fonts.check(s, text); } catch (e) { return false; } });
  if (!missing.length) return false;
  await Promise.all(missing.map(s => document.fonts.load(s, text).catch(() => null)));
  return true;
}
const mctx = document.createElement("canvas").getContext("2d");
function measureText(s, family, size, weight) {
  mctx.font = `${weight} ${size}px ${family}`;
  return mctx.measureText(s).width;
}
function resetMeasurer() { py && py.runPython("import render; render.set_measurer(js_measure)"); }

// Subset the fonts to exactly the characters on the cards and embed them, so the PNG matches the preview.
const fontCssCache = {};
async function embeddedFontCSS(cards) {
  const chars = [...new Set(textOf(cards).replace(/\s/g, ""))].sort().join("") + " ";
  const fams = new Set();
  cards.forEach(c => familiesIn(c.svg).forEach(f => fams.add(f)));
  const parts = await Promise.all([...fams].map(async f => {
    const key = f + "|" + chars;
    if (!fontCssCache[key]) fontCssCache[key] = (async () => {
      const url = `https://fonts.googleapis.com/css2?family=${GFONTS[f]}:wght@${WEIGHTS.join(";")}&text=${encodeURIComponent(chars)}`;
      let css = await (await fetch(url)).text();
      const urls = [...new Set([...css.matchAll(/url\((https:[^)]+)\)/g)].map(m => m[1]))];
      const datas = await Promise.all(urls.map(async u => blobToDataURL(await (await fetch(u)).blob())));
      urls.forEach((u, i) => { css = css.split(u).join(datas[i]); });
      return css;
    })();
    return fontCssCache[key];
  }));
  return parts.join("\n");
}
const blobToDataURL = b => new Promise((ok, no) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = no; r.readAsDataURL(b); });

// ---------- export ----------
async function toPNG(card, css, scale = 2) {
  const svg = card.svg.replace(/^(<svg[^>]*>)/, `$1<defs><style>${css.replace(/</g, "")}</style></defs>`);
  const url = URL.createObjectURL(new Blob([svg], {type: "image/svg+xml;charset=utf-8"}));
  try {
    const img = new Image();
    img.decoding = "sync";
    await new Promise((ok, no) => { img.onload = ok; img.onerror = () => no(new Error("SVG image failed to load")); img.src = url; });
    await new Promise(r => setTimeout(r, 60));   // let embedded fonts settle before painting
    const cv = document.createElement("canvas");
    cv.width = card.w * scale; cv.height = card.h * scale;
    const ctx = cv.getContext("2d");
    ctx.drawImage(img, 0, 0, cv.width, cv.height);
    return await new Promise(ok => cv.toBlob(ok, "image/png"));
  } finally { URL.revokeObjectURL(url); }
}
async function fontsFor(cards) {
  try { return {css: await embeddedFontCSS(cards), warn: ""}; }
  catch (e) { console.warn(e); return {css: "", warn: tr().fontWarn}; }
}
function fname(card, i) {
  const d = current.data;
  return `${d.ticker.replace(/\./g, "-")}-${d.fiscal_label.replace(/\s+/g, "")}-${i + 1}-${card.name}-${S.ratio.replace(":", "x")}.png`;
}
function save(blob, name) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = name;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}
async function downloadOne(i, btn) {
  const card = rendered[i], label = btn.textContent;
  btn.disabled = true; btn.textContent = "…";
  try {
    const {css, warn} = await fontsFor([card]);
    save(await toPNG(card, css), fname(card, i));
    if (warn) status(warn.trim());
  } catch (e) { status(tr().exportFail + e.message, true); }
  finally { btn.disabled = false; btn.textContent = label; }
}
async function downloadAll() {
  const btn = $("#zip"), label = btn.textContent, cards = rendered.slice();
  btn.disabled = true; btn.textContent = tr().zipping;
  try {
    const {css, warn} = await fontsFor(cards);
    const files = [];
    for (let i = 0; i < cards.length; i++) {
      files.push({name: fname(cards[i], i), data: new Uint8Array(await (await toPNG(cards[i], css)).arrayBuffer())});
    }
    const d = current.data;
    save(new Blob([zipStore(files)], {type: "application/zip"}), `${d.ticker.replace(/\./g, "-")}-${d.fiscal_label.replace(/\s+/g, "")}-${S.ratio.replace(":", "x")}.zip`);
    if (warn) status(warn.trim());
  } catch (e) { status(tr().exportFail + e.message, true); }
  finally { btn.disabled = false; btn.textContent = label; }
}

// Minimal ZIP writer (stored, no compression: PNGs are already compressed).
const CRC = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
function crc32(b) { let c = 0xFFFFFFFF; for (let i = 0; i < b.length; i++) c = CRC[(c ^ b[i]) & 255] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; }
function zipStore(files) {
  const enc = new TextEncoder(), chunks = [], central = [];
  let off = 0;
  for (const f of files) {
    const name = enc.encode(f.name), crc = crc32(f.data), size = f.data.length;
    const h = new DataView(new ArrayBuffer(30));
    h.setUint32(0, 0x04034b50, true); h.setUint16(4, 20, true); h.setUint16(6, 0x0800, true); h.setUint16(8, 0, true);
    h.setUint16(10, 0, true); h.setUint16(12, 0x21, true); h.setUint32(14, crc, true); h.setUint32(18, size, true);
    h.setUint32(22, size, true); h.setUint16(26, name.length, true); h.setUint16(28, 0, true);
    chunks.push(new Uint8Array(h.buffer), name, f.data);
    const c = new DataView(new ArrayBuffer(46));
    c.setUint32(0, 0x02014b50, true); c.setUint16(4, 20, true); c.setUint16(6, 20, true); c.setUint16(8, 0x0800, true);
    c.setUint16(10, 0, true); c.setUint16(12, 0, true); c.setUint16(14, 0x21, true); c.setUint32(16, crc, true);
    c.setUint32(20, size, true); c.setUint32(24, size, true); c.setUint16(28, name.length, true);
    c.setUint32(42, off, true);
    central.push(new Uint8Array(c.buffer), name);
    off += 30 + name.length + size;
  }
  const csize = central.reduce((a, b) => a + b.length, 0);
  const e = new DataView(new ArrayBuffer(22));
  e.setUint32(0, 0x06054b50, true); e.setUint16(8, files.length, true); e.setUint16(10, files.length, true);
  e.setUint32(12, csize, true); e.setUint32(16, off, true);
  return new Blob([...chunks, ...central, new Uint8Array(e.buffer)]);
}

// ---------- watermark ----------
function setupWatermark() {
  const h = $("#handle");
  h.value = S.handle;
  h.oninput = () => { S.handle = h.value; localStorage.echandle = h.value; schedule(250); };
  $("#avatar").onchange = async e => {
    const f = e.target.files[0]; if (!f) return;
    S.avatar = await shrinkImage(f, 160);
    try { localStorage.ecavatar = S.avatar; } catch (_) {}
    showAvatar(); schedule(0);
  };
  $("#avatarClear").onclick = () => { S.avatar = ""; localStorage.removeItem("ecavatar"); $("#avatar").value = ""; showAvatar(); schedule(0); };
  showAvatar();
}
function showAvatar() {
  $("#avatarImg").hidden = !S.avatar; $("#avatarImg").src = S.avatar || "";
  $("#avatarClear").hidden = !S.avatar;
}
async function shrinkImage(f, px) {
  const url = URL.createObjectURL(f);
  try {
    const img = new Image();
    await new Promise((ok, no) => { img.onload = ok; img.onerror = no; img.src = url; });
    const s = Math.min(img.width, img.height), cv = document.createElement("canvas");
    cv.width = cv.height = px;
    cv.getContext("2d").drawImage(img, (img.width - s) / 2, (img.height - s) / 2, s, s, 0, 0, px, px);
    return cv.toDataURL("image/jpeg", 0.88);
  } finally { URL.revokeObjectURL(url); }
}

// ---------- URL ----------
function saveURL() {
  const p = new URLSearchParams();
  p.set("t", S.ticker);
  if (S.period !== "quarter") p.set("p", S.period);
  if (S.ratio !== "4:5") p.set("r", S.ratio);
  if (S.style !== "light") p.set("s", S.style);
  if (S.font !== "auto") p.set("f", S.font);
  if (S.lang !== S.ui) p.set("lang", S.lang);
  if (S.ui !== "zh") p.set("ui", S.ui);
  if (S.headline) p.set("h", S.headline);
  if (S.off.size) p.set("hide", [...S.off].join(","));
  history.replaceState(null, "", "?" + p.toString());
}

// ---------- boot ----------
async function boot() {
  applyUI();
  bindSeg("#period", "period");
  bindSeg("#ratio", "ratio", () => { $("#ratiohint").textContent = tr().r[S.ratio]; });
  bindSeg("#font", "font");
  bindSeg("#lang", "lang");
  document.querySelectorAll("#uilang button").forEach(b => b.onclick = () => {
    const prev = S.ui; S.ui = b.dataset.v; localStorage.ecui = S.ui;
    if (S.lang === prev) { S.lang = S.ui; setSeg("#lang", S.lang); }
    applyUI(); schedule(0);
  });
  $("#headline").value = S.headline;
  $("#headline").oninput = e => { S.headline = e.target.value; schedule(300); };
  document.querySelectorAll(".colors input[type=checkbox]").forEach(cb => cb.onchange = () => { S.colorOn[cb.dataset.c] = cb.checked; schedule(0); });
  document.querySelectorAll(".colors input[type=color]").forEach(ci => ci.oninput = () => {
    const k = ci.id.slice(2); S.colorOn[k] = true; document.querySelector(`.colors [data-c=${k}]`).checked = true; schedule(80);
  });
  syncColorInputs();
  setupWatermark();
  setupSearch();
  $("#zip").onclick = downloadAll;
  $("#ticker").value = S.ticker;
  status(tr().boot);

  const listP = getJSON("data/tickers.json").then(l => { tickers = l; $("#coverage").textContent = tr().coverage(l.length); }).catch(() => {});
  getJSON("data/labels-zh.json").then(l => { labelsZh = l; }).catch(() => { labelsZh = {}; });
  try {
    let pyo, src, lastErr;
    const srcP = fetch("py/render.py").then(r => { if (!r.ok) throw new Error("render.py " + r.status); return r.text(); });
    for (const base of [PYODIDE, LOCAL_PYODIDE]) {          // CDN first, then the copy in this repo
      try {
        if (base !== PYODIDE) { try { delete window.loadPyodide; delete window._createPyodideModule; } catch (e) {} }
        await new Promise((ok, no) => { const s = document.createElement("script"); s.src = base + "pyodide.js"; s.onload = ok; s.onerror = () => no(new Error("pyodide.js")); document.head.appendChild(s); });
        pyo = await Promise.race([loadPyodide({indexURL: base}), new Promise((_, no) => setTimeout(() => no(new Error("timeout")), 45000))]);
        break;
      } catch (e) { console.warn("pyodide from", base, "failed:", e); window.__stage = "load " + (base === PYODIDE ? "cdn" : "local"); lastErr = e; pyo = null; }
    }
    if (!pyo) throw lastErr;
    window.__stage = "render.py"; src = await srcP;
    py = pyo;
    window.__stage = "init"; py.FS.writeFile("/home/pyodide/render.py", src);
    py.globals.set("js_measure", measureText);
    resetMeasurer();
    webRender = py.pyimport("render").web_render;
  } catch (e) {
    console.error(e); const st = (e && e.stack || "").split("\n").slice(0, 4).join(" | "); status(tr().bootFail + " [" + (window.__stage || "?") + "] (" + (e && e.message) + ") " + st + " · " + navigator.userAgent, true); return;
  }
  await listP;
  await (document.fonts ? document.fonts.ready : Promise.resolve());
  loadTicker();
}
boot();
