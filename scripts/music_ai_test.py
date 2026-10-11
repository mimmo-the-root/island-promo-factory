import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""SPIKE (throwaway): can ComfyUI's ACE-Step 1.5 make better trailer music than the numpy synth?

Usage: python music_ai_test.py --project <slug> [--seconds 30] [--count 3] [--mood dark|epic|calm|action]
Writes Projects/<map>/audio/_ai_test/ai_<mood>_<seed>.flac (+ .wav when ffmpeg is found). Nothing else is touched:
audio/music.wav and the pipeline are unchanged. Listen to the files and compare with audio/music.wav.
Needs ComfyUI running and the four ACE-Step 1.5 files (the script lists what is missing).
"""
import argparse
import json
import random
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import comfy_common as cc
import promo_project as pp

UNET = "acestep_v1.5_turbo.safetensors"
CLIP1, CLIP2 = "qwen_0.6b_ace15.safetensors", "qwen_4b_ace15.safetensors"
VAE = "ace_1.5_vae.safetensors"

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
        "10": {"class_type": "SaveAudio", "inputs": {"audio": ["9", 0], "filename_prefix": "audio/PromoMusicTest"}},
    }


def missing_models():
    out = []
    for folder, name in (("diffusion_models", UNET), ("text_encoders", CLIP1), ("text_encoders", CLIP2), ("vae", VAE)):
        try:
            have = cc.get_json("%s/models/%s" % (cc.COMFY_URL, folder))
        except Exception:
            have = []
        if name not in have:
            out.append("%s  ->  ComfyUI/models/%s/" % (name, folder))
    return out


def download_audio(history, dest):
    for node_out in history.get("outputs", {}).values():
        for a in node_out.get("audio", []):
            q = urllib.parse.urlencode({"filename": a["filename"], "subfolder": a.get("subfolder", ""), "type": a.get("type", "output")})
            with urllib.request.urlopen("%s/view?%s" % (cc.COMFY_URL, q)) as r:
                data = r.read()
            dest.write_bytes(data)
            return dest
    cc.fail("ComfyUI finished but returned no audio")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--mood", choices=sorted(MOODS), default=None)
    a = ap.parse_args()
    if a.project:
        import os
        os.environ["PROMO_PROJECT"] = a.project
    cfg = pp.load_config() or {}
    mood = a.mood or cfg.get("music_mood", "action")
    mood = mood if mood in MOODS else "action"
    tags, bpm, key = MOODS[mood]
    hint = STYLE_HINT.get(str(cfg.get("style", "")).upper())
    if hint:
        tags += ", " + hint
    tags += ", instrumental, no vocals"
    print("SPIKE: ACE-Step 1.5 | map %s | mood %s | %d bpm | %s | %.0f s" % (pp.project_name(), mood, bpm, key, a.seconds))
    print("prompt: %s" % tags)
    cc.check_server()
    miss = missing_models()
    if miss:
        print("\nMissing ACE-Step 1.5 files (download them, then restart ComfyUI):")
        for m in miss:
            print("  " + m)
        sys.exit(1)
    out = pp.project_dir() / "audio" / "_ai_test"
    out.mkdir(parents=True, exist_ok=True)
    try:
        import video_tools as vt
        ff = vt.find_tool("ffmpeg", "FFMPEG_PATH")
    except Exception:
        ff = None
    for i in range(a.count):
        seed = random.randint(1, 2 ** 48)
        print("\ncandidate %d/%d  seed %d" % (i + 1, a.count, seed))
        hist = cc.submit_and_wait(workflow(tags, bpm, key, a.seconds, seed), timeout=1800)
        f = download_audio(hist, out / ("ai_%s_%d.flac" % (mood, seed)))
        print("  saved %s (%d KB)" % (f.name, f.stat().st_size // 1024))
        if ff:
            subprocess.run([str(ff), "-y", "-v", "error", "-i", str(f), "-ar", "44100", "-ac", "2", str(f.with_suffix(".wav"))])
    print("\nLISTEN to the files in %s and compare them with audio/music.wav (the synth)." % out)
    print("This is a throwaway test: the pipeline still uses the synth.")


if __name__ == "__main__":
    main()
