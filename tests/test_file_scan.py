from pathlib import Path

import pytest

from core.file_scan import find_handcontrol_folders, guess_model_from_path, parse_rom_filename


@pytest.mark.parametrize(
    ("filename", "expected_model", "expected_version"),
    [
        ("YJ-L50S-3122MG-791_UI_118.3.10.ROM", "L50S", "V118.3.10"),
        ("ITE_NOR_yj_massage_4d_music_L36_v34.3.2.ROM", "L36", "V34.3.2"),
        ("ITE_NOR.ROM", "", ""),
        ("abc_L88_pro_v1.2.3.rom", "L88", "V1.2.3"),
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
        (r"D:\\workspace\\foo\\bar", "未知型号"),
    ],
)
def test_guess_model_from_path(dirpath: str, expected: str):
    assert guess_model_from_path(dirpath) == expected


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
