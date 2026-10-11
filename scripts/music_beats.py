import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Tempo and first-downbeat detection for a finished music track (numpy only).

Used by the beat-synced gameplay montage when the music is AI-made: an AI track has a tempo close to the one asked for but not exactly
that, and its first beat is not at t=0, so the cuts are planned on the MEASURED beat grid. detect() -> (bpm, first_downbeat_seconds, confidence).
"""
import numpy as np

FPS = 100          # onset-envelope frames per second


def onset_envelope(x, sr):
    """Positive spectral flux (log magnitude, 40 Hz - 8 kHz) at FPS frames per second, local-mean removed, scaled to mean 1."""
    n_fft, hop = 2048, int(sr / FPS)
    if len(x) < n_fft * 4:
        return np.zeros(1)
    win = np.hanning(n_fft).astype(np.float32)
    frames = 1 + (len(x) - n_fft) // hop
    idx = np.arange(n_fft)[None, :] + hop * np.arange(frames)[:, None]
    spec = np.abs(np.fft.rfft(x[idx] * win, axis=1))
    f = np.fft.rfftfreq(n_fft, 1.0 / sr)
    spec = spec[:, (f >= 40) & (f <= 8000)]
    lm = np.log1p(spec * 30.0)
    flux = np.maximum(0.0, np.diff(lm, axis=0)).sum(axis=1)
    flux = np.concatenate([[0.0], flux])
    k = int(FPS * 0.5)
    local = np.convolve(flux, np.ones(k) / k, mode="same")
    env = np.maximum(0.0, flux - local)
    m = env.mean()
    return env / m if m > 0 else env


def _comb(env, bpm, phases):
    """Mean envelope at the beats of a (bpm, phase-in-frames) grid; phases is an array of start offsets in frames."""
    p = FPS * 60.0 / bpm
    n = len(env)
    k = int((n - 1 - phases.max()) // p)
    pos = phases[:, None] + p * np.arange(max(1, k))[None, :]
    i0 = np.floor(pos).astype(int)
    fr = pos - i0
    i1 = np.minimum(i0 + 1, n - 1)
    val = env[i0] * (1 - fr) + env[i1] * fr
    return val.mean(axis=1)


def detect(path_or_samples, hint_bpm=None, lo=70.0, hi=190.0, sr=None):
    """(bpm, first downbeat in seconds, confidence 0-1). With a hint the search is limited to 0.85-1.15 x hint (no half/double-tempo mistakes)."""
    if isinstance(path_or_samples, (str, bytes)) or hasattr(path_or_samples, "__fspath__"):
        import music_ai
        x, sr = music_ai.read_wav(path_or_samples)
    else:
        x = np.asarray(path_or_samples, dtype=np.float32)
    env = onset_envelope(x, sr)
    if len(env) < FPS * 4 or env.max() <= 0:
        return (float(hint_bpm or 120.0), 0.0, 0.0)
    if hint_bpm:
        lo, hi = max(lo, hint_bpm * 0.85), min(hi, hint_bpm * 1.15)
    best = (-1.0, None, None)
    for step, span in ((0.25, None), (0.05, 0.6)):
        grid = np.arange(lo, hi + 1e-9, step) if span is None else np.arange(best[1] - span, best[1] + span + 1e-9, step)
        for b in grid:
            p = FPS * 60.0 / b
            ph = np.arange(0, int(p), 1.0)
            sc = _comb(env, b, ph)
            j = int(sc.argmax())
            if sc[j] > best[0]:
                best = (float(sc[j]), float(b), float(ph[j]))
    score, bpm, ph = best
    # which of the 4 beats of a bar is the downbeat: the one with the strongest envelope on every 4th beat
    p = FPS * 60.0 / bpm
    bars = []
    for j in range(4):
        bars.append(_comb(env, bpm / 4.0, np.array([ph + j * p]))[0])
    first = (ph + int(np.argmax(bars)) * p) / FPS
    first = first % (4 * 60.0 / bpm)
    conf = float(min(1.0, score / (env.mean() * 3.0 + 1e-9)))
    return round(bpm, 2), round(first, 3), round(conf, 2)


if __name__ == "__main__":
    for f in _sys.argv[1:]:
        print(f, detect(f))
