from pathlib import Path

from fwasset.core.firmware_catalog import enabled_firmware_types, load_firmware_catalog


def test_load_firmware_catalog_missing_file_is_nonfatal(tmp_path: Path):
    result = load_firmware_catalog(tmp_path / "missing.toml")

    assert result["ok"] is True
    assert result["status"] == "missing"
    assert result["firmware_types"] == []


def test_load_firmware_catalog_normalizes_rows(tmp_path: Path):
    catalog_path = tmp_path / "firmware_catalog.toml"
    catalog_path.write_text(
        """
[[firmware_types]]
key = "handcontrol_ui"
label = "手控UI"
dir_keywords = ["手控", "手控器"]
file_extensions = [".ROM", ".PKG"]
flash_mode = "auto_usb"
usb_flow = "paired_files"
tool_name = "手控流程"
tool_path = ""
enabled = true
""".strip(),
        encoding="utf-8",
    )

    result = load_firmware_catalog(catalog_path)

    assert result["ok"] is True
    assert result["status"] == "ok"
    assert result["firmware_types"][0]["file_extensions"] == [".rom", ".pkg"]
    assert result["firmware_types"][0]["usb_flow"] == "paired_files"
    assert result["firmware_types"][0]["tool_dir"] == ""


def test_enabled_firmware_types_filters_disabled_rows(tmp_path: Path):
    catalog_path = tmp_path / "firmware_catalog.toml"
    catalog_path.write_text(
        """
[[firmware_types]]
key = "handcontrol_ui"
enabled = true

[[firmware_types]]
key = "voice"
enabled = false
""".strip(),
        encoding="utf-8",
    )

    rows = enabled_firmware_types(catalog_path)

    assert [item["key"] for item in rows] == ["handcontrol_ui"]


def test_default_catalog_contains_20_types():
    rows = enabled_firmware_types()

    assert len(rows) == 20
    assert "handcontrol_ui" in [item["key"] for item in rows]
    assert "music_files" in [item["key"] for item in rows]
    assert "aging" in [item["key"] for item in rows]


def test_default_catalog_assigns_explicit_usb_flows():
    rows = {item["key"]: item for item in enabled_firmware_types()}

    assert rows["handcontrol_ui"]["usb_flow"] == "paired_files"
    # 断码屏手控走烧录工具（非U盘流程）——与普通手控UI区分开。
    assert rows["segmented_screen"]["flash_mode"] == "tool_launch"
    assert rows["segmented_screen"]["usb_flow"] == ""
    assert rows["music_bt"]["flash_mode"] == "tool_launch"
    assert rows["music_bt"]["usb_flow"] == ""
    assert rows["music_files"]["flash_mode"] == "auto_usb"
    assert rows["music_files"]["usb_flow"] == "directory_copy"


def test_default_catalog_contains_expanded_real_world_keywords():
    rows = {item["key"]: item for item in enabled_firmware_types()}

    assert "断码屏亚克力手控" in rows["handcontrol_ui"]["dir_keywords"]
    assert "蓝牙—语音" in rows["music_bt"]["dir_keywords"]
    assert "语言板" in rows["voice"]["dir_keywords"]
    assert "快捷键-旋钮" in rows["shortcut_key"]["dir_keywords"]
    assert "机芯板上程序" in rows["movement_3d"]["dir_keywords"]
    assert "机芯板下程序" in rows["movement_2d"]["dir_keywords"]
    assert "旋钮开关程序" in rows["knob_switch"]["dir_keywords"]
    assert "纸币机" in rows["card_reader"]["dir_keywords"]
    assert "3合一" in rows["triple_combo"]["dir_keywords"]
