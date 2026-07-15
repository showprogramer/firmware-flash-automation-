"""Tests for platform_default_service.set_default_variant — 写入 平台配置.toml。"""
from __future__ import annotations

from pathlib import Path

from fwasset.core.platform_config import load_platform_config
from fwasset.core.services.platform_default_service import (
    set_default_variant,
    set_module_default_for_model,
)


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


class TestSetModuleDefaultForModel:
    def test_writes_same_module_default_to_all_platform_blocks(self, tmp_path: Path):
        """型号+模块默认：同步所有 [[platform]] 块，不按「标准单机芯3D」分叉。"""
        (tmp_path / "平台配置.toml").write_text(
            "\n".join(
                [
                    "[[platform]]",
                    'name = "标准单机芯3D"',
                    "[platform.defaults]",
                    '"主板程序" = "量产_默认"',
                    '"蓝牙程序" = "中文-通用_默认"',
                    "",
                    "[[platform]]",
                    'name = "双机芯-上3D-下2D"',
                    "[platform.defaults]",
                    '"主板程序" = "量产_默认"',
                    '"蓝牙程序" = "英文-通用"',
                ]
            ),
            encoding="utf-8",
        )
        result = set_module_default_for_model(
            str(tmp_path),
            "蓝牙程序",
            "中文-通用_默认",
            log_fn=_silent,
            model_name="L36",
        )
        assert result["ok"] is True
        assert "「L36」蓝牙程序默认版本" in result["message"]
        loaded = {p.platform_name: p for p in load_platform_config(tmp_path)}
        assert loaded["标准单机芯3D"].defaults["蓝牙程序"] == "中文-通用_默认"
        assert loaded["双机芯-上3D-下2D"].defaults["蓝牙程序"] == "中文-通用_默认"
        # 未改动的其它模块保持原样
        assert loaded["标准单机芯3D"].defaults["主板程序"] == "量产_默认"

    def test_creates_placeholder_block_when_config_missing(self, tmp_path: Path):
        """无方案/无 platform 时才建内部块「默认」。"""
        result = set_module_default_for_model(
            str(tmp_path), "主板程序", "量产_默认", log_fn=_silent, model_name="L36"
        )
        assert result["ok"] is True
        loaded = load_platform_config(tmp_path)
        assert len(loaded) == 1
        assert loaded[0].platform_name == "默认"
        assert loaded[0].defaults["主板程序"] == "量产_默认"

    def test_bootstraps_platform_blocks_from_scheme_config(self, tmp_path: Path):
        """无 toml 但方案已声明 platform：首次设默认按方案名建块，而非孤岛「默认」。"""
        scheme = tmp_path / "定制" / "西班牙"
        scheme.mkdir(parents=True)
        (scheme / "方案配置.toml").write_text(
            'name = "西班牙"\nplatform = "标准单机芯3D"\n',
            encoding="utf-8",
        )
        scheme2 = tmp_path / "定制" / "马来西亚"
        scheme2.mkdir(parents=True)
        (scheme2 / "方案配置.toml").write_text(
            'name = "马来西亚"\nplatform = "标准单机芯3D"\n',
            encoding="utf-8",
        )
        scheme3 = tmp_path / "定制" / "双机芯客户"
        scheme3.mkdir(parents=True)
        (scheme3 / "方案配置.toml").write_text(
            'name = "双机芯客户"\nplatform = "双机芯-上3D-下2D"\n',
            encoding="utf-8",
        )

        result = set_module_default_for_model(
            str(tmp_path),
            "主板程序",
            "量产_默认",
            log_fn=_silent,
            model_name="L36",
        )
        assert result["ok"] is True
        loaded = {p.platform_name: p for p in load_platform_config(tmp_path)}
        assert set(loaded) == {"标准单机芯3D", "双机芯-上3D-下2D"}
        assert "默认" not in loaded
        assert loaded["标准单机芯3D"].defaults["主板程序"] == "量产_默认"
        assert loaded["双机芯-上3D-下2D"].defaults["主板程序"] == "量产_默认"
        assert set(result["payload"]["updated_platforms"]) == {
            "标准单机芯3D",
            "双机芯-上3D-下2D",
        }

    def test_ensure_adds_missing_scheme_platform_to_existing_config(self, tmp_path: Path):
        """已有 toml 时补全方案声明但尚未建块的 platform，不删旧块。"""
        (tmp_path / "平台配置.toml").write_text(
            '[[platform]]\nname = "标准单机芯3D"\n[platform.defaults]\n"主板程序" = "量产_默认"\n',
            encoding="utf-8",
        )
        scheme = tmp_path / "定制" / "新客"
        scheme.mkdir(parents=True)
        (scheme / "方案配置.toml").write_text(
            'name = "新客"\nplatform = "双机芯-上3D-下2D"\n',
            encoding="utf-8",
        )
        result = set_module_default_for_model(
            str(tmp_path), "蓝牙程序", "中文", log_fn=_silent, model_name="L36"
        )
        assert result["ok"] is True
        loaded = {p.platform_name: p for p in load_platform_config(tmp_path)}
        assert loaded["标准单机芯3D"].defaults["主板程序"] == "量产_默认"
        assert loaded["标准单机芯3D"].defaults["蓝牙程序"] == "中文"
        assert loaded["双机芯-上3D-下2D"].defaults["蓝牙程序"] == "中文"

    def test_rewrites_typo_ban_key_to_board_across_blocks(self, tmp_path: Path):
        """历史笔误「机芯版」写入后归一为「机芯板」；多块同义键不重复。"""
        (tmp_path / "平台配置.toml").write_text(
            "\n".join(
                [
                    "[[platform]]",
                    'name = "标准单机芯3D"',
                    "[platform.defaults]",
                    '"3D机芯版程序" = ""',
                    "",
                    "[[platform]]",
                    'name = "双机芯-上3D-下2D"',
                    "[platform.defaults]",
                    '"3D机芯板程序" = "旧值"',
                    '"3D机芯版程序" = "不应并存"',
                ]
            ),
            encoding="utf-8",
        )
        result = set_module_default_for_model(
            str(tmp_path),
            "3D机芯板程序",
            "YJ_ZD_3D",
            log_fn=_silent,
            model_name="L36",
        )
        assert result["ok"] is True
        assert result["payload"]["module_dir"] == "3D机芯板程序"
        loaded = {p.platform_name: p for p in load_platform_config(tmp_path)}
        for block in loaded.values():
            keys_3d = [k for k in block.defaults if "机芯" in k and "3D" in k]
            assert keys_3d == ["3D机芯板程序"]
            assert block.defaults["3D机芯板程序"] == "YJ_ZD_3D"
            assert "3D机芯版程序" not in block.defaults

    def test_canonical_module_dir_normalizes_typo(self):
        from fwasset.core.platform_config import canonical_module_dir

        assert canonical_module_dir("3D机芯版程序") == "3D机芯板程序"
        assert canonical_module_dir("2D机芯板程序") == "2D机芯板程序"
        assert canonical_module_dir("  3D机芯版程序  ") == "3D机芯板程序"
