# Project status & handoff — otfsearch modernization

_Last updated: 2026-06-04. This is the single source of truth for the whole effort:
the otfsearch rewrite, the cudasirecon engine work it depends on, the lessons from
the detours, and what's left to do._

---

## 0. The ultimate goal

Modernize **otfsearch** — a Python-2 Tkinter GUI that facility users run to drive SIM
(structured-illumination microscopy) reconstruction. The legacy app is an SSH client
that shells into a Linux box and orchestrates **Priism + MATLAB + the cudasirecon
CLI**. Target: a **local, single-process, pip-installable Python-3 package** that does
exactly the same things with far less complexity — no SSH, no Priism, no MATLAB.

Repos involved (all under `~/dev/self/`):
- **`otfsearch`** — the app being rewritten (this repo). The deliverable.
- **`cudasirecon`** — the GPU reconstruction engine (a dependency; became a detour).
- **`pycudasirecon`**, **`fiducialreg`**, **`mrc`** — supporting libraries.

---

## 1. otfsearch package — DONE and validated

A complete rewrite lives under `otfsearch/src/otfsearch/`. Legacy Py2 files moved to
`otfsearch/legacy/`. **25 unit tests pass; full OTF search + reconstruction validated
end-to-end on the GPU** (corr 0.9997 vs reference).

| Module | Replaces | Role |
|---|---|---|
| `settings.py` | `config.py` + `{wave}config` dir | one commented settings file |
| `io_mrc.py` | Priism CopyRegion/mergemrc/RunProj + `Mrc.py` | `.dv` I/O via `mrc` + numpy |
| `recon_worker.py` | the cudasirecon CLI plumbing | drives `cudasirecon` (native MRC) |
| `reconstruct.py` | `reconstructMulti`/`singleRecon` | split→recon→merge→`_PROC.dv` |
| `scoring.py` | `getRIH`/`CIP`/`getSAM`/log-parse | `score = RIH × avgmodamp2` |
| `search.py` | `scoreOTFs`/`makeBestReconstruction` | the OTF search (flagship) |
| `registration.py` | MATLAB `omxreg`/`omxregcal` | `fiducialreg` calibrate + apply |
| `project.py`, `batch.py`, `otfmatch.py`, `params.py`, `csvlog.py`, `filetypes.py`, `preflight.py`, `cli.py`, `gui/app.py` | the rest | projections, batch, OTF matching, params, CSV, file detection, preflight, CLI, tkinter GUI |

Engine interface is `recon_worker.ReconWorker.reconstruct(array, otf, **params) →
(result, log)`, so the rest of the package is decoupled from how reconstruction
actually happens.

**Key settings the user must set** before real use (`settings.py`): `OTF_DIR`,
`REGFILE_DIR`, and confirm `FAST_SI` (currently `False` = Angle→Z→Phase, the
cudasirecon default; flip if the instrument writes Z→Angle→Phase).

Nothing committed yet (working tree changes only).

---

## 2. cudasirecon engine — built, validated, PR in progress

The engine became a real detour because the available builds didn't work as assumed.

**Current state:** locally compiled **cudasirecon 1.3.0** from the **`newmrc`** branch
(tlambert03 fork; PR **#24** "remove IVE dependency"), with **CUDA 12.4**, native MRC,
no IVE. Validated: `cudasirecon` recon corr **0.9997** vs reference `proc.dv`, **0.986**
vs the talley-channel v1.0.2; `makeotf` runs. Build env = micromamba `simbuild`.

**The catch (the active work):** `newmrc`'s `dvfile.h` does **no data-type conversion**
on read, but real microscope raw `.dv` is **uint16** (15 significant bits) and
cudasirecon reads it straight into a `CImg<float>` buffer. The test data is all
float32, so this was never exercised. See §4 roadmap.

> **UPDATE 2026-06-05 — two `dvfile.h` bugs found & fixed; engine now usable on real data.**
> 1. **uint16 read/write conversion** added (B1) — validated corr 1.00000 vs float.
> 2. **Extended-header (`inbsym`) bug (the big one).** Real `.otf`/`.dv` carry large
>    extended headers (608.otf `inbsym=156672`, 528.otf `3072`, il2_001.dv `81920`),
>    but `DVFile`'s constructor left the file pointer at offset 1024 (after the main
>    header only). The engine loads the **OTF via bare `IMRdSec`** (sequential, no
>    positioning), so it read the ext-header region as OTF data → 608 OTF ≈ zeros →
>    `findk0()=(0,0)` → **all-NaN ch608**; 528 (small inbsym) read shifted → degraded
>    "sharper" recon (corr 0.66). The raw path was immune (it uses `IMPosnZWT`, which
>    adds `1024+inbsym`); TIFF mode and IVE/1.0.2 immune too. **This is why the
>    "version-parity" gap looked like a kernel regression but was an I/O bug — no git
>    bisect of the kernel was warranted.** Fix: `_dataOffset()/_seekToData()` (skip
>    `inbsym`) called from the read ctor, `open()`, and `putHeader()`. Probe confirms
>    sequential OTF read == positioned read (max abs diff 0); ch608 NaN gone.
> **Residual:** after the fix, newmrc(1.2.0) vs talley(1.0.2)/server = **0.92 ch528 /
> 0.78 ch608** — genuine 1.0.2→1.2.0 kernel evolution (the "crisper" look). Open A/B/C
> engine decision: A ship newmrc-1.3, B port the no-IVE + fixes onto v1.0.2 for exact
> production parity, C characterize/accept the change. Needs user call.

### What `newmrc`/`dvfile.h` actually does
It deletes the proprietary **IVE/Priism** dependency (precompiled `libimlib`/`libive`,
non-redistributable → the reason conda-forge cudasirecon is TIFF-only and the `talley`
channel exists) and reimplements the exact IVE `IM*` C API from scratch in one
self-contained header `src/dvfile.h` (a `DVFile` class over `std::fstream` + a
`std::map<int,DVFile>` "stream handle" shim with `IMOpen`/`IMRdHdr`/`IMRdSec`/`IMWrSec`/
`IMPosnZWT`/…). Because the shim signatures match IVE exactly, the rest of cudasirecon
compiles unchanged — just `#include "dvfile.h"` instead of linking IVE. Net result:
native, dependency-free MRC/DV that builds clean on modern toolchains (where the old
IVE static libs segfault).

### Confirmed IVE behavior to replicate (the conversion contract)
- IVE `IMAlCon(stream, flag)` controls a per-stream **ConversionFlag**, default **ON**
  = auto-convert stored type ↔ float.
- cudasirecon calls `IMAlCon(stream, 0)` (OFF) on the **OTF**, **output**, and
  **correction** streams, but **never on the raw input** → raw input keeps the default
  and is auto-converted to **float**. Output header mode is forced to `IW_FLOAT`
  (`setOutputHeader`, mrc.h:37), so float results write directly. → the fix is purely
  on **read**: convert integer stored types → float, gated by a per-stream flag that
  `IMAlCon` toggles (default on).

---

## 3. Lessons learned (the detours & surprises)

1. **No local Python on the box** — only the Windows-Store stub. Use **`uv`**
   (`uv run --no-project --with …`) for pure-python and **`micromamba`** envs for
   GPU/native. This unblocked all testing.
2. **pycudasirecon (conda 0.2.0) bindings are ABI-broken** vs cudasirecon 1.2.0 —
   `get_result()` returns `(0,0,0)` / segfaults. Don't rely on the in-process Python
   bindings. → otfsearch drives the **`cudasirecon` CLI** instead (simpler, and modamp
   capture becomes trivial: parse stdout, no fd-redirection).
3. **conda-forge cudasirecon is TIFF-only** ("not compiled with MRC support") because
   IVE can't be redistributed. The **`talley` channel** carries the IVE/MRC build.
4. **Engine orientation/params** (learned by testing, not docs):
   - `mrc.imread(raw.dv)` == **Y-flip** of `raw.tif`; mrc-read data uses the **negative**
     k0 angles already in `settings.OPTICS`.
   - **`fastSI=False`** for this data (Angle→Z→Phase). `fastSI=True` gave corr 0.49.
     (Main's PR #28 was exactly "fastSI-should-be-0" in the test config.)
   - Reconstruction zooms XY ×2 (`zoomfact=2`); output pixel size = input/2.
   - `hdr.d` = `(dx, dy, dz)`.
5. **`mrc` + NumPy 2.0**: `mrc` calls the removed `ndarray.newbyteorder` when reading
   `.dv` data → crash. **Pin `numpy<2`** for now (and/or fix `mrc` upstream). Header
   reads are fine; only data reads hit it.
6. **Windows file locking**: `mrc.bindFile` memory-maps and holds the handle, blocking
   later overwrite/delete (`[Errno 22]`) and leaking temp dirs. → `io_mrc.read_array`
   reads into memory + closes the handle.
7. **IVE static libs (`IVE.zip`) segfault at runtime** in `IMOpen` with the
   MSVC14.29+CUDA12 build (exit 139), even though they compile/link. The talley v1.0.2
   works with IVE but I don't have its exact recipe. → the **`newmrc`/`dvfile.h`
   (no-IVE)** path is both the working build AND the better long-term direction.
8. **`newmrc` is float-only so far** — the uint16 read-conversion is the missing piece
   (§2, §4). The "it works" validation (corr 0.9997) was all float32 test data and did
   **not** cover the uint16 path or makeotf-on-uint16.
9. **Windows CUDA build gotchas** (recipe in `cudasirecon-build` memory): must use the
   **Ninja** generator (conda `cuda-nvcc` has no VS MSBuild integration) and clear
   `CMAKE_GENERATOR*` env vars; **netlib** BLAS (`*=*netlib`) or `FindBLAS` fails; use
   absolute `-S/-B` paths (the inner shell mangles `cd`/`mkdir -p`/`../src`); the
   `vs2019_win-64` activation echoes a wall of `.bat` noise — filter it.

---

## 4. Remaining roadmap

### A. Finish cudasirecon PR #24 (immediate — engine correctness)
Tracked in tasks #10–13.
1. **Add data-type conversion to `dvfile.h`** (the headline). `readSec`: convert
   `BYTE/INT16/UINT16/LONG/EMTOM` → float; `FLOAT`/`COMPLEX` direct. `writeSection`:
   symmetric float→stored. Add a per-stream `_convert` flag (default **true**) that
   `IMAlCon` sets (replace the current no-op `IMAlCon`). This matches the confirmed IVE
   contract (§2). Output stays correct (mode forced to FLOAT).
2. **Validate with real uint16 data.** User is providing real raw tomorrow. Meanwhile,
   synthesize uint16 (mode 6) versions of `raw.dv`/`psf.dv` (15-bit range): show garbage
   pre-fix, then post-fix uint16 recon ≈ float recon, and `makeotf` on uint16 PSF ≈
   reference `otf.dv`.
3. **Test makeotf thoroughly** (PR notes it was untested) — it reads the (uint16) PSF
   into float buffers, so the same read-conversion covers it; compare its OTF output to
   the reference.
4. **Remaining IVE stubs**: `IMRtExHdrZWT` is used by the opt-in `bBgInExtHdr`
   (per-section background from the extended header) — decide implement vs document as
   unsupported; `IMAlLab`/`IMAlPrt` are cosmetic. Fix the `IMWrHdr` append-title FIXME.
5. **Round-trip unit tests** for `dvfile.h` (header + sections across dtypes).
6. **Commit `newmrc`, push, update PR #24** description/checklist. _Coordinate with the
   user before pushing — outward-facing._

### B. Package & distribute cudasirecon 1.3 (after A)
- Because `newmrc` drops IVE, this **could go to conda-forge** (no proprietary dep),
  not just the `talley` channel — a strategic improvement. Decide channel(s).
- conda-build/rattler from the feedstock recipe; broaden `CMAKE_CUDA_ARCHITECTURES`
  beyond sm_70; `anaconda upload` needs the user's token (outward-facing — confirm).
- This was deferred when we pivoted to PR #24.

### C. otfsearch end-to-end on real data (after a working engine exists)
1. Point otfsearch at the engine (`cudasirecon` on PATH) + set `OTF_DIR`/`REGFILE_DIR`.
2. Run a real raw SIM `.dv` through Optimized + Specify-OTFs paths; confirm `_PROC.dv`,
   `_LOG.txt`, `_scores.csv`, best-OTF population.
3. **Channel registration (fiducialreg) is code-complete but UNTESTED** — needs a real
   bead/grid calibration image. Validate calibrate → `.json` → apply → `-REGto{ref}.dv`.
4. **GUI smoke test** on an actual display (imports verified; window not yet launched).

### D. Cleanup / decisions
- Resolve the `numpy<2` pin: fix `mrc`'s `newbyteorder` upstream, then drop the pin.
- Decide whether otfsearch's CLI-subprocess engine stays, or revisit in-process once
  pycudasirecon bindings are fixed (CLI is currently simpler and works — keep it).
- Commit otfsearch (new `src/`, `tests/`, `pyproject.toml`, `legacy/`), open PR.
- Temp artifacts to clean when done: `cudasirecon/_validation/`, `IVE.zip`,
  `IVE_extracted/`, `src/IVE/`, the `build-1.3-ive` branch, `cmake_build/`.

---

## 5. Environments & reference (for whoever picks this up)
- **`uv`** — pure-python tests: `uv run --no-project --python 3.11 --with pytest --with "numpy<2" --with scipy --with mrc pytest -q otfsearch/tests/`
- **micromamba `otftest`** — conda-forge cudasirecon (TIFF-only) + mrc + numpy2 — older validation env.
- **micromamba `otftalley`** — talley cudasirecon 1.0.2 (MRC) + numpy 1.26 + the otfsearch package — the reference engine env.
- **micromamba `simbuild`** — the cudasirecon **build** env (CUDA 12.4, VS2019, netlib BLAS).
- Test data: `cudasirecon/test_data/` (raw.dv, psf.dv, otf.dv, proc.dv — all float32).
  Reference outputs: `cudasirecon/_validation/`.
- Plan file: `~/.claude/plans/this-folder-otfsearch-represents-eager-tulip.md`.
- Memory: `otfsearch-rewrite`, `cudasirecon-build` (in the project memory dir).
- cudasirecon PR: https://github.com/scopetools/cudasirecon/pull/24 (branch `newmrc`).
