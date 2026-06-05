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

## Install

The GPU engine comes from conda; everything else is pip:

```bash
conda create -n otfsearch -c talley -c conda-forge python=3.10 cudasirecon
conda activate otfsearch
pip install -e .          # this package (pins numpy<2)
pip install fiducialreg   # for channel registration
```

> Requires an NVIDIA GPU + matching CUDA runtime. There is no CPU reconstruction
> fallback; the GUI launches without the engine but reconstruction reports a clear
> error until the `cudasirecon` executable is on `PATH`.
>
> Use the **MRC-capable** `cudasirecon` build from the `talley` channel — it reads
> the facility's MRC `.otf` library directly. NumPy is pinned `< 2` for now because
> the `mrc` reader still calls the removed `ndarray.newbyteorder`.

## Configure

Edit **`src/otfsearch/settings.py`** — the single place for user values:

1. `OTF_DIR` / `REGFILE_DIR` — where the OTF and registration-file libraries live
2. `OPTICS` — per-wavelength line spacing + pattern angles (add a line here for a
   new emission channel)
3. global reconstruction defaults (NA, immersion RI, Wiener, oil-RI search range …)

Pixel sizes and channel/timepoint counts are read automatically from each `.dv`.

## Use

GUI:

```bash
otfsearch
```

CLI:

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
