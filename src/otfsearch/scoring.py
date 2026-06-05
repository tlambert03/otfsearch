"""Reconstruction-quality scoring (faithful port of legacy ``otfsearch.py``).

The OTF-search ranking metric is ``score = RIH * avgmodamp2`` where:

* **RIH** ("reconstructed intensity histogram", a.k.a. MMR) is a positive/negative
  intensity ratio computed from the reconstructed image (:func:`get_rih1`), and
* **avgmodamp2** is the mean of the per-angle ``Combined modamp`` values parsed
  from the cudasirecon log (:func:`parse_recon_log` + :func:`score_value`).

This module is pure numpy/scipy/skimage and is unit-testable without a GPU.
"""

from __future__ import annotations

import re

import numpy as np
from scipy import stats


# ─────────────────────────────────────────────────────────────────────────────
# RIH (positive/negative intensity ratio of the reconstruction)
# ─────────────────────────────────────────────────────────────────────────────
def calc_pos_neg_ratio(pc, bg, hist_min, hist_max, hist, n_pixels):
    """Ratio of summed positive- to negative-extreme intensities (port)."""
    hist_step = (hist_max - hist_min) / len(hist)

    # negative extreme: accumulate from the bottom until percentile reached
    neg_pc = 0.0
    neg_total = 0.0
    b = 0
    bin_value = float(hist_min)
    while neg_pc < pc and bin_value <= bg and b < len(hist):
        neg_pc += float(hist[b]) / n_pixels
        neg_total += (bin_value - bg) * hist[b]  # shift mode to 0
        b += 1
        bin_value += hist_step
    pc = neg_pc

    # positive extreme: accumulate from the top until the same percentile
    pos_pc = 0.0
    pos_total = 0.0
    b = len(hist) - 1
    bin_value = float(hist_max)
    while pos_pc < pc and b >= 0:
        pos_pc += float(hist[b]) / n_pixels
        pos_total += (bin_value - bg) * hist[b]
        b -= 1
        bin_value -= hist_step

    if neg_total == 0:
        return 0.0
    return float(abs(pos_total / neg_total))


def get_rih1(im, percentile: float = 0.0001, min_pixels: float = 100.0) -> float:
    """RIH of a single (multi-plane) reconstruction array (port of ``getRIH1``)."""
    flat = np.asarray(im).ravel()
    hist_min = flat.min()
    hist_max = flat.max()
    counts, edges = np.histogram(flat, bins=1024)
    background = edges[np.argmax(counts)]  # rough mode

    if hist_min <= background:
        total_pixels = len(flat)
        if total_pixels * percentile / 100 < min_pixels:
            percentile = min_pixels * 100 / total_pixels
        return calc_pos_neg_ratio(
            percentile / 100, background, hist_min, hist_max, counts, total_pixels
        )
    # histogram minimum above background -> cannot compute +/- ratio
    return 0.0


def get_rih(im) -> float:
    """RIH for a single-channel reconstruction ndarray."""
    return get_rih1(np.asarray(im))


# ─────────────────────────────────────────────────────────────────────────────
# SAM (sharpness/contrast metric) and CIP (raw-data quality metrics)
# ─────────────────────────────────────────────────────────────────────────────
def get_sam(im) -> float:
    """Per-plane Otsu-thresholded contrast metric (port of ``getSAM``)."""
    from skimage.filters import threshold_otsu

    im = np.asarray(im)
    slice_minima = [np.min(p) for p in im]
    slice_means = [
        np.average(p[np.where(p > threshold_otsu(p))]) for p in im
    ]
    avg_mean = np.nanmean(slice_means)
    min_std = np.std(slice_minima)
    return float(min_std / avg_mean)


def cip(im, phases: int = 5, angles: int = 3, zwin: int = 9):
    """Raw-data quality: ``(TIV, channelDecay, angleDiffs)`` (port of ``CIP``).

    * TIV          – total intensity variation across the central z-window
    * channelDecay – estimated % bleaching over depth (linear fit per angle)
    * angleDiffs   – % illumination difference between strongest/weakest angle
    """
    im = np.asarray(im)
    total = im.shape[-3]
    nz = total // (phases * angles)
    npz = nz * phases

    slice_means = list(reversed(np.mean(im.reshape(total, -1), axis=1)[::-1]))

    central_window = []
    for a in range(angles):
        z_first = (a * npz) + npz // 2 - (zwin * phases) // 2
        z_last = z_first + zwin * phases
        central_window.append(slice_means[z_first:z_last])
    # min/max over each window then combine (robust to ragged windows on small Z;
    # equivalent to legacy np.min(central_window) for real, equal-length windows)
    intens_min = min(np.min(w) for w in central_window if len(w))
    intens_max = max(np.max(w) for w in central_window if len(w))
    tiv = round(100 * (intens_max - intens_min) / intens_max, 2)

    x_slice = list(range(len(slice_means)))
    angle_decays = []
    angle_means = []
    for a in range(angles):
        nzp = nz * phases
        xa = x_slice[a * nzp:(a + 1) * nzp]
        ya = slice_means[a * nzp:(a + 1) * nzp]
        angle_means.append(np.mean(ya))
        fit = stats.linregress(xa, ya)
        angle_decays.append((fit[0] * nzp * -100.0) / fit[1])
    channel_decay = np.mean(angle_decays)
    if channel_decay < 0:
        channel_decay = 0
    channel_decay = round(channel_decay, 2)

    angle_max = np.max(angle_means)
    angle_min = np.min(angle_means)
    angle_diffs = round(100 * abs(angle_max - angle_min) / angle_max, 2)
    return tiv, channel_decay, angle_diffs


# ─────────────────────────────────────────────────────────────────────────────
# cudasirecon log parsing + the final score
# ─────────────────────────────────────────────────────────────────────────────
_NUM_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


def _lead_float(s: str) -> float:
    """Parse the first number in ``s`` (ignoring trailing units like ``%``)."""
    m = _NUM_RE.search(s)
    return float(m.group()) if m else 0.0


def parse_recon_log(log: str) -> dict:
    """Extract modamps / correlations / k0 fit values from the cudasirecon log."""
    lines = log.split("\n")
    modamps = [
        float(line.split("amp=")[1].split(",")[0])
        for line in lines
        if "Combined modamp" in line
    ]
    correls = [
        _lead_float(line.split(": ", 1)[1])
        for line in lines
        if "Correlation coefficient" in line
    ]
    spacings = [_lead_float(s) for s in log.split("spacing=")[1:]]
    angles = [_lead_float(s) for s in log.split("Optimum k0 angle=")[1:]]
    lengths = [_lead_float(s) for s in log.split("length=")[1:]]
    fit_deltas = [_lead_float(s) for s in log.split("best fit for k0 is ")[1:]]
    warnings = [line for line in lines if "WARNING" in line]
    wiener = ""
    if "wiener=" in log:
        wiener = log.split("wiener=")[1][:5]
    return {
        "modamp2": modamps[0:6:2],
        "modamp1": modamps[1:6:2],
        "avgmodamp": float(np.average(modamps)) if modamps else 0.0,
        "avgmodamp1": float(np.average(modamps[1:6:2])) if modamps else 0.0,
        "avgmodamp2": float(np.average(modamps[0:6:2])) if modamps else 0.0,
        "correl2": correls[0:6:2],
        "correl1": correls[1:6:2],
        "avgcorrel": float(np.average(correls)) if correls else 0.0,
        "avgcorrel1": float(np.average(correls[1:6:2])) if correls else 0.0,
        "avgcorrel2": float(np.average(correls[0:6:2])) if correls else 0.0,
        "spacings": spacings,
        "angles": angles,
        "lengths": lengths,
        "fitDeltas": fit_deltas,
        "warnings": warnings,
        "wiener": wiener,
    }


def score_value(rih: float, avgmodamp2: float) -> float:
    """The ranking metric: ``RIH * avgmodamp2`` (legacy ``score``)."""
    return float(rih) * float(avgmodamp2)


def best_otfs(score_dicts: list[dict], channels=None, report: int = 10,
              verbose: bool = True) -> dict:
    """Pick the highest-scoring OTF per channel (port of ``getBestOTFs``)."""
    results: dict[str, str] = {}
    if channels is None:
        channels = list({s["imChannel"] for s in score_dicts})
    for c in channels:
        ranked = sorted(
            (s for s in score_dicts if s["imChannel"] == c),
            key=lambda x: x["score"], reverse=True,
        )
        if not ranked:
            continue
        results[str(c)] = ranked[0]["OTFpath"]
        if verbose:
            print(f"Channel {c}:")
            print("{:<23} {:<6} {:<5} {:<7}".format("OTFcode", "Score", "RIH", "modamp"))
            for s in ranked[:report]:
                print("{:<23} {:<05.3}  {:<04.3}  {:<05.3}".format(
                    s["OTFcode"], s["score"], s["RIH"], s["avgmodamp2"]))
    return results
