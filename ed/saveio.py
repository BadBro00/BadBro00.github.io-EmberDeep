"""Save file handling (stdlib only)."""
from __future__ import annotations
import json
import os

DEFAULT = {
    "unlocked": 0, "coins": 0, "deaths": 0, "wins": 0,
    "best_time": None, "muted": False, "abilities": [],
    "beacons": [],
}


def path() -> str:
    import sys
    if getattr(sys, "frozen", False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "save.json")


def load(p: str | None = None) -> dict:
    st = dict(DEFAULT)
    st["abilities"] = []
    st["beacons"] = []
    try:
        with open(p or path()) as f:
            st.update(json.load(f))
    except (OSError, ValueError):
        pass
    return st


def save(st: dict, p: str | None = None) -> None:
    with open(p or path(), "w") as f:
        json.dump(st, f, indent=2)
