"""Score CSV output (per-file ``_scores.csv`` + optional master collection).

Ports the CSV-writing parts of legacy ``makeBestReconstruction``.
"""

from __future__ import annotations

import os

from . import settings


def write_scores_csv(score_dicts: list[dict], in_path: str) -> str:
    """Write ``{stem}_scores.csv`` next to the input; return its path."""
    import pandas as pd

    out = os.path.splitext(in_path)[0] + "_scores.csv"
    pd.DataFrame(score_dicts).to_csv(out)
    return out


def append_master(score_dicts: list[dict], master: str | None = None) -> None:
    """Append scores to the shared master CSV, checking column compatibility.

    Mirrors the legacy behaviour: create the file if missing, otherwise verify
    the columns match before appending, then drop duplicate rows.
    """
    import pandas as pd

    master = master or settings.MASTER_SCORE_CSV
    if not master:
        return
    df = pd.DataFrame(score_dicts)
    if not os.path.isfile(master):
        df.to_csv(master, mode="a", index=False)
        return
    existing_cols = pd.read_csv(master, nrows=1).columns
    if len(df.columns) != len(existing_cols):
        raise ValueError(
            f"Master CSV column count mismatch: new={len(df.columns)} "
            f"existing={len(existing_cols)}"
        )
    if not (df.columns == existing_cols).all():
        raise ValueError("Master CSV column names/order do not match")
    df.to_csv(master, mode="a", index=False, header=False)
    _dedupe(master)


def _dedupe(csv_path: str) -> None:
    import pandas as pd

    pd.read_csv(csv_path).drop_duplicates().to_csv(csv_path, index=False)
