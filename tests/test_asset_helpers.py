from pathlib import Path

from fwasset.core.asset_helpers import asset_dir_path, asset_primary_file_path, asset_rom_pkg_files, asset_usb_flow


def _asset(**overrides) -> dict:
    base = {
        "series": "L36",
        "firmware_type": "mainboard",
        "firmware_label": "主板程序",
        "flash_mode": "auto_usb",
        "usb_flow": "",
        "model": "L36",
        "version": "V1.0.0",
        "model_directory_name": "L36配置",
        "model_directory_path": "D:/root/L36配置",
        "path": "D:/root/L36配置/主板程序/V1.0.0",
        "directory_name": "V1.0.0",
        "files": ["main.bin"],
        "modified_time": 0,
        "tool_name": "",
        "tool_path": "",
        "tool_dir": "",
        "label": "L36 V1.0.0",
    }
    base.update(overrides)
    return base


def test_asset_usb_flow_returns_configured_flow():
    asset = _asset(usb_flow="directory_copy")
    assert asset_usb_flow(asset) == "directory_copy"


def test_asset_usb_flow_infer_paired_files_from_type():
    assert asset_usb_flow(_asset(firmware_type="handcontrol_ui", usb_flow="")) == "paired_files"
    assert asset_usb_flow(_asset(firmware_type="segmented_screen", usb_flow="")) == "paired_files"


def test_asset_usb_flow_infer_directory_copy_from_music():
    assert asset_usb_flow(_asset(firmware_type="music_bt", usb_flow="")) == "directory_copy"


def test_asset_usb_flow_returns_empty_for_unknown():
    assert asset_usb_flow(_asset(firmware_type="mainboard", usb_flow="")) == ""


def test_asset_usb_flow_configured_overrides_inferred():
    asset = _asset(firmware_type="handcontrol_ui", usb_flow="directory_copy")
    assert asset_usb_flow(asset) == "directory_copy"


def test_asset_rom_pkg_files_extracts_rom_and_pkg():
    asset = _asset(files=["main.bin", "program.rom", "data.pkg", "readme.txt"])
    rom, pkg = asset_rom_pkg_files(asset)
    assert rom == "program.rom"
    assert pkg == "data.pkg"


def test_asset_rom_pkg_files_returns_empty_when_missing():
    asset = _asset(files=["main.bin"])
    rom, pkg = asset_rom_pkg_files(asset)
    assert rom == ""
    assert pkg == ""


def test_asset_dir_path_returns_path():
    asset = _asset(path="D:/root/L36/主板/V1.0")
    assert asset_dir_path(asset) == "D:/root/L36/主板/V1.0"


def test_asset_dir_path_returns_empty_when_missing():
    assert asset_dir_path(_asset(path="")) == ""


def test_asset_primary_file_path_prefers_known_extensions():
    asset = _asset(
        path="D:/root/L36/主板/V1.0",
        files=["readme.txt", "main.rom", "data.pkg"],
    )
    result = asset_primary_file_path(asset)
    assert "main.rom" in result


def test_asset_primary_file_path_falls_back_to_first():
    asset = _asset(
        path="D:/root/L36/主板/V1.0",
        files=["unknown.xyz", "other.dat"],
    )
    result = asset_primary_file_path(asset)
    assert "unknown.xyz" in result


def test_asset_primary_file_path_uses_dir_when_no_files():
    asset = _asset(path="D:/root/L36/主板/V1.0", files=[])
    result = asset_primary_file_path(asset)
    assert Path(result) == Path("D:/root/L36/主板/V1.0")