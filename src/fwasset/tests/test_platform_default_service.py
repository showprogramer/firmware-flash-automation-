"""Tests for platform_default_service.set_default_variant — 写入 平台配置.toml。"""
from __future__ import annotations

from pathlib import Path

from fwasset.core.platform_config import load_platform_config
from fwasset.core.services.platform_default_service import set_default_variant


def _silent(_msg: str) -> None:
    pass


class TestSetDefaultVariant:
    def test_creates_config_when_missing(self, tmp_path: Path):
        result = set_default_variant(str(tmp_path), "标准单机芯3D", "主板程序", "量产_默认", log_fn=_silent)
        assert result["ok"] is True
        assert result["code"] == "ok"
        assert result["payload"]["previous_variant"] == ""
        loaded = load_platform_config(tmp_path)
        assert loaded[0].platform_name == "标准单机芯3D"
        assert loaded[0].defaults["主板程序"] == "量产_默认"

    def test_updates_existing_entry_and_preserves_others(self, tmp_path: Path):
        (tmp_path / "平台配置.toml").write_text(
            "\n".join(
                [
                    "[[platform]]",
                    'name = "标准单机芯3D"',
                    "[platform.defaults]",
                    '"主板程序" = "量产_默认"',
                    '"手控UI" = "量产中性_默认"',
                    "",
                    "[[platform]]",
                    'name = "双机芯-上3D-下2D"',
                    "[platform.defaults]",
                    '"主板程序" = "量产_默认"',
                ]
            ),
            encoding="utf-8",
        )
        result = set_default_variant(str(tmp_path), "标准单机芯3D", "主板程序", "防夹功能", log_fn=_silent)
        assert result["ok"] is True
        assert result["payload"]["previous_variant"] == "量产_默认"

        loaded = {p.platform_name: p for p in load_platform_config(tmp_path)}
        # 目标条目更新
        assert loaded["标准单机芯3D"].defaults["主板程序"] == "防夹功能"
        # 同平台其他模块与另一平台原样保留
        assert loaded["标准单机芯3D"].defaults["手控UI"] == "量产中性_默认"
        assert loaded["双机芯-上3D-下2D"].defaults["主板程序"] == "量产_默认"

    def test_creates_new_platform_entry_in_existing_file(self, tmp_path: Path):
        (tmp_path / "平台配置.toml").write_text(
            '[[platform]]\nname = "标准单机芯3D"\n[platform.defaults]\n"主板程序" = "量产_默认"\n',
            encoding="utf-8",
        )
        result = set_default_variant(str(tmp_path), "新平台", "腿部程序", "", log_fn=_silent)
        assert result["ok"] is True
        loaded = {p.platform_name: p for p in load_platform_config(tmp_path)}
        assert loaded["新平台"].defaults == {"腿部程序": ""}
        assert loaded["标准单机芯3D"].defaults == {"主板程序": "量产_默认"}

    def test_empty_variant_name_is_allowed(self, tmp_path: Path):
        result = set_default_variant(str(tmp_path), "标准单机芯3D", "腿部程序", "", log_fn=_silent)
        assert result["ok"] is True
        loaded = load_platform_config(tmp_path)
        assert loaded[0].defaults["腿部程序"] == ""

    def test_rejects_empty_platform_or_module(self, tmp_path: Path):
        result = set_default_variant(str(tmp_path), "", "主板程序", "x", log_fn=_silent)
        assert result["ok"] is False
        assert result["code"] == "invalid_args"

        result = set_default_variant(str(tmp_path), "平台", "", "x", log_fn=_silent)
        assert result["ok"] is False
        assert result["code"] == "invalid_args"

    def test_rejects_missing_root_dir(self, tmp_path: Path):
        missing = tmp_path / "不存在的目录"
        result = set_default_variant(str(missing), "平台", "主板程序", "x", log_fn=_silent)
        assert result["ok"] is False
        assert result["code"] == "invalid_args"
        assert "不存在" in result["message"]
