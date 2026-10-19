/* earnings-card web generator.
 * The cards are drawn by the same render.py the CLI uses, running in the browser through Pyodide
 * inside a Web Worker (worker.js), so browser extensions that patch the page can't break it.
 * Text widths: the page measures per-character width tables with canvas measureText and the web fonts,
 * and the worker sums them (py/measure_tables.py), so layouts match the fonts on screen.
 * Cards render one at a time (opts.only), so the grid fills in card by card with a progress count.
 * Data is precomputed nightly from SEC EDGAR into data/ (the browser can't call SEC directly). */
"use strict";
const CARD_ORDER = ["cover", "poster", "mix", "profit", "trend", "cash", "guide", "income", "yoy", "score", "post", "wide"];
const DEFAULT_OFF = ["income", "yoy", "score", "post"];   // newer templates: in the picker, unchecked until chosen
const EXTRA = ["poster", "income", "yoy", "score", "post"];   // shown under "more settings"
const STYLES = [
  {id: "light", zh: "杂志米白", en: "Paper", bg: "#F4F1EA", ink: "#151515", hi: "#8C6A3F"},
  {id: "dark", zh: "墨黑", en: "Ink", bg: "#121212", ink: "#F2EFE8", hi: "#D9A65E"},
  {id: "mono", zh: "极简黑白", en: "Swiss", bg: "#FFFFFF", ink: "#000000", hi: "#E10600"},
  {id: "terminal", zh: "终端", en: "Terminal", bg: "#0A0A0A", ink: "#FFB000", hi: "#33C7FF", tint: "#FFB000"},
  {id: "salmon", zh: "财经报纸", en: "Salmon", bg: "#FFF1E5", ink: "#33302E", hi: "#0D7680"},
  {id: "pop", zh: "小红书色块", en: "Pop", bg: "#FFF5F3", ink: "#1B1B1B", hi: "#FF2442"},
  {id: "bloomberg", zh: "彭博橙", en: "Bloomberg", bg: "#000000", ink: "#FB8B1E", hi: "#4AA3FF", tint: "#FB8B1E"},
  {id: "keynote", zh: "苹果发布会", en: "Keynote", bg: "#000000", ink: "#F5F5F7", hi: "#2997FF"},
  {id: "neon", zh: "赛博霓虹", en: "Neon", bg: "#0D0A1A", ink: "#22E4FF", hi: "#FF3DCB"},
  {id: "vintage", zh: "复古报纸", en: "Vintage", bg: "#EFE4C8", ink: "#2B2118", hi: "#9E2B1F"},
  {id: "morandi", zh: "莫兰迪", en: "Morandi", bg: "#E9E4DE", ink: "#6E7F8D", hi: "#6A7891", a2: "#8E7360"},
  {id: "glass", zh: "毛玻璃渐变", en: "Glass", bg: "#D8CCF0", ink: "#1F2240", hi: "#6B4EFF",
   grad: "linear-gradient(135deg,#B8C8F8,#E3C8EE,#F8DCCB)"},
];
// The main picker shows 8 styles (3 marked recommended); the other 4 sit under "more styles".
const MAIN_STYLES = ["light", "dark", "pop", "salmon", "keynote", "terminal", "vintage", "glass"];
const REC_STYLES = ["light", "dark", "pop"];
// Second accent (render.py THEMES[...]["a2"]) per style, for the colour picker's starting value.
const A2 = {light: "#8C6A3F", dark: "#D9A65E", mono: "#E10600", terminal: "#33C7FF", salmon: "#990F3D", pop: "#D46A00",
  bloomberg: "#4AA3FF", keynote: "#2997FF", neon: "#FF3DCB", vintage: "#9E2B1F", morandi: "#8E7360", glass: "#6B4EFF"};
const SIZES = {"4:5": [1080, 1350], "1:1": [1080, 1080], "9:16": [1080, 1920], "16:9": [1920, 1080]};
// Google Fonts families behind the CSS font stacks render.py writes into the SVG.
const GFONTS = {
  "Inter": "Inter", "Noto Sans SC": "Noto+Sans+SC", "Source Serif 4": "Source+Serif+4",
  "Noto Serif SC": "Noto+Serif+SC", "JetBrains Mono": "JetBrains+Mono",
};
const WEIGHTS = [400, 500, 600, 700, 800, 900];   // 900: hero figures and the serif cover headline
const fontWeights = f => f === "JetBrains Mono" ? WEIGHTS.filter(w => w <= 800) : WEIGHTS;   // Google serves Mono up to 800
const SECTORS = {
  zh: {tech: "信息技术", comm: "通信服务", disc: "可选消费", staples: "必需消费", health: "医疗保健", fin: "金融",
    ind: "工业", energy: "能源", util: "公用事业", re: "房地产", materials: "原材料", other: "其他"},
  en: {tech: "Information Technology", comm: "Communication Services", disc: "Consumer Discretionary", staples: "Consumer Staples",
    health: "Health Care", fin: "Financials", ind: "Industrials", energy: "Energy", util: "Utilities", re: "Real Estate",
    materials: "Materials", other: "Other"},
};

const T = {
  zh: {
    step1: "选股", step2: "选样子", step3: "微调", moreStyles: "更多风格", rec: "推荐", details: "详情",
    justFiled: "刚出财报", calendar: "近期财报日历", calCount: n => `${n} 家`, calNone: "未来两周没有覆盖的公司发财报",
    bmo: "盘前", amc: "盘后", wd: ["周日", "周一", "周二", "周三", "周四", "周五", "周六"], today: "今天", tomorrow: "明天",
    filedOn: d => `${d} 披露`, reportsOn: (d, w) => `${d} ${w}发布财报`,
    sum2: (st, r, lg) => `${st} · ${r} · ${lg === "zh" ? "中文" : "English"}`,
    sum3: (n, h, wm) => [`${n} 张卡片`, h ? "有标题" : "", wm ? "有水印" : ""].filter(Boolean).join(" · "),
    sampleBadge: "样张", sampleAlt: "NVDA 财报封面卡样张", sampleTitle: "生成后是这样的",
    sampleLede: (tk, n) => `这是英伟达（NVDA）的封面卡。画笔准备好后，会自动为 ${tk} 生成 ${n} 张：`,
    fBoot: ["正在准备画笔…", "正在准备画笔，第一次打开要多等一会儿…", "还在准备画笔，网络有点慢，请稍候…"],
    fFonts: "正在铺纸、摆好字体…", fLoading: t => `正在翻 ${t} 的财报…`, fDrawing: (i, n) => `正在排版第 ${i} 张（共 ${n} 张）…`,
    fBootFail: "画笔没能准备好，可能是网络不稳。点「重试」或刷新页面再试一次。", fRenderFail: "这张卡片没画出来，点「重试」再来一次。",
    brand: "财报卡生成器", gallery: "画廊", tickerList: "支持列表", title: "输入代码，生成财报卡",
    lede: "选季报或年报（最近 8 个季度、5 个财年都能选）、卡片模板、风格、比例和水印，卡片在浏览器里即时生成。数据来自 SEC EDGAR 官方财报。",
    ticker: "股票代码", generate: "生成", period: "报告期", quarter: "季报", annual: "年报", ratio: "图片比例", style: "风格",
    customColors: "自定义颜色", cBg: "背景", cInk: "文字", cHi: "强调色", cA2: "辅助色（第二条线、成本条）", cUpdown: "红涨绿跌",
    font: "字体", fAuto: "跟随风格",
    fSans: "无衬线", fSerif: "衬线", fMono: "等宽", cardLang: "卡片语言", headline: "一句话标题（可选）",
    headlinePh: "例如：营收同比翻倍，毛利率稳在 75%", headlineHint: "放在封面上，只写数据里看得到的事实。",
    ideasLab: "按数据生成的标题：", watermark: "水印", handlePh: "@你的账号", avatar: "头像", remove: "删除", cards: "卡片",
    more: "更多设置", extraCards: "更多模板", presets: "我的预设", presetNone: "选择已保存的预设…", presetSave: "保存当前设置",
    presetAsk: "给这套设置起个名字（风格、颜色、字体、比例、卡片、水印）：", presetSaved: n => `已保存预设「${n}」`,
    downloadAll: "下载全部（ZIP）", download: "下载", copyImg: "复制图片", copied: "已复制 ✓", copyFallback: "已改为下载",
    copyCaption: "复制文案", captionShow: "查看 / 编辑分享文案", captionCopied: "文案已复制，可以直接粘贴发帖",
    copyFail: "浏览器不允许写剪贴板，已把文案选中，按 Ctrl/⌘+C 复制",
    imgCopied: "图片已复制，可以直接粘贴到微信、小红书、X", imgFallback: "这个浏览器不支持复制图片，已改为下载 PNG",
    names: {cover: "封面", mix: "钱从哪里来", profit: "利润拆解", trend: "利润率趋势", cash: "现金流", guide: "管理层指引", wide: "横版封面",
      poster: "大数字海报", post: "推文截图风", income: "完整利润表", yoy: "同比对比卡", score: "记分牌"},
    fy: "财年", fq: "季度", fqOpt: q => `第 ${q} 季度`, latest: "（最新）", noPrev: "没有去年同期数据",
    noMix: "这期财报没有分业务数据", noGuide: "这只股票这一期没有整理好的指引", noGuideAnnual: "指引只有季报有",
    noWide: "16:9 下封面本身就是横版",
    r: {"4:5": "竖版 1080×1350 · 适合小红书 / 朋友圈", "1:1": "方图 1080×1080 · 通用（微博、Instagram）",
      "9:16": "长图 1080×1920 · 适合抖音 / 视频号 / Stories", "16:9": "横版 1920×1080 · 适合 X / 公众号头图 / PPT"},
    coverage: n => `已覆盖 ${n} 只美股，每晚自动更新。`, seeList: "查看列表",
    unsupported: t => `不支持 ${t}`, emptyTicker: "请输入股票代码", unsupportedTail: n => `目前覆盖 ${n} 只股票。`, didYouMean: "你是不是要找：",
    fullList: "查看全部支持的股票 →", recent: "最近：",
    partial: {no_quarter: "只有年报数据（季报暂缺）", no_annual: "只有季报数据（年报暂缺）", few_quarter: n => `只有最近 ${n} 个季度`,
      miss: (per, f) => `${per === "quarter" ? "最新季报" : "最新年报"}缺${f}`},
    fields: {revenue: "营收", net_income: "净利润", eps: "EPS", ocf: "经营现金流", fcf: "自由现金流"},
    partialHead: "数据不完整：", partialTail: "，相关卡片会缺项或自动隐藏。",
    stages: {worker: "启动渲染线程", probe: "正在准备画笔…", "load npmmirror": "正在准备画笔（首次约 10 MB，之后走缓存）…", "load cdn": "下载渲染引擎 Pyodide（首次约 10 MB，之后走缓存）", "load local": "CDN 不通，改从本站下载渲染引擎",
      "render.py": "加载卡片脚本", init: "初始化渲染引擎", fonts: "加载字体", data: "读取财报数据"},
    bootLine: (s, i, n, sec) => `加载引擎 ${i}/${n}：${s}… ${sec}s`,
    loading: t => `正在读取 ${t} 的财报数据…`, drawing: (i, n) => `渲染中 ${i}/${n}…`, done: n => `已生成 ${n} 张卡片`,
    notFound: (t, n) => `暂时没有 ${t} 的数据。目前覆盖 ${n} 只股票，想加更多可以在 GitHub 提 issue 或改 tools/tickers.txt。`,
    noPeriod: "这只股票没有这种报告期的数据，换一个试试。", noCards: "没有勾选可生成的卡片。",
    bootFail: "渲染引擎加载失败，请检查网络后点「重试」或刷新页面。", renderFail: "生成失败：", retry: "重试",
    zipping: "正在打包…", exportFail: "导出失败：", fontWarn: "（字体没能嵌入，PNG 会用系统字体）",
    lowContrast: r => `文字和背景对比度只有 ${r}:1（建议 ≥ 4.5），手机上可能看不清。`, jump: "看卡片 ↓",
    meta: (d) => `${d.fiscal_label} · 截至 ${d.period_end} · ${d.form.replace(" (derived)", "")} ${d.filed} 披露`,
    foot: '数据来自 SEC EDGAR（GAAP 口径），不构成投资建议。卡片由开源项目 <a href="https://github.com/TTNAN/earnings-card">earnings-card</a> 生成，也可以在 Claude Code / Codex 里装上 skill：<code>npx skills add TTNAN/earnings-card</code>',
  },
  en: {
    step1: "Pick a stock", step2: "Pick a look", step3: "Fine-tune", moreStyles: "More styles", rec: "Top", details: "Details",
    justFiled: "Just reported", calendar: "Earnings calendar", calCount: n => `${n} companies`, calNone: "No covered company reports in the next two weeks",
    bmo: "pre-market", amc: "after close", wd: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"], today: "Today", tomorrow: "Tomorrow",
    filedOn: d => `filed ${d}`, reportsOn: (d, w) => `reports ${w} ${d}`,
    sum2: (st, r, lg) => `${st} · ${r} · ${lg === "zh" ? "Chinese" : "English"}`,
    sum3: (n, h, wm) => [`${n} cards`, h ? "headline" : "", wm ? "watermark" : ""].filter(Boolean).join(" · "),
    sampleBadge: "Sample", sampleAlt: "Sample NVDA earnings cover card", sampleTitle: "Here's what you'll get",
    sampleLede: (tk, n) => `This is NVIDIA's cover card. Once the engine is ready, ${tk} gets ${n} cards:`,
    fBoot: ["Getting the brushes ready…", "Getting the brushes ready; the first visit takes a little longer…", "Still getting ready, the network is slow; hang on…"],
    fFonts: "Laying out the paper and fonts…", fLoading: t => `Reading ${t}'s filings…`, fDrawing: (i, n) => `Laying out card ${i} of ${n}…`,
    fBootFail: "Couldn't get ready, probably a network hiccup. Hit Retry or reload the page.", fRenderFail: "This card didn't come out. Hit Retry to try again.",
    brand: "Earnings card generator", gallery: "Gallery", tickerList: "Tickers", title: "Type a ticker, get the cards",
    lede: "Pick quarterly or annual (any of the last 8 quarters or 5 fiscal years), card templates, a style, an aspect ratio and your watermark. Cards render instantly in your browser from official SEC filings.",
    ticker: "Ticker", generate: "Generate", period: "Report", quarter: "Quarterly", annual: "Annual", ratio: "Aspect ratio", style: "Style",
    customColors: "Custom colours", cBg: "Background", cInk: "Text", cHi: "Accent", cA2: "Second accent (2nd line, cost bars)",
    cUpdown: "Red for up, green for down", font: "Font", fAuto: "Style's own",
    fSans: "Sans", fSerif: "Serif", fMono: "Mono", cardLang: "Card language", headline: "Headline (optional)",
    headlinePh: "e.g. Revenue doubled, margins held at 75%", headlineHint: "Goes on the cover. Stick to what the numbers show.",
    ideasLab: "From the numbers:", watermark: "Watermark", handlePh: "@your_handle", avatar: "Avatar", remove: "Delete", cards: "Cards",
    more: "More settings", extraCards: "More templates", presets: "My presets", presetNone: "Pick a saved preset…", presetSave: "Save current settings",
    presetAsk: "Name these settings (style, colours, font, ratio, cards, watermark):", presetSaved: n => `Saved preset “${n}”`,
    downloadAll: "Download all (ZIP)", download: "Download", copyImg: "Copy image", copied: "Copied ✓", copyFallback: "Downloaded instead",
    copyCaption: "Copy caption", captionShow: "View / edit the caption", captionCopied: "Caption copied, ready to paste",
    copyFail: "The browser blocked the clipboard; the caption is selected, press Ctrl/⌘+C",
    imgCopied: "Image copied, paste it into your post", imgFallback: "This browser can't copy images; downloaded the PNG instead",
    names: {cover: "Cover", mix: "Revenue mix", profit: "Profit", trend: "Margins", cash: "Cash flow", guide: "Outlook", wide: "Wide cover",
      poster: "Big number", post: "Social post", income: "Income statement", yoy: "Year over year", score: "Scorecard"},
    fy: "Fiscal year", fq: "Quarter", fqOpt: q => `Q${q}`, latest: " (latest)", noPrev: "No year-ago data",
    noMix: "No segment breakdown in this filing", noGuide: "No outlook prepared for this quarter", noGuideAnnual: "Outlook is quarterly only",
    noWide: "At 16:9 the cover already is landscape",
    r: {"4:5": "Portrait 1080×1350 · Instagram, Xiaohongshu, WeChat Moments", "1:1": "Square 1080×1080 · works everywhere",
      "9:16": "Story 1080×1920 · TikTok/Douyin, Stories, Reels", "16:9": "Landscape 1920×1080 · X, article headers, slides"},
    coverage: n => `${n} US stocks covered, refreshed nightly.`, seeList: "See the list",
    unsupported: t => `${t} isn't supported`, emptyTicker: "Type a ticker first", unsupportedTail: n => `${n} tickers are covered.`, didYouMean: "Did you mean:",
    fullList: "See every supported ticker →", recent: "Recent:",
    partial: {no_quarter: "annual data only (no quarterly)", no_annual: "quarterly data only (no annual)", few_quarter: n => `only the last ${n} quarters`,
      miss: (per, f) => `latest ${per === "quarter" ? "quarter" : "year"} has no ${f}`},
    fields: {revenue: "revenue", net_income: "net income", eps: "EPS", ocf: "operating cash flow", fcf: "free cash flow"},
    partialHead: "Partial data: ", partialTail: "; some cards will have gaps or be hidden.",
    stages: {worker: "starting the render thread", probe: "getting the brushes ready…", "load npmmirror": "getting the brushes ready (~10 MB the first time, cached after)…", "load cdn": "downloading the Pyodide engine (~10 MB the first time, cached after)",
      "load local": "CDN unreachable, loading the engine from this site", "render.py": "loading the card script", init: "starting the engine",
      fonts: "loading fonts", data: "loading filings"},
    bootLine: (s, i, n, sec) => `Loading engine ${i}/${n}: ${s}… ${sec}s`,
    loading: t => `Loading ${t} filings…`, drawing: (i, n) => `Rendering ${i}/${n}…`, done: n => `${n} cards ready`,
    notFound: (t, n) => `No data for ${t} yet. ${n} tickers are covered; open an issue or edit tools/tickers.txt on GitHub to add more.`,
    noPeriod: "No data for this report type, try the other one.", noCards: "No available card is selected.",
    bootFail: "The renderer failed to load. Check your connection, then Retry or reload.", renderFail: "Rendering failed: ", retry: "Retry",
    zipping: "Zipping…", exportFail: "Export failed: ", fontWarn: " (fonts could not be embedded; PNG uses system fonts)",
    lowContrast: r => `Text/background contrast is only ${r}:1 (aim for 4.5+); it may be hard to read on a phone.`, jump: "See cards ↓",
    meta: (d) => `${d.fiscal_label} · ${d.period === "annual" ? "fiscal year ended" : "quarter ended"} ${d.period_end} · ${d.form.replace(" (derived)", "")} filed ${d.filed}`,
    foot: 'Data from SEC EDGAR (GAAP). Not investment advice. Made with the open-source <a href="https://github.com/TTNAN/earnings-card">earnings-card</a>; agents can install it with <code>npx skills add TTNAN/earnings-card</code>',
  },
};

// ---------- storage ----------
const lsGet = k => { try { return JSON.parse(localStorage.getItem(k) || "null"); } catch (e) { return null; } };
const lsSet = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
// Per-tab state (the last session's settings, the UI language picked in this tab): a new tab or a first visit starts fresh.
const ssGet = k => { try { return JSON.parse(sessionStorage.getItem(k) || "null"); } catch (e) { return null; } };
const ssSet = (k, v) => { try { sessionStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
const ssStr = k => { try { return sessionStorage.getItem(k) || ""; } catch (e) { return ""; } };
const browserUI = () => /^zh/i.test(navigator.language || "") ? "zh" : ((navigator.language || "") ? "en" : "zh");

// ---------- state ----------
// Settings come from the URL; a bare URL (or one with only ?t=, as the ticker list links) starts from the
// last settings used in this tab (sessionStorage, so a new tab or first visit starts from the defaults). A link with more than t= is someone's exact setup: use it as it is.
const $ = s => document.querySelector(s);
const urlQ = new URLSearchParams(location.search);
try { localStorage.removeItem("ecLast"); localStorage.removeItem("ecui"); } catch (e) {}   // older builds restored these across tabs
const last = ssGet("ecLast");
const onlyTicker = [...urlQ.keys()].every(k => k === "t" || k === "ui");
const q = (() => {
  if (!onlyTicker || !last || !last.qs) return urlQ;
  const m = new URLSearchParams(last.qs);
  if (urlQ.get("t") && urlQ.get("t").toUpperCase() !== (m.get("t") || "").toUpperCase()) { m.delete("h"); m.delete("e"); }
  for (const [k, v] of urlQ) m.set(k, v);
  return m;
})();
const useLastColors = onlyTicker && last;
const S = {
  ui: ["zh", "en"].includes(urlQ.get("ui")) ? urlQ.get("ui") : (["zh", "en"].includes(ssStr("ecui")) ? ssStr("ecui") : browserUI()),
  ticker: (q.get("t") || "NVDA").toUpperCase().trim(),
  period: q.get("p") === "annual" ? "annual" : "quarter",
  ratio: ["4:5", "1:1", "9:16", "16:9"].includes(q.get("r")) ? q.get("r") : "4:5",
  style: STYLES.some(s => s.id === q.get("s")) ? q.get("s") : "light",
  font: ["auto", "sans", "serif", "mono"].includes(q.get("f")) ? q.get("f") : "auto",
  lang: q.get("lang") === "en" ? "en" : (q.get("lang") === "zh" ? "zh" : null),
  headline: q.get("h") || "",
  handle: localStorage.echandle || "",
  avatar: localStorage.ecavatar || "",
  colors: Object.assign({}, useLastColors && last.colors), colorOn: Object.assign({}, useLastColors && last.colorOn),
  updown: useLastColors && last.updown === "cn" ? "cn" : "",
  end: /^\d{4}-\d{2}-\d{2}$/.test(q.get("e") || "") ? q.get("e") : null,   // chosen period (its end date); null = latest
  // c = the chosen cards; older links only carry hide = the unchecked ones among the original seven
  off: q.get("c") ? new Set(CARD_ORDER.filter(c => !q.get("c").split(",").includes(c)))
    : new Set(DEFAULT_OFF.concat((q.get("hide") || "").split(",").filter(Boolean))),
};
if (!S.lang) S.lang = S.ui;
let engine = null, families = [], tickers = [], cov = {}, dataCache = {}, current = null, rendered = [], seq = 0;
const tr = () => T[S.ui];
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
const file = tk => tk.replace(/\./g, "-");
const known = tk => tickers.some(([t]) => t === tk);
const listURL = () => "tickers/" + (S.ui === "en" ? "?ui=en" : "");

// ---------- colour contrast (WCAG relative luminance) ----------
function lum(hex) {
  const c = hex.replace("#", ""), v = [0, 2, 4].map(i => parseInt(c.slice(i, i + 2), 16) / 255);
  const f = x => x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4);
  return 0.2126 * f(v[0]) + 0.7152 * f(v[1]) + 0.0722 * f(v[2]);
}
function contrast(a, b) { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); }
function mixHex(a, b, w) {
  const p = h => [0, 2, 4].map(i => parseInt(h.replace("#", "").slice(i, i + 2), 16));
  const x = p(a), y = p(b);
  return "#" + x.map((v, i) => Math.round(v + (y[i] - v) * w).toString(16).padStart(2, "0")).join("");
}
// The page stays neutral (near-white, black buttons) so the cards carry all the colour; the chosen
// style shows only on its thumbnail and the chip in the step-2 summary. (A page-wide tint was tried and dropped.)
function applyTint() {}

// ---------- toast ----------
let toastT = null;
function toast(msg) {
  const el = $("#toast"); el.textContent = msg; el.hidden = false;
  clearTimeout(toastT); toastT = setTimeout(() => { el.hidden = true; }, 2600);
}

// ---------- UI text ----------
function applyUI() {
  const t = tr();
  document.documentElement.lang = S.ui === "zh" ? "zh-CN" : "en";
  document.title = "earnings-card · " + t.brand;
  document.querySelectorAll('meta[property="og:title"],meta[name="twitter:title"]').forEach(m => m.setAttribute("content", document.title));
  const ogl = document.querySelector('meta[property="og:locale"]'); if (ogl) ogl.setAttribute("content", S.ui === "zh" ? "zh_CN" : "en_US");
  document.querySelectorAll("[data-i]").forEach(el => {
    const v = t[el.dataset.i];
    if (typeof v === "string") (el.dataset.i === "foot" ? el.innerHTML = v : el.textContent = v);
  });
  document.querySelectorAll("[data-ph]").forEach(el => el.placeholder = t[el.dataset.ph]);
  $("#avatarBtn").title = t.avatar;
  $("#navTickers").href = listURL();
  document.querySelectorAll("#ratio button").forEach(b => b.title = t.r[b.dataset.v]);
  $("#ratiohint").textContent = t.r[S.ratio];
  drawCoverage();
  drawSwatches();
  drawChecks();
  drawPeriodPicker();
  drawPresets();
  drawRecent();
  drawTickerNote();
  drawQuick();
  drawSummaries();
  if ($("#tkerr").dataset.t) showTkErr($("#tkerr").dataset.t);
  else if ($("#tkerr").dataset.empty) showEmptyErr();
  setSeg("#uilang", S.ui);
  if (current) $("#meta").innerHTML = metaHTML();
  if (rendered.length) drawTiles(rendered.map(c => c.name), rendered);
}
function drawCoverage() {
  if (!tickers.length) return;
  $("#coverage").innerHTML = `${esc(tr().coverage(tickers.length))} <a href="${listURL()}">${esc(tr().seeList)}</a>`;
}
function setSeg(sel, v) { document.querySelectorAll(sel + " button").forEach(b => b.classList.toggle("on", b.dataset.v === v)); }
function bindSeg(sel, key, after) {
  document.querySelectorAll(sel + " button").forEach(b => b.onclick = () => {
    S[key] = b.dataset.v; setSeg(sel, S[key]); after && after(); schedule();
  });
  setSeg(sel, S[key]);
}
function swatchHTML(s) {
  const on = s.id === S.style, rec = REC_STYLES.includes(s.id);
  return `<button class="sw${on ? " on" : ""}" data-v="${s.id}" aria-pressed="${on}" title="${esc(s[S.ui])}">
    <img src="styles/thumbs/${s.id}.webp" alt="" width="84" height="105" loading="lazy" decoding="async" style="background:${s.grad || s.bg}">
    ${rec ? `<span class="rec">${esc(tr().rec)}</span>` : ""}<em>${esc(s[S.ui])}</em></button>`;
}
function drawSwatches() {
  $("#styles").innerHTML = STYLES.filter(s => MAIN_STYLES.includes(s.id)).map(swatchHTML).join("");
  $("#styles2").innerHTML = STYLES.filter(s => !MAIN_STYLES.includes(s.id)).map(swatchHTML).join("");
  if (!MAIN_STYLES.includes(S.style)) $("#moreStyles").open = true;
  document.querySelectorAll(".sw").forEach(b => b.onclick = () => {
    S.style = b.dataset.v; drawSwatches(); syncColorInputs(); schedule();
  });
  const on = $(".sw.on");
  if (on && on.parentElement.scrollWidth > on.parentElement.clientWidth) on.scrollIntoView({block: "nearest", inline: "nearest"});
  drawSummaries();
}
function syncColorInputs() {
  const st = STYLES.find(s => s.id === S.style), base = {bg: st.bg, ink: st.ink, hi: st.hi, a2: A2[st.id]};
  for (const k of ["bg", "ink", "hi", "a2"]) {
    const el = $("#c-" + k);
    el.value = (S.colorOn[k] && S.colors[k] ? S.colors[k] : base[k]).toLowerCase();
    document.querySelector(`.colors [data-c=${k}]`).checked = !!S.colorOn[k];
  }
  $("#updown").checked = S.updown === "cn";
  checkContrast();
}
function checkContrast() {
  const st = STYLES.find(s => s.id === S.style), w = $("#cwarn");
  if (!S.colorOn.bg && !S.colorOn.ink) { w.hidden = true; return; }
  const bg = S.colorOn.bg ? $("#c-bg").value : st.bg, ink = S.colorOn.ink ? $("#c-ink").value : st.ink;
  const r = contrast(bg, ink);
  w.hidden = r >= 4.5;
  w.textContent = tr().lowContrast(r.toFixed(1));
}

// ---------- which cards ----------
function availability() {
  const t = tr(), d = current && current.data, a = {};
  for (const c of CARD_ORDER) a[c] = "";
  if (d && !(d.segments && Object.keys(d.segments).length)) a.mix = t.noMix;
  if (S.period === "annual") a.guide = t.noGuideAnnual;
  else if (!(current && current.guide)) a.guide = t.noGuide;
  if (S.ratio === "16:9") a.wide = t.noWide;
  if (d && "prev" in d && !d.prev) a.income = a.yoy = t.noPrev;
  return a;
}
// What render.py's card_names() will return, so placeholders can go up before the first card is back.
function expectedNames() {
  const av = availability();
  return CARD_ORDER.filter(c => !S.off.has(c) && !av[c]);
}
function drawChecks() {
  const t = tr(), av = availability();
  const row = c => `<label class="${av[c] ? "off" : ""}" title="${av[c]}">
    <input type="checkbox" value="${c}" ${av[c] ? "disabled" : ""} ${!av[c] && !S.off.has(c) ? "checked" : ""}>${t.names[c]}</label>`;
  $("#cards").innerHTML = CARD_ORDER.filter(c => !EXTRA.includes(c)).map(row).join("");
  $("#cards2").innerHTML = EXTRA.map(row).join("");
  document.querySelectorAll("#cards input, #cards2 input").forEach(i => i.onchange = () => {
    i.checked ? S.off.delete(i.value) : S.off.add(i.value); schedule();
  });
}

// ---------- status ----------
function status(msg, err, prog, detail) {
  const el = $("#status");
  el.hidden = !msg; el.classList.toggle("err", !!err);
  $("#statusText").textContent = msg || "";
  $("#statusDetail").hidden = !err || !detail;   // technical details only behind 详情, and only for errors
  $("#statusDetailText").textContent = detail || "";
  $("#retry").hidden = !err || !retryFn;
  // We can't measure how long Pyodide or a card will take, so the bar never pretends: it is an
  // indeterminate sweep whenever something is working (the text says what, and "card 3 of 8" is a real count).
  $("#prog").hidden = !prog || !!err;
}
let retryFn = null;
function fail(msg, retry, detail) { retryFn = retry || null; status(msg, true, null, detail); }

// ---------- ticker search ----------
function lev(a, b) {
  const m = Array.from({length: a.length + 1}, (_, i) => [i]);
  for (let j = 1; j <= b.length; j++) m[0][j] = j;
  for (let i = 1; i <= a.length; i++) for (let j = 1; j <= b.length; j++)
    m[i][j] = Math.min(m[i - 1][j] + 1, m[i][j - 1] + 1, m[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
  return m[a.length][b.length];
}
function searchHits(raw, n = 8) {
  const v = raw.trim().toUpperCase(), lv = raw.trim().toLowerCase(), flat = v.replace(/[.\-\s]/g, "");
  if (!v) return [];
  const zh = tk => (cov[tk] && cov[tk].zh) || "";
  const a = tickers.filter(([tk]) => tk.startsWith(v) || tk.replace(".", "").startsWith(flat));
  const b = tickers.filter(([tk, nm]) => !a.some(x => x[0] === tk) && (nm.toLowerCase().includes(lv) || zh(tk).toLowerCase().includes(lv)));
  return a.concat(b).slice(0, n);
}
// The ticker the input means: an exact ticker (BRKB / BRK-B / brk.b all mean BRK.B), or the only match of a name.
function resolveTicker(raw) {
  const v = raw.trim().toUpperCase(), flat = v.replace(/[.\-\s]/g, "");
  if (!v) return null;
  if (!tickers.length) return v;   // list didn't load: try the file anyway
  const ex = tickers.find(([tk]) => tk === v || tk.replace(".", "") === flat);
  if (ex) return ex[0];
  const zhHit = tickers.find(([tk]) => cov[tk] && cov[tk].zh === raw.trim());
  if (zhHit) return zhHit[0];
  const hits = searchHits(raw);
  return hits.length === 1 && !/^[A-Z.\-]{1,6}$/.test(v) ? hits[0][0] : null;
}
function similar(raw) {
  const v = raw.trim().toUpperCase();
  const hits = searchHits(raw, 3).map(h => h[0]);
  if (hits.length >= 3 || !/^[A-Z.\-]+$/.test(v)) return hits;
  const near = tickers.map(([tk]) => [tk, lev(v, tk)]).filter(([tk, d]) => d <= Math.max(1, Math.floor(v.length / 2)) && !hits.includes(tk))
    .sort((x, y) => x[1] - y[1]).map(x => x[0]);
  return hits.concat(near).slice(0, 3);
}
function showTkErr(raw) {
  raw = String(raw == null ? "" : raw).trim();
  if (!raw) { showEmptyErr(); return; }   // never "isn't supported" without the ticker in it
  const t = tr(), el = $("#tkerr"), sim = similar(raw);
  el.dataset.t = raw; delete el.dataset.empty;
  el.innerHTML = `<b>${esc(t.unsupported(raw.toUpperCase()))}</b>。${esc(t.unsupportedTail(tickers.length))}` +
    (sim.length ? `<br>${esc(t.didYouMean)} ${sim.map(s => `<button class="chip" data-t="${esc(s)}">${esc(s)}</button>`).join(" ")}` : "") +
    `<br><a href="${listURL()}">${esc(t.fullList)}</a>`;
  if (S.ui === "en") el.innerHTML = el.innerHTML.replace("</b>。", "</b>. ");
  el.hidden = false;
  el.querySelectorAll("button[data-t]").forEach(b => b.onclick = () => pickTicker(b.dataset.t));
}
function showEmptyErr() {
  const el = $("#tkerr"); delete el.dataset.t; el.dataset.empty = "1";
  el.innerHTML = `<b>${esc(tr().emptyTicker)}</b>`; el.hidden = false;
}
function hideTkErr() { const el = $("#tkerr"); el.hidden = true; delete el.dataset.t; delete el.dataset.empty; }
function drawTickerNote() {
  const t = tr(), el = $("#tknote"), c = cov[S.ticker];
  if (!c || !c.partial || !c.partial.length || $("#tkerr").dataset.t) { el.hidden = true; return; }
  const parts = c.partial.map(p => {
    if (p === "few_quarter") return t.partial.few_quarter(c.q.length);
    if (t.partial[p]) return t.partial[p];
    const [per, f] = p.split(":");
    return t.partial.miss(per, f.split(",").map(x => t.fields[x] || x).join(S.ui === "zh" ? "、" : ", "));
  });
  el.textContent = t.partialHead + parts.join(S.ui === "zh" ? "；" : "; ") + t.partialTail;
  el.hidden = false;
}
function drawRecent() {
  const r = (lsGet("ecRecent") || []).filter(tk => tk !== S.ticker && (!tickers.length || known(tk))).slice(0, 6);
  const el = $("#recent");
  el.hidden = !r.length;
  el.innerHTML = `<small>${esc(tr().recent)}</small>` + r.map(tk => `<button class="chip" data-t="${esc(tk)}">${esc(tk)}</button>`).join("");
  el.querySelectorAll("button").forEach(b => b.onclick = () => pickTicker(b.dataset.t));
}
function pushRecent(tk) {
  const r = (lsGet("ecRecent") || []).filter(x => x !== tk);
  r.unshift(tk); lsSet("ecRecent", r.slice(0, 7));
}
// Switch to a ticker (from the list, Enter, the Generate button or a chip). Unknown ones get an inline error;
// the cards on screen stay as they are, nothing falls back to another stock.
function pickTicker(raw, force) {
  const inp = $("#ticker");
  raw = String(raw == null ? "" : raw).trim();
  $("#sugg").hidden = true; inp.setAttribute("aria-expanded", "false");
  if (!raw) { showEmptyErr(); drawTickerNote(); inp.value = ""; inp.focus(); return; }   // nothing typed: say so, don't regenerate the last stock
  const tk = resolveTicker(raw);
  if (!tk) { showTkErr(raw); drawTickerNote(); return; }
  hideTkErr();
  inp.value = tk;
  if (tk !== S.ticker || !current || force) {
    if (tk !== S.ticker) { S.headline = ""; $("#headline").value = ""; S.end = null; }   // a headline and a period are about one stock
    S.ticker = tk; saveURL(); drawTickerNote(); drawRecent(); drawQuick(); loadTicker();
  } else schedule(0);
}
function setupSearch() {
  const inp = $("#ticker"), ul = $("#sugg");
  let hits = [], idx = 0;
  const mark = () => ul.querySelectorAll("li").forEach((li, i) => { li.classList.toggle("on", i === idx); li.setAttribute("aria-selected", i === idx); });
  const show = () => {
    hits = searchHits(inp.value); idx = 0;
    ul.innerHTML = hits.map(([tk, n], i) => {
      const zh = cov[tk] && cov[tk].zh && cov[tk].zh !== tk ? `<em>${esc(cov[tk].zh)}</em>` : "";
      return `<li role="option" data-t="${tk}" class="${i === 0 ? "on" : ""}"><b>${tk}</b>${zh}<span>${esc(n)}</span></li>`;
    }).join("");
    ul.hidden = !hits.length; inp.setAttribute("aria-expanded", String(!ul.hidden));
  };
  inp.addEventListener("input", () => { show(); if (!inp.value.trim() || $("#tkerr").dataset.empty) hideTkErr(); });
  inp.addEventListener("focus", () => { inp.select(); });
  inp.addEventListener("keydown", e => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (ul.hidden) { show(); return; } e.preventDefault();
      idx = (idx + (e.key === "ArrowDown" ? 1 : hits.length - 1)) % hits.length; mark();
    } else if (e.key === "Enter") {
      e.preventDefault();
      pickTicker(!ul.hidden && hits[idx] ? hits[idx][0] : inp.value);
      if ($("#tkerr").hidden) inp.blur();
    } else if (e.key === "Escape") { ul.hidden = true; inp.setAttribute("aria-expanded", "false"); }
  });
  ul.addEventListener("mousedown", e => { const li = e.target.closest("li"); if (li) { e.preventDefault(); pickTicker(li.dataset.t); inp.blur(); } });
  inp.addEventListener("blur", () => setTimeout(() => { ul.hidden = true; if (!inp.value.trim() && !$("#tkerr").dataset.empty) inp.value = S.ticker; }, 150));
  $("#go").onclick = () => pickTicker(inp.value, true);
}

// ---------- data ----------
async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(r.status + " " + url);
  return r.json();
}
let labelsZh = null;
async function loadTicker() {
  const tk = S.ticker, my = ++seq;
  if (tickers.length && !known(tk)) {   // e.g. ?t=XYZ in the URL
    current = null; rendered = []; $("#grid").innerHTML = ""; delete $("#grid").dataset.sig; $("#meta").innerHTML = "";
    $("#zip").disabled = $("#copyCap").disabled = true; $("#capbox").hidden = true; $("#ideas").hidden = true;
    $("#ticker").value = tk; showTkErr(tk); drawTickerNote();
    fail(tr().notFound(tk, tickers.length));
    return;
  }
  drawSlots(expectedNames(), true);
  if (engine) status(tr().fLoading(tk), false, true);
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
    current = null; rendered = []; $("#grid").innerHTML = ""; delete $("#grid").dataset.sig; $("#meta").innerHTML = "";
    $("#zip").disabled = $("#copyCap").disabled = true;
    fail(tr().notFound(tk, tickers.length), () => { delete dataCache[tk]; loadTicker(); });
    return;
  }
  if (my !== seq) return;
  pushRecent(tk); drawRecent();
  pickPeriod();
  drawPeriodPicker();
  drawChecks();
  drawSlots(expectedNames(), true);
  schedule(0);
}
// A data file holds, per report type, a block {ticker, company, period, series, periods: [...]} (last 8 quarters /
// 5 fiscal years, oldest first). render.py's period_record() rebuilds the chosen period's trend from series.
// Older files hold one record per type; treat it as a block with a single period.
const periodsOf = b => b ? (b.periods || [b]) : [];
function fyfq(p) {
  const m = /^FY(\d{4})(?: Q(\d))?/.exec(p.fiscal_label || "");
  return m ? {fy: m[1], fq: m[2] || ""} : {fy: p.period_end.slice(0, 4), fq: ""};
}
function pickPeriod() {
  const c = dataCache[S.ticker];
  if (!c) { current = null; return; }
  let b = c.rec[S.period];
  if (!b) {   // only one report type for this stock (e.g. a bank whose quarterly tags we can't read): switch to it
    const other = S.period === "quarter" ? "annual" : "quarter";
    if (c.rec[other]) { S.period = other; S.end = null; setSeg("#period", S.period); b = c.rec[other]; }
  }
  document.querySelectorAll("#period button").forEach(btn => { btn.disabled = !c.rec[btn.dataset.v]; });
  const ps = periodsOf(b);
  let p = ps.find(x => x.period_end === S.end);
  if (!p) { p = ps[ps.length - 1]; S.end = null; }
  if (!p) { current = null; return; }
  const d = b.periods ? Object.assign({ticker: b.ticker, company: b.company, period: b.period}, p) : p;
  // An outlook file belongs to one quarter: use it only for that quarter.
  const g = c.guide[S.lang];
  const guide = S.period === "quarter" && g && g.prior && g.prior.period === d.fiscal_label ? g : null;
  current = {data: d, block: b, guide, labels: Object.assign({}, labelsZh || {}, c.labels)};
}
function drawPeriodPicker() {
  const c = dataCache[S.ticker], b = c && c.rec[S.period], ps = periodsOf(b), t = tr();
  const fySel = $("#fy"), fqSel = $("#fq");
  $("#pp").hidden = !ps.length;
  if (!ps.length) return;
  const latest = ps[ps.length - 1], cur = ps.find(x => x.period_end === S.end) || latest, k = fyfq(cur);
  const years = [...new Set(ps.map(x => fyfq(x).fy))].reverse();
  fySel.innerHTML = years.map(y => `<option value="${y}"${y === k.fy ? " selected" : ""}>FY${y}${y === fyfq(latest).fy && S.period === "annual" ? t.latest : ""}</option>`).join("");
  const inYear = ps.filter(x => fyfq(x).fy === k.fy).reverse();
  fqSel.hidden = S.period === "annual";
  fqSel.innerHTML = inYear.map(x => {
    const f = fyfq(x).fq;
    return `<option value="${x.period_end}"${x === cur ? " selected" : ""}>${f ? t.fqOpt(f) : x.period_end}${x === latest ? t.latest : ""}</option>`;
  }).join("");
  $("#fyLab").textContent = t.fy; $("#fqLab").textContent = t.fq; $("#fqLab").hidden = S.period === "annual";
}
function setupPeriodPicker() {
  $("#fy").onchange = () => {
    const ps = periodsOf(dataCache[S.ticker] && dataCache[S.ticker].rec[S.period]);
    const hit = ps.filter(x => fyfq(x).fy === $("#fy").value);   // newest period of that year
    const p = hit[hit.length - 1];
    S.end = p && p !== ps[ps.length - 1] ? p.period_end : null;
    drawPeriodPicker(); schedule(0);
  };
  $("#fq").onchange = () => {
    const ps = periodsOf(dataCache[S.ticker] && dataCache[S.ticker].rec[S.period]);
    S.end = $("#fq").value === (ps[ps.length - 1] || {}).period_end ? null : $("#fq").value;
    drawPeriodPicker(); schedule(0);
  };
}
function metaHTML() {
  const d = current.data;
  const name = d.company === d.company.toUpperCase() ? d.company.replace(/\w\S*/g, w => w[0] + w.slice(1).toLowerCase()) : d.company;
  const zh = S.ui === "zh" && cov[d.ticker] && cov[d.ticker].zh && cov[d.ticker].zh !== d.ticker ? cov[d.ticker].zh + " · " : "";
  return `<b>${esc(d.ticker)}</b>${esc(zh)}${esc(name)} · ${esc(tr().meta(d))}`;
}

// ---------- tiles ----------
const cardSize = name => name === "wide" && S.ratio !== "16:9" ? [1600, 900] : SIZES[S.ratio];
function tileHTML(name, i, card) {
  const t = tr(), [w, h] = card ? [card.w, card.h] : cardSize(name);
  const wide = w > h && S.ratio !== "16:9";
  const body = card ? card.svg : `<div class="skel" style="aspect-ratio:${w}/${h}"><span>${esc(t.names[name] || name)}</span></div>`;
  return `<figure class="tile${wide ? " wide" : ""}${card ? "" : " loading"}" data-n="${name}">
    <div class="img">${body}</div>
    <figcaption><span>${i + 1} · ${t.names[name] || name} · ${w}×${h}</span>
      <span class="tbtn"><button data-act="copy" data-k="${i}" ${card ? "" : "disabled"}>${t.copyImg}</button><button data-act="dl" data-k="${i}" ${card ? "" : "disabled"}>${t.download}</button></span></figcaption></figure>`;
}
function bindTile(fig) {
  fig.querySelectorAll("figcaption button").forEach(b => b.onclick = () => (b.dataset.act === "copy" ? copyOne : downloadOne)(+b.dataset.k, b));
}
function drawTiles(names, cards) {
  const grid = $("#grid");
  grid.className = "grid r" + S.ratio.replace(":", "");
  grid.dataset.sig = names.join(",") + "|" + S.ratio + "|" + S.ui;
  grid.innerHTML = names.map((n, i) => tileHTML(n, i, cards && cards[i])).join("");
  grid.querySelectorAll("figure").forEach(bindTile);
  showActs(!!(cards && cards.some(Boolean)) || rendered.length > 0);
}
// Placeholders for this set of cards. When the set on screen is the same, keep the old cards (dimmed)
// and swap each one as its new version arrives, so a colour change doesn't flash grey boxes.
function drawSlots(names, keep) {
  if (!engine && !rendered.length) { drawSample(names); return; }
  const grid = $("#grid"), sig = names.join(",") + "|" + S.ratio + "|" + S.ui;
  if (keep && grid.dataset.sig === sig) { grid.querySelectorAll("figure").forEach(f => f.classList.add("stale")); return; }
  drawTiles(names, null);
}
// Before the engine is up there is nothing of theirs to show: a finished NVDA cover (pre-rendered) shows
// what they will get, with the list of cards this set will hold. Real tiles replace it once rendering starts.
function drawSample(names) {
  const grid = $("#grid"), t = tr(), lg = S.lang === "en" ? "en" : "zh";
  const sig = "sample|" + lg + "|" + names.join(",");
  showActs(false);
  if (grid.dataset.sig === sig) return;
  grid.className = "grid sample-on"; grid.dataset.sig = sig;
  const list = names.map(n => `<li>${esc(t.names[n] || n)}</li>`).join("");
  grid.innerHTML = `<div class="sample"><figure><div class="img"><img src="sample/nvda-cover-${lg}.webp" width="720" height="900" alt="${esc(t.sampleAlt)}" decoding="async"></div>
</figure>
    <div class="sample-tx"><span class="badge">${esc(t.sampleBadge)}</span><h3>${esc(t.sampleTitle)}</h3><p>${esc(t.sampleLede(S.ticker, names.length))}</p><ol>${list}</ol></div></div>`;
}
// Copy / download-all only appear once there is something to copy or download.
function showActs(on) { const a = $(".bar .acts"); if (a) a.hidden = !on; }
function fillSlot(i, card) {
  const old = $("#grid").children[i];
  if (!old) return;
  const tmp = document.createElement("div");
  tmp.innerHTML = tileHTML(card.name, i, card);
  const fig = tmp.firstElementChild;
  old.replaceWith(fig); bindTile(fig);
  showActs(true);
}

// ---------- rendering ----------
let timer = null;
function schedule(ms = 140) { clearTimeout(timer); timer = setTimeout(render, ms); saveURL(); drawSummaries(); }
function options() {
  const cards = CARD_ORDER.filter(c => !S.off.has(c));
  const o = {lang: S.lang, style: S.style, font: S.font, ratio: S.ratio, cards, headline: S.headline.trim(),
    handle: S.handle.trim(), avatar: S.avatar, guidance: current.guide, period_end: current.data.period_end,
    labels: S.lang === "zh" ? current.labels : {}};
  for (const k of ["bg", "ink", "hi", "a2"]) if (S.colorOn[k] && S.colors[k]) o[k] = S.colors[k];
  if (S.updown) o.updown = S.updown;
  return o;
}
let fontPass = 0, jobId = 0, job = null, rerun = false;
// One card at a time in the worker. Changes made meanwhile set `rerun`: the running set stops after its
// current card and the newest state starts over, so a burst of edits never queues up a backlog.
function render(quiet) {
  pickPeriod();
  drawPeriodPicker();
  drawChecks();
  if (!dataCache[S.ticker]) return;
  if (!current) { fail(tr().noPeriod); $("#grid").innerHTML = ""; delete $("#grid").dataset.sig; rendered = []; $("#zip").disabled = true; return; }
  $("#meta").innerHTML = metaHTML();
  if (!engine) { drawSlots(expectedNames(), true); return; }
  if (job) { rerun = true; return; }
  const names = expectedNames();
  if (!names.length) { $("#grid").innerHTML = ""; delete $("#grid").dataset.sig; rendered = []; $("#zip").disabled = true; fail(tr().noCards); return; }
  if (!quiet) { fontPass = 0; drawSlots(names, true); }
  job = {id: ++jobId, data: JSON.stringify(current.block), o: options(), i: 0, out: [], names, quiet: !!quiet};
  $("#zip").disabled = true;
  step();
}
function step() {
  if (!job.quiet) status(tr().fDrawing(job.i + 1, job.names.length), false, true);
  engine.postMessage({type: "render", id: job.id, data: job.data, opts: JSON.stringify(Object.assign({}, job.o, {only: job.i}))});
}
async function onWorker(m) {
  if (m.type === "extras") { onExtras(m); return; }
  if (m.type !== "result" && m.type !== "error") return;
  if (!job || m.id !== job.id) return;
  if (rerun) { rerun = false; job = null; render(); return; }
  if (m.type === "error") {
    console.error(m.message, m.stack); job = null;
    fail(tr().fRenderFail, () => render(), tr().renderFail + String(m.message).slice(0, 600));
    return;
  }
  const r = JSON.parse(m.out);
  if (job.i === 0 && r.names.join(",") !== job.names.join(",")) {   // the engine knows better (e.g. no year-ago data)
    job.names = r.names;
    if (!job.quiet) drawTiles(job.names, null);
  }
  if (!job.names.length) { job = null; $("#grid").innerHTML = ""; rendered = []; fail(tr().noCards); return; }
  const card = r.cards[0];
  job.out[job.i] = card;
  if ($("#grid").dataset.sig !== job.names.join(",") + "|" + S.ratio + "|" + S.ui) drawTiles(job.names, job.out);
  else fillSlot(job.i, card);
  job.i++;
  if (job.i < job.names.length) { step(); return; }
  const done = job; job = null;
  rendered = done.out;
  status("");
  $("#zip").disabled = !rendered.length;
  saveLast();
  requestExtras();
  watchJump();
  // Web fonts load lazily (Chinese fonts in slices): once the glyphs on these cards are in, measure again.
  if (await ensureFonts(rendered) && fontPass < 3) { fontPass++; await sendTables(); render(true); }
}

// ---------- caption + headline ideas ----------
let extrasKey = "", extrasId = 0;
function requestExtras() {
  if (!engine || !current) return;
  const key = [S.ticker, current.data.period_end, S.lang].join("|");
  if (key === extrasKey) return;
  extrasKey = key;
  const zh = cov[S.ticker] && cov[S.ticker].zh;
  engine.postMessage({type: "extras", id: "x" + (++extrasId), data: JSON.stringify(current.block),
    opts: JSON.stringify({lang: S.lang, period_end: current.data.period_end, name_zh: zh && zh !== S.ticker ? zh : ""})});
}
function onExtras(m) {
  if (m.id !== "x" + extrasId) return;
  if (!m.out) { console.warn("extras failed", m.message); extrasKey = ""; return; }
  const x = JSON.parse(m.out);
  $("#caption").value = x.caption;
  $("#capbox").hidden = false; $("#copyCap").disabled = false;
  const ideas = $("#ideas");
  ideas.hidden = !x.headlines.length;
  ideas.innerHTML = `<small>${esc(tr().ideasLab)}</small>` + x.headlines.map(h => `<button class="chip idea">${esc(h)}</button>`).join("");
  ideas.querySelectorAll("button").forEach(b => b.onclick = () => {
    S.headline = b.textContent.slice(0, 60); $("#headline").value = S.headline; schedule(0);
  });
}
async function copyText(text) {
  try { await navigator.clipboard.writeText(text); return true; }
  catch (e) {
    const ta = $("#caption"); $("#capbox").open = true; ta.focus(); ta.select();
    try { return document.execCommand("copy"); } catch (_) { return false; }
  }
}
async function copyCaption() {
  const ok = await copyText($("#caption").value);
  toast(ok ? tr().captionCopied : tr().copyFail);
}

// ---------- copy image ----------
async function copyOne(i, btn) {
  const card = (job && job.out[i]) || rendered[i], t = tr();
  if (!card) return;
  const label = btn.textContent;
  btn.disabled = true; btn.textContent = "…";
  const pngP = fontsFor([card]).then(({css}) => toPNG(card, css));
  let ok = false;
  // Safari wants the ClipboardItem made inside the click, holding a promise of the blob.
  if (window.ClipboardItem && navigator.clipboard && navigator.clipboard.write && window.isSecureContext) {
    try { await navigator.clipboard.write([new ClipboardItem({"image/png": pngP})]); ok = true; }
    catch (e) { console.warn("clipboard image failed", e); }
  }
  try {
    if (ok) { btn.textContent = t.copied; toast(t.imgCopied); }
    else { save(await pngP, fname(card, i)); btn.textContent = t.copyFallback; toast(t.imgFallback); }
  } catch (e) { btn.textContent = label; fail(t.exportFail + e.message); }
  setTimeout(() => { btn.textContent = label; btn.disabled = false; }, 1600);
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
  for (const f of fams) for (const w of fontWeights(f)) specs.push(`${w} 20px "${f}"`);
  const missing = specs.filter(s => { try { return !document.fonts.check(s, text); } catch (e) { return false; } });
  if (missing.length) await Promise.all(missing.map(s => document.fonts.load(s, text).catch(() => null)));
  return missing.length > 0 || loadedFaces() > tableFaces;   // new faces since the width tables: measure again
}
// Width tables for the worker: every char we expect, at 100px, per (font stack as render.py passes it, weight).
// Any other char >= U+2E80 uses the width of 中; anything else unlisted uses the width of n.
const mctx = document.createElement("canvas").getContext("2d");
const TABLE_CHARS = (() => {
  let s = "";
  for (let c = 32; c < 127; c++) s += String.fromCharCode(c);
  s += "·—–…×÷±°€£¥‘’“”•→←↑↓▲▼√≈≤≥‰é";
  s += "，。、：；（）％！？《》「」【】『』～￥＋－／　";
  return [...new Set(s)];
})();
const TABLE_WEIGHTS = [300, 400, 500, 600, 700, 800, 900];
function buildTables() {
  const t = {};
  for (const fam of families) for (const w of TABLE_WEIGHTS) {
    mctx.font = `${w} 100px ${fam}`;
    const chars = {};
    for (const ch of TABLE_CHARS) chars[ch] = mctx.measureText(ch).width;
    t[fam + "|" + w] = {chars, cjk: mctx.measureText("中").width, other: mctx.measureText("n").width};
  }
  return t;
}
// Canvas measureText doesn't wait for a web font: a weight that isn't loaded yet measures in a fallback face
// (and only starts loading). So load every face the tables use first, and remember how many faces were
// loaded when the tables were built: ensureFonts re-measures whenever more have loaded since.
let tableFaces = -1;
const loadedFaces = () => document.fonts ? [...document.fonts].filter(f => f.status === "loaded").length : 0;
async function loadTableFonts() {
  if (!document.fonts) return;
  const sample = TABLE_CHARS.join("") + "中";
  await Promise.all(families.flatMap(fam => TABLE_WEIGHTS.map(w => document.fonts.load(`${w} 100px ${fam}`, sample).catch(() => null))));
}
async function sendTables() {
  if (!engine) return;
  await loadTableFonts();
  tableFaces = loadedFaces();
  engine.postMessage({type: "tables", tables: buildTables()});
}

// Subset the fonts to exactly the characters on the cards and embed them, so the PNG matches the preview.
const fontCssCache = {};
async function embeddedFontCSS(cards) {
  const chars = [...new Set(textOf(cards).replace(/\s/g, ""))].sort().join("") + " ";
  const fams = new Set();
  cards.forEach(c => familiesIn(c.svg).forEach(f => fams.add(f)));
  const parts = await Promise.all([...fams].map(async f => {
    const key = f + "|" + chars;
    if (!fontCssCache[key]) fontCssCache[key] = (async () => {
      const url = `https://fonts.googleapis.com/css2?family=${GFONTS[f]}:wght@${fontWeights(f).join(";")}&text=${encodeURIComponent(chars)}`;
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
  const card = (job && job.out[i]) || rendered[i], label = btn.textContent;
  if (!card) return;
  btn.disabled = true; btn.textContent = "…";
  try {
    const {css, warn} = await fontsFor([card]);
    save(await toPNG(card, css), fname(card, i));
    if (warn) status(warn.trim());
  } catch (e) { fail(tr().exportFail + e.message); }
  finally { btn.disabled = false; btn.textContent = label; }
}
async function downloadAll() {
  const btn = $("#zip"), label = btn.textContent, cards = rendered.filter(Boolean);
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
  } catch (e) { fail(tr().exportFail + e.message); }
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

// ---------- presets (named style setups) ----------
const PRESET_KEYS = ["style", "font", "ratio", "lang", "colors", "colorOn", "updown"];
function snapshot() {
  const p = {};
  for (const k of PRESET_KEYS) p[k] = JSON.parse(JSON.stringify(S[k]));
  p.off = [...S.off]; p.handle = S.handle;
  return p;
}
function applyPreset(p) {
  for (const k of PRESET_KEYS) if (k in p) S[k] = JSON.parse(JSON.stringify(p[k]));
  if (p.off) S.off = new Set(p.off);
  if ("handle" in p) { S.handle = p.handle || ""; $("#handle").value = S.handle; localStorage.echandle = S.handle; }
  setSeg("#font", S.font); setSeg("#ratio", S.ratio); setSeg("#lang", S.lang);
  $("#ratiohint").textContent = tr().r[S.ratio];
  drawSwatches(); syncColorInputs(); drawChecks(); schedule(0);
}
function drawPresets() {
  const ps = lsGet("ecPresets") || {}, sel = $("#presetSel"), cur = sel.value;
  sel.innerHTML = `<option value="">${esc(tr().presetNone)}</option>` + Object.keys(ps).map(n => `<option${n === cur ? " selected" : ""}>${esc(n)}</option>`).join("");
  $("#presetDel").hidden = !sel.value;
}
function setupPresets() {
  const sel = $("#presetSel");
  sel.onchange = () => { const ps = lsGet("ecPresets") || {}; if (ps[sel.value]) applyPreset(ps[sel.value]); $("#presetDel").hidden = !sel.value; };
  $("#presetSave").onclick = () => {
    const name = (prompt(tr().presetAsk, sel.value || "") || "").trim().slice(0, 30);
    if (!name) return;
    const ps = lsGet("ecPresets") || {}; ps[name] = snapshot(); lsSet("ecPresets", ps);
    drawPresets(); sel.value = name; $("#presetDel").hidden = false; toast(tr().presetSaved(name));
  };
  $("#presetDel").onclick = () => {
    const ps = lsGet("ecPresets") || {}; delete ps[sel.value]; lsSet("ecPresets", ps); sel.value = ""; drawPresets();
  };
  drawPresets();
}

// ---------- "more settings" + mobile jump ----------
// Three steps: only step 1 starts open; a closed step shows a one-line summary of what it holds.
function setupSteps() {
  document.querySelectorAll(".step").forEach(d => d.addEventListener("toggle", drawSummaries));
}
function drawSummaries() {
  applyTint();
  const t = tr(), st = STYLES.find(x => x.id === S.style), c = current && current.data;
  const s1 = $("#sum1"), s2 = $("#sum2"), s3 = $("#sum3");
  if (!s1) return;
  s1.textContent = S.ticker + " · " + (c && c.fiscal_label ? c.fiscal_label : (S.period === "annual" ? t.annual : t.quarter));
  // a 12px chip of the current style (background + accent, honouring custom colours) before the words
  const bg = S.colorOn.bg && S.colors.bg ? S.colors.bg : st ? st.bg : "#eee";
  const ink = S.colorOn.ink && S.colors.ink ? S.colors.ink : st ? st.ink : "#000";
  const hi = S.colorOn.hi && S.colors.hi ? S.colors.hi : st ? st.hi : "#888";
  s2.innerHTML = `<i class="sw" style="background:linear-gradient(135deg,${esc(bg)} 0 50%,${esc(hi)} 50% 100%);border-color:${esc(ink)}" aria-hidden="true"></i>` + esc(t.sum2(st ? st[S.ui] : S.style, S.ratio, S.lang));
  s3.textContent = t.sum3(expectedNames().length, !!S.headline, !!S.handle);
}

// ---------- quick entries: just reported + earnings calendar ----------
let calendar = null;
// "YYYY-MM-DD" today in New York: report dates are US dates
function usToday() {
  try { return new Intl.DateTimeFormat("en-CA", {timeZone: "America/New_York"}).format(new Date()); }
  catch (e) { return new Date().toISOString().slice(0, 10); }
}
const md = d => S.ui === "zh" ? `${+d.slice(5, 7)}/${+d.slice(8, 10)}` : d.slice(5).replace("-", "/");
const wday = d => tr().wd[new Date(d + "T12:00:00Z").getUTCDay()];
function quickChip(tk, title, extra) {
  const zh = S.ui === "zh" && cov[tk] && cov[tk].zh && cov[tk].zh !== tk ? cov[tk].zh : "";
  return `<button class="chip qc${tk === S.ticker ? " on" : ""}" data-t="${esc(tk)}" title="${esc([zh, title].filter(Boolean).join(" · "))}">${esc(tk)}${extra || ""}</button>`;
}
// The ~8 tickers with the newest filings on file (coverage.json "filed").
function justFiled(rows, n = 8) {
  return rows.filter(r => r.filed).sort((a, b) => b.filed.localeCompare(a.filed) || a.t.localeCompare(b.t)).slice(0, n);
}
// Upcoming rows (today onward, within `days`), grouped by date: [[date, [rows]]].
function upcoming(cal, today, days = 14) {
  const rows = (cal && cal.rows) || [], end = new Date(Date.parse(today + "T00:00:00Z") + days * 864e5).toISOString().slice(0, 10);
  const g = new Map();
  for (const r of rows) {
    if (!r || !r.t || !r.date || r.date < today || r.date > end) continue;
    if (tickers.length && !known(r.t)) continue;
    if (!g.has(r.date)) g.set(r.date, []);
    g.get(r.date).push(r);
  }
  return [...g.entries()].sort((a, b) => a[0].localeCompare(b[0]));
}
function drawQuick() {
  const t = tr(), rows = Object.values(cov);
  const filed = justFiled(rows);
  $("#qFiled").hidden = !filed.length;
  $("#filedChips").innerHTML = filed.map(r => quickChip(r.t, t.filedOn(r.filed))).join("");
  const today = usToday(), days = upcoming(calendar, today);
  const n = days.reduce((k, [, r]) => k + r.length, 0);
  $("#qCal").hidden = !n;
  if (n) {
    const tmr = new Date(Date.parse(today + "T00:00:00Z") + 864e5).toISOString().slice(0, 10);
    const label = d => d === today ? t.today : d === tmr ? t.tomorrow + " " + wday(d) : `${md(d)} ${wday(d)}`;
    const [d0, r0] = days[0];
    $("#calNext").innerHTML = `${esc(t.calCount(n))} · <b>${esc(label(d0))}</b> ${r0.slice(0, 4).map(r => esc(r.t)).join(" ")}${r0.length > 4 ? " …" : ""}`;
    $("#calList").innerHTML = days.map(([d, rs]) => `<div class="calday"><span class="cald">${esc(label(d))}</span><div class="qchips">${
      rs.map(r => quickChip(r.t, t.reportsOn(md(d), wday(d)) + (r.time ? " · " + t[r.time] : ""),
        r.time ? `<i class="tm ${r.time}" aria-label="${esc(t[r.time])}"></i>` : "")).join("")}</div></div>`).join("")
      + `<div class="callegend"><span><i class="tm bmo"></i> ${esc(t.bmo)}</span><span><i class="tm amc"></i> ${esc(t.amc)}</span></div>`;
  }
  document.querySelectorAll("#quick .qc").forEach(b => b.onclick = () => { S.end = null; pickTicker(b.dataset.t, true); });
}

let jumpObs = null;
function watchJump() {
  const btn = $("#jump");
  if (jumpObs || !("IntersectionObserver" in window)) return;
  btn.onclick = () => $("#preview").scrollIntoView({behavior: "smooth"});
  jumpObs = new IntersectionObserver(es => {
    const vis = es.some(e => e.isIntersecting);
    btn.hidden = vis || window.innerWidth > 900 || !$("#grid").children.length;
  });
  jumpObs.observe($("#preview"));
}

// ---------- URL + last settings ----------
function saveURL() {
  const p = new URLSearchParams();
  p.set("t", S.ticker);
  if (S.period !== "quarter") p.set("p", S.period);
  if (S.end) p.set("e", S.end);
  if (S.ratio !== "4:5") p.set("r", S.ratio);
  if (S.style !== "light") p.set("s", S.style);
  if (S.font !== "auto") p.set("f", S.font);
  if (S.lang !== S.ui) p.set("lang", S.lang);
  if (S.ui !== "zh") p.set("ui", S.ui);
  if (S.headline) p.set("h", S.headline);
  const on = CARD_ORDER.filter(c => !S.off.has(c));
  if (on.join(",") !== CARD_ORDER.filter(c => !DEFAULT_OFF.includes(c)).join(",")) p.set("c", on.join(","));
  // A bare URL showing the untouched default (NVDA sample, browser language) stays bare: a fresh visit is a clean homepage.
  const bare = !location.search || location.search === "?";
  const keys = [...p.keys()];
  if (bare && p.get("t") === "NVDA" && keys.every(k => k === "t" || (k === "ui" && S.ui === browserUI()))) return;
  history.replaceState(null, "", "?" + p.toString());
}
// The settings to come back to next visit (colours aren't in the URL, so they live here).
function saveLast() {
  if (!current) return;
  const p = new URLSearchParams(location.search); p.delete("ui"); p.set("lang", S.lang);
  try { sessionStorage.ecui = S.ui; } catch (e) {}   // this tab keeps its UI language too
  ssSet("ecLast", {qs: p.toString(), colors: S.colors, colorOn: S.colorOn, updown: S.updown});
}

// ---------- boot ----------
const STAGES = ["worker", "probe", "load npmmirror", "load cdn", "load local", "render.py", "init"];
let bootT0 = 0, bootStage = "worker", bootTick = null;
function showBoot() {
  if ($("#status").classList.contains("err") && !$("#status").hidden) return;   // e.g. an unsupported ticker: keep saying so
  // Friendly words only: which CDN or stage the engine is on stays out of sight (it is in the error details).
  const t = tr(), sec = (Date.now() - bootT0) / 1000;
  if (bootStage === "fonts") { status(t.fFonts, false, true); return; }
  status(t.fBoot[sec < 8 ? 0 : sec < 25 ? 1 : 2], false, true);
}
async function bootEngine() {
  bootT0 = Date.now(); bootStage = "worker"; showBoot();
  clearInterval(bootTick); bootTick = setInterval(showBoot, 1000);
  try {
    engine = await startEngine(st => { bootStage = st; showBoot(); });
  } catch (e) {
    console.error(e);
    clearInterval(bootTick);
    const st = String(e && e.stack || "").split("\n").slice(0, 4).join(" | "), t = tr();
    fail(t.fBootFail, bootEngine, "[" + (e && e.stage || "?") + (t.stages[e && e.stage] ? " · " + t.stages[e.stage] : "") + "] (" + (e && e.message) + ") " + st + " · " + navigator.userAgent);
    return;
  }
  clearInterval(bootTick);
  bootStage = "fonts"; showBoot();
  await (document.fonts ? document.fonts.ready : Promise.resolve());
  await sendTables();
  if (dataCache[S.ticker]) schedule(0);
  else if (!$("#status").classList.contains("err")) status(tr().fLoading(S.ticker), false, true);
}
async function boot() {
  applyUI();
  bindSeg("#period", "period", () => { S.end = null; pickPeriod(); drawPeriodPicker(); });
  setupPeriodPicker();
  bindSeg("#ratio", "ratio", () => { $("#ratiohint").textContent = tr().r[S.ratio]; });
  bindSeg("#font", "font");
  bindSeg("#lang", "lang", () => { pickPeriod(); });
  document.querySelectorAll("#uilang button").forEach(b => b.onclick = () => {
    const prev = S.ui; S.ui = b.dataset.v; try { sessionStorage.ecui = S.ui; } catch (_) {}
    if (S.lang === prev) { S.lang = S.ui; setSeg("#lang", S.lang); }
    applyUI(); schedule(0);
  });
  $("#headline").value = S.headline;
  $("#headline").oninput = e => { S.headline = e.target.value; schedule(400); };
  document.querySelectorAll(".colors input[data-c]").forEach(cb => cb.onchange = () => {
    S.colorOn[cb.dataset.c] = cb.checked; if (cb.checked) S.colors[cb.dataset.c] = $("#c-" + cb.dataset.c).value;
    if (!cb.checked) syncColorInputs(); checkContrast(); schedule(0);
  });
  document.querySelectorAll(".colors input[type=color]").forEach(ci => ci.oninput = () => {
    const k = ci.id.slice(2); S.colorOn[k] = true; S.colors[k] = ci.value;
    document.querySelector(`.colors [data-c=${k}]`).checked = true; checkContrast(); schedule(120);
  });
  $("#updown").onchange = e => { S.updown = e.target.checked ? "cn" : ""; schedule(0); };
  syncColorInputs();
  setupWatermark();
  setupSearch();
  setupPresets();
  setupSteps();
  $("#zip").onclick = downloadAll;
  $("#copyCap").onclick = copyCaption;
  $("#retry").onclick = () => { const f = retryFn; retryFn = null; status(""); f && f(); };
  $("#ticker").value = S.ticker;
  drawSlots(expectedNames());

  // The engine (slow, first visit ~10 MB) and the data (small) load at the same time.
  const listP = Promise.all([
    getJSON("data/tickers.json").then(l => { tickers = l; }).catch(() => {}),
    getJSON("data/coverage.json").then(l => { for (const r of l) cov[r.t] = r; }).catch(() => {}),
  ]).then(() => { drawCoverage(); drawTickerNote(); drawRecent(); drawQuick(); });
  // the calendar is optional: a missing or empty file just hides that row
  Promise.all([listP, getJSON("data/calendar.json").then(c => { calendar = c; }).catch(() => { calendar = null; })]).then(drawQuick);
  getJSON("data/labels-zh.json").then(l => { labelsZh = l; }).catch(() => { labelsZh = {}; });
  const engP = bootEngine();
  await listP;
  loadTicker();
  await engP;
}
// Pyodide + render.py live in worker.js; the page itself never loads pyodide.js.
function startEngine(onStage) {
  return new Promise((ok, no) => {
    let stage = "worker", w;
    const fail = (msg, stack, st) => no(Object.assign(new Error(msg), {stage: st || stage, stack: stack || ""}));
    try { w = new Worker("worker.js"); } catch (e) { fail(String(e && e.message || e), e && e.stack); return; }
    w.onerror = e => { e.preventDefault(); fail(e.message || "worker failed to start", e.filename ? `${e.filename}:${e.lineno}` : ""); };
    w.onmessage = e => {
      const m = e.data;
      if (m.type === "stage") { stage = m.stage; onStage && onStage(stage); }
      else if (m.type === "bootError") { fail(m.message, m.stack, m.stage); w.terminate(); }
      else if (m.type === "ready") {
        families = m.families;
        w.onmessage = ev => onWorker(ev.data);
        w.onerror = ev => {   // the worker died mid-session: say so instead of spinning forever
          ev.preventDefault(); job = null; rerun = false; engine = null;
          fail(tr().fBootFail, bootEngine, "[worker] (" + ev.message + ") · " + navigator.userAgent);
        };
        ok(w);
      }
    };
  });
}
boot();
