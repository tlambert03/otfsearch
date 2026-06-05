import numpy as np

from otfsearch import scoring


def test_calc_pos_neg_ratio_symmetric():
    # symmetric histogram about the mode (bg=0) -> ratio 1.0
    r = scoring.calc_pos_neg_ratio(0.5, 0, -2, 2, [10, 0, 0, 10], 20)
    assert r == 1.0


def test_calc_pos_neg_ratio_positive_skew():
    # twice as much positive intensity -> ratio 2.0
    r = scoring.calc_pos_neg_ratio(1.0, 0, -2, 2, [10, 0, 0, 20], 30)
    assert r == 2.0


def test_calc_pos_neg_ratio_no_negatives():
    # negTotal stays 0 -> guarded to 0.0 (no crash)
    assert scoring.calc_pos_neg_ratio(0.5, 0, -2, 2, [0, 0, 0, 10], 10) == 0.0


def test_parse_recon_log():
    log = "\n".join([
        "set wiener=0.0010 done",
        "Combined modamp for dir 0: amp=0.50, x",
        "Combined modamp for dir 1: amp=0.10, x",
        "Combined modamp for dir 2: amp=0.60, x",
        "Combined modamp for dir 3: amp=0.20, x",
        "Combined modamp for dir 4: amp=0.70, x",
        "Combined modamp for dir 5: amp=0.30, x",
        "Correlation coefficient: 0.9",
        "Correlation coefficient: 0.8",
        "spacing=0.2035 microns",
        "Optimum k0 angle=1.234, length=5.6",
        "best fit for k0 is 0.010 something",
    ])
    p = scoring.parse_recon_log(log)
    assert p["modamp2"] == [0.50, 0.60, 0.70]   # indices 0,2,4
    assert p["modamp1"] == [0.10, 0.20, 0.30]   # indices 1,3,5
    assert abs(p["avgmodamp2"] - 0.6) < 1e-9
    assert p["wiener"] == "0.001"
    assert p["spacings"] == [0.2035]
    assert p["angles"] == [1.234]


def test_score_value():
    assert scoring.score_value(2.0, 0.6) == 1.2


def test_cip_flat_stack_is_zero():
    arr = np.ones((30, 4, 4), dtype="f")  # 3 angles * 5 phases * 2 z
    tiv, decay, diffs = scoring.cip(arr)
    assert tiv == 0.0
    assert decay == 0
    assert diffs == 0.0


def test_best_otfs_picks_highest_score():
    scores = [
        {"imChannel": 528, "OTFpath": "/a.otf", "OTFcode": "a", "score": 1.0,
         "RIH": 1.0, "avgmodamp2": 1.0},
        {"imChannel": 528, "OTFpath": "/b.otf", "OTFcode": "b", "score": 3.0,
         "RIH": 1.5, "avgmodamp2": 2.0},
        {"imChannel": 608, "OTFpath": "/c.otf", "OTFcode": "c", "score": 2.0,
         "RIH": 1.0, "avgmodamp2": 2.0},
    ]
    best = scoring.best_otfs(scores, verbose=False)
    assert best == {"528": "/b.otf", "608": "/c.otf"}
