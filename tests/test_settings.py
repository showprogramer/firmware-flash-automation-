from pathlib import Path

import pytest

import core.settings as settings
from core.settings import _as_str_list, load_toml_config


def test_load_toml_config_missing_file(tmp_path: Path):
    cfg, status, err = load_toml_config(tmp_path / "missing.toml")
    assert cfg == {}
    assert status == "missing"
    assert err == ""



def test_load_toml_config_ok(tmp_path: Path):
    p = tmp_path / "ok.toml"
    p.write_text("[paths]\nroot_dir='D:/x'\n", encoding="utf-8")

    cfg, status, err = load_toml_config(p)

    assert status == "ok"
    assert err == ""
    assert cfg["paths"]["root_dir"] == "D:/x"



def test_load_toml_config_parse_error(tmp_path: Path):
    p = tmp_path / "bad.toml"
    p.write_text("[paths\nroot_dir='x'", encoding="utf-8")

    cfg, status, err = load_toml_config(p)

    assert cfg == {}
    assert status == "parse_error"
    assert err



def test_load_toml_config_parser_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    p = tmp_path / "ok.toml"
    p.write_text("[paths]\nroot_dir='D:/x'\n", encoding="utf-8")

    import builtins

    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name in ("tomllib", "tomli"):
            raise ModuleNotFoundError(name)
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    cfg, status, err = load_toml_config(p)

    assert cfg == {}
    assert status == "parser_missing"
    assert "tomli" in err



def test_as_str_list_falls_back_to_default_on_invalid_value():
    assert _as_str_list("bad", [".rom"], lower=True) == [".rom"]



def test_as_str_list_falls_back_to_default_on_empty_list():
    assert _as_str_list([], [".rom"], lower=True) == [".rom"]



def test_scan_defaults_are_available():
    assert settings.SCAN_ROM_EXTENSIONS == [".rom"]
    assert settings.SCAN_PKG_EXTENSIONS == [".pkg"]
    assert settings.SCAN_EXCLUDE_DIR_KEYWORDS
    assert settings.SCAN_MODEL_PATTERNS
    assert settings.SCAN_VERSION_PATTERNS
    assert settings.SCAN_PATH_MODEL_PATTERNS

