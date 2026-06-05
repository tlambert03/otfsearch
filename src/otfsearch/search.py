"""Optimized reconstruction: score every matching OTF, pick the best per channel.

Faithful port of legacy ``scoreOTFs`` / ``getBestOTFs`` / ``makeBestReconstruction``,
but in-memory (no Priism temp dir / symlinks) and using the persistent
:class:`~otfsearch.recon_worker.ReconWorker`.
"""

from __future__ import annotations

import os
from typing import Callable

import numpy as np

from . import io_mrc, otfmatch, params, scoring, settings
from .recon_worker import ReconWorker
from .reconstruct import postprocess, reconstruct_file


def _log(on_log: Callable[[str], None] | None, msg: str) -> None:
    (on_log or print)(msg)


def score_otfs(
    in_path: str,
    *,
    cropsize: int = settings.CROPSIZE,
    otf_dir: str | None = None,
    recon_waves: list[int] | None = None,
    force_channels: dict[int, int] | None = None,
    oil_min: int = settings.OIL_MIN,
    oil_max: int = settings.OIL_MAX,
    max_age: int | None = settings.MAX_AGE,
    max_num: int | None = settings.MAX_NUM,
    worker: ReconWorker | None = None,
    on_log: Callable[[str], None] | None = None,
) -> list[dict]:
    """Reconstruct ``in_path`` with every matching OTF; return per-recon score dicts."""
    otf_dir = otf_dir or settings.OTF_DIR
    im = io_mrc.imread(in_path)
    hdr = im.Mrc.hdr
    dz, _dy, dxy = io_mrc.voxel_size(hdr)
    num_times = int(hdr.NumTimes)
    in_ctime = os.path.getctime(in_path)

    channels = io_mrc.split_channels(im, hdr)
    if recon_waves:
        channels = [(a, w) for (a, w) in channels if w in recon_waves]

    otf_dict = otfmatch.build_otf_dict(otf_dir)

    own_worker = worker is None
    worker = worker or ReconWorker()
    all_scores: list[dict] = []
    try:
        for arr, im_channel in channels:
            # clip to first timepoint + central crop (for speed)
            arr = io_mrc.take_first_timepoints(arr, num_times, 1)
            arr = io_mrc.crop_center_xy(arr, cropsize)

            tiv, channel_decay, angle_diffs = scoring.cip(arr)
            _log(on_log, f"Channel {im_channel}: bleaching {channel_decay}%, "
                         f"angle var {angle_diffs}%, TIV {tiv}%")
            if channel_decay > 30:
                _log(on_log, f"WARNING: channel {im_channel} bleaching {channel_decay}%")
            if angle_diffs > 20:
                _log(on_log, f"WARNING: channel {im_channel} angle diff {angle_diffs}%")

            file_info = {
                "input": in_path,
                "TIV": tiv,
                "channelDecay": channel_decay,
                "angleDiffs": angle_diffs,
                "imChannel": im_channel,
                "input-ctime": in_ctime,
            }

            otf_wave = im_channel
            if force_channels and im_channel in force_channels:
                otf_wave = force_channels[im_channel]
            candidates = otfmatch.matching_otfs(
                otf_dict, otf_wave, oil_min, oil_max, max_age=max_age, max_num=max_num
            )
            if not candidates:
                _log(on_log, f"No matching OTFs for channel {im_channel} "
                             f"(otf wave {otf_wave}) in {otf_dir}")
            p = params.recon_params_for_wave(im_channel, xyres=dxy, zres=dz)
            for otf in candidates:
                result, log = worker.reconstruct(arr, otf["path"], **p)
                parsed = scoring.parse_recon_log(log)
                try:
                    rih = round(scoring.get_rih(result), 3)
                except Exception:  # noqa: BLE001
                    rih = 0.1
                try:
                    sam = round(scoring.get_sam(result), 3)
                except Exception:  # noqa: BLE001
                    sam = 0.1
                score = {
                    "OTFcode": otf["code"],
                    "OTFoil": otf["oil"],
                    "OTFangle": otf["angle"][1:] if otf.get("angle") else "",
                    "OTFbead": otf.get("beadnum"),
                    "OTFdate": otf.get("date"),
                    "OTFwave": otf.get("wavelength"),
                    "OTFpath": otf["path"],
                    "RIH": rih,
                    "SAM": sam,
                    **parsed,
                    **file_info,
                }
                score["score"] = scoring.score_value(rih, parsed["avgmodamp2"])
                all_scores.append(score)
                _log(on_log, f"{otf['code']}: modamp "
                             f"{parsed['avgmodamp2']:0.3f}  RIH {rih:0.2f}  "
                             f"score {score['score']:0.3f}")
        return all_scores
    finally:
        if own_worker:
            worker.close()


def make_best_reconstruction(
    in_path: str,
    *,
    cropsize: int = settings.CROPSIZE,
    otf_dir: str | None = None,
    recon_waves: list[int] | None = None,
    force_channels: dict[int, int] | None = None,
    oil_min: int = settings.OIL_MIN,
    oil_max: int = settings.OIL_MAX,
    max_age: int | None = settings.MAX_AGE,
    max_num: int | None = settings.MAX_NUM,
    wiener: float | None = None,
    do_reg: bool = settings.DO_REG,
    do_max: bool = settings.DO_MAX,
    reg_file: str | None = None,
    ref_channel: int = settings.REF_CHANNEL,
    reg_mode: str = settings.REG_MODE,
    write_csv: bool = True,
    append_master: bool = True,
    worker: ReconWorker | None = None,
    on_log: Callable[[str], None] | None = None,
) -> dict:
    """Full optimized reconstruction. Returns a dict of best OTFs + output paths."""
    own_worker = worker is None
    worker = worker or ReconWorker()
    try:
        all_scores = score_otfs(
            in_path, cropsize=cropsize, otf_dir=otf_dir, recon_waves=recon_waves,
            force_channels=force_channels, oil_min=oil_min, oil_max=oil_max,
            max_age=max_age, max_num=max_num, worker=worker, on_log=on_log,
        )
        best = scoring.best_otfs(all_scores)
        if not best:
            raise RuntimeError("OTF search produced no scored reconstructions")

        _log(on_log, "Reconstructing final file with best OTFs ...")
        proc_path, log_path = reconstruct_file(
            in_path, best, recon_waves=recon_waves, wiener=wiener,
            worker=worker, on_log=on_log,
        )

        registered, max_proj = postprocess(
            proc_path, do_reg=do_reg, do_max=do_max, reg_file=reg_file,
            ref_channel=ref_channel, reg_mode=reg_mode, on_log=on_log,
        )

        score_csv = None
        if write_csv:
            from . import csvlog
            score_csv = csvlog.write_scores_csv(all_scores, in_path)
            if append_master and settings.MASTER_SCORE_CSV:
                csvlog.append_master(all_scores)

        return {
            "best_otfs": best,
            "reconstruction": proc_path,
            "log": log_path,
            "registered": registered,
            "max": max_proj,
            "scores_csv": score_csv,
        }
    finally:
        if own_worker:
            worker.close()
