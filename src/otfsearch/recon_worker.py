"""Reconstruction engine: drive the ``cudasirecon`` CLI natively on MRC ``.dv``.

This targets the MRC-capable ``cudasirecon`` build (the ``talley`` conda channel),
which reads and writes DeltaVision ``.dv``/``.otf`` directly — exactly like the
legacy pipeline.  For each channel we:

  1. write the (split/cropped) channel array to a temp single-channel ``.dv``
     (with the correct voxel size — the engine reads pixel size from the header),
  2. run ``cudasirecon <in.dv> <out.dv> <otf> -c <config>`` (the OTF library's MRC
     ``.otf`` files are passed straight through, no conversion),
  3. read back the output ``.dv`` and parse stdout for the per-angle
     ``Combined modamp is: amp=...`` lines used by the OTF search.

Keeping everything MRC-native means no TIFF round-trip, no complex→float OTF
conversion, and no Y-flip/angle-orientation handling.

NOTE: reading the engine's ``.dv`` output back via ``mrc`` requires NumPy < 2 (the
``mrc`` package still calls ``ndarray.newbyteorder``); this is pinned in
``pyproject.toml``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from typing import Callable

import numpy as np

from . import io_mrc

# cudasirecon config keys for MRC mode.  Pixel sizes (xyres/zres/zresPSF) are read
# from the .dv header, and cropping is done in numpy, so those are intentionally
# excluded here.
_CONFIG_KEYS = {
    "ndirs", "nphases", "na", "nimm", "ls", "k0angles", "wiener", "background",
    "otfRA", "dampenOrder0", "fastSI", "zoomfact", "zzoom", "nordersout",
    "explodefact", "gammaApo", "nosuppress", "nokz0", "equalizez", "equalizet",
}


def find_cudasirecon(exe: str | None = None) -> str:
    """Locate the ``cudasirecon`` executable (or raise a helpful error)."""
    found = exe or shutil.which("cudasirecon")
    if not found:
        raise RuntimeError(
            "The 'cudasirecon' executable was not found on PATH.\n"
            "Install the MRC-capable build with: "
            "conda install -c talley -c conda-forge cudasirecon"
        )
    return found


def params_to_config(params: dict) -> str:
    """Render a recon-params dict as a cudasirecon config file string."""
    lines = []
    for key, val in params.items():
        if key not in _CONFIG_KEYS:
            continue
        if isinstance(val, bool):
            val = 1 if val else 0
        elif isinstance(val, (tuple, list)):
            val = ",".join(str(x) for x in val)
        lines.append(f"{key}={val}")
    return "\n".join(lines) + "\n"


def _resolve_otf_path(otf, tmpdir: str, dxy: float, dz: float) -> str:
    """Return an OTF path the engine can read (MRC ``.otf``/``.dv`` pass through)."""
    if isinstance(otf, np.ndarray):
        path = os.path.join(tmpdir, "otf.dv")
        io_mrc.write_simple_dv(otf, path, dxy=dxy, dz=dz)
        return path
    return str(otf)


def reconstruct_cli(
    array: np.ndarray,
    otf,
    *,
    exe: str | None = None,
    on_log: Callable[[str], None] | None = None,
    **params,
) -> tuple[np.ndarray, str]:
    """Reconstruct one channel via the cudasirecon CLI; return ``(result, log)``."""
    xyres = float(params.pop("xyres", 0.08))
    zres = float(params.pop("zres", 0.125))
    wave = int(params.pop("wavelength", 0))
    params.pop("zresPSF", None)  # OTF is precomputed; engine reads dz from header
    params.pop("cropXY", None)   # cropping is done in numpy

    exe = find_cudasirecon(exe)
    tmp = tempfile.mkdtemp(prefix="otfsearch_recon_")
    try:
        in_dv = os.path.join(tmp, "raw.dv")
        out_dv = os.path.join(tmp, "raw_proc.dv")
        io_mrc.write_simple_dv(array, in_dv, dxy=xyres, dz=zres, wave=wave)
        otf_path = _resolve_otf_path(otf, tmp, xyres, zres)
        cfg = os.path.join(tmp, "config.txt")
        with open(cfg, "w") as f:
            f.write(params_to_config(params))

        cmd = [exe, in_dv, out_dv, otf_path, "-c", cfg]
        if on_log is None:
            proc = subprocess.run(cmd, capture_output=True, text=True)
            log = (proc.stdout or "") + (proc.stderr or "")
        else:
            log = _run_streaming(cmd, on_log)

        if not os.path.exists(out_dv):
            raise RuntimeError("cudasirecon produced no output:\n" + log[-2000:])
        # read into memory + release the handle so the temp dir can be removed
        result = io_mrc.read_array(out_dv)
        return result, log
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _run_streaming(cmd: list[str], on_log: Callable[[str], None]) -> str:
    """Run ``cmd``, streaming combined stdout/stderr to ``on_log``; return full log."""
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )
    lines: list[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        lines.append(line)
        on_log(line.rstrip("\n"))
    proc.wait()
    return "".join(lines)


class ReconWorker:
    """Reconstruction handle with a stable interface for the rest of the package.

    Each :meth:`reconstruct` call launches the cudasirecon CLI. ``start``/``close``
    are no-ops (kept so callers can reuse one worker across a batch/search).
    """

    def __init__(self, exe: str | None = None):
        self._exe = exe

    def start(self) -> None:  # noqa: D401 - interface compatibility
        pass

    def close(self) -> None:
        pass

    def __enter__(self) -> "ReconWorker":
        return self

    def __exit__(self, *exc) -> None:
        pass

    def reconstruct(self, array, otf, *, on_log=None, **params):
        return reconstruct_cli(array, otf, exe=self._exe, on_log=on_log, **params)


def reconstruct_capture(array, otf, **params):
    """Reconstruct one channel, returning ``(result, log)`` (CLI-backed)."""
    return reconstruct_cli(array, otf, **params)
