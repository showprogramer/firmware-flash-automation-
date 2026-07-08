from __future__ import annotations

import os
import subprocess
from pathlib import Path

from fwasset.core.types import FirmwareAsset


def open_path_in_explorer(path: str, log_fn=print) -> bool:
    """在系统文件管理器中打开目录/文件；失败记录日志并返回 False。

    UI 双击行 / 右键「打开目录」共用此入口，避免多处复制 startfile 逻辑。
    """
    if not path or not os.path.exists(path):
        log_fn(f"无法打开目录：路径不存在 ({path})")
        return False
    try:
        if os.name == "nt":
            os.startfile(path)  # noqa: S606
        elif os.name == "posix":
            subprocess.run(["xdg-open", path], check=False)
        return True
    except Exception as exc:  # noqa: BLE001
        log_fn(f"打开目录失败: {exc}")
        return False


def asset_flash_mode(asset: FirmwareAsset) -> str:
    firmware_type = str(asset.get("firmware_type", "") or "")
    # 蓝牙、断码屏手控固定走烧录工具（断码屏区别于普通手控UI的U盘流程）。
    if firmware_type in {"music_bt", "segmented_screen"}:
        return "tool_launch"
    return str(asset.get("flash_mode", "") or "")


def asset_usb_flow(asset: FirmwareAsset) -> str:
    firmware_type = str(asset.get("firmware_type", "") or "")
    if firmware_type == "music_bt":
        return ""
    configured = str(asset.get("usb_flow", "") or "")
    if configured:
        return configured
    # 普通手控UI走U盘配对流程；断码屏手控不在此列（走烧录工具）。
    if firmware_type == "handcontrol_ui":
        return "paired_files"
    if firmware_type == "music_files":
        return "directory_copy"
    return ""


def asset_rom_pkg_files(asset: FirmwareAsset) -> tuple[str, str]:
    rom_file = next((name for name in asset.get("files", []) if name.lower().endswith(".rom")), "")
    pkg_file = next((name for name in asset.get("files", []) if name.lower().endswith(".pkg")), "")
    return rom_file, pkg_file


def asset_dir_path(asset: FirmwareAsset) -> str:
    return str(asset.get("path", "") or "")


def asset_primary_file_name(asset: FirmwareAsset) -> str:
    """该资产要烧的主固件文件名（不含路径）。

    优先取常见固件后缀（.bin/.hex/.rom/.pkg/.zip），否则取第一个文件；
    无文件则返回空串。供 UI「程序名称」列等处复用。
    """
    files = [str(name) for name in asset.get("files", []) if str(name).strip()]
    # 手控等 rom/pkg 配对资源：固定显示 rom 名称（用户要求）。
    rom = next((name for name in files if name.lower().endswith(".rom")), "")
    if rom:
        return rom
    preferred_exts = (".bin", ".hex", ".pkg", ".zip")
    primary = next((name for name in files if name.lower().endswith(preferred_exts)), "")
    if not primary and files:
        primary = files[0]
    return primary


def asset_primary_file_path(asset: FirmwareAsset) -> str:
    base_path = Path(str(asset.get("path", "") or ""))
    primary = asset_primary_file_name(asset)
    return str(base_path / primary) if primary else str(base_path)
