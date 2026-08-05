import re
from enum import StrEnum
from pathlib import Path

from fwasset.core.types import FirmwareAsset


class SortKey(StrEnum):
    PATH = "path"
    MODEL = "model"
    VERSION = "version"


def _model_sort_value(model: str) -> tuple[int, str, int, str]:
    text = str(model or "").strip().upper()
    match = re.search(r"([A-Z]+)(\d+)([A-Z]*)", text)
    if not match:
        return (1, text, -1, "")
    prefix, number, suffix = match.groups()
    return (0, prefix, int(number), suffix)


def _version_sort_value(version: str) -> tuple[int, tuple[int, ...], str]:
    text = str(version or "").strip().upper()
    match = re.search(r"(\d+(?:\.\d+)*)", text)
    if not match:
        return (1, (), text)
    parts = tuple(int(part) for part in match.group(1).split("."))
    return (0, parts, text)


def _path_sort_value(folder: FirmwareAsset) -> tuple[object, ...]:
    path = Path(str(folder.get("path", "") or ""))
    parts = [str(part) for part in path.parts]
    return tuple(_natural_text_sort_value(part) for part in parts)


def _folder_name_sort_value(folder: FirmwareAsset) -> tuple[object, ...]:
    return _natural_text_sort_value(Path(str(folder.get("path", "") or "")).name)


def _natural_text_sort_value(text: str) -> tuple[object, ...]:
    parts = re.split(r"(\d+)", str(text or "").strip().lower())
    normalized = []
    for part in parts:
        if not part:
            continue
        normalized.append((0, int(part)) if part.isdigit() else (1, part))
    return tuple(normalized)


def apply_sort(
    folders: list[FirmwareAsset],
    sort_key: SortKey,
    ascending: bool = True,
) -> list[FirmwareAsset]:
    def _sort_value(folder: FirmwareAsset) -> tuple[object, ...]:
        model = str(folder.get("model", ""))
        version = str(folder.get("version", ""))
        if sort_key == SortKey.MODEL:
            return (
                _model_sort_value(model),
                _version_sort_value(version),
                _folder_name_sort_value(folder),
            )
        if sort_key == SortKey.VERSION:
            return (
                _version_sort_value(version),
                _model_sort_value(model),
                _folder_name_sort_value(folder),
            )
        return (
            _path_sort_value(folder),
            _model_sort_value(model),
            _version_sort_value(version),
        )

    return sorted(list(folders), key=_sort_value, reverse=not ascending)
