import os
import re
from pathlib import Path

from core.settings import (
    SCAN_EXCLUDE_DIR_KEYWORDS,
    SCAN_MODEL_PATTERNS,
    SCAN_PATH_MODEL_PATTERNS,
    SCAN_PATH_VERSION_PATTERNS,
    SCAN_PKG_EXTENSIONS,
    SCAN_ROM_EXTENSIONS,
    SCAN_VERSION_PATTERNS,
)
from core.types import HandcontrolFolder


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
    return any(keyword and keyword in dirpath for keyword in SCAN_EXCLUDE_DIR_KEYWORDS)


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
    results: list[HandcontrolFolder] = []
    root_path = Path(root)

    for dirpath, _, filenames in os.walk(root_path):
        if _is_excluded_dir(dirpath):
            continue

        rom_files = [f for f in filenames if _has_allowed_extension(f, SCAN_ROM_EXTENSIONS)]
        pkg_files = [f for f in filenames if _has_allowed_extension(f, SCAN_PKG_EXTENSIONS)]

        if rom_files and pkg_files:
            rom = rom_files[0]
            pkg = pkg_files[0]
            model, version = parse_rom_filename(rom)
            if not model:
                model = guess_model_from_path(dirpath)
            if not version:
                version = guess_version_from_path(dirpath)

            results.append(
                {
                    "path": dirpath,
                    "rom_file": rom,
                    "pkg_file": pkg,
                    "model": model,
                    "version": version,
                    "label": f"{model}  {version}  [{Path(dirpath).name}]",
                }
            )

    results.sort(key=lambda x: x["path"])
    return results
