"""Channel registration via fiducialreg (replaces the old MATLAB omxreg pipeline).

Two operations, mirroring the legacy workflow:

* :func:`calibrate` — measure transforms from a multi-channel bead/grid image and
  save a ``.json`` registration file (was MATLAB ``omxregcal`` -> ``.mat``).
* :func:`apply_registration` — align a multi-channel reconstruction to a reference
  channel, writing ``{stem}-REGto{ref}.dv`` (was MATLAB ``omxreg``).

Fidelity note: fiducialreg is a *different algorithm* than the old MATLAB code, so
transforms are not numerically identical and old ``.mat`` files cannot be reused.
"""

from __future__ import annotations

import datetime
import os

import numpy as np

from . import io_mrc, settings


def _regfile_name(out_dir: str, waves: list[int], date: str | None = None) -> str:
    date = date or datetime.date.today().strftime("%y%m%d")
    wavestr = "-".join(str(w) for w in waves)
    return os.path.join(out_dir, f"OMXreg_{date}_waves{wavestr}_grid.json")


def calibrate(
    calib_path: str,
    *,
    out_dir: str | None = None,
    refs: list[int] | None = None,
    modes: tuple[str, ...] = ("translation", "rigid", "similarity", "affine", "2step"),
    date: str | None = None,
) -> str:
    """Compute registration transforms from a calibration image; save a ``.json``.

    ``refs=None`` registers all-to-all (legacy "all"); ``refs=[ref]`` references
    everything to ``ref`` (legacy ``--refs``).  Returns the saved file path.
    """
    from fiducialreg import CloudSet

    out_dir = out_dir or settings.REGFILE_DIR
    im = io_mrc.imread(calib_path)
    hdr = im.Mrc.hdr
    dz, _dy, dx = io_mrc.voxel_size(hdr)
    channels = io_mrc.split_channels(im, hdr)
    data = [arr for arr, _ in channels]
    labels = [int(w) for _, w in channels]

    cs = CloudSet(data=data, labels=labels, dx=dx, dz=dz)
    out = _regfile_name(out_dir, labels, date)
    cs.write_all_tforms(out, refs=refs, modes=modes)
    return out


def pick_reg_file(in_path: str, directory: str | None = None) -> str | None:
    """Newest ``.json`` reg file whose wavelengths cover the image's channels."""
    directory = directory or settings.REGFILE_DIR
    files = [f for f in os.listdir(directory) if f.endswith(".json")]
    files.sort(key=lambda x: x.split("_")[1], reverse=True)  # newest date first
    im_waves = set(io_mrc._hdr_waves(io_mrc.read_header(in_path)))
    for f in files:
        try:
            file_waves = {int(w) for w in f.split("waves")[1].split("_")[0].split("-")}
        except (IndexError, ValueError):
            continue
        if im_waves.issubset(file_waves):
            return os.path.join(directory, f)
    return None


def apply_registration(
    in_path: str,
    *,
    reg_file: str | None = None,
    ref_channel: int = settings.REF_CHANNEL,
    do_max: bool = False,
    mode: str = settings.REG_MODE,
    out_path: str | None = None,
) -> tuple[str, str | None]:
    """Align a multi-channel reconstruction to ``ref_channel``.

    Returns ``(registered_path, max_proj_path_or_None)``.
    """
    from fiducialreg import RegFile, register_image_to_wave

    if reg_file is None:
        reg_file = pick_reg_file(in_path)
        if not reg_file:
            raise FileNotFoundError(
                f"No registration file found in {settings.REGFILE_DIR} for {in_path}"
            )
    rf = RegFile(reg_file)

    im = io_mrc.imread(in_path)
    hdr = im.Mrc.hdr
    dz, dy, dx = io_mrc.voxel_size(hdr)
    channels = io_mrc.split_channels(im, hdr)

    registered: list[tuple[np.ndarray, int]] = []
    for arr, wave in channels:
        if wave == ref_channel:
            registered.append((np.asarray(arr), wave))
        else:
            out_arr = register_image_to_wave(
                np.asarray(arr), rf, imwave=wave, refwave=ref_channel,
                voxsize=[dz, dy, dx], mode=mode,
            )
            registered.append((np.asarray(out_arr), wave))

    if out_path is None:
        out_path = os.path.splitext(in_path)[0] + f"-REGto{ref_channel}.dv"
    io_mrc.merge_channels(registered, out_path, hdr, dxy=dx, dz=dz)

    max_proj = None
    if do_max:
        from . import project

        max_path = os.path.splitext(in_path)[0] + f"-REGto{ref_channel}-MAX.dv"
        max_proj = project.max_project(out_path, out_path=max_path)
    return out_path, max_proj
