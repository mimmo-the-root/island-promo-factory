import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Make a single step visible in the live console (cases that do not use run_all: conform, one-off Qwen runs).

Usage: activity.py run --project SLUG --label "Removing the title" [--expected 240] -- qwen_run.py untitle
Runs the kit script after `--` (same Python, PROMO_PROJECT=SLUG), shows it in the console as a running stage with progress and estimate,
keeps its output in Projects/<slug>/final/activity.log, and marks it done or failed. Exit code = the script's exit code.
Several runs in a row (within 6 h) become the stages of one session; a full run_all is never overwritten.
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import promo_project as pp

SCRIPTS = Path(__file__).resolve().parent
SESSION_H = 6


def _load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def run(slug, label, expected, cmd):
    proj = pp.projects_dir() / slug
    final = proj / "final"
    final.mkdir(parents=True, exist_ok=True)
    sp, logp = final / "run_status.json", final / "activity.log"
    cur = _load(sp)
    now = time.time()
    if cur and cur.get("kind") != "activity" and cur.get("state") == "running":
        track = False                      # a full run_all owns the console right now
    else:
        track = True
    if track:
        if not (cur and cur.get("kind") == "activity" and now - cur.get("started", 0) < SESSION_H * 3600):
            cur = {"kind": "activity", "map": slug, "state": "running", "started": now, "stages": []}
            logp.write_text("", encoding="utf-8")
        stage = {"name": label, "state": "running", "t0": now, "expected": expected, "seconds": 0, "note": ""}
        cur["stages"].append(stage)
        cur["state"] = "running"
        cur["failed"] = ""

    lock = threading.Lock()

    def save():
        if track:
            with lock:
                cur["updated"] = time.time()
                sp.write_text(json.dumps(cur), encoding="utf-8")

    save()
    stop = threading.Event()

    def beat():
        while not stop.wait(15):
            save()

    threading.Thread(target=beat, daemon=True).start()
    script = Path(cmd[0])
    if not script.is_absolute():
        script = SCRIPTS / script
    env = dict(os.environ, PROMO_PROJECT=slug, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
    rc = 1
    with open(logp, "a", encoding="utf-8", errors="replace") as log:
        log.write("--- %s\n" % label)
        log.flush()
        try:
            p = subprocess.Popen([sys.executable, str(script)] + cmd[1:], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 env=env, text=True, encoding="utf-8", errors="replace")
            for line in p.stdout:
                sys.stdout.write(line)
                log.write(line)
                log.flush()
            rc = p.wait()
        except Exception as e:
            log.write("ERROR: %s\n" % e)
            print("ERROR:", e)
        log.write("--- %s: %s\n" % (label, "done" if rc == 0 else "FAILED (exit %d)" % rc))
    stop.set()
    if track:
        stage["state"] = "done" if rc == 0 else "failed"
        stage["seconds"] = time.time() - now
        cur["state"] = "done" if rc == 0 else "failed"
        cur["failed"] = "" if rc == 0 else label
        cur["total"] = time.time() - cur["started"]
        save()
    return rc


def main():
    argv = sys.argv[1:]
    cmd = []
    if "--" in argv:
        i = argv.index("--")
        argv, cmd = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["run"])
    ap.add_argument("--project", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--expected", type=int, default=120)
    a = ap.parse_args(argv)
    if not cmd:
        print("usage: activity.py run --project SLUG --label TEXT -- script.py [args]")
        return 2
    if not (pp.projects_dir() / a.project / "config.json").exists():
        print("map '%s' not found" % a.project)
        return 2
    return run(a.project, a.label, a.expected, cmd)


if __name__ == "__main__":
    sys.exit(main())
