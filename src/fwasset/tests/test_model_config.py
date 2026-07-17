"""Tests for model_config — slug / 型号配置.toml load-save。"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from fwasset.core import config_io
from fwasset.core import model_config as model_config_mod
from fwasset.core.model_config import (
    load_model_config,
    save_model_id,
    slugify_model_id,
)


class TestSlugifyModelId:
    def test_common_program_suffix(self):
        assert slugify_model_id("L50程序") == "l50"
        assert slugify_model_id("L36程序") == "l36"

    def test_dual_core_chinese(self):
        assert slugify_model_id("L36双机芯-上3D-下2D程序") == "l36双机芯-上3d-下2d"

    def test_directory_suffix_and_no_suffix(self):
        assert slugify_model_id("L36目录") == "l36"
        assert slugify_model_id("L50") == "l50"

    def test_dangerous_chars_and_spaces(self):
        assert slugify_model_id("L36  程序") == "l36"
        assert ":" not in slugify_model_id("L36:坏名程序")
        assert slugify_model_id("  --L36--程序  ").startswith("l36") or slugify_model_id(
            "  --L36--程序  "
        ) == "l36"

    def test_empty_fallback(self):
        assert slugify_model_id("") == "model"
        assert slugify_model_id("///") == "model"
        assert slugify_model_id("程序") == "model"


class TestLoadSaveModelConfig:
    def test_missing(self, tmp_path: Path):
        mid, status, err = load_model_config(tmp_path)
        assert mid == ""
        assert status == "missing"
        assert err == ""

    def test_ok(self, tmp_path: Path):
        (tmp_path / "型号配置.toml").write_text(
            'model_id = "l36"\n', encoding="utf-8"
        )
        mid, status, err = load_model_config(tmp_path)
        assert mid == "l36"
        assert status == "ok"
        assert err == ""

    def test_no_id(self, tmp_path: Path):
        (tmp_path / "型号配置.toml").write_text("# only comment\n", encoding="utf-8")
        mid, status, err = load_model_config(tmp_path)
        assert mid == ""
        assert status == "no_id"

        (tmp_path / "型号配置.toml").write_text('model_id = ""\n', encoding="utf-8")
        mid, status, _ = load_model_config(tmp_path)
        assert status == "no_id"

    def test_parse_error(self, tmp_path: Path):
        (tmp_path / "型号配置.toml").write_text("[[broken\n", encoding="utf-8")
        mid, status, err = load_model_config(tmp_path)
        assert mid == ""
        assert status == "parse_error"
        assert err

    def test_parser_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        (tmp_path / "型号配置.toml").write_text('model_id = "x"\n', encoding="utf-8")
        monkeypatch.setattr(model_config_mod, "tomllib", None)
        mid, status, err = load_model_config(tmp_path)
        assert status == "parser_missing"
        assert mid == ""
        assert err

    def test_save_and_reload(self, tmp_path: Path):
        save_model_id(tmp_path, "l50")
        mid, status, _ = load_model_config(tmp_path)
        assert status == "ok"
        assert mid == "l50"

    def test_save_preserves_shared_modules_section(self, tmp_path: Path):
        path = tmp_path / "型号配置.toml"
        path.write_text(
            "\n".join(
                [
                    'model_id = "old"',
                    "",
                    '[shared_modules."快捷键程序"]',
                    'source_model_id = "l36"',
                    'source_group = "l36-single"',
                    'source_module = "快捷键程序"',
                    'source_relative_path = "L36程序/通用/快捷键/贝乐"',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        save_model_id(tmp_path, "new-id")
        text = path.read_text(encoding="utf-8")
        assert 'model_id = "new-id"' in text
        assert '[shared_modules."快捷键程序"]' in text
        assert 'source_model_id = "l36"' in text
        assert 'source_relative_path = "L36程序/通用/快捷键/贝乐"' in text
        mid, status, _ = load_model_config(tmp_path)
        assert status == "ok"
        assert mid == "new-id"

    def test_save_replace_failure_keeps_bytes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        path = tmp_path / "型号配置.toml"
        original = 'model_id = "keep"\n'
        path.write_text(original, encoding="utf-8")
        original_bytes = path.read_bytes()

        def boom(_src: str, _dst: str) -> None:
            raise OSError("replace failed")

        monkeypatch.setattr(config_io.os, "replace", boom)
        with pytest.raises(OSError):
            save_model_id(tmp_path, "other")
        assert path.read_bytes() == original_bytes
        assert list(tmp_path.glob(".型号配置.toml.*.tmp")) == []

    def test_chinese_model_root(self, tmp_path: Path):
        root = tmp_path / "L36双机芯-上3D-下2D程序"
        root.mkdir()
        save_model_id(root, "l36双机芯-上3d-下2d")
        mid, status, _ = load_model_config(root)
        assert status == "ok"
        assert mid == "l36双机芯-上3d-下2d"
