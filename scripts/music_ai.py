import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Trailer / gameplay music: AI (ACE-Step 1.5 through ComfyUI) with the numpy synth as automatic fallback.

Usage:
  music_ai.py [--seed N] [--seconds 40] [--mood dark|epic|calm|action] [--engine auto|ai|synth] [--candidates 3] [--out PATH]
  music_ai.py --test [--candidates 3]       listening test: files go to audio/_ai_test/, nothing else is touched
  music_ai.py use <file.wav>                make another candidate the music of the map (music.wav + gameplay_music.wav)
Engine: "music_engine" in the map's config.json or PROMO_MUSIC_ENGINE (auto = AI when ComfyUI + the ACE-Step files are there, else synth;
ai = AI only; synth = the old synthesiser). "music_candidates" (default 3) = tracks generated, the best one by automatic scoring is kept
and the others stay in audio/_candidates/ (listen, then `music_ai.py use <file>` to switch).
ACE-Step runs on its own (after Qwen is done): the models of ComfyUI are unloaded before and after, so the GPU memory is free for each.
Default output: Projects/<map>/audio/music.wav (+ music_mood.txt, music_engine.txt: "ai" or "synth").
"""
import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import wave
from pathlib import Path

import numpy as np

import promo_project as pp

UNET = "acestep_v1.5_turbo.safetensors"
CLIP1, CLIP2 = "qwen_0.6b_ace15.safetensors", "qwen_4b_ace15.safetensors"
VAE = "ace_1.5_vae.safetensors"
COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")
DEBUG = os.environ.get("PROMO_DEBUG") == "1"

MOODS = {   # tags, bpm, key
    "dark": ("dark cinematic horror trailer music, low evolving drones, tense strings, eerie piano, deep sub bass, heavy impact hits, "
             "slow build to a powerful climax, wide stereo, modern film score", 100, "E minor"),
    "epic": ("epic cinematic trailer music, powerful orchestra, taiko drums, brass, choir pads, rising tension, huge climax, "
             "hybrid orchestral, modern film score", 112, "D minor"),
    "calm": ("calm cozy chill instrumental, warm soft synth pads, gentle plucks, light percussion, relaxed, uplifting, wide stereo", 84, "A minor"),
    "action": ("high energy action trailer music, aggressive electronic drums, distorted bass, driving synth arpeggios, risers and "
               "impact hits, build up and drop, modern hybrid trailer", 150, "F minor"),
}
STYLE_HINT = {"HORROR": "creepy, spooky", "SCI_FI": "futuristic, sci-fi", "FIRE": "intense, aggressive", "ICE": "cold, icy, crystalline",
              "NEON": "neon synthwave", "GOLD": "grand, triumphant", "WHITE": "clean, bright"}


def log(msg):
    print("music: " + msg, flush=True)


def _cfg():
    try:
        return pp.load_config() or {}
    except BaseException:
        return {}


def engine_setting(cfg=None):
    v = os.environ.get("PROMO_MUSIC_ENGINE") or (cfg if cfg is not None else _cfg()).get("music_engine", "auto")
    v = str(v).strip().lower()
    return v if v in ("auto", "ai", "synth") else "auto"


def candidates_setting(cfg=None):
    try:
        return max(1, min(8, int(os.environ.get("PROMO_MUSIC_CANDIDATES") or (cfg if cfg is not None else _cfg()).get("music_candidates", 3))))
    except (TypeError, ValueError):
        return 3


def _get(url, timeout=5):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _post(url, data, timeout=30):
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8") or "{}")


def comfy_up():
    try:
        _get(COMFY_URL + "/system_stats", 3)
        return True
    except Exception:
        return False


def missing_models():
    """ACE-Step files ComfyUI does not list (needs ComfyUI running)."""
    out = []
    for folder, name in (("diffusion_models", UNET), ("text_encoders", CLIP1), ("text_encoders", CLIP2), ("vae", VAE)):
        try:
            have = _get("%s/models/%s" % (COMFY_URL, folder))
        except Exception:
            have = []
        if name not in have:
            out.append("%s (models/%s)" % (name, folder))
    return out


def free_gpu():
    """Unload every model ComfyUI holds, so each AI stage (Qwen artwork, ACE-Step music) gets the whole GPU memory."""
    try:
        _post(COMFY_URL + "/free", {"unload_models": True, "free_memory": True})
    except Exception:
        pass


def ai_ready(start=True):
    """(ok, reason). Starts ComfyUI when it is not running and the portable build is next to the kit."""
    if not comfy_up():
        if start:
            try:
                import services
                services.start_comfy()
            except BaseException as e:      # services prints its own explanation
                if DEBUG:
                    print("music: could not start ComfyUI: %s" % e)
        if not comfy_up():
            return False, "ComfyUI is not running (start_comfyui.bat)"
    miss = missing_models()
    if miss:
        return False, "ACE-Step files missing: %s -> python scripts\\models.py download --group audio" % ", ".join(miss)
    return True, ""


def prompt_for(mood, cfg=None):
    cfg = cfg if cfg is not None else _cfg()
    tags, bpm, key = MOODS.get(mood, MOODS["action"])
    hint = STYLE_HINT.get(str(cfg.get("style", "")).upper())
    if hint:
        tags += ", " + hint
    return tags + ", instrumental, no vocals", bpm, key


def workflow(tags, bpm, key, seconds, seed):
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": UNET, "weight_dtype": "default"}},
        "2": {"class_type": "DualCLIPLoader", "inputs": {"clip_name1": CLIP1, "clip_name2": CLIP2, "type": "ace", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
        "4": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["1", 0], "shift": 3}},
        "5": {"class_type": "TextEncodeAceStepAudio1.5", "inputs": {
            "clip": ["2", 0], "tags": tags, "lyrics": "[Instrumental]", "seed": seed, "bpm": bpm, "duration": float(seconds),
            "timesignature": "4", "language": "en", "keyscale": key, "generate_audio_codes": True, "cfg_scale": 2.0,
            "temperature": 0.85, "top_p": 0.9, "top_k": 0, "min_p": 0.0}},
        "6": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["5", 0]}},
        "7": {"class_type": "EmptyAceStep1.5LatentAudio", "inputs": {"seconds": float(seconds), "batch_size": 1}},
        "8": {"class_type": "KSampler", "inputs": {"model": ["4", 0], "positive": ["5", 0], "negative": ["6", 0], "latent_image": ["7", 0],
                                                    "seed": seed, "steps": 8, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "9": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
        "10": {"class_type": "SaveAudio", "inputs": {"audio": ["9", 0], "filename_prefix": "audio/PromoMusic"}},
    }


def _run_comfy(wf, timeout=1800):
    import time
    resp = _post(COMFY_URL + "/prompt", {"prompt": wf, "client_id": "promo-music"})
    if resp.get("node_errors"):
        raise RuntimeError("ComfyUI node errors: %s" % json.dumps(resp["node_errors"])[:400])
    pid = resp.get("prompt_id")
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            h = _get("%s/history/%s" % (COMFY_URL, pid))
        except Exception:
            h = {}
        if pid in h:
            st = h[pid].get("status", {})
            for m in st.get("messages", []):
                if isinstance(m, list) and len(m) >= 2 and m[0] == "execution_error":
                    raise RuntimeError("ComfyUI execution error: %s" % str(m[1])[:400])
            if st.get("completed") or st.get("status_str") == "success":
                return h[pid]
        time.sleep(2)
    raise RuntimeError("ComfyUI timeout after %d s" % timeout)


def _fetch_audio(hist, dest):
    for node_out in hist.get("outputs", {}).values():
        for a in node_out.get("audio", []):
            q = urllib.parse.urlencode({"filename": a["filename"], "subfolder": a.get("subfolder", ""), "type": a.get("type", "output")})
            with urllib.request.urlopen("%s/view?%s" % (COMFY_URL, q), timeout=120) as r:
                dest.write_bytes(r.read())
            return dest
    raise RuntimeError("ComfyUI returned no audio")


def _ffmpeg():
    import video_tools as vt
    ff = vt.find_tool("ffmpeg", "FFMPEG_PATH")
    if not ff:
        raise RuntimeError("ffmpeg not found")
    return ff


def read_wav(path):
    """(mono float32 array, sample rate) of a 16-bit PCM wav."""
    with wave.open(str(path), "rb") as w:
        sr, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
        raw = w.readframes(n)
    a = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    return (a.reshape(-1, ch).mean(axis=1) if ch > 1 else a), sr


def score_track(path):
    """Heuristic 0-100 for 'a trailer track with impact': dynamics, a build towards the end, healthy level, no clipping, no dead air.
    It only ranks candidates; the final judgement is the user's ear."""
    x, sr = read_wav(path)
    if len(x) < sr * 2:
        return 0.0
    win = int(sr * 0.5)
    n = len(x) // win
    rms = np.sqrt((x[:n * win].reshape(n, win) ** 2).mean(axis=1) + 1e-12)
    db = 20 * np.log10(rms)
    dyn = float(np.percentile(db, 90) - np.percentile(db, 10))
    head, tail = db[:max(1, n // 5)].mean(), db[int(n * 0.6):].mean()
    arc = float(tail - head)
    level = float(db.mean())
    clip = float((np.abs(x) > 0.99).mean())
    dead = float((db < -50).mean())
    s = min(dyn, 12.0) / 12.0 * 40 + max(0.0, min(arc, 8.0)) / 8.0 * 30
    s += 20 * max(0.0, 1 - abs(level + 16) / 12.0)          # about -16 dBFS RMS is a healthy trailer level
    s -= clip * 800 + dead * 100
    return round(max(0.0, min(100.0, s)), 1)


def generate_ai(mood, seconds, seed, dest, candidates=3, cand_dir=None, cfg=None):
    """Make `candidates` ACE-Step tracks, keep the best-scoring one as `dest` (wav, 44.1 kHz stereo). Returns a dict, or raises."""
    tags, bpm, key = prompt_for(mood, cfg)
    log("ACE-Step 1.5 | mood %s | %d bpm | %s | %.0f s | %d candidate(s)" % (mood, bpm, key, seconds, candidates))
    log("prompt: %s" % tags)
    ff = _ffmpeg()
    cand_dir = Path(cand_dir) if cand_dir else dest.parent / "_candidates"
    cand_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    free_gpu()
    made = []
    try:
        for i in range(candidates):
            sd = rng.randint(1, 2 ** 48)
            log("candidate %d/%d (seed %d) ..." % (i + 1, candidates, sd))
            hist = _run_comfy(workflow(tags, bpm, key, seconds, sd))
            with tempfile.TemporaryDirectory() as td:
                flac = _fetch_audio(hist, Path(td) / "t.flac")
                wav = cand_dir / ("%s_%d_%d.wav" % (dest.stem, i + 1, sd))
                r = subprocess.run([str(ff), "-y", "-v", "error", "-i", str(flac), "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(wav)],
                                   capture_output=True, text=True)
                if r.returncode != 0 or not wav.exists():
                    raise RuntimeError("ffmpeg could not convert the track: %s" % (r.stderr or "")[-200:])
            sc = score_track(wav)
            log("candidate %d: score %.1f" % (i + 1, sc))
            made.append((sc, wav, sd))
    finally:
        free_gpu()
    if not made:
        raise RuntimeError("no candidate was produced")
    best = max(made, key=lambda t: t[0])
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(best[1]), str(dest))
    log("kept: %s (score %.1f); the others stay in %s (switch with: music_ai.py use <file>)" % (best[1].name, best[0], cand_dir.name))
    return {"engine": "ai", "bpm": bpm, "key": key, "seed": best[2], "score": best[0], "candidates": len(made)}


def generate_synth(mood, seconds, seed, dest):
    import music_generator as mg
    buf, bpm, key, prog = mg.generate(seed, seconds, mood)
    dest.parent.mkdir(parents=True, exist_ok=True)
    mg.write_wav(dest, buf)
    log("synth: seed=%d mood=%s bpm=%d key=+%d progression=%s" % (seed, mood, bpm, key, prog))
    return {"engine": "synth", "bpm": bpm, "key": key, "seed": seed}


def make_track(mood, seconds, seed, dest, engine=None, candidates=None, cfg=None):
    """One track at `dest`: AI when allowed and available, else the synth. Never raises because of the AI part."""
    cfg = cfg if cfg is not None else _cfg()
    dest = Path(dest)
    engine = engine or engine_setting(cfg)
    if engine != "synth":
        ok, why = ai_ready()
        if ok:
            try:
                return generate_ai(mood, seconds, seed, dest, candidates or candidates_setting(cfg), cfg=cfg)
            except (Exception, SystemExit) as e:
                why = "AI generation failed: %s" % e
        if engine == "ai":
            raise RuntimeError("music_engine is 'ai' but: %s" % why)
        log("AI music not used (%s) -> using the built-in synth" % why)
    return generate_synth(mood, seconds, seed, dest)


def will_use_ai(cfg=None):
    """Quick, side-effect free guess for the run_all time estimate."""
    cfg = cfg if cfg is not None else _cfg()
    return engine_setting(cfg) != "synth" and comfy_up() and not missing_models()


def use_candidate(path):
    src = Path(path)
    if not src.is_file():
        print("file not found: %s" % src)
        return 1
    audio = pp.project_dir() / "audio"
    audio.mkdir(parents=True, exist_ok=True)
    for name in ("music.wav", "gameplay_music.wav"):
        shutil.copyfile(str(src), str(audio / name))
    (audio / "music_engine.txt").write_text("ai", encoding="utf-8")
    print("music.wav and gameplay_music.wav of %s are now %s (rebuild the trailer: run_all %s --no-qwen --skip-video)" % (pp.project_name(), src.name, pp.project_name()))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("action", nargs="?", choices=["use"], help="use <file>: make a candidate the map's music")
    ap.add_argument("file", nargs="?")
    ap.add_argument("--project", default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--seconds", type=float, default=40.0)
    ap.add_argument("--mood", choices=sorted(MOODS), default=None)
    ap.add_argument("--engine", choices=["auto", "ai", "synth"], default=None)
    ap.add_argument("--candidates", type=int, default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--test", action="store_true", help="listening test into audio/_ai_test/, music.wav is not touched")
    a = ap.parse_args(argv)
    if a.project:
        os.environ["PROMO_PROJECT"] = a.project
    if a.action == "use":
        if not a.file:
            ap.error("use needs a file")
        return use_candidate(a.file)
    cfg = _cfg()
    mood = a.mood or cfg.get("music_mood", "action")
    mood = mood if mood in MOODS else "action"
    seed = a.seed if a.seed is not None else random.randint(1, 2 ** 31)
    audio = pp.project_dir() / "audio"
    if a.test:
        out = audio / "_ai_test" / "test.wav"
        r = make_track(mood, a.seconds, seed, out, engine="ai", candidates=a.candidates or 3, cfg=cfg)
        print("Listen to the files in %s" % out.parent)
        return 0
    out = Path(a.out) if a.out else audio / "music.wav"
    r = make_track(mood, a.seconds, seed, out, a.engine, a.candidates, cfg)
    if not a.out:
        (audio / "music_mood.txt").write_text(mood, encoding="utf-8")     # lets run_all redo the track when the mood changes
        (audio / "music_engine.txt").write_text(r["engine"], encoding="utf-8")
    log("done: %s (%s)" % (out, r["engine"]))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as e:
        print("ERROR: %s" % e)
        sys.exit(1)
