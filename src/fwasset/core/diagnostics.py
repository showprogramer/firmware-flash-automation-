from __future__ import annotations

import json
import platform
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from fwasset.core.settings import load_toml_config

_PATH_KEYS = {
    "config_path",
    "log_path",
    "output_path",
    "path",
    "root_dir",
}


def _mask_path(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    name = Path(text.replace("\\", "/")).name
    if name:
        return f"<redacted>/{name}"
    return "<redacted>"


def sanitize_snapshot(value: object, key: str | None = None) -> Any:
    if isinstance(value, Path):
        value = str(value)

    if isinstance(value, dict):
        return {str(k): sanitize_snapshot(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_snapshot(item, key) for item in value]
    if isinstance(value, tuple):
        return [sanitize_snapshot(item, key) for item in value]

    lowered = (key or "").lower()
    if isinstance(value, str) and lowered in _PATH_KEYS:
        return _mask_path(value)
    return value


def build_diagnostic_bundle(
    output_path: str | Path,
    *,
    app_state: dict,
    config_path: str | Path,
    log_path: str | Path,
) -> dict:
    output = Path(output_path)
    config_file = Path(config_path)
    log_file = Path(log_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    cfg, cfg_status, cfg_error = load_toml_config(config_file)
    sanitized_config = sanitize_snapshot(cfg)
    sanitized_state = sanitize_snapshot(app_state)

    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "config_status": cfg_status,
        "config_error": cfg_error,
        "log_exists": log_file.exists(),
    }

    entries: list[str] = []
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:

        def _write_json(name: str, payload: object) -> None:
            zf.writestr(name, json.dumps(payload, ensure_ascii=False, indent=2))
            entries.append(name)

        _write_json("meta.json", meta)
        _write_json("state/app_state.json", sanitized_state)
        _write_json("state/folders.json", sanitized_state.get("folders", []))
        _write_json(
            "config/config.sanitized.json",
            {
                "path": sanitize_snapshot(str(config_file), "config_path"),
                "status": cfg_status,
                "error": cfg_error,
                "config": sanitized_config,
            },
        )

        if log_file.exists():
            zf.write(log_file, "logs/app.log")
            entries.append("logs/app.log")
        else:
            zf.writestr("logs/app.log.missing.txt", f"missing: {log_file}\n")
            entries.append("logs/app.log.missing.txt")

    return {
        "ok": True,
        "output_path": str(output),
        "entries": entries,
    }
