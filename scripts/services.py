import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Start the helper programs for a run, so nobody has to double-click .bat files: ComfyUI and the live console.

Usage:
  services.py comfy [--wait 240]                  start ComfyUI if it is not running (own window), wait until it answers
  services.py console --project SLUG [--no-open]  start the live console (dashboard) for the map, open it in the browser
  services.py stop --project SLUG                 close the live console of the map
  services.py status [--project SLUG]             what is running
Exit code 0 = service is up, 1 = it could not be started (the reason is printed).
Env: COMFY_URL (default http://127.0.0.1:8188), PROMO_PROJECTS_DIR.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

import promo_project as pp

ROOT = pp.ROOT
COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")
FLAGS_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
FLAGS_DETACHED = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)


def up(url, timeout=3):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def comfy_dir():
    for c in (ROOT.parent / "ComfyUI_windows_portable", ROOT / "ComfyUI_windows_portable"):
        if (c / "python_embeded" / "python.exe").exists() and (c / "ComfyUI" / "main.py").exists():
            return c
    return None


def start_comfy(wait=240):
    if up(COMFY_URL + "/system_stats"):
        print("ComfyUI: already running at %s" % COMFY_URL)
        return 0
    cu = comfy_dir()
    if cu is None:
        print("ComfyUI: not found next to this folder (expected ..\\ComfyUI_windows_portable). Install it (docs/INSTALL.md) or start your own on %s." % COMFY_URL)
        return 1
    if os.name != "nt":
        print("ComfyUI: automatic start is only implemented for the Windows portable build.")
        return 1
    print("ComfyUI: starting from %s (a new window opens; keep it open) ..." % cu)
    subprocess.Popen([str(cu / "python_embeded" / "python.exe"), "-s", str(cu / "ComfyUI" / "main.py"), "--windows-standalone-build"],
                     cwd=str(cu), creationflags=FLAGS_NEW_CONSOLE, close_fds=True)
    t0 = time.time()
    while time.time() - t0 < wait:
        if up(COMFY_URL + "/system_stats"):
            print("ComfyUI: ready after %d s" % (time.time() - t0))
            return 0
        time.sleep(3)
    print("ComfyUI: did not answer within %d s. Look at its window (driver / GPU error?). The run can still use --no-qwen." % wait)
    return 1


def start_console(slug, port=8765, open_browser=True):
    proj = pp.projects_dir() / slug
    if not (proj / "config.json").exists():
        print("console: map '%s' not found in %s" % (slug, pp.projects_dir()))
        return 1
    (proj / "final").mkdir(exist_ok=True)
    info_file = proj / "final" / "console.json"
    try:
        info = json.loads(info_file.read_text(encoding="utf-8"))
        if up(info["url"] + "/api/variants"):
            print("console: already running at %s" % info["url"])
            if open_browser:
                webbrowser.open(info["url"])
            return 0
    except Exception:
        pass
    log = open(ROOT / "last_console.log", "w", encoding="utf-8")
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8", PROMO_PROJECTS_DIR=str(pp.projects_dir()))
    cmd = [str(pp.find_python()), str(Path(__file__).resolve().parent / "dashboard.py"), "--project", slug, "--port", str(port), "--no-open", "--idle-min", os.environ.get("PROMO_CONSOLE_IDLE_MIN", "30")]
    proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env, creationflags=FLAGS_DETACHED, close_fds=True)
    for _ in range(40):
        time.sleep(0.5)
        try:
            txt = (ROOT / "last_console.log").read_text(encoding="utf-8", errors="replace")
        except OSError:
            txt = ""
        for line in txt.splitlines():
            if line.startswith("dashboard: http://"):
                url = line.split("dashboard: ", 1)[1].strip()
                if up(url + "/api/variants"):
                    info_file.write_text(json.dumps({"url": url, "pid": proc.pid, "started": time.time()}), encoding="utf-8")
                    print("console: %s" % url)
                    if open_browser:
                        webbrowser.open(url)
                    return 0
    print("console: did not start, see last_console.log")
    return 1


def stop_console(slug):
    f = pp.projects_dir() / slug / "final" / "console.json"
    try:
        info = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        print("console: not running")
        return 0
    pid = info.get("pid")
    if pid and up(info["url"] + "/api/variants"):
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
            else:
                os.kill(int(pid), 15)
        except Exception as e:
            print("console: could not stop it (%s)" % e)
            return 1
    try:
        f.unlink()
    except OSError:
        pass
    print("console: closed")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["comfy", "console", "stop", "status"])
    ap.add_argument("--project")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--wait", type=int, default=240)
    ap.add_argument("--no-open", action="store_true")
    a = ap.parse_args()
    if a.what == "comfy":
        return start_comfy(a.wait)
    if a.what == "console":
        if not a.project:
            print("console needs --project SLUG")
            return 2
        return start_console(a.project, a.port, not a.no_open)
    if a.what == "stop":
        if not a.project:
            print("stop needs --project SLUG")
            return 2
        return stop_console(a.project)
    print("ComfyUI: %s" % ("running" if up(COMFY_URL + "/system_stats") else "not running"))
    if a.project:
        try:
            url = json.loads((pp.projects_dir() / a.project / "final" / "console.json").read_text(encoding="utf-8"))["url"]
            print("console: %s" % (url if up(url + "/api/variants") else "not running"))
        except Exception:
            print("console: not running")
    return 0


if __name__ == "__main__":
    sys.exit(main())
