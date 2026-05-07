import os
import re
from pathlib import Path

from fwasset.core.settings import (
    SCAN_EXCLUDE_DIR_KEYWORDS,
    SCAN_MODEL_PATTERNS,
    SCAN_PATH_MODEL_PATTERNS,
    SCAN_PATH_VERSION_PATTERNS,
    SCAN_PKG_EXTENSIONS,
    SCAN_ROM_EXTENSIONS,
    SCAN_VERSION_PATTERNS,
)
from fwasset.core.firmware_catalog import DEFAULT_FIRMWARE_CATALOG_PATH, enabled_firmware_types
from fwasset.core.types import FirmwareAsset, HandcontrolFolder


def _match_first_group(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        try:
            match = re.search(pattern, text, re.IGNORECASE)
        except re.error:
            continue
        if match:
            return match.group(1)
    return ""


def _normalize_version(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text.upper() if text[:1].upper() == "V" else f"V{text}"


def _has_allowed_extension(filename: str, extensions: list[str]) -> bool:
    lower_name = filename.lower()
    return any(lower_name.endswith(ext) for ext in extensions)


def _is_excluded_dir(dirpath: str) -> bool:
    lower_path = str(dirpath or "").lower()
    return any(keyword and str(keyword).lower() in lower_path for keyword in SCAN_EXCLUDE_DIR_KEYWORDS)


def _files_match_extensions(filenames: list[str], extensions: list[str]) -> bool:
    normalized_exts = [ext.lower() for ext in extensions if str(ext).strip()]
    if not normalized_exts:
        return False
    for name in filenames:
        lower_name = name.lower()
        if any(lower_name.endswith(ext) for ext in normalized_exts):
            return True
    return False


def _match_catalog_type(dirpath: str, filenames: list[str], type_configs: list[dict]) -> dict | None:
    lower_parts = [part.lower() for part in Path(dirpath).parts]
    for cfg in type_configs:
        keywords = [str(item).strip().lower() for item in cfg.get("dir_keywords", []) if str(item).strip()]
        if cfg.get("key") == "handcontrol_ui":
            has_rom = _files_match_extensions(filenames, SCAN_ROM_EXTENSIONS)
            has_pkg = _files_match_extensions(filenames, SCAN_PKG_EXTENSIONS)
            if has_rom and has_pkg:
                return cfg
        if keywords and not any(keyword in part for keyword in keywords for part in lower_parts):
            continue
        if not _files_match_extensions(filenames, cfg.get("file_extensions", [])):
            continue
        return cfg
    return None


def _extract_model_version(dirpath: str, filenames: list[str]) -> tuple[str, str]:
    for name in filenames:
        model, version = parse_rom_filename(name)
        if model or version:
            return model or guess_model_from_path(dirpath), version or guess_version_from_path(dirpath)
    return guess_model_from_path(dirpath), guess_version_from_path(dirpath)


def guess_series_from_model_or_path(model: str, dirpath: str) -> str:
    """Infer series from model first, then path segments, using the [A-Z]+[0-9]+ prefix rule."""
    candidates = [str(model or "")]
    candidates.extend(reversed([str(part) for part in Path(dirpath).parts]))
    for candidate in candidates:
        match = re.search(r"([A-Za-z]+\d+)", candidate)
        if match:
            return match.group(1).upper()
    return "未知系列"


def _model_directory_for_asset(root_path: Path, folder_path: Path) -> Path:
    try:
        relative_parts = folder_path.relative_to(root_path).parts
    except ValueError:
        relative_parts = folder_path.parts
    if not relative_parts:
        return folder_path
    return root_path / relative_parts[0]


def scan_firmware_assets(root: str, catalog_path: str | Path | None = None) -> tuple[list[FirmwareAsset], list[str]]:
    """
    Scan root using catalog-configured directory keywords and file extensions.
    Returns recognized assets plus explicit directory read errors.
    """
    root_path = Path(root)
    if not root_path.exists():
        raise FileNotFoundError(f"扫描根目录不存在: {root}")
    if not root_path.is_dir():
        raise NotADirectoryError(f"扫描根目录不是目录: {root}")

    type_configs = enabled_firmware_types(Path(catalog_path) if catalog_path else DEFAULT_FIRMWARE_CATALOG_PATH)
    results: list[FirmwareAsset] = []
    errors: list[str] = []

    def _on_walk_error(exc: OSError):
        if exc.filename:
            errors.append(f"{exc.filename}: {exc.strerror}")
        else:
            errors.append(str(exc))

    for dirpath, _, filenames in os.walk(root_path, onerror=_on_walk_error):
        if _is_excluded_dir(dirpath):
            continue
        cfg = _match_catalog_type(dirpath, filenames, type_configs)
        if cfg is None:
            continue

        folder_path = Path(dirpath)
        model_directory = _model_directory_for_asset(root_path, folder_path)
        model, version = _extract_model_version(dirpath, filenames)
        series = guess_series_from_model_or_path(model, str(model_directory))
        files = sorted(filenames)
        label = f"{model}  {version or '-'}  [{folder_path.name}]  {cfg['label']}"
        results.append(
            {
                "series": series,
                "firmware_type": cfg["key"],
                "firmware_label": cfg["label"],
                "flash_mode": cfg["flash_mode"],
                "model": model,
                "version": version,
                "model_directory_name": model_directory.name,
                "model_directory_path": str(model_directory),
                "path": str(folder_path),
                "directory_name": folder_path.name,
                "files": files,
                "modified_time": folder_path.stat().st_mtime,
                "tool_name": cfg["tool_name"],
                "tool_path": cfg["tool_path"],
                "tool_dir": cfg.get("tool_dir", ""),
                "label": label,
            }
        )

    results.sort(key=lambda item: (item["path"], item["firmware_type"]))
    return results, errors


def parse_rom_filename(name: str) -> tuple[str, str]:
    """
    Parse model and version from ROM filename using configurable regex rules.
    """
    name_no_ext = Path(name).stem

    model = _match_first_group(name_no_ext, SCAN_MODEL_PATTERNS).upper()
    version = _normalize_version(_match_first_group(name_no_ext, SCAN_VERSION_PATTERNS))

    return model, version


def guess_model_from_path(dirpath: str) -> str:
    """Guess model from path segments using configurable regex rules."""
    for part in reversed(Path(dirpath).parts):
        matched = _match_first_group(part, SCAN_PATH_MODEL_PATTERNS)
        if matched:
            return matched.upper()
    return "未知型号"


def guess_version_from_path(dirpath: str) -> str:
    """Guess version from folder name/path segments when ROM filename has no version."""
    for part in reversed(Path(dirpath).parts):
        matched = _match_first_group(part, SCAN_PATH_VERSION_PATTERNS)
        if matched:
            return _normalize_version(matched)
    return ""


def find_handcontrol_folders(root: str) -> list[HandcontrolFolder]:
    """
    Recursively scan root and find folders containing both configured ROM and PKG files.
    Priority: ROM filename -> folder/path fallback.
    """
    assets, _errors = scan_firmware_assets(root)
    results: list[HandcontrolFolder] = []
    for asset in assets:
        if asset["firmware_type"] != "handcontrol_ui":
            continue
        rom_files = [name for name in asset["files"] if _has_allowed_extension(name, SCAN_ROM_EXTENSIONS)]
        pkg_files = [name for name in asset["files"] if _has_allowed_extension(name, SCAN_PKG_EXTENSIONS)]
        if not rom_files or not pkg_files:
            continue
        results.append(
            {
                "path": asset["path"],
                "rom_file": rom_files[0],
                "pkg_file": pkg_files[0],
                "model": asset["model"],
                "version": asset["version"],
                "label": f"{asset['model']}  {asset['version']}  [{Path(asset['path']).name}]",
            }
        )

    results.sort(key=lambda x: x["path"])
    return results
