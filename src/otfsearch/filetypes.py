"""Raw-SIM / reconstruction file detection (ported from legacy ``otfsearch.py``)."""

from __future__ import annotations

import os

from . import io_mrc

_PROCESSED_MARKERS = ("_SIR", "_PROC", "_WF")


def is_raw_sim_file(path: str) -> bool:
    """True if ``path`` looks like an unprocessed raw SIM ``.dv``.

    Same rules as the legacy ``isRawSIMfile``: a ``.dv`` whose name has no
    processed-marker, and whose per-(time, wave) plane count is a multiple of 15
    (3 angles x 5 phases).
    """
    if os.path.splitext(path)[1] != ".dv":
        return False
    base = os.path.basename(path)
    if any(marker in base for marker in _PROCESSED_MARKERS):
        return False
    try:
        hdr = io_mrc.read_header(path)
        num_waves = int(hdr.NumWaves)
        num_times = int(hdr.NumTimes)
        total_planes = int(hdr.Num[2])
        planes_per = total_planes // (num_times * num_waves)
        return planes_per % 15 == 0
    except Exception as e:  # noqa: BLE001 - mirror legacy tolerance
        print(f"Error reading header in: {path} ({e})")
        return False


def is_already_processed(path: str) -> bool:
    """True if a ``_PROC.dv`` or ``_SIR.dv`` already exists for ``path``."""
    if path.endswith(".dv"):
        if os.path.exists(path.replace(".dv", "_PROC.dv")):
            return True
        if os.path.exists(path.replace(".dv", "_SIR.dv")):
            return True
    return False


def is_a_reconstruction(path: str) -> bool:
    """True if ``path`` is a reconstruction output (``*PROC.dv`` / ``*PROC_MAX.dv``)."""
    return path.endswith("PROC.dv") or path.endswith("PROC_MAX.dv")
