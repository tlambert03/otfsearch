"""Per-user persistent overrides for a few settings.

``settings.py`` holds the code-level defaults.  The GUI lets a user change the
library locations (OTF directory, reg-file directory); those choices are stored
here as JSON so they survive across sessions.  This is the persistence the old
``config.py`` never had — there you edited the module by hand.
"""

from __future__ import annotations

import json
from pathlib import Path

PATH = Path.home() / ".otfsearch.json"

# only these keys are persisted; everything else stays per-session
KEYS = ("otf_dir", "regfile_dir")


def load() -> dict:
    """Return the persisted overrides (``{}`` if none/unreadable)."""
    try:
        data = json.loads(PATH.read_text())
    except (OSError, ValueError):
        return {}
    return {k: data[k] for k in KEYS if k in data}


def set_value(key: str, value: str) -> None:
    """Persist a single ``key`` (no-op for unknown keys or on write error)."""
    if key not in KEYS:
        return
    data = load()
    data[key] = value
    try:
        PATH.write_text(json.dumps(data, indent=2))
    except OSError:
        pass
