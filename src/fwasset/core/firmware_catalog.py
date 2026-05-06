from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from fwasset.core.settings import APP_ROOT, load_toml_config
from fwasset.core.types import FirmwareType


DEFAULT_FIRMWARE_CATALOG_PATH = APP_ROOT / "firmware_catalog.toml"


class FirmwareTypeConfig(TypedDict):
    key: FirmwareType
    label: str
    dir_keywords: list[str]
    file_extensions: list[str]
    flash_mode: str
    tool_name: str
    tool_path: str
    tool_dir: str
    enabled: bool


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _normalize_type(node: Any) -> FirmwareTypeConfig | None:
    if not isinstance(node, dict):
        return None
    key = str(node.get("key", "")).strip()
    if not key:
        return None
    return {
        "key": key,  # type: ignore[typeddict-item]
        "label": str(node.get("label", key)).strip() or key,
        "dir_keywords": _as_str_list(node.get("dir_keywords", [])),
        "file_extensions": [item.lower() for item in _as_str_list(node.get("file_extensions", []))],
        "flash_mode": str(node.get("flash_mode", "tool_launch")).strip() or "tool_launch",
        "tool_name": str(node.get("tool_name", "")).strip(),
        "tool_path": str(node.get("tool_path", "")).strip(),
        "tool_dir": str(node.get("tool_dir", "")).strip(),
        "enabled": bool(node.get("enabled", True)),
    }


def load_firmware_catalog(path: Path | None = None) -> dict[str, Any]:
    catalog_path = path or DEFAULT_FIRMWARE_CATALOG_PATH
    raw_cfg, status, error = load_toml_config(catalog_path)
    items = raw_cfg.get("firmware_types", []) if isinstance(raw_cfg, dict) else []

    normalized: list[FirmwareTypeConfig] = []
    for item in items:
        row = _normalize_type(item)
        if row is not None:
            normalized.append(row)

    return {
        "ok": status in {"ok", "missing"},
        "status": status,
        "error": error,
        "path": str(catalog_path),
        "firmware_types": normalized,
    }


def enabled_firmware_types(path: Path | None = None) -> list[FirmwareTypeConfig]:
    catalog = load_firmware_catalog(path)
    return [item for item in catalog.get("firmware_types", []) if item.get("enabled", True)]
