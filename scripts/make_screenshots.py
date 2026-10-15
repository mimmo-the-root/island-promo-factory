import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Reproducible manual screenshots: photographs the console on the finished demo map with a headless browser.

Usage: make_screenshots.py [--project demo] [--out docs/manual/images]
Needs: the demo map already built (demo.bat, or make_demo.py + run_all --no-qwen --social) and `pip install playwright` with a
Chromium (in the cloud container PLAYWRIGHT_BROWSERS_PATH is already set; never run `playwright install` there).
Result: console-done.png, console-social.png (lowercase names: build_manual.py only accepts those).
The console is started on a private port from this script and stopped at the end; the maker's own consoles are not touched.
"""
import argparse
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import promo_project as pp

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default="demo")
    ap.add_argument("--out", default=str(ROOT / "docs" / "manual" / "images"))
    ap.add_argument("--port", type=int, default=8899)
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PROMO_PROJECT=a.project, PROMO_PROJECTS_DIR=str(pp.projects_dir()))
    srv = subprocess.Popen([sys.executable, str(ROOT / "scripts" / "dashboard.py"), "--project", a.project, "--port", str(a.port), "--no-open"],
                           env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = "http://127.0.0.1:%d" % a.port
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(base + "/api/version", timeout=2).read()
                break
            except Exception:
                time.sleep(0.5)
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1280, "height": 1500}, device_scale_factor=1)
            pg.goto(base + "/")
            pg.wait_for_selector("#result:not([hidden])", timeout=30000)
            pg.wait_for_timeout(1500)
            pg.screenshot(path=str(out / "console-done.png"))
            soc = pg.locator("#social")
            soc.scroll_into_view_if_needed()
            pg.wait_for_timeout(500)
            soc.screenshot(path=str(out / "console-social.png"))
            b.close()
    finally:
        srv.terminate()
    print("screenshots written to %s" % out)


if __name__ == "__main__":
    main()
