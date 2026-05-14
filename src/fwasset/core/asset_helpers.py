from __future__ import annotations

from pathlib import Path

from fwasset.core.types import FirmwareAsset


def asset_flash_mode(asset: FirmwareAsset) -> str:
    firmware_type = str(asset.get("firmware_type", "") or "")
    if firmware_type == "music_bt":
        return "tool_launch"
    return str(asset.get("flash_mode", "") or "")


def asset_usb_flow(asset: FirmwareAsset) -> str:
    firmware_type = str(asset.get("firmware_type", "") or "")
    if firmware_type == "music_bt":
        return ""
    configured = str(asset.get("usb_flow", "") or "")
    if configured:
        return configured
    if firmware_type in {"handcontrol_ui", "segmented_screen"}:
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


def asset_primary_file_path(asset: FirmwareAsset) -> str:
    base_path = Path(str(asset.get("path", "") or ""))
    files = [str(name) for name in asset.get("files", []) if str(name).strip()]
    preferred_exts = (".bin", ".hex", ".rom", ".pkg", ".zip")
    primary = next((name for name in files if name.lower().endswith(preferred_exts)), "")
    if not primary and files:
        primary = files[0]
    return str(base_path / primary) if primary else str(base_path)
