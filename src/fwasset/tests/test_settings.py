from pathlib import Path

import pytest

import fwasset.core.settings as settings
from fwasset.core.settings import _resolve_runtime_dir, ensure_runtime_dir, load_toml_config


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


def test_scan_defaults_are_available():
    assert isinstance(settings.TOOL_ROOT, str)
    assert settings.SCAN_ROM_EXTENSIONS == [".rom"]
    assert settings.SCAN_PKG_EXTENSIONS == [".pkg"]
    assert settings.SCAN_EXCLUDE_DIR_KEYWORDS
    assert settings.SCAN_MODEL_PATTERNS
    assert settings.SCAN_VERSION_PATTERNS
    assert settings.SCAN_PATH_MODEL_PATTERNS



def test_runtime_dir_defaults_to_project_runtime():
    runtime_dir = _resolve_runtime_dir(Path("D:/app"), env_value="")

    assert runtime_dir == Path("D:/app/.runtime")


def test_runtime_dir_env_override_resolves_relative_to_app_root():
    runtime_dir = _resolve_runtime_dir(Path("D:/app"), env_value="local-runtime")

    assert runtime_dir == Path("D:/app/local-runtime")


def test_ensure_runtime_dir_creates_directory(tmp_path: Path):
    runtime_dir = ensure_runtime_dir(tmp_path / "runtime")

    assert runtime_dir.is_dir()
