"""Build per-wavelength reconstruction parameters.

Replaces the old directory of ``{wave}config`` files.  Returns a plain kwargs
dict whose keys match :class:`pycudasirecon.ReconParams` fields, so it can be
splatted straight into ``pycudasirecon.reconstruct(array, otf=..., **params)``.

``pycudasirecon`` is intentionally *not* imported here (it needs the compiled
GPU library), so this module is importable and testable anywhere.
"""

from __future__ import annotations

from . import settings


def recon_params_for_wave(
    wave: int,
    *,
    xyres: float,
    zres: float,
    wiener: float | None = None,
    background: float | None = None,
    nimm: float | None = None,
    na: float | None = None,
    zoomfact: float | None = None,
    cropsize: int = 0,
    zres_psf: float | None = None,
    otfcutoff: float | None = None,
    **overrides,
) -> dict:
    """Return reconstruction kwargs for one channel.

    ``xyres``/``zres`` come from the input ``.dv`` header (required because we
    feed cudasirecon an in-memory array, which has no pixel-size metadata).
    For ``ls``/``k0angles``/``na``/``nimm``/``background``/``wiener`` the priority
    is: explicit argument > per-wave ``settings.OPTICS`` value > global default.
    Any extra keyword overrides win.
    """
    if wave not in settings.OPTICS:
        raise KeyError(
            f"No optics defined for wavelength {wave}; add it to settings.OPTICS"
        )
    opt = settings.OPTICS[wave]

    def pick(arg, key, default):
        if arg is not None:
            return arg
        return opt.get(key, default)

    params: dict = {
        "ndirs": settings.NDIRS,
        "nphases": settings.NPHASES,
        "na": pick(na, "na", settings.NA),
        "nimm": pick(nimm, "nimm", settings.NIMM),
        "ls": opt["ls"],
        "k0angles": tuple(opt["k0"]),
        "wiener": pick(wiener, "wiener", settings.WIENER),
        "background": pick(background, "background", settings.BACKGROUND),
        "otfRA": settings.OTF_RA,
        "dampenOrder0": settings.DAMPEN_ORDER0,
        "fastSI": settings.FAST_SI,
        "otfcutoff": pick(otfcutoff, "otfcutoff", settings.OTFCUTOFF),
        "zoomfact": settings.ZOOMFACT if zoomfact is None else zoomfact,
        "xyres": xyres,
        "zres": zres,
        "wavelength": int(wave),
    }
    if zres_psf is not None:
        params["zresPSF"] = zres_psf
    if cropsize:
        params["cropXY"] = int(cropsize)
    params.update(overrides)
    return params
