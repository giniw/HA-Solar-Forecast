"""Helpers for multi-array forecast payloads from solar-forecast.com."""

from __future__ import annotations

import re
from typing import Any

ARRAY_KEY_RE = re.compile(r"^array_(\d+)_kWatt$")

# Match /index PANEL_LINE_COLORS
PANEL_LINE_COLORS = [
    "#b06b77",
    "#30ab2b",
    "#9fc1d6",
    "#f0a030",
    "#7b68ee",
    "#20b2aa",
    "#ff7f50",
    "#e91e8c",
]


def array_series_key(array_num: int) -> str:
    return f"array_{array_num}_kWatt"


def discover_array_numbers(data: dict[str, Any] | None) -> list[int]:
    """Return sorted 1-based array indices present in a /forecast payload."""
    if not data:
        return []

    found: set[int] = set()

    system_info = data.get("system_info") or {}
    for item in system_info.get("arrays") or []:
        try:
            found.add(int(item["array"]))
        except (KeyError, TypeError, ValueError):
            continue

    for key in data:
        match = ARRAY_KEY_RE.match(str(key))
        if match:
            found.add(int(match.group(1)))

    return sorted(n for n in found if array_series_key(n) in data)


def array_meta(data: dict[str, Any] | None, array_num: int) -> dict[str, Any]:
    """Return system_info metadata for one array, or a minimal fallback."""
    system_info = (data or {}).get("system_info") or {}
    for item in system_info.get("arrays") or []:
        try:
            if int(item.get("array")) == array_num:
                return dict(item)
        except (TypeError, ValueError):
            continue
    return {"array": array_num}


def normalize_arrays(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Build a stable arrays list for the HA panel / sensors."""
    result = []
    for num in discover_array_numbers(data):
        meta = array_meta(data, num)
        result.append(
            {
                "array": num,
                "key": array_series_key(num),
                "label": f"Array {num}",
                "capacity_kw": meta.get("capacity_kw"),
                "tilt": meta.get("tilt"),
                "orientation": meta.get("orientation"),
                "color": PANEL_LINE_COLORS[(num - 1) % len(PANEL_LINE_COLORS)],
            }
        )
    return result
