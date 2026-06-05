import pytest

from otfsearch import params, settings


def test_basic_params_for_528():
    p = params.recon_params_for_wave(528, xyres=0.08, zres=0.125)
    opt = settings.OPTICS[528]
    assert p["ls"] == opt["ls"]
    assert p["k0angles"] == tuple(opt["k0"])
    assert p["ndirs"] == settings.NDIRS
    assert p["nphases"] == settings.NPHASES
    assert p["zoomfact"] == settings.ZOOMFACT
    assert p["wavelength"] == 528
    assert p["xyres"] == 0.08
    assert p["zres"] == 0.125
    # per-wave values from settings.OPTICS (528: na=1.42, nimm=1.515, bg=0, wiener=0.001)
    assert p["na"] == opt["na"]
    assert p["nimm"] == opt["nimm"]
    assert p["wiener"] == opt["wiener"]
    assert p["background"] == opt["background"]


def test_per_wave_values_and_global_fallback():
    # 608's ls must be the corrected SIconfig value, not the old 0.2075
    assert params.recon_params_for_wave(608, xyres=0.08, zres=0.125)["ls"] == 0.229
    # 477 has no per-wave "na" -> falls back to the global default
    assert "na" not in settings.OPTICS[477]
    assert params.recon_params_for_wave(477, xyres=0.08, zres=0.125)["na"] == settings.NA
    # 683 has per-wave wiener=0.002
    assert params.recon_params_for_wave(683, xyres=0.08, zres=0.125)["wiener"] == 0.002


def test_cropsize_sets_cropxy():
    p = params.recon_params_for_wave(528, xyres=0.08, zres=0.125, cropsize=256)
    assert p["cropXY"] == 256
    p2 = params.recon_params_for_wave(528, xyres=0.08, zres=0.125)
    assert "cropXY" not in p2


def test_overrides_win():
    p = params.recon_params_for_wave(528, xyres=0.08, zres=0.125, wiener=0.02,
                                     nimm=1.518, dampenOrder0=False)
    assert p["wiener"] == 0.02
    assert p["nimm"] == 1.518
    assert p["dampenOrder0"] is False


def test_unknown_wave_raises():
    with pytest.raises(KeyError):
        params.recon_params_for_wave(999, xyres=0.08, zres=0.125)


def test_zres_psf_optional():
    p = params.recon_params_for_wave(528, xyres=0.08, zres=0.125)
    assert "zresPSF" not in p
    p2 = params.recon_params_for_wave(528, xyres=0.08, zres=0.125, zres_psf=0.125)
    assert p2["zresPSF"] == 0.125
