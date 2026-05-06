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


def test_default_catalog_contains_19_types():
    rows = enabled_firmware_types()

    assert len(rows) == 19
    assert "handcontrol_ui" in [item["key"] for item in rows]
    assert "aging" in [item["key"] for item in rows]
