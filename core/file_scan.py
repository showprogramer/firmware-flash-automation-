import os
import re
from pathlib import Path

from core.types import HandcontrolFolder


def parse_rom_filename(name: str) -> tuple[str, str]:
    """
    Parse model and version from ROM filename.
    Supported examples:
      YJ-L50S-3122MG-791_UI_118.3.10.ROM
      ITE_NOR_yj_massage_4d_music_L36_v34.3.2.ROM
      ITE_NOR.ROM
    """
    name_no_ext = Path(name).stem

    model_match = re.search(r'(?:^|[_\-])((L\d+[A-Za-z]*))(?:[_\-]|$)', name_no_ext, re.IGNORECASE)
    model = model_match.group(1).upper() if model_match else ""

    ver_match = re.search(r'[Vv](\d+\.\d+(?:\.\d+)?)', name_no_ext)
    if not ver_match:
        ver_match = re.search(r'_UI_(\d+\.\d+(?:\.\d+)?)', name_no_ext)
    if not ver_match:
        ver_match = re.search(r'_(\d+\.\d+\.\d+)$', name_no_ext)
    version = "V" + ver_match.group(1) if ver_match else ""

    return model, version


def guess_model_from_path(dirpath: str) -> str:
    """Guess model from path segments."""
    for part in reversed(Path(dirpath).parts):
        m = re.search(r'\b(L\d+[A-Za-z]*(?:max|pro|s)?)\b', part, re.IGNORECASE)
        if m:
            return m.group(1).upper()
    return "未知型号"


def find_handcontrol_folders(root: str) -> list[HandcontrolFolder]:
    """
    Recursively scan root and find folders containing both .ROM and .PKG files.
    """
    results: list[HandcontrolFolder] = []
    root_path = Path(root)

    for dirpath, _, filenames in os.walk(root_path):
        if "CH341SER" in dirpath or "主板程序" in dirpath:
            continue

        rom_files = [f for f in filenames if f.lower().endswith(".rom")]
        pkg_files = [f for f in filenames if f.lower().endswith(".pkg")]

        if rom_files and pkg_files:
            rom = rom_files[0]
            pkg = pkg_files[0]
            model, version = parse_rom_filename(rom)
            if not model:
                model = guess_model_from_path(dirpath)

            results.append(
                {
                    "path": dirpath,
                    "rom_file": rom,
                    "pkg_file": pkg,
                    "model": model,
                    "version": version,
                    "label": f"{model}  {version}  [{Path(dirpath).name}]",
                }
            )

    results.sort(key=lambda x: x["path"])
    return results
