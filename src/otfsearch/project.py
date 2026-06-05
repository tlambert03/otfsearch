"""Pseudo-widefield and projections (pure-numpy ports; replaces Priism RunProj).

Ports legacy ``pseudoWF``, ``stackmath`` and ``maxprj`` from ``otfsearch.py``.
ImgSequence handling (0=ZTW, 1=WZT, 2=ZWT) is preserved.
"""

from __future__ import annotations

import os

import numpy as np

from . import io_mrc, settings


def pseudo_widefield(
    in_path: str,
    *,
    nangles: int = settings.NDIRS,
    nphases: int = settings.NPHASES,
    extract: int | None = None,
    out_path: str | None = None,
) -> str:
    """Average out the SIM phases to make a pseudo-widefield ``_WF.dv``."""
    im = io_mrc.imread(in_path)
    hdr = im.Mrc.hdr
    nt = int(hdr.NumTimes)
    nw = int(hdr.NumWaves)
    ny, nx = int(hdr.Num[1]), int(hdr.Num[0])
    total = int(hdr.Num[2])

    nz_f = total / (nphases * nangles * nw * nt)
    if nz_f % 1 != 0:  # OTFs etc. with nangles == 1
        nangles = 1
        nz_f = total / (nphases * nangles * nw * nt)
    nz = int(nz_f)

    seq = int(hdr.ImgSequence)
    arr = np.asarray(im)
    if seq == 0:  # ZTW
        ordered = arr.reshape(nw, nt, nangles, nz, nphases, ny, nx)
        ordered = np.transpose(ordered, (1, 2, 3, 4, 0, 5, 6))
    elif seq == 1:  # WZT
        ordered = arr.reshape(nt, nangles, nz, nphases, nw, ny, nx)
    elif seq == 2:  # ZWT
        ordered = arr.reshape(nt, nw, nangles, nz, nphases, ny, nx)
        ordered = np.transpose(ordered, (0, 2, 3, 4, 1, 5, 6))
    else:
        raise ValueError("Unknown image sequence in input file")

    avg = np.mean(ordered, 3).astype(arr.dtype)  # average phases
    # order now (nt, nangles, nz, nw, ny, nx)
    if extract:
        if extract not in range(1, nangles + 1):
            extract = 1
        avg = avg[:, extract - 1, :, :, :, :]
    else:
        avg = np.mean(avg, 1).astype(arr.dtype)  # average angles
    avg = np.squeeze(avg)
    if avg.ndim > 4:
        raise ValueError("pseudo-widefield cannot write 5-D images")

    if out_path is None:
        out_path = io_mrc.proc_output_path(in_path, "_WF")
    waves = [int(w) for w in hdr.wave if int(w) != 0]
    io_mrc.write_dv(avg, out_path, hdr, waves=waves, img_sequence=1)
    return out_path


def stackmath(in_path: str, operator: str = "max", out_path: str | None = None) -> str:
    """Project a reconstruction over Z (max/sum/std/avg); writes ``_<OP>.dv``."""
    im = io_mrc.imread(in_path)
    hdr = im.Mrc.hdr
    nt = int(hdr.NumTimes)
    nw = int(hdr.NumWaves)
    ny, nx = int(hdr.Num[1]), int(hdr.Num[0])
    total = int(hdr.Num[2])
    nz = total // (nw * nt)

    seq = int(hdr.ImgSequence)
    arr = np.asarray(im)
    if seq == 0:  # ZTW
        ordered = arr.reshape(nw, nt, nz, ny, nx)
        ordered = np.transpose(ordered, (1, 2, 0, 3, 4))
    elif seq == 1:  # WZT
        ordered = arr.reshape(nt, nz, nw, ny, nx)
    elif seq == 2:  # ZWT
        ordered = arr.reshape(nt, nw, nz, ny, nx)
        ordered = np.transpose(ordered, (0, 2, 1, 3, 4))
    else:
        raise ValueError("Unknown image sequence in input file")

    # ordered axes are now (t, z, w, y, x); project over z (axis 1)
    ops = {
        "max": np.max, "maximum": np.max,
        "sum": np.sum,
        "std": np.std, "stdev": np.std,
        "avg": np.average, "average": np.average,
    }
    if operator not in ops:
        raise ValueError("operator must be one of: max, sum, std, avg")
    proj = np.squeeze(ops[operator](ordered, 1))
    if proj.ndim > 4:
        raise ValueError("cannot write 5-D images")

    if out_path is None:
        out_path = io_mrc.proc_output_path(in_path, "_" + operator.upper())
    waves = [int(w) for w in hdr.wave if int(w) != 0]
    io_mrc.write_dv(proj, out_path, hdr, waves=waves, img_sequence=1)
    return out_path


def max_project(in_path: str, out_path: str | None = None) -> str:
    """Max-Z projection of a reconstruction -> ``_MAX.dv`` (legacy ``maxprj``)."""
    if out_path is None:
        out_path = io_mrc.proc_output_path(in_path, "_MAX")
    return stackmath(in_path, "max", out_path=out_path)
