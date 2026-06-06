# otfsearch

Local, single-process SIM (structured-illumination microscopy) reconstruction with
automatic **OTF search**, channel registration, and a Tkinter GUI.

This is a modernized rewrite of the original client/server tool. It now runs as one
local process — **no SSH, no Priism, no MATLAB, no CLI round-trips**. It operates on
local `.dv` files and writes outputs next to the input.

* Reconstruction: the [`cudasirecon`](https://github.com/scopetools/cudasirecon)
  command-line engine (conda **`talley` channel**, MRC-capable; **needs an NVIDIA
  GPU**). The package drives it natively on `.dv`/`.otf` files and parses its stdout
  for the per-angle modulation amplitudes used by the OTF search.
* Channel registration: [`fiducialreg`](https://github.com/tlambert03/fiducialreg)
  (replaces the old MATLAB pipeline)
* `.dv`/MRC I/O: [`mrc`](https://pypi.org/project/mrc/) (replaces Priism + `Mrc.py`)

## Quick start (pixi — recommended)

[pixi](https://pixi.sh) gives you the whole thing — the GPU engine, the GUI, and every
dependency — in one reproducible, project-local environment. No manual conda/pip steps,
nothing installed globally.

1. **Install pixi** (once):
   - Windows (PowerShell): `iwr -useb https://pixi.sh/install.ps1 | iex`
   - Linux / macOS: `curl -fsSL https://pixi.sh/install.sh | bash`
2. **Clone and run:**
   ```bash
   git clone https://github.com/tlambert03/otfsearch
   cd otfsearch
   pixi run otfsearch      # first run resolves the env, then launches the GUI
   ```

That's it. pixi reads `[tool.pixi.*]` in `pyproject.toml`, pulls the MRC-capable
`cudasirecon` engine from the **`talley` channel**, and installs everything else from
conda-forge + PyPI into `.pixi/` (gitignored). The exact versions are locked in
`pixi.lock`, so every machine gets the same environment.

Other tasks:

```bash
pixi run cli ...     # the command-line interface (see "Use" below)
pixi run test        # run the unit tests
pixi run check       # quick sanity check: imports + is cudasirecon on PATH?
pixi shell           # drop into an activated shell in the environment
```

> **Requires an NVIDIA GPU + a driver supporting CUDA 12.** There is no CPU
> reconstruction fallback; the GUI launches without a GPU, but reconstruction reports a
> clear error until the `cudasirecon` engine can run.

## Manual install (conda + pip)

If you'd rather manage the environment yourself:

```bash
conda create -n otfsearch -c talley -c conda-forge python=3.10 cudasirecon "numpy<2"
conda activate otfsearch
pip install -e .                                              # this package
pip install "fiducialreg @ git+https://github.com/tlambert03/fiducialreg"  # registration
```

> Use the **MRC-capable** `cudasirecon` build from the `talley` channel — it reads the
> facility's MRC `.otf` library directly. NumPy is pinned `< 2` for now because the
> `mrc` reader still calls the removed `ndarray.newbyteorder`.

## Configure

Edit **`src/otfsearch/settings.py`** — the single place for user values:

1. `OTF_DIR` / `REGFILE_DIR` — where the OTF and registration-file libraries live
2. `OPTICS` — per-wavelength line spacing + pattern angles (add a line here for a
   new emission channel)
3. global reconstruction defaults (NA, immersion RI, Wiener, oil-RI search range …)

Pixel sizes and channel/timepoint counts are read automatically from each `.dv`.

## Use

With pixi, prefix the commands with `pixi run` (or run them inside `pixi shell`); with a
manual install, run them directly in the activated environment.

GUI:

```bash
pixi run otfsearch          # or just `otfsearch`
```

CLI (`pixi run cli ...`, or `otfsearch-cli ...`):

```bash
otfsearch-cli optimal raw.dv --otf-dir /OTFs            # OTF search + reconstruct
otfsearch-cli single  raw.dv --otf 528=/OTFs/528.otf    # reconstruct with given OTF
otfsearch-cli register file_PROC.dv --regfile reg.json  # apply channel registration
otfsearch-cli calibrate beads.dv --out-dir /regfiles    # build a registration file
```

## Develop / test

The pure-python parts (settings, OTF matching, params, scoring math) are unit-tested
without a GPU:

```bash
pip install pytest
pytest tests/             # GPU/mrc-dependent tests skip automatically
```

Reconstruction end-to-end can be verified against the cudasirecon test data
(`raw.dv`, `psf.dv`, `otf.dv`).
