# Shruti Lab v2 — research plan, first results, and what to do next

## 0. Files
| File | Purpose |
|---|---|
| `index-v1-fixed.html` | Your presentation version. Identical to the one you tested, with one bug fixed (the waveform picture on *Explore Shruti* never drew because two elements shared an id). |
| `index-v2.html` | Research version: everything in v1 + **Simulation Study** page + **drone-aware mode** on the Live page. |
| `analyze_results.py` | Statistics + figures for the CSV exported from the Simulation Study. |
| `score_tracks.py` | Scores *any* pitch tracker (the app's, pYIN, CREPE, …) on an exported simulated recording. |

Open the HTML files by double-clicking (Chrome). Python: `pip install pandas numpy scipy matplotlib` (and `librosa` for pYIN).

## 1. What was added in v2
1. **Drone-aware tracker.** Calibrate on the drone alone, then subtract its average power spectrum (over-subtraction α = 3, floor β = 0.05) from each frame before a YIN-style pitch search. Same confidence rejection / jump guard / smoothing as v1, so only the *front end* differs.
2. **Room-adaptive settings (a hypothesis, not a feature that works).** The decay time is measured with the interrupted-noise method and used to set smoothing/confidence.
3. **Simulation Study.** Seeded synthetic melody (vibrato, glides, rests) + 4-string tanpura-like drone + white noise + synthetic room, with known true pitch; four trackers scored; CSV and WAV export.
4. **Live drone mode.** Play a synthetic drone (or use your own tanpura), calibrate for 3 s, sing.

## 2. First simulation results (seeds 101–103; settings were tuned on seeds 1–2)
108 simulated recordings (4 drone levels × 3 noise levels × 3 room decay times × 3 seeds). Raw pitch accuracy within ±50 ¢ (RPA50), %:

| Drone (voice vs drone) | Baseline | Improved v1 | Drone-aware | Drone-aware + room-adaptive |
|---|---|---|---|---|
| none | 97.0 | 86.6 | 86.6 | 83.3 |
| voice +6 dB | 64.3 | 28.4 | 85.1 | 82.2 |
| equal (0 dB) | 27.6 | 0.9 | 63.0 | 58.6 |
| voice −3 dB | 16.7 | 0.0 | 45.7 | 41.6 |

Paired comparisons (difference A−B in RPA50, 95% bootstrap CI):
* **H2 (drone-aware vs improved v1, drone present):** +54.8 points [51.0, 58.5], better in 81 of 81 recordings. **Supported for accuracy in simulation.** *Not* supported for false alarms: drone-aware reported more pitch in rests (+4.0 points) than improved v1, which simply reported very little (it found a pitch in only ~39% of voiced frames).
* **H3 (room-adaptive vs plain drone-aware, reverberant):** −5.5 points [−6.8, −4.3]. **Rejected in this form** — the rule "smooth more when the room is more reverberant" hurts at note changes.
* **H1 (improved v1 vs baseline):** **Rejected** on this metric: with no drone, plain autocorrelation scored higher than the smoothed YIN pipeline (97.0 vs 86.6). The extra smoothing costs accuracy at note changes. The improved pipeline mainly reduces false alarms and octave errors.
* When both trackers lock onto the drone, they often return Sa/2 or Pa (the low drone strings) instead of the voice — that is the failure the drone-aware front end removes.

Live check: a Chrome test with a fake microphone playing a drone-only intro followed by melody + drone (equal loudness) gave 19/29 correct voiced samples for drone-aware, 0/29 for improved v1 and 1/28 for baseline. This is one clip, a sanity check, not a result.

**Read these as simulation findings only.** The voice, drone and room are models. The tuned settings (α, β, thresholds) were chosen by looking at simulated data; the held-out seeds reduce, but do not remove, optimism.

## 3. Is it patentable / publishable? An honest assessment
* **Patent:** I cannot tell you, and nobody can before a prior-art search. Spectral subtraction with a noise (here: drone) profile and YIN are both old; drone-related processing is already studied in Indian-music research (tonic identification, predominant melody extraction). The *combination* "calibrated drone-spectrum subtraction before YIN-type tracking, for Indian vocal music" may or may not be new. In India, computer programmes and algorithms "per se" are excluded (Section 3(k)); a claim would need a demonstrable technical effect — a patent attorney must judge this. Ask your professor / college IPR cell about disclosure *before* presenting or publishing the method; do not rely on a grace period.
* **Paper:** much more realistic. A paper can be a careful, reproducible evaluation: open simulator, real recordings, comparison with pYIN and one more tracker, negative results (H1 and H3 failing are informative), limits of the drone-aware method (needs calibration, fails when the voice is much quieter than the drone).

## 4. Plan
**Week 1 — prior art (before more building).** Search Google Scholar, Google Patents, Espacenet and InPASS. Suggested terms: *drone suppression pitch*, *tanpura interference pitch tracking*, *Hindustani vocal pitch extraction drone*, *predominant melody extraction accompaniment*, *spectral subtraction fundamental frequency estimation*, *noise-profile calibration pitch tracker*. Log every query, date, and the 10 closest results with a one-line note on what each does and does not cover. Starting reading list: pYIN (Mauch & Dixon, 2014), Gulati et al. on tonic identification in Indian art music (two papers, see the links on the Research page), Salamon & Gómez on melody extraction (Melodia). Verify every reference yourself.
**Week 2 — simulation, properly.** Run the Standard preset with ≥ 10 new seeds; export the CSV; run `analyze_results.py`. Vary Sa (male/female ranges), vibrato depth, drone level at finer steps, reverberation DRR. Report all conditions, including failures.
**Weeks 3–4 — real recordings.** Same laptop and microphone, fixed distance, browser audio processing off. Record ≥ 10 repetitions per condition of a sustained "aa" on Sa and Pa and a short phrase: (a) no drone, (b) a real tanpura app/shruti box at a fixed volume, (c) noise, (d) two rooms. Real ground truth is the problem: ask the singer to match a reference tone, or use an independent hardware tuner/reference recording, and say clearly where no truth exists.
**Week 5 — external baselines.** For each recording export WAV + truth + tracks, run pYIN (`--pyin`) and one more tracker via `--extra`, and score everything with `score_tracks.py`.
**Week 6 — write.** Introduction, related work (from Week 1), method, simulator description, experiments, results, limitations, reproducibility statement (versions `shruti-pitch/1.0.0`, `shruti-sim/2.0.0`, seeds, settings JSON).

## 5. Things to be careful about
* Do not tune settings on the seeds you report; keep a separate evaluation set.
* RPA counts a missing estimate as a miss, so a tracker that stays silent is penalised on accuracy but not on false alarms — always read both.
* Pooled averages depend on which conditions you chose; show the per-condition tables.
* The drone-aware mode assumes the drone is stationary and calibrated in the same room and level.
* `score_tracks.py --pyin` has not been run by me (the library could not be installed in my sandbox); everything else in the two scripts was run on real exported data.
