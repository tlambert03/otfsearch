"""otfsearch — local, single-process SIM reconstruction + OTF search.

The heavy/optional dependencies (``pycudasirecon``, ``fiducialreg``, ``mrc``,
``tkinter``) are imported lazily by the submodules that need them, so importing
this top-level package is cheap and side-effect free.
"""

__version__ = "1.0.0"
