"""Tests for platform_config.py — load_platform_config and default_variant_for."""
from __future__ import annotations

from pathlib import Path

import pytest

from fwasset.core.platform_config import PlatformDefaults, default_variant_for, load_platform_config


def make_platform_toml(tmp_path: Path, content: str) -> Path:
    toml_file = tmp_path / "平台配置.toml"
    toml_file.write_text(content, encoding="utf-8")
    return tmp_path


class TestLoadPlatformConfig:
    def test_returns_empty_when_no_file(self, tmp_path: Path):
        result = load_platform_config(tmp_path)
        assert result == []

    def test_parses_single_platform(self, tmp_path: Path):
        make_platform_toml(
            tmp_path,
            '[[platform]]\nname = "标准单机芯3D"\n[platform.defaults]\n"主板程序" = "量产_默认"\n"手控UI" = "量产中性_默认"\n',
        )
        result = load_platform_config(tmp_path)
        assert len(result) == 1
        assert result[0].platform_name == "标准单机芯3D"
        assert result[0].defaults["主板程序"] == "量产_默认"
        assert result[0].defaults["手控UI"] == "量产中性_默认"

    def test_parses_multiple_platforms(self, tmp_path: Path):
        make_platform_toml(
            tmp_path,
            '[[platform]]\nname = "标准单机芯3D"\n[platform.defaults]\n"主板程序" = "量产_默认"\n\n[[platform]]\nname = "双机芯-上3D-下2D"\n[platform.defaults]\n"主板程序" = "量产_默认"\n"快捷键" = "贝乐"\n',
        )
        result = load_platform_config(tmp_path)
        assert len(result) == 2
        names = [p.platform_name for p in result]
        assert "标准单机芯3D" in names
        assert "双机芯-上3D-下2D" in names

    def test_skips_entry_without_name(self, tmp_path: Path):
        make_platform_toml(
            tmp_path,
            '[[platform]]\n[platform.defaults]\n"主板程序" = "量产_默认"\n',
        )
        result = load_platform_config(tmp_path)
        assert result == []

    def test_returns_empty_on_invalid_toml(self, tmp_path: Path):
        toml_file = tmp_path / "平台配置.toml"
        toml_file.write_bytes(b"[invalid toml\x00\xff")
        result = load_platform_config(tmp_path)
        assert result == []


class TestDefaultVariantFor:
    def _platforms(self) -> list[PlatformDefaults]:
        return [
            PlatformDefaults("标准单机芯3D", {"主板程序": "量产_默认", "手控UI": "量产中性_默认"}),
            PlatformDefaults("双机芯-上3D-下2D", {"主板程序": "量产_默认", "快捷键": "贝乐"}),
        ]

    def test_finds_existing_variant(self):
        result = default_variant_for(self._platforms(), "标准单机芯3D", "主板程序")
        assert result == "量产_默认"

    def test_returns_empty_for_unknown_module(self):
        result = default_variant_for(self._platforms(), "标准单机芯3D", "不存在的模块")
        assert result == ""

    def test_returns_empty_for_unknown_platform(self):
        result = default_variant_for(self._platforms(), "不存在的平台", "主板程序")
        assert result == ""

    def test_empty_platforms_list(self):
        result = default_variant_for([], "标准单机芯3D", "主板程序")
        assert result == ""
