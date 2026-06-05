"""OTF library parsing and matching (ported from legacy ``otfsearch.py``).

OTF files are named per ``settings.OTF_TEMPLATE``, e.g.::

    528_20160601_1516_oil_0.238_2.otf
    │   │        │    │   │     └ beadnum
    │   │        │    │   └ angle
    │   │        │    └ medium
    │   │        └ oil (immersion RI x1000)
    │   └ date
    └ wavelength

The parsed dicts are passed straight into the scoring code, which reads keys
``code``, ``path``, ``oil``, ``angle``, ``beadnum``, ``date``, ``wavelength``.
"""

from __future__ import annotations

import os
import time

from . import settings


def otf_code(name: str, template: str = settings.OTF_TEMPLATE,
             delim: str = settings.OTF_DELIM) -> str:
    """Compact identifier, e.g. ``w528d20160601o15160.238b2``."""
    splits = os.path.basename(name).split(settings.OTF_EXT)[0].split(delim)
    t = template.split(delim)
    return (
        "w" + splits[t.index("wavelength")]
        + "d" + splits[t.index("date")]
        + "o" + splits[t.index("oil")]
        + splits[t.index("angle")]
        + "b" + splits[t.index("beadnum")]
    )


def build_otf_dict(directory: str, template: str = settings.OTF_TEMPLATE,
                   delim: str = settings.OTF_DELIM,
                   ext: str = settings.OTF_EXT) -> list[dict]:
    """Parse every ``*.otf`` in ``directory`` into a list of metadata dicts."""
    names = [f for f in os.listdir(directory) if f.endswith(ext)]
    keys = template.split(delim)
    out: list[dict] = []
    for name in names:
        fields = name.split(ext)[0].split(delim)
        d = dict(zip(keys, fields))
        full = os.path.join(directory, name)
        d["path"] = full
        d["ctime"] = os.stat(full).st_ctime
        d["code"] = otf_code(name, template, delim)
        out.append(d)
    return out


def matching_otfs(otf_dict: list[dict], wave: int, oil_min: int, oil_max: int,
                  max_age: int | None = None, max_num: int | None = None) -> list[dict]:
    """Filter the OTF list for one channel (faithful port of ``getMatchingOTFs``).

    Keeps OTFs whose wavelength matches and whose oil RI is in
    ``[oil_min, oil_max]``; optionally restricts to those created within
    ``max_age`` days and to the ``max_num`` most-recent; returns them sorted by
    oil RI ascending.
    """
    matches = [
        o for o in otf_dict
        if o["wavelength"] == str(wave)
        and oil_min <= int(o["oil"]) <= oil_max
    ]
    if max_age is not None:
        oldest = time.time() - max_age * 24 * 60 * 60
        matches = [o for o in matches if o["ctime"] >= oldest]
    matches.sort(key=lambda x: x["ctime"], reverse=True)
    if max_num is not None:
        matches = matches[:max_num]
    return sorted(matches, key=lambda x: x["oil"])
