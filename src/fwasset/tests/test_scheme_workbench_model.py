"""Tests for SchemeWorkbenchModel: scheme module listing with platform fallback.

These tests build a fake L36-like directory tree on disk, scan it into a temp
SQLite index, then verify the view-model returns the correct custom + fallback
module lists. They are pure data-layer tests (no display), so not marked ui.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fwasset.core.asset_index import save_assets
from fwasset.core.file_scan import scan_firmware_assets
from fwasset.ui.view_models.scheme_workbench_model import SchemeWorkbenchModel


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture()
def l36_tree(tmp_path: Path) -> Path:
    """Build a minimal L36-shaped firmware tree.

    通用 has 主板程序 (量产_默认 default + 防夹功能 variant), a single-variant
    3D机芯版程序 and 腿部程序 (no _默认 subdir → dir itself is the asset).
    定制/西班牙 only ships 主板程序 → everything else should fall back.
    """
    root = tmp_path / "L36程序"

    # platform config at the model root
    _write(
        root / "平台配置.toml",
        "\n".join(
            [
                "[[platform]]",
                'name = "标准单机芯3D"',
                "[platform.defaults]",
                '"主板程序" = "量产_默认"',
                '"3D机芯版程序" = ""',
                '"腿部程序" = ""',
            ]
        ),
    )

    # 通用 modules
    _write(root / "通用" / "主板程序" / "量产_默认" / "YJ_3DMain_L36_V40.bin")
    _write(root / "通用" / "主板程序" / "防夹功能" / "YJ_3DMain_L36_V24.bin")
    _write(root / "通用" / "3D机芯版程序" / "YJ_ZD_3D_Core_L36_V20.mot")
    _write(root / "通用" / "腿部程序" / "Yj_Foot_L36_V5.hex")

    # 定制 scheme: only ships its own 主板程序
    scheme = root / "定制" / "西班牙"
    _write(scheme / "方案配置.toml", 'name = "西班牙"\nplatform = "标准单机芯3D"\n')
    _write(scheme / "主板程序" / "YJ_3DMain_L36_西班牙_V40.bin")

    return root


def _bind_model(root: Path, tmp_path: Path) -> SchemeWorkbenchModel:
    db = tmp_path / "index.db"
    assets, _errors = scan_firmware_assets(str(root))
    save_assets(assets, str(root), path=db)
    model = SchemeWorkbenchModel()
    model.bind(db, root)
    return model


def test_platform_config_is_loaded_from_scan_root(l36_tree: Path, tmp_path: Path) -> None:
    model = _bind_model(l36_tree, tmp_path)
    assert model._platforms, "平台配置.toml should be loaded from the scan root"
    names = {p.platform_name for p in model._platforms}
    assert "标准单机芯3D" in names


def test_scheme_includes_custom_exclusive_module(l36_tree: Path, tmp_path: Path) -> None:
    model = _bind_model(l36_tree, tmp_path)
    cards = model.get_scheme_modules("L36", "西班牙")
    exclusive = [c for c in cards if c.source_type == "custom_exclusive"]
    labels = {c.asset["firmware_label"] for c in exclusive}
    assert "主板程序" in labels


def test_scheme_falls_back_to_common_default_variant(l36_tree: Path, tmp_path: Path) -> None:
    """主板 is custom, but the scheme has no 3D机芯/腿部 → fall back to 通用."""
    model = _bind_model(l36_tree, tmp_path)
    cards = model.get_scheme_modules("L36", "西班牙")
    fallback = [c for c in cards if c.is_fallback]
    fb_labels = {c.asset["firmware_label"] for c in fallback}
    # single-variant modules with empty default_dir must still fall back.
    # NOTE: firmware_label comes from the catalog ("3D机芯板程序", 板), while the
    # 通用/ directory and 平台配置.toml key are "3D机芯版程序" (版) — the matcher
    # tolerates this discrepancy, so we assert on the catalog label here.
    assert "3D机芯板程序" in fb_labels
    assert "腿部程序" in fb_labels


def test_load_all_models_filters_filename_noise(tmp_path: Path) -> None:
    """A file whose name contains 'L50' under the L36 tree must not create an L50 model.

    The dropdown should reflect the structural model root (L36), not noisy
    per-file parsed models.
    """
    root = tmp_path / "L36程序"
    _write(root / "平台配置.toml", '[[platform]]\nname = "标准单机芯3D"\n[platform.defaults]\n')
    # 通用 mainboard whose filename mentions L50S → would parse model as L50S
    _write(root / "通用" / "主板程序" / "量产_默认" / "YJ_3DMain_L36_V40.bin")
    _write(root / "通用" / "主板程序" / "同L50S" / "YJ_3DMain_L50S_V9.bin")

    model = _bind_model(root, tmp_path)
    models = model.load_all_models()
    assert models == ["L36"], f"expected only structural model L36, got {models}"


def test_scheme_module_tree_groups_variants_under_one_row(tmp_path: Path) -> None:
    """手控UI 有多个变体时，应收成 ONE module row with children, not铺平."""
    root = tmp_path / "L36程序"
    _write(root / "平台配置.toml", '[[platform]]\nname = "标准单机芯3D"\n[platform.defaults]\n')
    # scheme with 3 手控UI variants + 1 主板
    scheme = root / "定制" / "马来" / "方案配置.toml"
    _write(scheme, 'name = "马来"\nplatform = "标准单机芯3D"\n')
    base = root / "定制" / "马来"
    _write(base / "主板程序" / "YJ_3DMain_L36_V40.bin")
    _write(base / "手控UI" / "L36 手控UI-A" / "a.rom")
    _write(base / "手控UI" / "L36 手控UI-A" / "a.pkg")
    _write(base / "手控UI" / "L36 手控UI-B" / "b.rom")
    _write(base / "手控UI" / "L36 手控UI-B" / "b.pkg")
    _write(base / "手控UI" / "L36 手控UI-C" / "c.rom")
    _write(base / "手控UI" / "L36 手控UI-C" / "c.pkg")

    model = _bind_model(root, tmp_path)
    tree = model.get_scheme_module_tree("L36", "马来")

    by_label = {row.label: row for row in tree}
    assert "主板程序" in by_label
    assert "手控UI" in by_label
    # 主板 single variant → 1 child (or treated as leaf)
    assert len(by_label["主板程序"].variants) == 1
    # 手控UI three variants grouped under ONE row
    assert len(by_label["手控UI"].variants) == 3


def test_scheme_module_tree_marks_custom_vs_common(l36_tree: Path, tmp_path: Path) -> None:
    """每个模块行应标明是 定制专属 还是 通用默认（不含'回源'字样）。"""
    model = _bind_model(l36_tree, tmp_path)
    tree = model.get_scheme_module_tree("L36", "西班牙")
    by_label = {row.label: row for row in tree}
    # 西班牙 ships 主板程序 → 定制专属
    assert by_label["主板程序"].source_kind == "custom"
    # 西班牙 lacks 3D机芯/腿部 → 通用默认
    assert by_label["3D机芯板程序"].source_kind == "common"
    # the literal word "回源" must never appear in any user-facing label
    for row in tree:
        assert "回源" not in row.source_label
        for v in row.variants:
            assert "回源" not in v.source_label


def test_covered_module_is_not_duplicated_by_fallback(l36_tree: Path, tmp_path: Path) -> None:
    """主板程序 is shipped by the scheme → it must NOT also appear as a fallback."""
    model = _bind_model(l36_tree, tmp_path)
    cards = model.get_scheme_modules("L36", "西班牙")
    mainboard_fallbacks = [
        c for c in cards if c.is_fallback and c.asset["firmware_label"] == "主板程序"
    ]
    assert mainboard_fallbacks == []
