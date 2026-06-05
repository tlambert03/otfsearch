import os
import time

from otfsearch import otfmatch


def test_otf_code():
    name = "528_20160601_1516_oil_0.238_2.otf"
    assert otfmatch.otf_code(name) == "w528d20160601o15160.238b2"


def test_build_otf_dict(tmp_path):
    names = [
        "528_20160601_1516_oil_0.238_2.otf",
        "608_20160601_1518_oil_0.270_1.otf",
        "not_an_otf.txt",
    ]
    for n in names:
        (tmp_path / n).write_bytes(b"")
    d = otfmatch.build_otf_dict(str(tmp_path))
    assert len(d) == 2  # the .txt is ignored
    by_wave = {o["wavelength"]: o for o in d}
    assert set(by_wave) == {"528", "608"}
    o = by_wave["528"]
    assert o["oil"] == "1516"
    assert o["angle"] == "0.238"
    assert o["beadnum"] == "2"
    assert o["code"] == "w528d20160601o15160.238b2"
    assert os.path.basename(o["path"]) == "528_20160601_1516_oil_0.238_2.otf"


def _fake(wave, oil, ctime=0.0):
    return {"wavelength": str(wave), "oil": str(oil), "ctime": ctime,
            "code": f"w{wave}o{oil}", "path": f"/{wave}_{oil}.otf"}


def test_matching_filters_wave_and_oil():
    otfs = [_fake(528, 1512), _fake(528, 1525), _fake(608, 1515)]
    out = otfmatch.matching_otfs(otfs, 528, 1510, 1520)
    assert [o["oil"] for o in out] == ["1512"]  # 1525 out of range, 608 wrong wave


def test_matching_sorted_by_oil_ascending():
    otfs = [_fake(528, 1519), _fake(528, 1512), _fake(528, 1516)]
    out = otfmatch.matching_otfs(otfs, 528, 1510, 1520)
    assert [o["oil"] for o in out] == ["1512", "1516", "1519"]


def test_matching_max_num_keeps_most_recent():
    otfs = [_fake(528, 1512, ctime=1.0), _fake(528, 1514, ctime=3.0),
            _fake(528, 1516, ctime=2.0)]
    out = otfmatch.matching_otfs(otfs, 528, 1510, 1520, max_num=2)
    # keeps the 2 most-recent (ctime 3.0 & 2.0 -> oil 1514 & 1516), sorted by oil
    assert [o["oil"] for o in out] == ["1514", "1516"]


def test_matching_max_age():
    now = time.time()
    otfs = [_fake(528, 1512, ctime=now), _fake(528, 1514, ctime=now - 10 * 86400)]
    out = otfmatch.matching_otfs(otfs, 528, 1510, 1520, max_age=5)
    assert [o["oil"] for o in out] == ["1512"]
