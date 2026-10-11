import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Generate an original, royalty-free trailer music bed (numpy only, no samples, no models).

Usage: music_generator.py [--seed N] [--seconds 40] [--mood action|dark|epic|calm] [--out PATH]
Default mood: "music_mood" in the map's config.json (chosen from the artwork, like the title style), else action.
Default output: Projects/<map>/audio/music.wav (picked up by trailer_builder.py).
The same seed always gives the same track; a new seed gives a different one
(key, tempo, chord progression, arpeggio pattern and drum pattern change).
All sound is synthesised from scratch by this script, so it contains no third-party material.
"""
import argparse
import wave

import numpy as np

import promo_project as pp

SR = 44100
MINOR = [0, 2, 3, 5, 7, 8, 10]
# chord progressions as scale degrees (0-based) per bar, 4 bars each
PROGRESSIONS = {
    "dark": [[0, 5, 2, 6], [0, 3, 5, 4], [0, 0, 5, 6]],
    "epic": [[0, 5, 2, 6], [0, 6, 5, 6], [0, 2, 5, 6]],
    "calm": [[0, 5, 3, 4], [0, 3, 0, 4], [5, 3, 0, 4]],
    "action": [[0, 5, 2, 6], [0, 6, 5, 6], [0, 0, 5, 6], [0, 5, 6, 4]],
}
TEMPO = {"dark": (92, 108), "epic": (104, 124), "calm": (76, 90), "action": (146, 168)}


def config_mood():
    """The map's music mood (config.json "music_mood"): dark = horror/spooky, epic = war/fantasy, calm = chill/cozy, action = fast arcade. Default action."""
    try:
        import json
        m = json.loads((pp.project_dir() / "config.json").read_text(encoding="utf-8")).get("music_mood", "action")
        return m if m in PROGRESSIONS else "action"
    except BaseException:      # no map selected / unreadable config
        return "action"


def midi_hz(m):
    return 440.0 * 2 ** ((np.asarray(m, dtype=np.float64) - 69) / 12)


def chord_notes(root_midi, degree):
    notes = []
    for k in (0, 2, 4):
        d = degree + k
        notes.append(root_midi + MINOR[d % 7] + 12 * (d // 7))
    return notes


def put(buf, start_s, sig, pan=0.0, gain=1.0):
    i = int(start_s * SR)
    if i >= buf.shape[0]:
        return
    n = min(len(sig), buf.shape[0] - i)
    l, r = gain * (1 - max(pan, 0)), gain * (1 + min(pan, 0))
    buf[i:i + n, 0] += sig[:n] * l
    buf[i:i + n, 1] += sig[:n] * r


def env(n, a, r):
    t = np.arange(n) / SR
    e = np.minimum(1.0, t / max(a, 1e-4))
    e *= np.minimum(1.0, np.maximum(0.0, (n / SR - t)) / max(r, 1e-4))
    return e


def pad(freq, dur, bright):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for det in (-0.12, 0.0, 0.12):
        f = freq * 2 ** (det / 12)
        for h in range(1, 3 + int(bright * 5)):
            out += np.sin(2 * np.pi * f * h * t) / (h ** 1.4)
    return out * env(n, 0.6, 0.8) / 3.0


def pluck(freq, dur=0.5):
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = np.sin(2 * np.pi * freq * t) + 0.5 * np.sin(2 * np.pi * 2 * freq * t) + 0.25 * np.sin(2 * np.pi * 3 * freq * t)
    return sig * np.exp(-t * 7.0) * env(n, 0.003, 0.05)


def bass(freq, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(2 * np.pi * 2 * freq * t)
    return sig * env(n, 0.01, 0.08)


def kick():
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    f = 45 + 110 * np.exp(-t * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-t * 9) * 1.2


def snare(rng):
    n = int(0.28 * SR)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    return (noise * np.exp(-t * 18) * 0.5 + np.sin(2 * np.pi * 190 * t) * np.exp(-t * 25) * 0.4)


def hat(rng, open_=False):
    n = int((0.25 if open_ else 0.05) * SR)
    t = np.arange(n) / SR
    noise = np.diff(rng.standard_normal(n + 1))  # crude high-pass
    return noise * np.exp(-t * (14 if open_ else 70)) * 0.25


def riser(dur, rng):
    n = int(dur * SR)
    t = np.arange(n) / SR
    noise = np.diff(rng.standard_normal(n + 1))
    return noise * (t / dur) ** 3 * 0.35


def delay(buf, beat_s, fb=0.35, mix=0.30):
    d = int(beat_s * 0.75 * SR)
    out = buf.copy()
    wet = np.zeros_like(buf)
    wet[d:, 0] = buf[:-d, 1]
    wet[d:, 1] = buf[:-d, 0]
    for k in range(1, 5):
        sh = d * k
        if sh >= buf.shape[0]:
            break
        out[sh:, 0] += mix * (fb ** (k - 1)) * (buf[:-sh, 1] if k % 2 else buf[:-sh, 0])
        out[sh:, 1] += mix * (fb ** (k - 1)) * (buf[:-sh, 0] if k % 2 else buf[:-sh, 1])
    return out


def saw(freq, dur, nh=10, det=0.07, a=0.004, decay=6.0):
    """Detuned two-voice saw (band-limited by harmonic count), plucky decay."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for d in (-det, det):
        f = freq * 2 ** (d / 12)
        for h in range(1, nh + 1):
            out += np.sin(2 * np.pi * f * h * t) / h
    return out * env(n, a, 0.03) * np.exp(-t * decay) * 0.5


def clap(rng):
    n = int(0.22 * SR)
    t = np.arange(n) / SR
    noise = np.diff(rng.standard_normal(n + 1))
    burst = (np.exp(-((t % 0.012)) * 400) * (t < 0.036))
    return noise * (0.55 * np.exp(-t * 22) + 0.9 * burst) * 0.7 + np.sin(2 * np.pi * 185 * t) * np.exp(-t * 30) * 0.35


def crash(rng, dur=1.6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    return np.diff(rng.standard_normal(n + 1)) * np.exp(-t * 2.6) * 0.45


def generate_action(seed, seconds):
    """Fast, aggressive game-trailer track: driving 16th bass, saw lead, stabs, sidechain pump, snare rolls."""
    rng = np.random.default_rng(seed)
    bpm = int(rng.integers(146, 169))
    key = int(rng.integers(0, 12))
    root = 33 + key  # A1 + key
    prog = PROGRESSIONS["action"][int(rng.integers(0, len(PROGRESSIONS["action"])))]
    beat = 60.0 / bpm
    bar = 4 * beat
    s16 = beat / 4
    n_bars = int(np.ceil(seconds / bar)) + 1
    length = int((n_bars * bar + 3.0) * SR)
    mel = np.zeros((length, 2))   # bass, lead, stabs, pad  (gets sidechained)
    drm = np.zeros((length, 2))   # drums
    motif = [int(x) for x in rng.integers(0, 7, size=8)]
    motif[0] = 0
    bass_pat = [1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0]
    oct_pat = [0, 0, 12, 0, 0, 12, 0, 0, 0, 0, 12, 0, 0, 12, 0, 12]
    for b in range(n_bars):
        t0 = b * bar
        deg = prog[b % len(prog)]
        r_midi = root + MINOR[deg % 7]
        chord = chord_notes(root + 24, deg)
        # bass: 16th pulse with octave jumps
        for i in range(16):
            if bass_pat[i]:
                f = midi_hz(r_midi + oct_pat[i])
                put(mel, t0 + i * s16, saw(f, s16 * 1.8, nh=7, det=0.03, decay=9.0) * 0.55 + bass(f, s16 * 1.8) * 0.5, gain=0.55)
        # chord stabs on off-beat eighths (from bar 1)
        if b >= 1:
            for e in (1, 3, 5, 7):
                for k, m in enumerate(chord):
                    put(mel, t0 + e * beat / 2, saw(midi_hz(m), beat * 0.35, nh=8, decay=10.0), pan=(k - 1) * 0.4, gain=0.17)
        # lead hook (from bar 2): 8th-note motif two octaves up, alternate bars lift
        if b >= 2:
            for e in range(8):
                d = (motif[e] + (2 if (b % 2) else 0)) % 7
                m = root + 36 + MINOR[d] + (12 if e in (3, 7) and b % 4 == 3 else 0)
                put(mel, t0 + e * beat / 2, saw(midi_hz(m), beat * 0.55, nh=12, det=0.12, decay=3.5), pan=0.15 * (1 if e % 2 else -1), gain=0.24)
        else:
            for k, m in enumerate(chord):
                put(mel, t0, pad(midi_hz(m), bar + 0.4, 0.9), pan=(k - 1) * 0.35, gain=0.25)
        # drums
        for q in range(4):
            put(drm, t0 + q * beat, kick(), gain=0.95)
        if b >= 1:
            put(drm, t0 + beat, clap(rng), gain=0.6)
            put(drm, t0 + 3 * beat, clap(rng), gain=0.6)
            for i in range(16):
                if i % 2 == 0:
                    put(drm, t0 + i * s16 + (s16 if False else 0), hat(rng, open_=(i % 4 == 2)), pan=0.3, gain=0.55)
                elif b >= 2:
                    put(drm, t0 + i * s16, hat(rng), pan=-0.3, gain=0.30)
        if b % 4 == 0 and b > 0:
            put(drm, t0, crash(rng), gain=0.8)
        if b % 4 == 3:  # snare roll into the next section, accelerating
            for i in range(16):
                if i >= 8:
                    put(drm, t0 + i * s16, snare(rng), gain=0.25 + 0.5 * (i - 8) / 8.0)
            put(drm, t0 + 3 * beat, riser(beat, rng), gain=0.5)
    # sidechain pump on the melodic bus (follows the kick)
    tt = np.arange(length) / SR
    ph = (tt % beat)
    duck = 0.28 + 0.72 * (1 - np.exp(-ph / 0.11))
    mel *= duck[:, None]
    mix = delay(mel, beat, fb=0.3, mix=0.18) * 0.9 + drm
    mix = mix[: int(seconds * SR)]
    mix = np.tanh(mix * 0.8)  # drive: loud, punchy, glued
    mix = mix / (float(np.max(np.abs(mix))) or 1.0) * 0.80
    return mix, bpm, key, prog


def generate(seed, seconds, mood):
    if mood == "action":
        return generate_action(seed, seconds)
    rng = np.random.default_rng(seed)
    lo, hi = TEMPO[mood]
    bpm = int(rng.integers(lo, hi + 1))
    key = int(rng.integers(0, 12))  # semitone offset from A
    root = 45 + key  # A2 + key
    prog = PROGRESSIONS[mood][int(rng.integers(0, len(PROGRESSIONS[mood])))]
    arp_pat = [int(x) for x in rng.permutation([0, 1, 2, 1, 2, 1, 0, 2])[:8]]
    beat = 60.0 / bpm
    bar = 4 * beat
    n_bars = int(np.ceil(seconds / bar)) + 1
    buf = np.zeros((int((n_bars * bar + 3.0) * SR), 2))
    # arrangement: bars 0-1 pad only, 2+ bass+arp, 4+ drums, last bars drive; ramp 0..1
    for b in range(n_bars):
        t0 = b * bar
        deg = prog[b % 4]
        prog_pos = b / max(n_bars - 1, 1)
        notes = chord_notes(root + 12, deg)
        bright = min(1.0, 0.25 + prog_pos * 1.1)
        for k, m in enumerate(notes):
            put(buf, t0, pad(midi_hz(m), bar + 0.8, bright), pan=(k - 1) * 0.35, gain=0.22)
        if b >= 2:
            bf = midi_hz(root + MINOR[deg % 7] - 12 + 12)
            for e in range(8):
                put(buf, t0 + e * beat / 2, bass(bf, beat / 2 * 0.9), gain=0.33)
            for s in range(16):
                idx = arp_pat[s % 8]
                m = notes[idx] + 12 * (1 + (s // 8) % 2)
                put(buf, t0 + s * beat / 4, pluck(midi_hz(m)), pan=0.4 * (1 if s % 2 else -1), gain=0.10 + 0.08 * bright)
        if b >= 4:
            for q in range(4):
                put(buf, t0 + q * beat, kick(), gain=0.55)
            put(buf, t0 + beat, snare(rng), gain=0.45)
            put(buf, t0 + 3 * beat, snare(rng), gain=0.45)
            for e in range(8):
                put(buf, t0 + e * beat / 2 + beat / 4 * (e % 2 == 1) * 0, hat(rng, open_=(e % 4 == 3)), pan=0.3, gain=0.55)
        if b == 3 or b == n_bars - 2:
            put(buf, t0 + bar - min(bar, 2.0), riser(min(bar, 2.0), rng), gain=0.5)
    buf = delay(buf, beat)
    total = int(seconds * SR)
    buf = buf[:total]
    # gentle limiter + normalise to about -1.5 dBFS peak
    buf = np.tanh(buf * 1.2)
    peak = float(np.max(np.abs(buf))) or 1.0
    buf = buf / peak * 0.84
    return buf, bpm, key, prog


def write_wav(path, buf):
    pcm = (np.clip(buf, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=None, help="default: random (printed, so you can reproduce it)")
    ap.add_argument("--seconds", type=float, default=40.0)
    ap.add_argument("--mood", choices=sorted(PROGRESSIONS), default=None, help="default: music_mood from the map config.json, else action")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    seed = a.seed if a.seed is not None else int(np.random.SeedSequence().entropy % 100000)
    a.mood = a.mood or config_mood()
    out = _P(a.out) if a.out else pp.project_dir() / "audio" / "music.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    buf, bpm, key, prog = generate(seed, a.seconds, a.mood)
    write_wav(out, buf)
    if not a.out:
        (out.parent / "music_mood.txt").write_text(a.mood, encoding="utf-8")   # lets run_all redo the track when the mood changes
    print("music: seed=%d mood=%s bpm=%d key=+%d progression=%s" % (seed, a.mood, bpm, key, prog))
    print("written: %s (%.0f s). Original synthesis, no third-party material." % (out, a.seconds))
    print("Rebuild the trailer: python scripts/trailer_builder.py")


if __name__ == "__main__":
    main()
