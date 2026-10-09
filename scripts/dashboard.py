import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Mission-control web console for a Island Promo Factory run (local, read-only).

Usage: dashboard.py [--project SLUG] [--port 8765] [--no-open]     (view the last run of a map)
       run_all.py --ui                                              (starts it automatically and opens the browser)
Shows: overall progress bar with % and ETA, the pipeline stages, a live preview of what is being produced
(finished artwork, the trailer frame being rendered), a gallery of results as they land, a colour-coded live log,
and at the end the lightbox board with one download link per file plus a ZIP of the whole pack.
Serves http://127.0.0.1:<port> only (this computer). Reads Projects/<map>/final/run_status.json and promo_pack/.
"""
import argparse
import io
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import promo_project as pp
import version as V

ROOT = Path(__file__).resolve().parent.parent
IMG_EXT = (".png", ".jpg", ".jpeg")
FRAME_RE = re.compile(r"frame (\d+)/(\d+)")
SCRIPT_RE = re.compile(r"RUNNING: (\S+\.py)")

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Island Promo Factory - Live</title><style>
:root{--bg:#07080d;--panel:#0f111a;--line:#222639;--txt:#e9ebf5;--dim:#7c829c;--c1:#22e1ff;--c2:#a45bff;--c3:#ff4fa3;--amb:#ffc247;--ok:#37e6a0;--bad:#ff5468}
@media (prefers-color-scheme: light){:root{--bg:#eef0f6;--panel:#fff;--line:#d8dcea;--txt:#12141d;--dim:#667090;--amb:#b07600;--ok:#0f9d68;--bad:#d4384c}}
*{box-sizing:border-box}html{background:var(--bg)}body{margin:0;color:var(--txt);font:15px/1.45 system-ui,Segoe UI,sans-serif;min-height:100vh;
background:radial-gradient(1200px 500px at 15% -10%,rgba(164,91,255,.18),transparent 60%),radial-gradient(900px 500px at 95% 0,rgba(34,225,255,.14),transparent 60%),var(--bg)}
body:before{content:"";position:fixed;inset:0;pointer-events:none;opacity:.35;background-image:linear-gradient(var(--line) 1px,transparent 1px),linear-gradient(90deg,var(--line) 1px,transparent 1px);background-size:44px 44px;mask-image:linear-gradient(#000,transparent 70%);-webkit-mask-image:linear-gradient(#000,transparent 70%)}
main{position:relative;max-width:1240px;margin:0 auto;padding:22px 18px 70px}
.top{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap}
.ver{margin-left:10px;padding:2px 8px;border:1px solid var(--line);border-radius:99px;color:var(--dim);letter-spacing:.06em;font-weight:600}
.upd{display:none;margin:0 0 14px;padding:10px 14px;border-radius:10px;border:1px solid var(--amb);background:rgba(255,194,71,.1);color:var(--txt)}
.brand{font-size:12px;letter-spacing:.28em;color:var(--c1);font-weight:700}.map{font-size:34px;font-weight:800;letter-spacing:-.01em;margin:2px 0}
.badge{display:inline-flex;align-items:center;gap:8px;padding:6px 12px;border-radius:99px;border:1px solid var(--line);background:var(--panel);font-size:12px;letter-spacing:.12em;font-weight:700}
.badge i{width:9px;height:9px;border-radius:50%;background:var(--dim)}.badge.running i{background:var(--c1);animation:pulse 1s infinite}.badge.done i{background:var(--ok)}.badge.failed i{background:var(--bad)}
@keyframes pulse{50%{opacity:.3;transform:scale(.7)}}
.clock{display:grid;grid-template-columns:repeat(3,auto);gap:22px;margin:18px 0 12px}
.clock div small{display:block;color:var(--dim);font-size:11px;letter-spacing:.16em}.clock b{font:700 38px/1 ui-monospace,Consolas,monospace;font-variant-numeric:tabular-nums}
.clock .pct{background:linear-gradient(90deg,var(--c1),var(--c3));-webkit-background-clip:text;background-clip:text;color:transparent}
.bar{display:flex;gap:4px;height:22px;margin-bottom:6px}.seg{position:relative;flex:1 1 0;background:var(--panel);border:1px solid var(--line);border-radius:6px;overflow:hidden}
.seg .f{position:absolute;inset:0 auto 0 0;width:0;background:linear-gradient(90deg,var(--c1),var(--c2),var(--c3));transition:width .6s ease}
.seg.running .f:after{content:"";position:absolute;inset:0;background:linear-gradient(90deg,transparent,rgba(255,255,255,.55),transparent);animation:shim 1.2s infinite}
@keyframes shim{from{transform:translateX(-100%)}to{transform:translateX(100%)}}
.seg.done .f{width:100%}.seg.failed{border-color:var(--bad)}.seg.failed .f{width:100%;background:var(--bad)}
.seg span{position:absolute;left:8px;top:2px;font-size:11px;letter-spacing:.08em;font-weight:700;mix-blend-mode:difference;color:#fff;white-space:nowrap}
.note{color:var(--dim);font-size:13px;min-height:20px;margin-bottom:16px}
.grid{display:grid;grid-template-columns:1.25fr 1fr;gap:16px}@media(max-width:900px){.grid{grid-template-columns:1fr}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px}
.card h3{margin:0 0 10px;font-size:11px;letter-spacing:.2em;color:var(--dim)}
.live{position:relative;aspect-ratio:16/9;border-radius:10px;overflow:hidden;background:#000;display:grid;place-items:center}
.live img{width:100%;height:100%;object-fit:contain;animation:fade .5s}.live .tag{position:absolute;left:10px;top:10px;padding:4px 9px;border-radius:6px;background:rgba(0,0,0,.65);color:#fff;font-size:11px;letter-spacing:.1em}
.live .rec{position:absolute;right:12px;top:12px;width:10px;height:10px;border-radius:50%;background:var(--bad);animation:pulse 1s infinite}
@keyframes fade{from{opacity:.3}to{opacity:1}}
.nodes{display:grid;gap:8px}.node{display:grid;grid-template-columns:22px 1fr auto;gap:10px;align-items:center;padding:9px 10px;border:1px solid var(--line);border-radius:10px}
.node .d{width:12px;height:12px;border-radius:50%;background:var(--line)}.node.running{border-color:var(--c1);box-shadow:0 0 0 1px var(--c1) inset,0 0 22px rgba(34,225,255,.18)}
.node.running .d{background:var(--c1);animation:pulse 1s infinite}.node.done .d{background:var(--ok)}.node.failed{border-color:var(--bad)}.node.failed .d{background:var(--bad)}.node.skipped{opacity:.5}
.node small{color:var(--dim)}.node time{font:600 13px ui-monospace,Consolas,monospace;color:var(--dim)}
.log{height:300px;overflow:auto;background:#05060a;border-radius:10px;padding:10px;font:12px/1.5 ui-monospace,Consolas,monospace;color:#9aa0b8;white-space:pre-wrap}
.log .ok{color:var(--ok)}.log .bad{color:var(--bad)}.log .hd{color:var(--c1);font-weight:700}.log .wr{color:var(--amb)}
.gal{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}.gal a{display:block;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:#000;animation:pop .5s}
.gal img{width:100%;aspect-ratio:16/10;object-fit:cover;display:block}.gal small{display:block;padding:4px 7px;color:var(--dim);font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
@keyframes pop{from{transform:scale(.85);opacity:0}to{transform:none;opacity:1}}
#result{margin-top:18px}#result.win{animation:win 1.6s ease}@keyframes win{0%{box-shadow:0 0 0 0 rgba(55,230,160,.7)}100%{box-shadow:0 0 0 40px rgba(55,230,160,0)}}
.sheet img{width:100%;border-radius:10px;border:1px solid var(--line)}
.files{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:8px;margin:14px 0}
.files a{display:flex;justify-content:space-between;gap:10px;padding:10px 12px;background:var(--panel);border:1px solid var(--line);border-radius:8px;color:var(--txt);text-decoration:none}
.files a:hover{border-color:var(--c1)}.files span{color:var(--dim);white-space:nowrap}
.btn{display:inline-block;background:linear-gradient(90deg,var(--c1),var(--c3));color:#06070b;font-weight:800;padding:14px 24px;border-radius:12px;text-decoration:none;letter-spacing:.04em}
.vrow{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:12px;margin-top:12px}
.vbox{border:1px solid var(--line);border-radius:12px;padding:14px;background:var(--panel)}
.vbox h4{margin:0 0 8px;font-size:16px;letter-spacing:.06em}.vbox small{color:var(--dim)}
.vbox button{background:linear-gradient(90deg,var(--c1),var(--c3));color:#06070b;font-weight:800;border:0;border-radius:10px;padding:10px 16px;cursor:pointer;margin:6px 8px 6px 0}
.vbox button:disabled{opacity:.45;cursor:not-allowed}.vbox img{width:100%;border-radius:8px;margin-top:8px;border:1px solid var(--line)}
.vbox a{color:var(--c1)}
</style></head><body><main>
<div class="top"><div><div class="brand">ISLAND PROMO FACTORY<span class="ver" id="ver"></span></div><div class="map" id="map">...</div></div><div class="badge idle" id="badge"><i></i><span id="btxt">IDLE</span></div></div>
<div class="upd" id="upd"></div>
<div class="clock"><div><small>PROGRESS</small><b class="pct" id="pct">0%</b></div><div><small>ELAPSED</small><b id="el">0:00</b></div><div><small>TIME LEFT (EST.)</small><b id="eta">--:--</b></div></div>
<div class="bar" id="bar"></div><div class="note" id="note">Waiting for a run...</div>
<div class="grid"><div class="card"><h3>NOW PRODUCING</h3><div class="live"><img id="live" alt="" hidden><div class="tag" id="ltag" hidden></div><div class="rec" id="rec" hidden></div><span id="lph" style="color:var(--dim)">preview appears as soon as something is made</span></div></div>
<div class="card"><h3>PIPELINE</h3><div class="nodes" id="nodes"></div></div></div>
<div class="grid" style="margin-top:16px"><div class="card"><h3>RESULTS SO FAR</h3><div class="gal" id="gal"></div></div><div class="card"><h3>LIVE LOG</h3><div class="log" id="log"></div></div></div>
<div id="vars" class="card" style="margin-top:16px"><h3>A/B VARIANTS - same map, new seed</h3>
<div class="note" id="vnote">Generate a different version of the images to A/B test thumbnails. Version A (the files above) is never touched.</div>
<div class="vrow" id="vrow"></div></div>
<div id="result" class="card" hidden><h3>KIT LIGHTBOX</h3><div class="sheet"><a href="/pack/lightbox.png" target="_blank" rel="noopener"><img id="sheet" alt="kit lightbox"></a></div>
<h3 style="margin-top:18px">DOWNLOAD</h3><div class="files" id="files"></div><a class="btn" href="/pack.zip">DOWNLOAD EVERYTHING (ZIP)</a> <a class="btn" style="background:transparent;color:var(--c1);border:1px solid var(--c1)" href="/pack/lightbox.png" download>DOWNLOAD THE LIGHTBOX (PNG)</a></div>
<script>
const $=id=>document.getElementById(id);let shownSheet=false,lastLive="",won=false;
const fmt=s=>{s=Math.max(0,Math.round(s));const m=Math.floor(s/60);return m+":"+String(s%60).padStart(2,"0")};
const esc=t=>t.replace(/&/g,"&amp;").replace(/</g,"&lt;");
function cls(l){if(/FAILED|ERROR|Traceback/.test(l))return"bad";if(/WARNING/.test(l))return"wr";if(/^\s*(---|=+)|RUNNING:/.test(l))return"hd";if(/SUCCESS|OK:|READY|done|PASS|written/.test(l))return"ok";return""}
async function tick(){try{const d=await (await fetch("/api/status")).json();const st=d.state||"idle";
$("map").textContent=d.map||"";$("badge").className="badge "+st;$("btxt").textContent=st==="running"?"RUNNING":st==="done"?(d.kind==="activity"?"STEP DONE":"COMPLETE"):st==="failed"?"FAILED":"IDLE";
$("pct").textContent=Math.round((d.pct||0)*100)+"%";$("el").textContent=fmt(d.elapsed||d.total||0);
$("eta").textContent=st==="running"?(d.eta==null?"--:--":"~"+fmt(d.eta)):st==="done"?"0:00":"--:--";
const runSt=(d.stages||[]).filter(s=>s.state!=="skipped"),tot=runSt.reduce((a,s)=>a+(s.expected||30),0)||1;
$("bar").innerHTML=runSt.map(s=>{const f=s.state==="running"?Math.round((s.prog||0)*100):s.state==="done"?100:0;
return `<div class="seg ${s.state}" style="flex:${(s.expected||30)/tot}"><div class="f" style="width:${f}%"></div><span>${(s.expected||30)/tot>0.09?s.name.toUpperCase():""}</span></div>`}).join("");
$("note").textContent=st==="running"?(d.sub||""):st==="done"?(d.kind==="activity"?"Step finished in "+fmt(d.total||0)+". Waiting for the next one.":"Finished in "+fmt(d.total||0)+" - your files are ready below."):st==="failed"?"Stopped at '"+(d.failed||"?")+"' - the red lines in the log say why.":"";
$("nodes").innerHTML=(d.stages||[]).map(s=>`<div class="node ${s.state}"><span class="d"></span><div><b>${s.name}</b><br><small>${s.state==="skipped"?(s.note||"skipped"):s.state==="running"?(s.sub||"working..."):s.state==="pending"?"waiting":s.state==="failed"?"failed":"done"}</small></div><time>${s.state==="running"?fmt(s.live||0):s.state==="done"||s.state==="failed"?fmt(s.seconds||0):""}</time></div>`).join("");
const lg=$("log"),near=lg.scrollHeight-lg.scrollTop-lg.clientHeight<60;lg.innerHTML=(d.log||[]).map(l=>`<div class="${cls(l)}">${esc(l)}</div>`).join("");if(near)lg.scrollTop=lg.scrollHeight;
if(d.latest){const key=d.latest.rel+"@"+d.latest.mtime;if(key!==lastLive){lastLive=key;const im=$("live");im.src="/img?rel="+encodeURIComponent(d.latest.rel)+"&t="+d.latest.mtime;im.hidden=false;$("lph").hidden=true;$("ltag").hidden=false;$("ltag").textContent=d.latest.name}}
$("rec").hidden=st!=="running";
const g=d.gallery||[];$("gal").innerHTML=g.map(a=>`<a href="/img?rel=${encodeURIComponent(a.rel)}" target="_blank" rel="noopener"><img loading="lazy" src="/thumb?rel=${encodeURIComponent(a.rel)}&t=${a.mtime}"><small>${a.name}</small></a>`).join("");
if(st==="done"&&d.files&&d.files.length){const r=$("result");r.hidden=false;if(!won){r.classList.add("win");won=true}
if(!shownSheet){$("sheet").src="/pack/lightbox.png?t="+Date.now();shownSheet=true}
$("files").innerHTML=d.files.filter(f=>f.name!=="lightbox.png").map(f=>`<a href="/pack/${encodeURIComponent(f.name)}" download><b>${f.name}</b><span>${f.mb} MB</span></a>`).join("")}
}catch(e){}}
async function ver(){try{const v=await (await fetch("/api/version")).json();
$("ver").textContent="v"+v.version;
const u=$("upd");if(v.newer){u.style.display="block";u.textContent="Update available: v"+v.latest+" (you have v"+v.version+"). When this run is finished, close the window and run update.bat."}else{u.style.display="none"}}catch(e){}}
tick();setInterval(tick,1000);ver();setInterval(ver,600000);
const TOKEN="__TOKEN__";
async function varTick(){try{const d=await (await fetch("/api/variants")).json();
$("vrow").innerHTML=["B","C"].map(n=>{const v=d.variants[n]||{state:"idle"};const run=v.state==="running";
const busy=d.busy&&!run;
const img=v.state==="done"&&v.thumb?`<a href="/var/${n}/${encodeURIComponent(v.thumb)}" target="_blank" rel="noopener"><img src="/var/${n}/${encodeURIComponent(v.thumb)}?t=${v.mtime}"></a>`:"";
const dl=v.state==="done"?` <a href="/var/${n}.zip">download variant ${n} (zip)</a>`:"";
return `<div class="vbox"><h4>VARIANT ${n}</h4><small>${run?"working... "+(v.stage||"")+" ("+fmt((Date.now()/1000)-v.started)+")":v.state==="done"?"ready - seed "+v.seed+" - "+fmt(v.seconds||0):v.state==="failed"?"failed: "+(v.error||"see log"):"not generated yet"}</small><br>
<button onclick="mkVar('${n}')" ${run||busy?"disabled":""}>${v.state==="done"?"REGENERATE "+n+" (new seed)":"GENERATE VARIANT "+n}</button>${dl}${img}</div>`}).join("");
$("vnote").textContent=d.busy?"A generation is running: wait for it to finish (one at a time).":"Generate a different version of the images to A/B test thumbnails. Version A (the files above) is never touched."}catch(e){}}
async function mkVar(n){await fetch("/api/variant?name="+n,{method:"POST",headers:{"X-Promo-Token":TOKEN}});varTick()}
varTick();setInterval(varTick,2500);

document.addEventListener("click",e=>{const a=e.target.closest&&e.target.closest("a[href]");if(a&&!a.hasAttribute("download")&&a.getAttribute("href")[0]!=="#"){a.target="_blank";a.rel="noopener"}},true);
</script></main></body></html>"""


LAST_REQUEST = [time.time()]   # last time any page / API call reached the server (idle shutdown)


def _safe(proj, rel):
    """Resolve rel inside the project folder only (no traversal); images only."""
    f = (proj / rel).resolve()
    try:
        f.relative_to(proj.resolve())
    except ValueError:
        return None
    return f if f.is_file() and f.suffix.lower() in IMG_EXT else None


def compute(proj, log_lines, d):
    """Add pct / eta / sub labels / gallery / latest to the status dict."""
    now = time.time()
    st = d.get("state", "idle")
    stages = d.get("stages", [])
    run = [s for s in stages if s.get("state") != "skipped"]
    exp_total = sum(s.get("expected", 30) for s in run) or 1
    done_work = 0.0
    script = None
    for line in log_lines[-200:]:
        m = SCRIPT_RE.search(line)
        if m:
            script = m.group(1)
    done_act = sum(s.get("seconds", 0) for s in run if s.get("state") == "done")
    done_exp = sum(s.get("expected", 30) for s in run if s.get("state") == "done")
    speed = max(0.3, min(4.0, done_act / done_exp)) if done_exp > 0 and done_act > 0 else 1.0
    remaining = 0.0
    for s in run:
        exp = s.get("expected", 30)
        if s.get("state") == "done":
            done_work += exp
        elif s.get("state") == "running":
            live = now - s.get("t0", now)
            s["live"] = live
            prog = min(0.97, live / max(1.0, exp * speed))
            sub = ""
            framed = False
            if s["name"] == "trailer":
                for line in reversed(log_lines[-60:]):
                    m = FRAME_RE.search(line)
                    if m:
                        prog = min(0.99, int(m.group(1)) / max(1, int(m.group(2))))
                        sub = "rendering frame %s of %s" % (m.group(1), m.group(2))
                        framed = True
                        break
                sub = sub or "building the trailer"
            elif s["name"] == "images":
                sub = ("running " + script) if script else "starting"
            else:
                sub = s["name"] + "..."
            if framed and prog > 0.05:
                remaining += live * (1 - prog) / prog
            else:
                remaining += max(2.0, exp * speed - live)
            if live > exp * speed * 1.25 and not framed:
                sub += " (taking longer than usual)"
            s["prog"], s["sub"] = prog, sub
            done_work += prog * exp
        else:
            remaining += exp * speed
    d["sub"] = next((s.get("sub", "") for s in run if s.get("state") == "running"), "")
    if st == "running":
        elapsed = now - d.get("started", now)
        d["elapsed"] = elapsed
        d["pct"] = min(0.99, done_work / exp_total)
        d["eta"] = remaining if (done_work > 1 or elapsed > 8) else None
    elif st == "done":
        d["pct"] = 1.0
    else:
        d["pct"] = done_work / exp_total
    # gallery + latest: images produced during this run (or the final pack when finished)
    since = d.get("started", 0) - 2
    found = []
    for sub in ("background", "final", "promo_pack"):
        base = proj / sub
        if base.is_dir():
            for f in base.iterdir():
                if f.is_file() and f.suffix.lower() in IMG_EXT and f.stat().st_mtime >= since and f.name != "lightbox.png":
                    found.append((f.stat().st_mtime, "%s/%s" % (sub, f.name), f.name))
    found.sort(reverse=True)
    live_cands = [x for x in found if x[2] == "_live_frame.jpg" or x[1].startswith(("final/", "background/"))]
    if live_cands:
        t, rel, name = live_cands[0]
        d["latest"] = {"rel": rel, "name": "trailer render (live)" if name == "_live_frame.jpg" else name, "mtime": int(t * 1000)}
    d["gallery"] = [{"rel": rel, "name": name, "mtime": int(t * 1000)} for t, rel, name in found
                    if not name.startswith("_") and not rel.startswith("promo_pack/")][:24]
    if st == "done" and not d["gallery"]:
        pack = proj / "promo_pack"
        d["gallery"] = [{"rel": "promo_pack/" + f.name, "name": f.name, "mtime": int(f.stat().st_mtime * 1000)}
                        for f in sorted(pack.glob("*.png")) if f.name != "lightbox.png"] if pack.is_dir() else []
    return d


def read_status(proj):
    """run_status.json of this map; an activity session whose wrapper died (no heartbeat) is reported as interrupted."""
    d = {}
    try:
        d = json.loads((proj / "final" / "run_status.json").read_text(encoding="utf-8"))
    except Exception:
        return d
    if d.get("kind") == "activity" and d.get("state") == "running" and time.time() - d.get("updated", 0) > 90:
        d["state"], d["failed"] = "failed", "interrupted"
        for s in d.get("stages", []):
            if s.get("state") == "running":
                s["state"] = "failed"
    return d


def log_lines_for(proj, status):
    """The log that belongs to THIS map: its activity log for single steps, last_run_all.log only when this map has a full run."""
    try:
        if status.get("kind") == "activity" or not status:
            f = proj / "final" / "activity.log"
        else:
            f = ROOT / "last_run_all.log"
        return f.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []


def make_handler(proj):
    pack = proj / "promo_pack"
    status_file = proj / "final" / "run_status.json"
    log_file = ROOT / "last_run_all.log"
    thumbs = {}
    token = secrets.token_urlsafe(16)
    vdir = proj / "variants"
    procs = {}

    def vstate(n):
        try:
            d = json.loads((vdir / n / "status.json").read_text(encoding="utf-8"))
        except Exception:
            return {"state": "idle"}
        if d.get("state") == "running" and not (n in procs and procs[n].poll() is None):
            d["state"] = "failed"  # the worker is gone (window closed?)
            d["error"] = "interrupted"
        if d.get("state") == "done":
            for cand in ("promo_pack/01_landscape_with_text_1920x1080.png", "final/thumbnail_horizontal_title.png"):
                f = vdir / n / cand
                if f.is_file():
                    d["thumb"] = cand
                    d["mtime"] = int(f.stat().st_mtime)
                    break
        return d

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, code, body, ctype, extra=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            names = {"pack": "promo_pack.zip", "B": "variant_B.zip", "C": "variant_C.zip"}
            if extra in names:          # fixed header text only: nothing from the request ever reaches a header
                self.send_header("Content-Disposition", 'attachment; filename="%s"' % names[extra])
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            LAST_REQUEST[0] = time.time()
            u = urlparse(self.path)
            path, q = unquote(u.path), parse_qs(u.query)
            if path == "/":
                return self.send(200, PAGE.replace("__TOKEN__", token).encode("utf-8"), "text/html; charset=utf-8")
            if path == "/api/variants":
                vs = {n: vstate(n) for n in ("B", "C")}
                running = any(v.get("state") == "running" for v in vs.values())
                try:
                    running = running or read_status(proj).get("state") == "running"
                except Exception:
                    pass
                return self.send(200, json.dumps({"variants": vs, "busy": running}).encode("utf-8"), "application/json")
            if path.startswith("/var/"):
                parts = path[5:].split("/", 1)
                n = parts[0][:-4] if parts[0].endswith(".zip") else parts[0]
                if n in ("B", "C"):
                    if parts[0].endswith(".zip") and len(parts) == 1:
                        buf = io.BytesIO()
                        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
                            for f in sorted((vdir / n / "promo_pack").glob("*")):
                                if f.is_file() and f.name != "lightbox.png":
                                    z.write(f, f.name)
                        return self.send(200, buf.getvalue(), "application/zip",
                                         "B" if n == "B" else "C")
                    if len(parts) == 2:
                        listing = {p.relative_to(vdir / n).as_posix(): p for p in (vdir / n).rglob("*") if p.is_file()}
                        f = listing.get(parts[1])          # only names that really exist in the folder; request text never reaches a path
                        if f and f.suffix.lower() in IMG_EXT:
                            return self.send(200, f.read_bytes(), "image/png")
            if path == "/api/version":
                return self.send(200, json.dumps(V.info(check=False)).encode("utf-8"), "application/json")
            if path == "/api/status":
                d = {"map": proj.name, "state": "idle", "stages": []}
                d.update(read_status(proj))
                lines = log_lines_for(proj, read_status(proj))
                d["log"] = lines[-80:]
                try:
                    compute(proj, lines, d)
                except Exception as e:  # never break the page because of an estimate
                    d["sub"] = "(status error: %s)" % e
                d["files"] = []
                if pack.is_dir():
                    for f in sorted(pack.iterdir()):
                        if f.is_file() and f.suffix.lower() in (".png", ".mp4", ".md", ".txt"):
                            d["files"].append({"name": f.name, "mb": "%.2f" % (f.stat().st_size / 1048576.0)})
                return self.send(200, json.dumps(d).encode("utf-8"), "application/json")
            if path in ("/img", "/thumb"):
                f = _safe(proj, (q.get("rel") or [""])[0])
                if f is None:
                    return self.send(404, b"not found", "text/plain")
                if path == "/img":
                    ct = "image/jpeg" if f.suffix.lower() in (".jpg", ".jpeg") else "image/png"
                    return self.send(200, f.read_bytes(), ct)
                key = (str(f), f.stat().st_mtime)
                if key not in thumbs:
                    from PIL import Image
                    with Image.open(f) as im:
                        im = im.convert("RGB")
                        im.thumbnail((420, 300))
                        buf = io.BytesIO()
                        im.save(buf, "JPEG", quality=80)
                    thumbs[key] = buf.getvalue()
                return self.send(200, thumbs[key], "image/jpeg")
            if path == "/pack.zip":
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
                    for f in sorted(pack.iterdir()):
                        if f.is_file() and f.name != "lightbox.png":
                            z.write(f, f.name)
                return self.send(200, buf.getvalue(), "application/zip",
                                 "pack")
            if path.startswith("/pack/"):
                f = {p.name: p for p in pack.iterdir() if p.is_file()}.get(path[6:]) if pack.is_dir() else None  # lookup in the listing: no path traversal
                if f is not None:
                    ct = {"png": "image/png", "mp4": "video/mp4", "md": "text/plain", "txt": "text/plain"}.get(f.suffix[1:].lower(), "application/octet-stream")
                    return self.send(200, f.read_bytes(), ct)
            self.send(404, b"not found", "text/plain")

        def do_POST(self):
            LAST_REQUEST[0] = time.time()
            u = urlparse(self.path)
            q = parse_qs(u.query)
            host_ok = (self.headers.get("Host") or "").split(":")[0] in ("127.0.0.1", "localhost")
            if u.path != "/api/variant" or not host_ok or self.headers.get("X-Promo-Token") != token:
                return self.send(403, b"forbidden", "text/plain")  # blocks other web pages from triggering a run
            n = (q.get("name") or [""])[0]
            if n not in ("B", "C"):
                return self.send(400, b"bad variant", "text/plain")
            busy = any(p.poll() is None for p in procs.values())
            try:
                busy = busy or read_status(proj).get("state") == "running"
            except Exception:
                pass
            if busy:
                return self.send(409, b"busy", "text/plain")
            qwen = True
            try:
                qwen = bool(json.loads(status_file.read_text(encoding="utf-8")).get("qwen", True))
            except Exception:
                pass
            cmd = [sys.executable, str(Path(__file__).resolve().parent / "variant.py"), "--project", proj.name, "--name", n]
            if not qwen:
                cmd.append("--no-qwen")
            (vdir / n).mkdir(parents=True, exist_ok=True)
            (vdir / n / "status.json").write_text(json.dumps({"name": n, "state": "running", "stage": "starting", "started": time.time()}), encoding="utf-8")
            procs[n] = subprocess.Popen(cmd, env=dict(os.environ, PROMO_PROJECT=proj.name, PROMO_PROJECTS_DIR=str(proj.parent)))
            return self.send(202, b"started", "text/plain")

    return H


def serve(proj, port=8765, open_browser=True, block=False):
    for p in range(port, port + 20):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", p), make_handler(proj))
            break
        except OSError:
            continue
    else:
        raise SystemExit("no free port near %d" % port)
    url = "http://127.0.0.1:%d" % p
    print("dashboard: %s" % url)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    threading.Thread(target=V.latest_release, daemon=True).start()  # fills the update cache; silent when offline
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    if block:
        try:
            while True:
                t.join(1)
        except KeyboardInterrupt:
            pass
    return srv, url


def busy(proj):
    """True while a run or a variant is generating: the console must stay up."""
    try:
        if read_status(proj).get("state") == "running":
            return True
    except Exception:
        pass
    for f in (proj / "variants").glob("*/status.json") if (proj / "variants").is_dir() else []:
        try:
            if json.loads(f.read_text(encoding="utf-8")).get("state") == "running":
                return True
        except Exception:
            pass
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--idle-min", type=float, default=0,
                    help="exit by itself after this many minutes without any page request and without a run in progress (0 = never)")
    a = ap.parse_args()
    if a.project:
        os.environ["PROMO_PROJECT"] = a.project
    proj = pp.project_dir()
    if a.idle_min <= 0:
        serve(proj, a.port, not a.no_open, block=True)
        return
    serve(proj, a.port, not a.no_open, block=False)
    try:
        while True:
            time.sleep(1)
            if time.time() - LAST_REQUEST[0] > a.idle_min * 60 and not busy(proj):
                print("console: idle for %.0f min, closing" % a.idle_min)
                return
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
