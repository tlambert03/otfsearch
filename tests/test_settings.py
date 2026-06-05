from otfsearch import settings


def test_waves_matches_optics():
    assert settings.WAVES == list(settings.OPTICS)


def test_optics_entries_well_formed():
    for wave, opt in settings.OPTICS.items():
        assert isinstance(wave, int)
        assert isinstance(opt["ls"], float)
        assert len(opt["k0"]) == settings.NDIRS


def test_search_defaults_sane():
    assert settings.CROPSIZE in settings.VALID_CROPSIZES
    assert settings.OIL_MIN in settings.VALID_OIL_RANGE
    assert settings.OIL_MAX in settings.VALID_OIL_RANGE
    assert settings.OIL_MIN <= settings.OIL_MAX
