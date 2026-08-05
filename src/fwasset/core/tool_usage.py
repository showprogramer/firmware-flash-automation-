from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fwasset.core.settings import APP_ROOT

DEFAULT_TOOL_USAGE_PATH = APP_ROOT / "tool_usage.json"
MAX_RECENT_TOOLS = 8


def load_tool_usage(path: str | Path | None = None) -> dict[str, list[str]]:
    usage_path = Path(path) if path is not None else DEFAULT_TOOL_USAGE_PATH
    if not usage_path.exists():
        return {"favorites": [], "recent": []}
    try:
        data: Any = json.loads(usage_path.read_text(encoding="utf-8"))
    except Exception:
        return {"favorites": [], "recent": []}
    if not isinstance(data, dict):
        return {"favorites": [], "recent": []}
    return {
        "favorites": _clean_keys(data.get("favorites", [])),
        "recent": _clean_keys(data.get("recent", []))[:MAX_RECENT_TOOLS],
    }


def save_tool_usage(
    usage: dict[str, list[str]], path: str | Path | None = None
) -> bool:
    usage_path = Path(path) if path is not None else DEFAULT_TOOL_USAGE_PATH
    payload = {
        "favorites": _clean_keys(usage.get("favorites", [])),
        "recent": _clean_keys(usage.get("recent", []))[:MAX_RECENT_TOOLS],
    }
    try:
        usage_path.parent.mkdir(parents=True, exist_ok=True)
        usage_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return True
    except Exception:
        return False


def toggle_favorite_tool(
    fw_type: str, usage: dict[str, list[str]]
) -> dict[str, list[str]]:
    key = str(fw_type or "").strip()
    favorites = _clean_keys(usage.get("favorites", []))
    if not key:
        return {**usage, "favorites": favorites}
    if key in favorites:
        favorites.remove(key)
    else:
        favorites.insert(0, key)
    return {**usage, "favorites": favorites}


def record_recent_tool(
    fw_type: str, usage: dict[str, list[str]]
) -> dict[str, list[str]]:
    key = str(fw_type or "").strip()
    recent = _clean_keys(usage.get("recent", []))
    if not key:
        return {**usage, "recent": recent[:MAX_RECENT_TOOLS]}
    if key in recent:
        recent.remove(key)
    recent.insert(0, key)
    return {**usage, "recent": recent[:MAX_RECENT_TOOLS]}


def _clean_keys(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    cleaned: list[str] = []
    for value in values:
        key = str(value or "").strip()
        if key and key not in cleaned:
            cleaned.append(key)
    return cleaned
