from pathlib import Path

import pytest

import handcontrol.core.file_scan as file_scan
from handcontrol.core.file_scan import (
    find_handcontrol_folders,
    guess_model_from_path,
    guess_version_from_path,
    parse_rom_filename,
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

    ignored2 = tmp_path / "主板程序" / "skip2"
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

