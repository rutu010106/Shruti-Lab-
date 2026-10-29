#!/usr/bin/env python3
"""
score_tracks.py — score ANY pitch tracker on a Shruti Lab simulated recording, with one common scorer.

Inputs (all three are downloaded from the app: Simulation Study → "6. Export one condition"):
    shruti_runN_seedS.wav          the simulated audio (voice + drone + noise + room)
    shruti_runN_seedS_truth.csv    ground truth every 10 ms: time_s, voiced, f0_hz
    shruti_runN_seedS_tracks.csv   the app's own trackers: method, time_s, f0_hz

Usage:
    python score_tracks.py --wav X.wav --truth X_truth.csv --tracks X_tracks.csv [--pyin]
                           [--extra NAME=path.csv ...] [--window 0.128]

    --pyin     also run librosa.pyin on the WAV (pip install librosa). pYIN: Mauch & Dixon, ICASSP 2014.
    --extra    score another tracker's output: a CSV with columns time_s,f0_hz (blank/0/NaN = unvoiced)
               e.g. the output of CREPE, Praat, SPICE, ... exported to that format.

Scoring (identical for every tracker, so they are comparable to each other):
    A track point at time t is judged on the window [t - w/2, t + w/2] (default w = 128 ms):
      voiced truth : >= 90% of the window is a sung note   -> counts for RPA / recall / octave errors
      rest         : <= 10% of the window is a sung note   -> counts for false alarms
      otherwise    : ignored (note edges)
    RPA50 / RPA20 : voiced truth frames whose estimate is within 50 / 20 cents (missing estimate = miss).
Note: numbers can differ slightly from the in-app table because the frame definition here is
time-window based (10 ms truth grid) rather than sample based.  Compare trackers WITHIN this script.

Needs: numpy, pandas, scipy (and librosa for --pyin).
"""
import argparse, sys
import numpy as np, pandas as pd
from scipy.io import wavfile

def load_truth(path):
    t = pd.read_csv(path)
    return t.time_s.to_numpy(float), t.voiced.to_numpy(int) == 1, pd.to_numeric(t.f0_hz, errors="coerce").to_numpy(float)

def score(times, f0, tt, mask, tf0, w=0.128):
    times = np.asarray(times, float); f0 = np.asarray(f0, float)
    f0 = np.where(np.isfinite(f0) & (f0 > 0), f0, np.nan)
    tcents = 1200 * np.log2(np.where(mask & np.isfinite(tf0), tf0, np.nan))
    nv = nu = hit50 = hit20 = det = octv = fa = 0; errs = []
    for t, f in zip(times, f0):
        lo, hi = np.searchsorted(tt, t - w / 2), np.searchsorted(tt, t + w / 2, side="right")
        if hi - lo < 3:
            continue
        frac = mask[lo:hi].mean()
        if frac >= 0.9:
            nv += 1; truth = np.nanmean(tcents[lo:hi])
            if np.isfinite(f):
                det += 1; e = 1200 * np.log2(f) - truth; errs.append(abs(e))
                hit50 += abs(e) <= 50; hit20 += abs(e) <= 20
                k = round(e / 1200)
                if k != 0 and abs(e - 1200 * k) <= 50:
                    octv += 1
        elif frac <= 0.1:
            nu += 1; fa += np.isfinite(f)
    pct = lambda a, b: 100 * a / b if b else float("nan")
    return dict(voiced_frames=nv, rest_frames=nu, RPA50=pct(hit50, nv), RPA20=pct(hit20, nv), reported_pct=pct(det, nv),
                octave_err_pct=pct(octv, nv), median_abs_err_cents=float(np.median(errs)) if errs else float("nan"),
                false_alarm_pct=pct(fa, nu))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", required=True); ap.add_argument("--truth", required=True); ap.add_argument("--tracks")
    ap.add_argument("--pyin", action="store_true"); ap.add_argument("--extra", action="append", default=[])
    ap.add_argument("--window", type=float, default=0.128); ap.add_argument("--fmin", type=float, default=70); ap.add_argument("--fmax", type=float, default=1000)
    ap.add_argument("--out", default="scores.csv")
    a = ap.parse_args()
    tt, mask, tf0 = load_truth(a.truth); rows = {}
    if a.tracks:
        d = pd.read_csv(a.tracks)
        for m, g in d.groupby("method", sort=False):
            rows[m] = score(g.time_s, pd.to_numeric(g.f0_hz, errors="coerce"), tt, mask, tf0, a.window)
    for item in a.extra:
        name, _, path = item.partition("=")
        g = pd.read_csv(path); cols = {c.lower(): c for c in g.columns}
        tcol = cols.get("time_s") or cols.get("time"); fcol = cols.get("f0_hz") or cols.get("frequency") or cols.get("f0")
        if not tcol or not fcol: sys.exit("--extra %s needs columns time_s and f0_hz" % path)
        rows[name] = score(g[tcol], pd.to_numeric(g[fcol], errors="coerce"), tt, mask, tf0, a.window)
    if a.pyin:
        try:
            import librosa
        except ImportError:
            sys.exit("librosa is not installed. Run: pip install librosa   (then repeat with --pyin)")
        sr, x = wavfile.read(a.wav); x = x.astype(np.float32) / (32768.0 if x.dtype == np.int16 else 1.0)
        fl = 2048 if sr <= 16000 else 4096; hop = fl // 4
        f0, vflag, vprob = librosa.pyin(x, fmin=a.fmin, fmax=a.fmax, sr=sr, frame_length=fl, hop_length=hop, center=True)
        times = librosa.times_like(f0, sr=sr, hop_length=hop)
        rows["pyin (librosa)"] = score(times, np.where(vflag, f0, np.nan), tt, mask, tf0, a.window)
    if not rows: sys.exit("Nothing to score: give --tracks, --extra or --pyin.")
    res = pd.DataFrame(rows).T.round(1); res.to_csv(a.out)
    print(res.to_string()); print("\nSaved", a.out)

if __name__ == "__main__":
    main()
