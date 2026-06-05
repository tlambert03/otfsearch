"""Batch processing of a directory (ports legacy ``batchRecon`` + GUI ``dobatch``)."""

from __future__ import annotations

import os
from typing import Callable

from . import filetypes, io_mrc
from .recon_worker import ReconWorker


def collect_files(directory: str, mode: str, skip_processed: bool = True) -> list[str]:
    """Find files to process under ``directory`` for the given ``mode``."""
    found: list[str] = []
    for root, _dirs, files in os.walk(directory):
        for name in files:
            path = os.path.join(root, name)
            if mode == "register":
                if filetypes.is_a_reconstruction(path):
                    try:
                        if int(io_mrc.read_header(path).NumWaves) > 1:
                            found.append(path)
                    except Exception:  # noqa: BLE001
                        pass
            else:
                if filetypes.is_raw_sim_file(path):
                    if skip_processed and filetypes.is_already_processed(path):
                        continue
                    found.append(path)
    return sorted(found)


def batch(
    directory: str,
    mode: str,
    *,
    skip_processed: bool = True,
    only_optimize_first: bool = False,
    recon_kwargs: dict | None = None,
    reg_kwargs: dict | None = None,
    otf_for=None,
    on_log: Callable[[str], None] | None = None,
    worker: ReconWorker | None = None,
) -> list[dict]:
    """Run ``mode`` ('optimal' | 'single' | 'register') over a directory.

    Reuses a single :class:`ReconWorker` across the whole batch (one CUDA init).
    ``only_optimize_first`` runs the full OTF search on the first file, then reuses
    those best OTFs for the remaining files (single reconstruction).
    Returns a list of per-file result dicts (``{"file", "outputs"/"error"}``).
    """
    log = on_log or print
    recon_kwargs = dict(recon_kwargs or {})
    reg_kwargs = dict(reg_kwargs or {})

    files = collect_files(directory, mode, skip_processed)
    if not files:
        log(f"No matching files found in {directory} for mode '{mode}'")
        return []

    own_worker = worker is None and mode in ("optimal", "single")
    if mode in ("optimal", "single"):
        worker = worker or ReconWorker()

    results: list[dict] = []
    best_first = None
    try:
        for i, path in enumerate(files):
            log(f"[{i + 1}/{len(files)}] {path}")
            try:
                if mode == "optimal":
                    from .search import make_best_reconstruction
                    from .reconstruct import reconstruct_file
                    if only_optimize_first and best_first is not None:
                        out, logp = reconstruct_file(
                            path, best_first, worker=worker, on_log=on_log,
                            **_single_only(recon_kwargs),
                        )
                        results.append({"file": path, "outputs": {"reconstruction": out, "log": logp}})
                    else:
                        res = make_best_reconstruction(
                            path, worker=worker, on_log=on_log, **recon_kwargs
                        )
                        best_first = res["best_otfs"]
                        results.append({"file": path, "outputs": res})
                elif mode == "single":
                    from .reconstruct import reconstruct_file
                    out, logp = reconstruct_file(
                        path, otf_for, worker=worker, on_log=on_log,
                        **_single_only(recon_kwargs),
                    )
                    results.append({"file": path, "outputs": {"reconstruction": out, "log": logp}})
                elif mode == "register":
                    from .registration import apply_registration
                    out, mx = apply_registration(path, **reg_kwargs)
                    results.append({"file": path, "outputs": {"registered": out, "max": mx}})
                else:
                    raise ValueError(f"Unknown batch mode: {mode}")
            except Exception as e:  # noqa: BLE001 - keep going on per-file errors
                log(f"Skipping {path} due to error: {e}")
                results.append({"file": path, "error": str(e)})
        log("Batch finished")
        return results
    finally:
        if own_worker and worker is not None:
            worker.close()


def _single_only(kwargs: dict) -> dict:
    """Keep only kwargs that reconstruct_file accepts (drop search-only ones)."""
    allowed = {"recon_waves", "wiener", "background", "timepoints"}
    return {k: v for k, v in kwargs.items() if k in allowed}
