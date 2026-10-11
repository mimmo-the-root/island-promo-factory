import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Download the AI models the kit uses into ComfyUI's models folder (resumable, size-checked).

Usage:
  python models.py status                       what is installed / missing (all groups)
  python models.py download [--group image|audio|all] [--optional]
                                                download the missing REQUIRED files (add --optional for the extras)
  python models.py download --dry-run           only list what would be downloaded
Groups:  image = Qwen Image Edit (AI artwork)      audio = ACE-Step 1.5 (AI music for trailer and gameplay)
Where:   ..\\ComfyUI_windows_portable\\ComfyUI\\models next to this kit, or COMFY_MODELS_DIR, or --dir.
A download that stops (network, Ctrl+C) is resumed from the same point the next time. Files are checked against the size the
server announces and only then renamed to their final name, so a half-downloaded file is never mistaken for a model.
If a download fails, the files and the exact folders are in docs/INSTALL.md (manual download).
"""
import argparse
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HF = "https://huggingface.co/"
# group, ComfyUI sub folder, file name, URL, expected size in bytes (about, used for the disk check and as a fallback), required, licence note
MODELS = [
    ("image", "diffusion_models", "qwen_image_edit_2511_int8_convrot.safetensors",
     HF + "Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_edit_2511_int8_convrot.safetensors", 20499083824, True),
    ("image", "text_encoders", "qwen_2.5_vl_7b_fp8_scaled.safetensors",
     HF + "Comfy-Org/HunyuanVideo_1.5_repackaged/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors", 9384670680, True),
    ("image", "vae", "qwen_image_vae.safetensors",
     HF + "Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors", 253806246, True),
    ("image", "loras", "Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors",
     HF + "lightx2v/Qwen-Image-Edit-2511-Lightning/resolve/main/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors", 849608296, False),
    ("image", "upscale_models", "RealESRGAN_x4plus.pth",
     "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth", 67040989, False),
    ("audio", "diffusion_models", "acestep_v1.5_turbo.safetensors",
     HF + "Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/diffusion_models/acestep_v1.5_turbo.safetensors", 4787825604, True),
    ("audio", "text_encoders", "qwen_0.6b_ace15.safetensors",
     HF + "Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/text_encoders/qwen_0.6b_ace15.safetensors", 1191588248, True),
    ("audio", "text_encoders", "qwen_4b_ace15.safetensors",
     HF + "Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/text_encoders/qwen_4b_ace15.safetensors", 8379154232, True),
    ("audio", "vae", "ace_1.5_vae.safetensors",
     HF + "Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/vae/ace_1.5_vae.safetensors", 337431732, True),
]
ROOT = Path(__file__).resolve().parent.parent


def models_dir(override=None):
    for c in (override, os.environ.get("COMFY_MODELS_DIR")):
        if c:
            return Path(c)
    for base in (ROOT.parent / "ComfyUI_windows_portable", ROOT / "ComfyUI_windows_portable"):
        if (base / "ComfyUI" / "models").is_dir():
            return base / "ComfyUI" / "models"
    return None


def entries(group="all", optional=False):
    return [m for m in MODELS if group in ("all", m[0]) and (optional or m[5])]


def _gb(n):
    return "%.1f GB" % (n / 1e9) if n >= 1e8 else "%.0f MB" % (n / 1e6)


def present(mdir, m):
    """True when the file exists and is (about) complete."""
    p = Path(mdir) / m[1] / m[2]
    try:
        return p.is_file() and p.stat().st_size >= 0.98 * m[4]
    except OSError:
        return False


def status(mdir, group="all"):
    """[(entry, installed)] for the required and optional files of a group."""
    return [(m, present(mdir, m)) for m in entries(group, True)]


def missing(mdir, group="all", optional=False):
    return [m for m in entries(group, optional) if not present(mdir, m)]


def _remote_size(url, timeout=30):
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            n = r.headers.get("Content-Length")
            return int(n) if n else None
    except Exception:
        return None


def download(m, mdir, retries=4):
    """Download one file with resume. Returns True on success."""
    dest = Path(mdir) / m[1] / m[2]
    part = dest.with_name(dest.name + ".part")
    dest.parent.mkdir(parents=True, exist_ok=True)
    want = _remote_size(m[3]) or m[4]
    for attempt in range(1, retries + 1):
        have = part.stat().st_size if part.exists() else 0
        if have > want:
            part.unlink()
            have = 0
        if have == want:
            break
        req = urllib.request.Request(m[3], headers={"Range": "bytes=%d-" % have} if have else {})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                if have and r.status != 206:
                    have = 0                      # server ignored the range: start again
                mode = "ab" if have else "wb"
                done, t0, last = have, time.time(), -1
                with open(part, mode) as f:
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        f.write(chunk)
                        done += len(chunk)
                        pct = int(done * 100 / want) if want else 0
                        if pct // 5 != last // 5:
                            last = pct
                            sp = (done - have) / max(1e-6, time.time() - t0) / 1e6
                            print("    %3d%%  %s / %s  (%.1f MB/s)" % (pct, _gb(done), _gb(want), sp), flush=True)
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            print("    interrupted (%s), attempt %d/%d" % (e, attempt, retries), flush=True)
            time.sleep(3 * attempt)
            continue
        if part.exists() and part.stat().st_size == want:
            break
    if part.exists() and part.stat().st_size == want:
        if dest.exists():
            dest.unlink()
        part.replace(dest)
        return True
    print("    FAILED: %s (the partial file is kept; run the command again to resume, or download it by hand: %s)" % (m[2], m[3]))
    return False


def main(argv=None):
    ap = argparse.ArgumentParser(description="Download the AI models into ComfyUI")
    ap.add_argument("action", choices=["status", "download"])
    ap.add_argument("--group", choices=["image", "audio", "all"], default="all")
    ap.add_argument("--optional", action="store_true", help="also the optional files (faster LoRA, upscaler)")
    ap.add_argument("--dir", default=None, help="ComfyUI models folder (default: next to the kit)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    mdir = models_dir(a.dir)
    if mdir is None:
        print("ComfyUI models folder not found next to this kit (expected ..\\ComfyUI_windows_portable\\ComfyUI\\models).")
        print("Install ComfyUI first (docs/INSTALL.md step 3) or pass --dir <path> / set COMFY_MODELS_DIR.")
        return 1
    print("models folder: %s" % mdir)
    if a.action == "status":
        for m, ok in status(mdir, a.group):
            print("%-8s %-6s %s  (%s, %s)" % ("OK" if ok else ("MISSING" if m[5] else "optional"), m[0], m[2], m[1], _gb(m[4])))
        return 0
    todo = missing(mdir, a.group, a.optional)
    if not todo:
        print("Everything is already in place (%s)." % a.group)
        return 0
    need = sum(m[4] for m in todo)
    print("To download: %d file(s), about %s" % (len(todo), _gb(need)))
    for m in todo:
        print("  %-6s %s -> %s\\  (%s)" % (m[0], m[2], m[1], _gb(m[4])))
    if a.dry_run:
        return 0
    try:
        import shutil
        free = shutil.disk_usage(str(mdir)).free
        if free < need * 1.05:
            print("Not enough free disk space: %s free, about %s needed." % (_gb(free), _gb(need)))
            return 1
    except OSError:
        pass
    bad = 0
    for i, m in enumerate(todo, 1):
        print("\n[%d/%d] %s (%s)" % (i, len(todo), m[2], _gb(m[4])), flush=True)
        if not download(m, mdir):
            bad += 1
    print("\n%s" % ("All downloads finished. Restart ComfyUI so it sees the new files." if not bad else
                    "%d file(s) failed. Run the same command again (it resumes), or use the manual links in docs/INSTALL.md." % bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
