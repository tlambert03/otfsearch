# otfsearch

Local SIM (structured-illumination microscopy) reconstruction with OTF search, channel
registration, and a Tkinter GUI. Operates on local `.dv` files and writes outputs next
to the input.

- Reconstruction: the [`cudasirecon`](https://github.com/scopetools/cudasirecon) CLI
  (conda `talley` channel, MRC-capable; requires an NVIDIA GPU). Driven on `.dv`/`.otf`
  files; its stdout is parsed for the per-angle modulation amplitudes used by the OTF
  search.
- Channel registration: [`fiducialreg`](https://github.com/tlambert03/fiducialreg).
- `.dv`/MRC I/O: [`mrc`](https://pypi.org/project/mrc/).

Requires an NVIDIA GPU and a driver supporting CUDA 12. No CPU reconstruction fallback:
the GUI runs without a GPU, but reconstruction errors until `cudasirecon` can run.

## Run with pixi

Install pixi (https://pixi.sh), then:

```bash
git clone https://github.com/tlambert03/otfsearch
cd otfsearch
pixi run otfsearch
```

Tasks: `otfsearch` (tkinter GUI), `qt` (PyQt6, basic), `qt-advanced` (PyQt6, full
controls), `cli`, `test`, `check`.

## Manual install (conda + pip)

```bash
conda create -n otfsearch -c talley -c conda-forge python=3.10 cudasirecon "numpy<2"
conda activate otfsearch
pip install -e .
pip install "fiducialreg @ git+https://github.com/tlambert03/fiducialreg"
```

numpy is pinned `<2`: the `mrc` reader still calls the removed `ndarray.newbyteorder`.

## Configure

Edit `src/otfsearch/settings.py`:

- `OTF_DIR` / `REGFILE_DIR` — OTF and registration-file library locations
- `OPTICS` — per-wavelength line spacing and pattern angles
- reconstruction defaults (NA, immersion RI, Wiener, oil-RI search range, ...)

Pixel sizes and channel/timepoint counts are read from each `.dv` header.

## CLI

```bash
otfsearch-cli optimal raw.dv --otf-dir /OTFs            # OTF search + reconstruct
otfsearch-cli single  raw.dv --otf 528=/OTFs/528.otf   # reconstruct with a given OTF
otfsearch-cli register file_PROC.dv --regfile reg.json # apply channel registration
otfsearch-cli calibrate beads.dv --out-dir /regfiles   # build a registration file
```

Under pixi: `pixi run cli optimal ...`, or `pixi shell` then run directly.

## Test

```bash
pixi run test          # or: pytest tests/
```

GPU/mrc-dependent tests skip without a GPU.
