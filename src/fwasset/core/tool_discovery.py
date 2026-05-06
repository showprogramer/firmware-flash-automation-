"""Tool discovery and launch helpers."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Callable

from fwasset.core.firmware_catalog import DEFAULT_FIRMWARE_CATALOG_PATH, load_firmware_catalog
from fwasset.core.settings import APP_ROOT, TOOL_ROOT


TOOL_FILENAME_PATTERNS: dict[str, list[str]] = {
    "mainboard": ["*烧录*.exe", "*flash*.exe", "*ISP*.exe", "*主板*.exe", "*.exe"],
    "voice": ["*语音*.exe", "*voice*.exe", "*.exe"],
    "shortcut_key": ["*快捷*.exe", "*shortcut*.exe", "*.exe"],
    "movement_3d": ["*3D*.exe", "*3d*.exe", "*.exe"],
    "movement_2d": ["*2D*.exe", "*2d*.exe", "*.exe"],
    "knob_switch": ["*旋钮*.exe", "*knob*.exe", "*.exe"],
    "leg": ["*腿部*.exe", "*leg*.exe", "*.exe"],
    "knee": ["*膝盖*.exe", "*knee*.exe", "*.exe"],
    "sonic": ["*音波*.exe", "*sonic*.exe", "*.exe"],
    "health_detection": ["*健康*.exe", "*health*.exe", "*.exe"],
    "commercial_mainboard": ["*商用*.exe", "*commercial*.exe", "*.exe"],
    "card_reader": ["*刷卡*.exe", "*card*.exe", "*.exe"],
    "leyao_yao": ["*摇摇*.exe", "*乐摇摇*.exe", "*.exe"],
    "triple_combo": ["*三合*.exe", "*combo*.exe", "*.exe"],
}
_DISCOVERY_CACHE: dict[tuple[str, str, str, str, str], str] = {}


def clear_tool_discovery_cache():
    _DISCOVERY_CACHE.clear()


def _tool_patterns(fw_type: str) -> list[str]:
    patterns = list(TOOL_FILENAME_PATTERNS.get(fw_type, ["*.exe"]))
    for fallback in ["*.exe", "*.bat", "*.cmd"]:
        if fallback not in patterns:
            patterns.append(fallback)
    return patterns


def _valid_tool_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in {".exe", ".bat", ".cmd"}


def _normalize_keywords(*values: object) -> list[str]:
    keywords: list[str] = []
    for value in values:
        if isinstance(value, list):
            keywords.extend(_normalize_keywords(*value))
            continue
        text = str(value or "").strip().lower()
        if len(text) > 1:
            keywords.append(text)
    return list(dict.fromkeys(keywords))


def _find_executable_in_dir(directory: Path, patterns: list[str]) -> Path | None:
    if not directory.exists() or not directory.is_dir():
        return None
    for pattern in patterns:
        for tool_file in sorted(directory.glob(pattern), key=lambda item: item.name.lower()):
            if _valid_tool_file(tool_file):
                return tool_file
    return None


def _find_explicit_tool(tool_path: str) -> Path | None:
    path = Path(str(tool_path or "").strip())
    if not str(path):
        return None
    if not path.is_absolute():
        path = APP_ROOT / path
    return path if _valid_tool_file(path) else None


def _find_by_exact_tool_dir(tool_root: Path, tool_dir: str, patterns: list[str]) -> Path | None:
    if not tool_dir:
        return None
    candidate = Path(tool_dir)
    if not candidate.is_absolute():
        candidate = tool_root / candidate
    return _find_executable_in_dir(candidate, patterns)


def _find_by_fuzzy_dir(tool_root: Path, patterns: list[str], keywords: list[str]) -> Path | None:
    if not tool_root.exists() or not tool_root.is_dir():
        return None
    for directory in sorted((item for item in tool_root.rglob("*") if item.is_dir()), key=lambda item: str(item).lower()):
        lower_name = directory.name.lower()
        if any(keyword in lower_name for keyword in keywords):
            result = _find_executable_in_dir(directory, patterns)
            if result:
                return result
    return _find_executable_in_dir(tool_root, patterns)


def discover_tool_path(
    fw_type: str,
    tool_name: str = "",
    *,
    tool_path: str = "",
    tool_dir: str = "",
    dir_keywords: list[str] | None = None,
) -> str:
    """Discover a launchable tool path using catalog/config priority."""
    configured_root = str(TOOL_ROOT or "")
    cache_key = (fw_type, tool_name, tool_path, tool_dir, configured_root)
    if cache_key in _DISCOVERY_CACHE:
        return _DISCOVERY_CACHE[cache_key]

    patterns = _tool_patterns(fw_type)
    explicit = _find_explicit_tool(tool_path)
    if explicit:
        _DISCOVERY_CACHE[cache_key] = str(explicit)
        return str(explicit)

    tool_root = Path(configured_root) if configured_root else None
    if tool_root and tool_root.exists():
        exact = _find_by_exact_tool_dir(tool_root, tool_dir, patterns)
        if exact:
            _DISCOVERY_CACHE[cache_key] = str(exact)
            return str(exact)
        keywords = _normalize_keywords(tool_dir, tool_name, fw_type.split("_"), dir_keywords or [])
        fuzzy = _find_by_fuzzy_dir(tool_root, patterns, keywords)
        if fuzzy:
            _DISCOVERY_CACHE[cache_key] = str(fuzzy)
            return str(fuzzy)

    fallback_root = APP_ROOT / "tools"
    exact = _find_by_exact_tool_dir(fallback_root, tool_dir, patterns)
    if exact:
        _DISCOVERY_CACHE[cache_key] = str(exact)
        return str(exact)
    fallback = _find_by_fuzzy_dir(
        fallback_root,
        patterns,
        _normalize_keywords(tool_dir, tool_name, fw_type.split("_"), dir_keywords or []),
    )
    result = str(fallback) if fallback else ""
    _DISCOVERY_CACHE[cache_key] = result
    return result


def auto_discover_all_tools(progress_callback: Callable[[str, str], None] | None = None) -> dict[str, str]:
    catalog = load_firmware_catalog()
    discovered: dict[str, str] = {}

    for item in catalog.get("firmware_types", []):
        fw_type = item.get("key", "")
        tool_name = item.get("tool_name", "")
        current_path = item.get("tool_path", "")
        flash_mode = item.get("flash_mode", "")

        if flash_mode == "tool_launch" and fw_type:
            if progress_callback:
                progress_callback(fw_type, f"正在查找: {tool_name}...")
            found_path = discover_tool_path(
                fw_type,
                tool_name,
                tool_path=current_path,
                tool_dir=item.get("tool_dir", ""),
                dir_keywords=item.get("dir_keywords", []),
            )
            if found_path:
                discovered[fw_type] = found_path
                if progress_callback:
                    progress_callback(fw_type, f"找到: {found_path}")
            elif progress_callback:
                progress_callback(fw_type, f"未找到: {tool_name}")

    return discovered


def save_tool_paths_to_catalog(tool_paths: dict[str, str]) -> bool:
    try:
        content = DEFAULT_FIRMWARE_CATALOG_PATH.read_text(encoding="utf-8")
        for fw_type, tool_path in tool_paths.items():
            escaped_path = str(tool_path).replace("\\", "\\\\")
            pattern = (
                rf'(\[\[firmware_types\]\][^[]*key\s*=\s*["\']{re.escape(fw_type)}["\'][^[]*?)'
                rf'tool_path\s*=\s*["\'][^"\']*["\']'
            )

            def _replace(match: re.Match[str]) -> str:
                return f'{match.group(1)}tool_path = "{escaped_path}"'

            content = re.sub(pattern, _replace, content, flags=re.DOTALL)
        DEFAULT_FIRMWARE_CATALOG_PATH.write_text(content, encoding="utf-8")
        clear_tool_discovery_cache()
        return True
    except Exception:
        return False


def launch_tool(tool_path: str) -> dict:
    if not tool_path:
        return {"ok": False, "message": "工具路径未配置"}

    path_obj = Path(tool_path)
    if not path_obj.exists():
        return {"ok": False, "message": f"工具不存在: {tool_path}"}

    try:
        subprocess.Popen(
            [str(path_obj)],
            cwd=str(path_obj.parent),
            shell=False,
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0,
        )
        return {"ok": True, "message": f"已启动: {path_obj.name}"}
    except Exception as exc:
        return {"ok": False, "message": f"启动失败: {exc}"}
