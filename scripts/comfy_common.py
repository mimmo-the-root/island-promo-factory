import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Shared ComfyUI API helpers for Island Promo Factory (upload, submit, wait, download)."""
import json
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")
DEBUG = os.environ.get("PROMO_DEBUG") == "1"
SEED_NODE = "170:169"


def fail(msg):
    print(f"\nERROR: {msg}")
    sys.exit(1)


def _http_error(error):
    print(f"\nCOMFYUI HTTP ERROR {error.code}")
    try:
        print(error.read().decode("utf-8", errors="replace"))
    except Exception:
        pass


def get_json(url):
    with urllib.request.urlopen(urllib.request.Request(url)) as r:
        return json.loads(r.read().decode("utf-8"))


def post_json(url, data):
    req = urllib.request.Request(
        url, data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        _http_error(e)
        raise


def check_server():
    try:
        get_json(f"{COMFY_URL}/system_stats")
    except Exception as e:
        fail(f"ComfyUI not reachable at {COMFY_URL} ({e}). Start ComfyUI first.")


def upload_image(path, prefix="PromoFactory"):
    """Upload to ComfyUI input with a unique name; return LoadImage name."""
    path = Path(path)
    if not path.exists():
        raise RuntimeError(f"Image not found: {path}")
    name = f"{prefix}_{uuid.uuid4().hex[:12]}{path.suffix.lower()}"
    boundary = "----PromoFactory" + uuid.uuid4().hex
    body = bytearray()
    body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; "
             f"filename=\"{name}\"\r\nContent-Type: image/png\r\n\r\n").encode()
    body += path.read_bytes()
    body += (f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\n"
             f"true\r\n--{boundary}--\r\n").encode()
    req = urllib.request.Request(
        f"{COMFY_URL}/upload/image", data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            res = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        _http_error(e)
        raise
    n = res.get("name")
    if not n:
        raise RuntimeError("Upload returned no name")
    sub = res.get("subfolder", "")
    out = f"{sub}/{n}" if sub else n
    print(f"  uploaded {path.name} -> {out}")
    return out


def randomize_seed(workflow):
    """Random seed per run unless PROMO_SEED is set (reproducible)."""
    env = os.environ.get("PROMO_SEED")
    seed = int(env) if env else random.randint(1, 2**48)
    if SEED_NODE in workflow:
        workflow[SEED_NODE]["inputs"]["seed"] = seed
    print(f"  seed: {seed}")
    return seed


def submit_and_wait(workflow, timeout=1200):
    resp = post_json(f"{COMFY_URL}/prompt", {"prompt": workflow, "client_id": str(uuid.uuid4())})
    if resp.get("node_errors"):
        print(json.dumps(resp["node_errors"], indent=2))
        fail("ComfyUI reported node errors")
    pid = resp.get("prompt_id")
    if not pid:
        fail("No prompt_id returned")
    print(f"  prompt_id: {pid}")
    start = time.time()
    while True:
        el = time.time() - start
        if el > timeout:
            fail(f"Timeout after {timeout}s")
        try:
            h = get_json(f"{COMFY_URL}/history/{pid}")
        except Exception:
            time.sleep(2)
            continue
        if pid in h:
            st = h[pid].get("status", {})
            for m in st.get("messages", []):
                if isinstance(m, list) and len(m) >= 2 and m[0] == "execution_error":
                    fail(f"Workflow execution error: {m[1]}")
            if st.get("completed") or st.get("status_str") == "success":
                print(f"  done in {int(el)}s")
                return h[pid]
        print(f"  processing {int(el)}s", end="\r")
        time.sleep(2)


def download_output(history, dest, runs_dir, label):
    """Download first output image via /view; save to dest + archive copy in runs_dir."""
    for node_out in history.get("outputs", {}).values():
        for img in node_out.get("images", []):
            fn = img.get("filename")
            if not fn:
                continue
            q = urllib.parse.urlencode({"filename": fn, "subfolder": img.get("subfolder", ""),
                                        "type": img.get("type", "output")})
            with urllib.request.urlopen(f"{COMFY_URL}/view?{q}") as r:
                data = r.read()
            dest = Path(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            runs_dir = Path(runs_dir)
            runs_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            (runs_dir / f"{label}_{stamp}.png").write_bytes(data)
            print(f"  saved {dest} ({len(data)//1024} KB)")
            return dest
    fail("ComfyUI finished but returned no image")
