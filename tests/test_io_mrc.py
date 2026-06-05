import os

import numpy as np
import pytest

from otfsearch import io_mrc


# ── pure-numpy helpers (no mrc / GPU needed) ──
def test_crop_center_xy_even():
    a = np.arange(8 * 8, dtype="f").reshape(8, 8)[None]  # (1, 8, 8)
    out = io_mrc.crop_center_xy(a, 4)
    assert out.shape == (1, 4, 4)
    # central 4x4 of an 8x8 starts at index 2
    assert np.array_equal(out[0], a[0, 2:6, 2:6])


def test_crop_center_xy_noop_when_small():
    a = np.zeros((3, 4, 4), dtype="f")
    assert io_mrc.crop_center_xy(a, 256) is a


def test_proc_output_path():
    assert io_mrc.proc_output_path("/data/foo.dv") == "/data/foo_PROC.dv"
    assert io_mrc.proc_output_path("/data/foo.dv", "_WF") == "/data/foo_WF.dv"


# ── optional round-trip against a real .dv (needs the mrc package) ──
def _sample_dv():
    env = os.environ.get("OTFSEARCH_TEST_DV")
    if env and os.path.exists(env):
        return env
    # default: the cudasirecon test data, if checked out alongside this repo
    here = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    cand = os.path.join(here, "cudasirecon", "test_data", "raw.dv")
    return cand if os.path.exists(cand) else None


def test_read_split_write_roundtrip(tmp_path):
    pytest.importorskip("mrc")
    sample = _sample_dv()
    if not sample:
        pytest.skip("no sample .dv available (set OTFSEARCH_TEST_DV)")
    im = io_mrc.imread(sample)
    hdr = im.Mrc.hdr
    chans = io_mrc.split_channels(im, hdr)
    assert chans, "expected at least one channel"
    arr, wave = chans[0]
    assert arr.ndim == 3
    out = str(tmp_path / "rt.dv")
    io_mrc.write_dv(arr, out, hdr, waves=[wave])
    back = io_mrc.imread(out)
    assert tuple(back.shape[-2:]) == tuple(arr.shape[-2:])
