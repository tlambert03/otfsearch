"""Multi-channel reconstruction: split -> recon per channel -> merge -> _PROC.dv.

Replaces the legacy ``reconstructMulti`` (and the Priism split/merge it used).
This is the "Specify OTFs" daily-use path; the OTF search (search.py) reuses
:func:`reconstruct_channels` for its final best-OTF reconstruction.
"""

from __future__ import annotations

import os
from typing import Callable

import numpy as np

from . import io_mrc, params, settings
from .recon_worker import ReconWorker

OtfFor = "dict | Callable[[int], str]"


def resolve_otf(otf_for, wave: int) -> str:
    """Resolve the OTF path for ``wave`` from a dict / callable / OTF_DIR fallback."""
    if callable(otf_for):
        return otf_for(wave)
    if isinstance(otf_for, dict):
        for key in (wave, str(wave)):
            if key in otf_for:
                return otf_for[key]
    cand = os.path.join(settings.OTF_DIR, f"{wave}.otf")
    if settings.OTF_DIR and os.path.exists(cand):
        return cand
    raise KeyError(f"No OTF provided (and no default found) for channel {wave}")


def reconstruct_channels(
    channels: list[tuple[np.ndarray, int]],
    otf_for,
    *,
    dxy: float,
    dz: float,
    wiener: float | None = None,
    background: float | None = None,
    worker: ReconWorker | None = None,
    on_log: Callable[[str], None] | None = None,
    **param_overrides,
) -> list[dict]:
    """Reconstruct each ``(array, wave)`` channel; return per-channel result dicts.

    Each dict has keys ``wave``, ``otf``, ``result`` (ndarray), ``log`` (str).
    """
    own_worker = worker is None
    worker = worker or ReconWorker()
    try:
        out: list[dict] = []
        for arr, wave in channels:
            otf = resolve_otf(otf_for, wave)
            p = params.recon_params_for_wave(
                wave, xyres=dxy, zres=dz, wiener=wiener,
                background=background, **param_overrides,
            )
            if on_log is not None:
                on_log(f"Reconstructing channel {wave} with {os.path.basename(otf)} ...")
            result, log = worker.reconstruct(arr, otf, on_log=on_log, **p)
            out.append({"wave": wave, "otf": otf, "result": result, "log": log})
        return out
    finally:
        if own_worker:
            worker.close()


def reconstruct_file(
    in_path: str,
    otf_for,
    *,
    out_path: str | None = None,
    recon_waves: list[int] | None = None,
    wiener: float | None = None,
    background: float | None = None,
    timepoints: int | None = None,
    worker: ReconWorker | None = None,
    write_log: bool = True,
    on_log: Callable[[str], None] | None = None,
    **param_overrides,
) -> tuple[str, str | None]:
    """Reconstruct a raw SIM ``.dv`` and write ``_PROC.dv`` (+ ``_LOG.txt``).

    Returns ``(proc_path, log_path)``.  ``otf_for`` is a ``{wave: otf_path}`` dict
    (int or str keys), a callable ``wave -> path``, or ``None`` (OTF_DIR fallback).
    """
    if out_path is None:
        out_path = io_mrc.proc_output_path(in_path)

    im = io_mrc.imread(in_path)
    hdr = im.Mrc.hdr
    dz, _dy, dxy = io_mrc.voxel_size(hdr)
    num_times = int(hdr.NumTimes)

    channels = io_mrc.split_channels(im, hdr)
    if recon_waves:
        channels = [(a, w) for (a, w) in channels if w in recon_waves]
    if timepoints:
        channels = [
            (io_mrc.take_first_timepoints(a, num_times, timepoints), w)
            for (a, w) in channels
        ]

    results = reconstruct_channels(
        channels, otf_for, dxy=dxy, dz=dz, wiener=wiener, background=background,
        worker=worker, on_log=on_log, **param_overrides,
    )

    merged = [(r["result"], r["wave"]) for r in results]
    io_mrc.merge_channels(
        merged, out_path, hdr, dxy=dxy / settings.ZOOMFACT, dz=dz,
    )

    log_path = None
    if write_log:
        log_path = os.path.splitext(out_path)[0] + "_LOG.txt"
        _write_recon_log(log_path, in_path, results)
    return out_path, log_path


def postprocess(
    proc_path: str,
    *,
    do_reg: bool = False,
    do_max: bool = False,
    reg_file: str | None = None,
    ref_channel: int = settings.REF_CHANNEL,
    reg_mode: str = settings.REG_MODE,
    on_log: Callable[[str], None] | None = None,
) -> tuple[str | None, str | None]:
    """Optional registration / max-projection of a reconstruction.

    Returns ``(registered_path, max_proj_path)`` (either may be ``None``).
    Registration only runs on multi-channel files (matches legacy behaviour).
    """
    registered = max_proj = None
    num_waves = int(io_mrc.read_header(proc_path).NumWaves)
    if do_reg and num_waves > 1:
        from . import registration
        if on_log:
            on_log("Applying channel registration ...")
        registered, max_proj = registration.apply_registration(
            proc_path, reg_file=reg_file, ref_channel=ref_channel,
            do_max=do_max, mode=reg_mode,
        )
    elif do_max:
        from . import project
        max_proj = project.max_project(proc_path)
    return registered, max_proj


def _write_recon_log(log_path: str, in_path: str, results: list[dict]) -> None:
    """Write the per-channel reconstruction log (mirrors legacy ``_LOG.txt``)."""
    try:
        from . import scoring
    except Exception:  # noqa: BLE001
        scoring = None
    with open(log_path, "w") as f:
        f.write(f"INPUT FILE: {in_path} \n\n")
        for r in results:
            f.write("#" * 80 + "\n\n")
            f.write(f"WAVELENGTH: {r['wave']} \n")
            f.write(f"OTF: {r['otf']} \n")
            rih = 0.1
            if scoring is not None:
                try:
                    rih = scoring.get_rih(r["result"])
                    if isinstance(rih, (list, tuple)):
                        rih = float(np.mean(rih))
                except Exception:  # noqa: BLE001
                    rih = 0.1
            f.write(f"RECONSTRUCTION SCORE (RIH): {rih:0.2f} \n\n")
            f.write("RECONSTRUCTION LOG: \n")
            f.write(r["log"])
            f.write("\n")
