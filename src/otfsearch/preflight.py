"""Startup checks for the optional native dependencies."""

from __future__ import annotations

import shutil


def check_gpu_stack() -> str | None:
    """Return ``None`` if the ``cudasirecon`` engine is available, else a message.

    The reconstruction engine is the ``cudasirecon`` command-line executable
    (conda, needs an NVIDIA GPU). This lets the GUI launch and show a clear
    message rather than crashing when it is missing.
    """
    if shutil.which("cudasirecon") is None:
        return (
            "The 'cudasirecon' reconstruction engine was not found on PATH.\n"
            "Install it (and an NVIDIA GPU driver) with:\n"
            "    conda install -c conda-forge cudasirecon"
        )
    return None


def check_mrc() -> str | None:
    try:
        import mrc  # noqa: F401
    except Exception as e:  # noqa: BLE001
        return f"The 'mrc' package (for .dv files) is missing: {e}\n    pip install mrc"
    return None


def check_fiducialreg() -> str | None:
    try:
        import fiducialreg  # noqa: F401
    except Exception as e:  # noqa: BLE001
        return (
            "Channel registration needs 'fiducialreg' "
            f"({type(e).__name__}: {e}).\n    pip install fiducialreg"
        )
    return None
