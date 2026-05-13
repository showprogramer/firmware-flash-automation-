from pathlib import Path

import pytest

import fwasset.core.file_scan as file_scan
from fwasset.core.file_scan import (
    find_handcontrol_folders,
    guess_model_from_path,
    guess_series_from_model_or_path,
    guess_version_from_path,
    parse_rom_filename,
    scan_firmware_assets,
)


@pytest.mark.parametrize(
    ("filename", "expected_model", "expected_version"),
    [
        ("YJ-L50S-3122MG-791_UI_118.3.10.ROM", "L50S", "V118.3.10"),
        ("ITE_NOR_yj_massage_4d_music_L36_v34.3.2.ROM", "L36", "V34.3.2"),
        ("ITE_NOR.ROM", "", ""),
        ("abc_L88_pro_v1.2.3.rom", "L88", "V1.2.3"),
        ("ITE_NOR_yj_massage_4d_music_L50_heat_38.3.1_003.ROM", "L50", "V38.3.1_003"),
        ("ITE_NOR_yj_Smassage_4d_music_L50_heat_38.3.1_019.ROM", "L50", "V38.3.1_019"),
        ("L35A手控UI.ROM", "L35A", ""),
        ("ITE_NOR_yj_massage_L26A_Max_music_72.33.ROM", "L26A", "V72.33"),
        ("YJ-L39S-2122XN-K032_UI_126.3.1.ROM", "L39S", "V126.3.1"),
        ("ITE_NOR 120.3.1.ROM", "", "V120.3.1"),
        ("ITE_NOR_yj_massage__NULL_s_V50.3.6.ROM", "", "V50.3.6"),
        ("NULLLOG_16.3.7_FY.ROM", "", "V16.3.7"),
        ("ITE_NOR_yj_Smassage_L36_4d_Beelogo_103.3.1.ROM", "L36", "V103.3.1"),
        ("ITE_NOR_yj_Smassage_L36_H530_62.3.2.ROM", "L36", "V62.3.2"),
        ("ITE_NOR_yj_massage_4d_l65_46_002.ROM", "L65", "V46_002"),
        ("zey_standard_project_l50s_47_005.ROM", "L50S", "V47_005"),
    ],
)
def test_parse_rom_filename(filename: str, expected_model: str, expected_version: str):
    model, version = parse_rom_filename(filename)
    assert model == expected_model
    assert version == expected_version


@pytest.mark.parametrize(
    ("dirpath", "expected"),
    [
        (r"D:\\workspace\\release\\L36\\pkg", "L36"),
        (r"D:\\workspace\\L50Smax\\test", "L50SMAX"),
        (r"D:\\workspace\\L35A手控UI\\pkg", "L35A"),
        (r"D:\\workspace\\foo\\bar", "未知型号"),
    ],
)
def test_guess_model_from_path(dirpath: str, expected: str):
    assert guess_model_from_path(dirpath) == expected


@pytest.mark.parametrize(
    ("dirpath", "expected"),
    [
        (r"D:\\workspace\\NOLLLOG_V17.3.2\\pkg", "V17.3.2"),
        (r"D:\\workspace\\release\\38.3.1_003\\pkg", "V38.3.1_003"),
        (r"D:\\workspace\\foo\\bar", ""),
    ],
)
def test_guess_version_from_path(dirpath: str, expected: str):
    assert guess_version_from_path(dirpath) == expected


@pytest.mark.parametrize(
    ("model", "dirpath", "expected"),
    [
        ("L36A", r"D:\\workspace\\L36A手控\\release", "L36"),
        ("L50SMAX", r"D:\\workspace\\L50Smax\\release", "L50"),
        ("", r"D:\\workspace\\L39-零重力\\主板程序", "L39"),
        ("未知型号", r"D:\\workspace\\foo\\bar", "未知系列"),
    ],
)
def test_guess_series_from_model_or_path(model: str, dirpath: str, expected: str):
    assert guess_series_from_model_or_path(model, dirpath) == expected



def test_find_handcontrol_folders_filters_and_sorts(tmp_path: Path):
    a = tmp_path / "A_folder"
    a.mkdir()
    (a / "YJ-L50S-3122MG-791_UI_118.3.10.ROM").write_text("rom", encoding="utf-8")
    (a / "firmware.pkg").write_text("pkg", encoding="utf-8")

    b = tmp_path / "B_folder"
    b.mkdir()
    (b / "ITE_NOR.ROM").write_text("rom", encoding="utf-8")
    (b / "ITE_NOR.PKG").write_text("pkg", encoding="utf-8")

    ignored1 = tmp_path / "CH341SER" / "skip1"
    ignored1.mkdir(parents=True)
    (ignored1 / "L99_v1.0.0.ROM").write_text("rom", encoding="utf-8")
    (ignored1 / "x.pkg").write_text("pkg", encoding="utf-8")

    ignored2 = tmp_path / "接线图" / "skip2"
    ignored2.mkdir(parents=True)
    (ignored2 / "L100_v2.0.0.ROM").write_text("rom", encoding="utf-8")
    (ignored2 / "x.pkg").write_text("pkg", encoding="utf-8")

    not_match = tmp_path / "C_only_rom"
    not_match.mkdir()
    (not_match / "L77_v1.0.0.ROM").write_text("rom", encoding="utf-8")

    results = find_handcontrol_folders(str(tmp_path))

    assert len(results) == 2
    assert [Path(item["path"]).name for item in results] == ["A_folder", "B_folder"]

    first = results[0]
    assert first["model"] == "L50S"
    assert first["version"] == "V118.3.10"
    assert first["rom_file"].endswith(".ROM")
    assert first["pkg_file"].lower().endswith(".pkg")
    assert "A_folder" in first["label"]

    second = results[1]
    assert second["model"] == "未知型号"
    assert second["version"] == ""
    assert "B_folder" in second["label"]



def test_find_handcontrol_folders_falls_back_to_path_for_model_and_version(tmp_path: Path):
    target = tmp_path / "L35A手控UI" / "NOLLLOG_V17.3.2"
    target.mkdir(parents=True)
    (target / "ITE_NOR.ROM").write_text("rom", encoding="utf-8")
    (target / "ITE_NOR.PKG").write_text("pkg", encoding="utf-8")

    results = find_handcontrol_folders(str(tmp_path))

    assert len(results) == 1
    assert results[0]["model"] == "L35A"
    assert results[0]["version"] == "V17.3.2"



def test_parse_rom_filename_uses_configurable_patterns(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(file_scan, "SCAN_MODEL_PATTERNS", [r"MODEL-(X\d+)"])
    monkeypatch.setattr(file_scan, "SCAN_VERSION_PATTERNS", [r"REV-(\d+\.\d+)"])

    model, version = file_scan.parse_rom_filename("firmware_MODEL-X55_REV-2.5.ROM")

    assert model == "X55"
    assert version == "V2.5"



def test_guess_model_from_path_uses_configurable_patterns(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(file_scan, "SCAN_PATH_MODEL_PATTERNS", [r"(HC\d{2})"])

    assert file_scan.guess_model_from_path(r"D:\\workspace\\release\\HC88\\pkg") == "HC88"



def test_guess_version_from_path_uses_configurable_patterns(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(file_scan, "SCAN_PATH_VERSION_PATTERNS", [r"REL-(\d+\.\d+_\d+)"])

    assert file_scan.guess_version_from_path(r"D:\\workspace\\REL-9.8_007\\pkg") == "V9.8_007"



def test_find_handcontrol_folders_uses_configurable_extensions_and_excludes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(file_scan, "SCAN_ROM_EXTENSIONS", [".bin"])
    monkeypatch.setattr(file_scan, "SCAN_PKG_EXTENSIONS", [".pack"])
    monkeypatch.setattr(file_scan, "SCAN_EXCLUDE_DIR_KEYWORDS", ["ignore_me"])
    monkeypatch.setattr(file_scan, "SCAN_MODEL_PATTERNS", [r"FW-(Z\d+)"])
    monkeypatch.setattr(file_scan, "SCAN_VERSION_PATTERNS", [r"VER-(\d+\.\d+)"])

    good = tmp_path / "ok"
    good.mkdir()
    (good / "FW-Z88_VER-3.7.bin").write_text("rom", encoding="utf-8")
    (good / "bundle.pack").write_text("pkg", encoding="utf-8")

    ignored = tmp_path / "ignore_me" / "child"
    ignored.mkdir(parents=True)
    (ignored / "FW-Z99_VER-9.9.bin").write_text("rom", encoding="utf-8")
    (ignored / "bundle.pack").write_text("pkg", encoding="utf-8")

    results = file_scan.find_handcontrol_folders(str(tmp_path))

    assert len(results) == 1
    assert results[0]["model"] == "Z88"
    assert results[0]["version"] == "V3.7"
    assert results[0]["rom_file"].endswith(".bin")
    assert results[0]["pkg_file"].endswith(".pack")


def test_scan_firmware_assets_uses_catalog_types(tmp_path: Path):
    handcontrol_dir = tmp_path / "L35A手控UI" / "release"
    handcontrol_dir.mkdir(parents=True)
    (handcontrol_dir / "YJ-L35A_UI_1.2.3.ROM").write_text("rom", encoding="utf-8")
    (handcontrol_dir / "firmware.pkg").write_text("pkg", encoding="utf-8")

    voice_dir = tmp_path / "语音板"
    voice_dir.mkdir()
    (voice_dir / "voice_v2.0.0.bin").write_text("voice", encoding="utf-8")

    assets, errors = scan_firmware_assets(str(tmp_path))

    assert errors == []
    assert len(assets) == 2
    assert [item["firmware_type"] for item in assets] == ["handcontrol_ui", "voice"]
    assert assets[0]["series"] == "L35"
    assert assets[0]["model_directory_name"] == "L35A手控UI"
    assert assets[0]["flash_mode"] == "auto_usb"
    assert assets[0]["usb_flow"] == "paired_files"
    assert assets[1]["firmware_label"] == "语音程序"
    assert "tool_dir" in assets[1]


def test_scan_firmware_assets_uses_expanded_catalog_keywords_and_excludes(tmp_path: Path):
    mainboard_dir = tmp_path / "L36配置" / "L36主板"
    mainboard_dir.mkdir(parents=True)
    (mainboard_dir / "main_v1.0.0.bin").write_text("main", encoding="utf-8")

    bluetooth_dir = tmp_path / "L36配置" / "蓝牙—语音"
    bluetooth_dir.mkdir(parents=True)
    (bluetooth_dir / "bt_v2.0.0.hex").write_text("bt", encoding="utf-8")

    ignored_photo_dir = tmp_path / "L36配置" / "照片" / "语音板"
    ignored_photo_dir.mkdir(parents=True)
    (ignored_photo_dir / "voice_v3.0.0.bin").write_text("voice", encoding="utf-8")

    ignored_old_dir = tmp_path / "L36配置" / "旧" / "快捷键程序"
    ignored_old_dir.mkdir(parents=True)
    (ignored_old_dir / "shortcut_v4.0.0.bin").write_text("shortcut", encoding="utf-8")

    assets, errors = scan_firmware_assets(str(tmp_path))

    assert errors == []
    assert [item["firmware_type"] for item in assets] == ["mainboard", "music_bt"]
    assert [item["model_directory_name"] for item in assets] == ["L36配置", "L36配置"]
    assert all(Path(item["model_directory_path"]).name == "L36配置" for item in assets)


def test_segmented_screen_before_handcontrol_ui_in_catalog(tmp_path: Path):
    """P0-3: '断码屏' directory with ROM+PKG should match segmented_screen, not handcontrol_ui."""
    seg_dir = tmp_path / "L39MAX" / "断码屏亚克力手控"
    seg_dir.mkdir(parents=True)
    (seg_dir / "YJ-L39max_UI_125.3.2.ROM").write_text("rom", encoding="utf-8")
    (seg_dir / "ITEPKG03.PKG").write_text("pkg", encoding="utf-8")

    assets, errors = scan_firmware_assets(str(tmp_path))

    assert errors == []
    assert len(assets) == 1
    assert assets[0]["firmware_type"] == "segmented_screen", f"Expected segmented_screen, got {assets[0]['firmware_type']}"


def test_music_bt_detects_mot_files(tmp_path: Path):
    """P0-2: Bluetooth directories with .mot files should be detected as music_bt."""
    bt_dir = tmp_path / "L36" / "蓝牙板"
    bt_dir.mkdir(parents=True)
    (bt_dir / "YJ_Bt_Eng_Massage_R5F104BC_Pro_V15.mot").write_text("bt", encoding="utf-8")

    assets, errors = scan_firmware_assets(str(tmp_path))

    assert errors == []
    assert len(assets) == 1
    assert assets[0]["firmware_type"] == "music_bt", f"Expected music_bt, got {assets[0]['firmware_type']}"


def test_movement_3d_detects_mot_files(tmp_path: Path):
    """P0-2: 3D机芯 directories with .mot files should be detected as movement_3d."""
    motor_dir = tmp_path / "L36" / "3d机芯板"
    motor_dir.mkdir(parents=True)
    (motor_dir / "motor_v1.mot").write_text("motor", encoding="utf-8")

    assets, errors = scan_firmware_assets(str(tmp_path))

    assert errors == []
    assert len(assets) == 1
    assert assets[0]["firmware_type"] == "movement_3d", f"Expected movement_3d, got {assets[0]['firmware_type']}"


def test_version_extracted_from_space_separated_rom(tmp_path: Path):
    """P0-1: 'ITE_NOR 120.3.1.ROM' should extract version V120.3.1."""
    hand_dir = tmp_path / "L36" / "手控"
    hand_dir.mkdir(parents=True)
    (hand_dir / "ITE_NOR 120.3.1.ROM").write_text("rom", encoding="utf-8")
    (hand_dir / "ITEPKG03.PKG").write_text("pkg", encoding="utf-8")

    assets, errors = scan_firmware_assets(str(tmp_path))

    assert errors == []
    assert len(assets) == 1
    assert assets[0]["model"] == "L36"
    assert assets[0]["version"] == "V120.3.1", f"Expected V120.3.1, got '{assets[0]['version']}'"
