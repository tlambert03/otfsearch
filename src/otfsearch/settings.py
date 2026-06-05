"""User-editable settings for otfsearch.

This single module replaces the old ``config.py`` *and* the directory of
per-wavelength ``{wave}config`` files.  There are only three things to edit:

  1. where the OTF and registration-file libraries live,
  2. the per-wavelength optics (line spacing + pattern angles),
  3. the global reconstruction defaults.

Everything else (pixel sizes, number of timepoints, channels present, ...) is
read automatically from each input ``.dv`` file's header at run time.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# 1. WHERE THE REFERENCE LIBRARIES LIVE
#    These are the only paths the program needs.  Outputs are always written
#    next to the input file.  (Both are also editable on the GUI "Settings" tab.)
# ─────────────────────────────────────────────────────────────────────────────
OTF_DIR = ""        # folder containing the .otf library, e.g. r"D:\SIMrecon\OTFs"
REGFILE_DIR = ""    # folder containing .json registration files


# ─────────────────────────────────────────────────────────────────────────────
# 2. PER-WAVELENGTH OPTICS  (ported verbatim from the facility SIconfig files)
#    Add an entry here when you start using a new emission line.
#      ls         = SIM illumination line spacing in microns
#      k0         = the three pattern (k0) angles, in radians
#      na/nimm/background/wiener = per-wave overrides; omit to use the globals in
#                   section 3 below.
# ─────────────────────────────────────────────────────────────────────────────
OPTICS: dict[int, dict] = {
    435: {"ls": 0.1920, "k0": (-0.831000, -1.884600, 0.213000), "na": 1.35, "nimm": 1.515, "background": 90,  "wiener": 0.001},
    477: {"ls": 0.2035, "k0": (-0.803400, -1.856900, 0.238900),             "nimm": 1.516, "background": 90,  "wiener": 0.001},
    528: {"ls": 0.2035, "k0": (-0.804300, -1.855500, 0.238800), "na": 1.42, "nimm": 1.515, "background": 0,   "wiener": 0.001},
    541: {"ls": 0.2035, "k0": (-0.798300, -1.849100, 0.244700),             "nimm": 1.516, "background": 90,  "wiener": 0.001},
    608: {"ls": 0.2290, "k0": (-0.775600, -1.826500, 0.270100), "na": 1.42, "nimm": 1.516, "background": 80,  "wiener": 0.001},
    683: {"ls": 0.2290, "k0": (-0.768500, -1.823400, 0.276100), "na": 1.42, "nimm": 1.516, "background": 100, "wiener": 0.002},
}

#: valid emission channels (was ``config.valid['waves']``)
WAVES: list[int] = list(OPTICS)


# ─────────────────────────────────────────────────────────────────────────────
# 3. GLOBAL RECONSTRUCTION DEFAULTS
#    Tune these to match the instrument.  They become the defaults of the
#    pycudasirecon.ReconParams that drive every reconstruction.
# ─────────────────────────────────────────────────────────────────────────────
NA = 1.42            # detection numerical aperture
NIMM = 1.515         # refractive index of the immersion medium
NDIRS = 3            # SIM pattern directions (angles)
NPHASES = 5          # phases per direction
ZOOMFACT = 2         # lateral oversampling factor of the reconstruction
OTF_RA = True        # use rotationally-averaged OTF
DAMPEN_ORDER0 = True  # dampen the order-0 (widefield) component in assembly
# SIM acquisition order. False = Angle->Z->Phase (cudasirecon default, matches the
# test data). Set True only if your instrument stores Z->Angle->Phase ("fast SI").
# If reconstructions look scrambled, flip this.
FAST_SI = False

WIENER = 0.001       # default Wiener filter constant
BACKGROUND = 90      # default camera background to subtract
# Band-overlap cutoff used in makeoverlaps() for k0/modamp fitting.  cudasirecon's
# own default is 0.006, but the long-running production engine (1.0.2) used 0.008;
# we pin 0.008 here so reconstructions track that engine (notably for low-SNR
# channels).  See PROJECT_STATUS.md "engine version" notes.
OTFCUTOFF = 0.008

# ── OTF-search knobs (all overridable from the GUI "Optimized" tab) ──
CROPSIZE = 256       # central crop (px) used while screening OTFs (power of 2)
OIL_MIN = 1512       # min OTF immersion-oil RI to consider (x1000)
OIL_MAX = 1520       # max OTF immersion-oil RI to consider (x1000)
MAX_AGE = None       # max OTF age in days to consider (None = no limit)
MAX_NUM = None       # max number of OTFs to test per channel (None = no limit)

# ── registration / post-processing defaults ──
REF_CHANNEL = 528    # default reference channel for channel registration
REG_MODE = "2step"   # fiducialreg transform mode (translation/rigid/similarity/
                     # affine/2step/cpd_*)
DO_REG = False       # apply channel registration by default
DO_MAX = False       # write a max-Z projection by default
DO_WF = False        # write a pseudo-widefield image by default

# ── OTF filename convention ──
# e.g.  528_20160601_1516_oil_0.238_2.otf
#       └wave └date    └oil  └med └angle└bead
OTF_TEMPLATE = "wavelength_date_oil_medium_angle_beadnum"
OTF_DELIM = "_"
OTF_EXT = ".otf"

# ── master score collection (optional; set to None to disable) ──
MASTER_SCORE_CSV: str | None = None


# ── validation helpers (kept here so the GUI and CLI agree) ──
VALID_CROPSIZES = [36, 64, 128, 256, 512, 1024]
VALID_OIL_RANGE = range(1510, 1530)
