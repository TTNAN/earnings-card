/* earnings-card render worker.
 * Runs Pyodide + render.py off the main thread. Browser extensions inject content scripts into pages,
 * not workers, so one that patches page globals can no longer break the engine.
 * Text widths come from tables the page measures with its web fonts (py/measure_tables.py).
 *
 * page -> worker: {type: "tables", tables}            new width tables (sent again when fonts load)
 *                 {type: "render", id, data, opts}     JSON strings in, as render.web_render takes them
 *                                                      (opts.only = card index: one card + {names} of the set)
 *                 {type: "extras", id, data, opts}     caption + headline ideas (render.web_extras)
 * worker -> page: {type: "ready", families}           engine up; families = font stacks to measure
 *                 {type: "result", id, out}            out = JSON string [{name, svg, w, h}] (or {names, cards})
 *                 {type: "extras", id, out}            out = JSON string {caption, headlines}, null on error
 *                 {type: "error", id, message, stack}
 *                 {type: "bootError", stage, message, stack}
 *                 {type: "stage", stage}               boot progress, for the error message */
// Emscripten's tzset reads the zone name as toLocaleTimeString(undefined, {timeZoneName:"short"}).split(" ")[1].
// Some system locales (e.g. Edge on Chinese Windows) format without a space there, so the name is undefined and
// Pyodide crashes at boot ("reading 'length'"). Always format that call in en-US so the split works.
(() => {
  const orig = Date.prototype.toLocaleTimeString;
  Date.prototype.toLocaleTimeString = function (locales, opts) {
    if (opts && opts.timeZoneName) {
      const r = orig.call(this, "en-US", opts);
      return r.split(" ")[1] ? r : r + " UTC";
    }
    return orig.call(this, locales, opts);
  };
})();

"use strict";
const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/";
const NPMMIRROR = "https://cdn.npmmirror.com/packages/pyodide/0.26.4/files/";   // Alibaba CDN, fast in mainland China
const LOCAL_PYODIDE = new URL("pyodide/", self.location.href).href;
const SOURCES = [NPMMIRROR, PYODIDE, LOCAL_PYODIDE];
const PROBE_TIMEOUT = 6000;
const TIMEOUT = 90000;

let py = null, stage = "start";
const queue = [];   // messages that arrive before the engine is up
const setStage = s => { stage = s; self.postMessage({type: "stage", stage: s}); };

async function getText(path) {
  const r = await fetch(new URL(path, self.location.href).href);
  if (!r.ok) throw new Error(path + " " + r.status);
  return r.text();
}

// importScripts is synchronous and has no timeout: on a stalled CDN it hangs the worker forever.
// So first fetch pyodide.js from every source at once (with a short timeout) and order the sources
// by who answered first; importScripts then reads the already-fetched file from the HTTP cache.
async function probe(base) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), PROBE_TIMEOUT);
  const t0 = Date.now();
  try {
    const r = await fetch(base + "pyodide.js", {signal: ctl.signal, cache: "force-cache"});
    if (!r.ok) throw new Error("status " + r.status);
    await r.text();
    return Date.now() - t0;
  } finally { clearTimeout(t); }
}

async function rankSources() {
  const res = await Promise.all(SOURCES.map(b => probe(b).then(ms => ({b, ms}), () => ({b, ms: Infinity}))));
  const ok = res.filter(r => r.ms < Infinity).sort((a, z) => a.ms - z.ms).map(r => r.b);
  const rest = SOURCES.filter(b => !ok.includes(b));
  return ok.concat(rest);
}

async function loadFrom(base) {
  try { delete self.loadPyodide; delete self._createPyodideModule; } catch (e) {}
  importScripts(base + "pyodide.js");   // throws on a network error
  let timer;
  try {
    return await Promise.race([
      self.loadPyodide({indexURL: base}),
      new Promise((_, no) => { timer = setTimeout(() => no(new Error("timeout after " + TIMEOUT / 1000 + "s")), TIMEOUT); }),
    ]);
  } finally { clearTimeout(timer); }
}

async function boot() {
  const srcP = Promise.all([getText("py/render.py"), getText("py/measure_tables.py")]);
  srcP.catch(() => {});
  let pyo = null, lastErr = null;
  setStage("probe");
  const order = await rankSources();
  for (const base of order) {
    setStage("load " + (base === LOCAL_PYODIDE ? "local" : base === NPMMIRROR ? "npmmirror" : "cdn"));
    try { pyo = await loadFrom(base); break; }
    catch (e) { console.warn("pyodide from", base, "failed:", e); lastErr = e; pyo = null; }
  }
  if (!pyo) throw lastErr || new Error("pyodide did not load");
  setStage("render.py");
  const [render, mt] = await srcP;
  setStage("init");
  pyo.FS.writeFile("/home/pyodide/render.py", render);
  pyo.FS.writeFile("/home/pyodide/measure_tables.py", mt);
  pyo.runPython("import render, measure_tables");
  py = {
    webRender: pyo.pyimport("render").web_render,
    webExtras: pyo.pyimport("render").web_extras,
    setTables: pyo.pyimport("measure_tables").set_tables,
    families: pyo.runPython("import json; json.dumps(measure_tables.families())"),
  };
}

function handle(m) {
  if (m.type === "tables") {
    py.setTables(JSON.stringify(m.tables));
  } else if (m.type === "extras") {   // caption + headline ideas for one period
    try { self.postMessage({type: "extras", id: m.id, out: py.webExtras(m.data, m.opts)}); }
    catch (e) { self.postMessage({type: "extras", id: m.id, out: null, message: String(e && e.message || e)}); }
  } else if (m.type === "render") {
    try {
      self.postMessage({type: "result", id: m.id, out: py.webRender(m.data, m.opts)});
    } catch (e) {
      self.postMessage({type: "error", id: m.id, message: String(e && e.message || e).slice(0, 2000), stack: String(e && e.stack || "")});
    }
  }
}

self.onmessage = e => { if (py) handle(e.data); else queue.push(e.data); };

boot().then(() => {
  self.postMessage({type: "ready", families: JSON.parse(py.families)});
  // Before ready the page only ever sends tables + one render; keep just the newest of each.
  // (extras are only sent after ready.)
  const tables = queue.filter(m => m.type === "tables").pop(), job = queue.filter(m => m.type === "render").pop();
  queue.length = 0;
  if (tables) handle(tables);
  if (job) handle(job);
}, e => {
  console.error(e);
  self.postMessage({type: "bootError", stage, message: String(e && e.message || e), stack: String(e && e.stack || "")});
});
