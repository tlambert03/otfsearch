"""DeltaVision/MRC (.dv) I/O built on the ``mrc`` package + numpy.

This module replaces *all* of the old Priism image operations
(``CopyRegion`` split/crop, ``mergemrc`` merge, ``RunProj`` projection) and the
bundled Python-2 ``Mrc.py``.  The canonical read/split/merge/write pattern is
taken from ``cudasirecon/recon.py`` (same author).

NOTE (verify on real data): a handful of header field accesses are centralized
in the small ``_hdr_*`` helpers below.  If the installed ``mrc`` package names a
field differently, fix it in one place here.
"""

from __future__ import annotations

import os
from typing import Any

import numpy as np


def _mrc():
    """Import the ``mrc`` package lazily (so pure helpers import without it)."""
    try:
        import mrc
    except ImportError as e:  # pragma: no cover - import guard
        raise ImportError(
            "The 'mrc' package is required to read/write .dv files. "
            "Install it with `pip install mrc`."
        ) from e
    return mrc


# ─────────────────────────────────────────────────────────────────────────────
# header access (centralized so the mrc-API touchpoints live in one place)
# ─────────────────────────────────────────────────────────────────────────────
def read_header(path: str) -> Any:
    """Return the MRC header object for ``path`` (header only, no data read)."""
    m = _mrc().open(path)
    try:
        return m.hdr
    finally:
        m.close()


def _hdr_num_waves(hdr: Any) -> int:
    return int(hdr.NumWaves)


def _hdr_num_times(hdr: Any) -> int:
    return int(hdr.NumTimes)


def _hdr_total_planes(hdr: Any) -> int:
    # hdr.Num is (nx, ny, nz_total) where nz_total spans waves*times*angles*phases*z
    return int(hdr.Num[2])


def _hdr_waves(hdr: Any) -> list[int]:
    """Emission wavelengths present (zeros stripped)."""
    return [int(w) for w in hdr.wave if int(w) != 0]


def _hdr_img_sequence(hdr: Any) -> int:
    # 0 = ZTW, 1 = WZT, 2 = ZWT
    return int(hdr.ImgSequence)


def voxel_size(hdr: Any) -> tuple[float, float, float]:
    """Return ``(dz, dy, dx)`` voxel size in microns.

    NOTE (verify): the Priism/``mrc`` header stores per-axis sampling in
    ``hdr.d`` ordered ``(dx, dy, dz)``.
    """
    dx, dy, dz = (float(v) for v in hdr.d)
    return dz, dy, dx


# ─────────────────────────────────────────────────────────────────────────────
# reading
# ─────────────────────────────────────────────────────────────────────────────
def imread(path: str) -> np.ndarray:
    """Read a .dv/MRC file into an ndarray with ``.Mrc`` metadata attached.

    Uses ``mrc.bindFile`` (not ``mrc.imread``) because the latter returns a plain
    ndarray with no header handle.  NOTE: this is memory-mapped and holds an open
    file handle (which blocks overwrite/delete on Windows) — use
    :func:`read_array` when you only need the data and want the handle released.
    """
    return _mrc().bindFile(path)


def read_array(path: str) -> np.ndarray:
    """Read a .dv/MRC file into an in-memory float32 array, releasing the handle.

    Avoids the Windows file-locking that ``imread``'s memory-map causes, so the
    source file (e.g. a temp reconstruction) can be deleted/overwritten afterward.
    """
    im = _mrc().bindFile(path)
    arr = np.array(im, dtype=np.float32, copy=True)
    try:
        im.Mrc.close()
    except Exception:  # noqa: BLE001
        pass
    del im
    return arr


def split_channels(im: np.ndarray, hdr: Any) -> list[tuple[np.ndarray, int]]:
    """Split a (possibly multi-channel) raw stack into ``[(array3d, wave), ...]``.

    Mirrors ``cudasirecon/recon.py``: the channel axis is the 3rd-to-last
    dimension, so a single channel is ``np.take(im, c, -3)`` giving a 3-D
    ``(angles*phases*z, y, x)`` stack — exactly what cudasirecon expects.

    NOTE (verify on multi-channel data): this assumes the file's ImgSequence
    places the wavelength axis at -3.  If channels come out interleaved, the
    de-interleave must follow ``hdr.ImgSequence`` (0=ZTW, 1=WZT, 2=ZWT).
    """
    arr = np.asarray(im)
    waves = _hdr_waves(hdr)
    nw = _hdr_num_waves(hdr)
    if nw <= 1:
        return [(np.ascontiguousarray(arr), waves[0])]
    # Find the channel axis robustly: the axis whose size == NumWaves.  Prefer the
    # 3rd-to-last axis (raw Z-major files, the cudasirecon/recon.py convention);
    # fall back to the first matching axis (e.g. W-major ``_PROC.dv`` outputs).
    if arr.shape[-3] == nw:
        wave_axis = arr.ndim - 3
    else:
        matches = [ax for ax, s in enumerate(arr.shape) if s == nw]
        if not matches:
            raise ValueError(
                f"No axis matches NumWaves={nw} in array shape {arr.shape}"
            )
        wave_axis = matches[0]
    return [
        (np.ascontiguousarray(np.take(arr, c, wave_axis)), int(hdr.wave[c]))
        for c in range(nw)
    ]


# ─────────────────────────────────────────────────────────────────────────────
# writing
# ─────────────────────────────────────────────────────────────────────────────
def write_dv(
    array: np.ndarray,
    out_path: str,
    src_hdr: Any,
    *,
    waves: list[int],
    dxy: float | None = None,
    dz: float | None = None,
    img_sequence: int | None = None,
) -> str:
    """Write ``array`` to ``out_path`` as a .dv, copying metadata from ``src_hdr``.

    ``waves`` are the per-channel emission wavelengths (channel axis = -3 when
    ``len(waves) > 1``).  ``dxy``/``dz`` override the voxel size (the
    reconstruction zooms XY, so callers should pass ``input_dxy / ZOOMFACT``).
    ``img_sequence`` overrides the header's ImgSequence (e.g. 1 = WZT for
    projections / pseudo-widefield outputs).
    """
    mrc = _mrc()
    array = np.ascontiguousarray(array, dtype=np.float32)
    m = mrc.Mrc2(out_path, mode="w")
    m.initHdrForArr(array)
    mrc.copyHdrInfo(m.hdr, src_hdr)
    m.hdr.NumWaves = len(waves)
    m.hdr.wave = (list(waves) + [0, 0, 0, 0, 0])[:5]
    if img_sequence is not None:
        m.hdr.ImgSequence = img_sequence
    if dxy is not None or dz is not None:
        odx, ody, odz = (dxy, dxy, dz)
        cur = list(m.hdr.d)
        if odx is not None:
            cur[0] = odx
        if ody is not None:
            cur[1] = ody
        if odz is not None:
            cur[2] = odz
        m.hdr.d = tuple(cur)
    m.writeHeader()
    m.writeStack(array)
    m.close()
    return out_path


def merge_channels(
    results: list[tuple[np.ndarray, int]],
    out_path: str,
    src_hdr: Any,
    *,
    dxy: float | None = None,
    dz: float | None = None,
) -> str:
    """Stack per-channel results ``[(array3d, wave), ...]`` into a multi-channel .dv.

    NOTE (verify on multi-channel output): the channel axis is placed at -3
    (``z, wave, y, x``), matching ``cudasirecon/recon.py``.  The written header's
    ImgSequence is copied from ``src_hdr``; confirm a viewer interprets the
    channel order correctly, and set ``img_sequence`` here if not.
    """
    if len(results) == 1:
        array, wave = results[0]
        return write_dv(array, out_path, src_hdr, waves=[wave], dxy=dxy, dz=dz)
    arrays = [r[0] for r in results]
    waves = [r[1] for r in results]
    stacked = np.stack(arrays, -3)  # (z, wave, y, x)
    return write_dv(stacked, out_path, src_hdr, waves=waves, dxy=dxy, dz=dz)


# ─────────────────────────────────────────────────────────────────────────────
# cropping (numpy replacements for Priism CopyRegion)
# ─────────────────────────────────────────────────────────────────────────────
def crop_center_xy(array: np.ndarray, cropsize: int) -> np.ndarray:
    """Central crop the last two (Y, X) axes to ``cropsize`` x ``cropsize``."""
    ny, nx = array.shape[-2], array.shape[-1]
    if ny <= cropsize and nx <= cropsize:
        return array
    y0 = max(0, (ny // 2) - (cropsize // 2))
    x0 = max(0, (nx // 2) - (cropsize // 2))
    return np.ascontiguousarray(
        array[..., y0 : y0 + cropsize, x0 : x0 + cropsize]
    )


def write_simple_dv(
    array: np.ndarray,
    out_path: str,
    *,
    dxy: float,
    dz: float,
    wave: int = 0,
    img_sequence: int = 0,
) -> str:
    """Write a single-channel ``.dv`` from a bare array (no source header needed).

    Used to hand cudasirecon a temp input with the correct voxel size (the engine
    reads pixel size from the MRC header).
    """
    mrc = _mrc()
    array = np.ascontiguousarray(array, dtype=np.float32)
    m = mrc.Mrc2(out_path, mode="w")
    m.initHdrForArr(array)
    m.hdr.NumWaves = 1
    m.hdr.wave = [int(wave), 0, 0, 0, 0]
    m.hdr.d = (dxy, dxy, dz)
    m.hdr.ImgSequence = img_sequence
    m.writeHeader()
    m.writeStack(array)
    m.close()
    return out_path


def take_first_timepoints(chan: np.ndarray, num_times: int, n: int | None) -> np.ndarray:
    """Keep the first ``n`` timepoints of a per-channel stack.

    ``chan`` is a single channel's ``(time*angles*phases*z, y, x)`` stack.

    NOTE (verify): assumes time is the outermost factor of the leading axis
    (true for OMX/DV fast-SI raw data, matching the legacy Priism ``-t=`` crop).
    """
    if num_times <= 1 or not n or n >= num_times:
        return chan
    per = chan.shape[0] // num_times
    return np.ascontiguousarray(chan[: per * n])


def proc_output_path(in_path: str, suffix: str = "_PROC") -> str:
    """``/a/b/file.dv`` -> ``/a/b/file_PROC.dv`` (matches legacy naming)."""
    stem, ext = os.path.splitext(in_path)
    return stem + suffix + ext
