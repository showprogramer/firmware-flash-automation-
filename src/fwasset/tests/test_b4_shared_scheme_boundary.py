"""B4 / B4b / B6：方案回源与共享边界硬化。"""

from __future__ import annotations

from pathlib import Path

from fwasset.core.asset_index import save_assets
from fwasset.core.file_scan import scan_firmware_assets
from fwasset.core.model_config import SharedModuleRef, save_model_id, save_shared_module
from fwasset.ui_common.view_models.scheme_workbench_model import SchemeWorkbenchModel


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _bind(root: Path, db_path: Path) -> SchemeWorkbenchModel:
    assets, errors = scan_firmware_assets(str(root))
    assert not errors
    save_assets(assets, str(root), path=db_path)
    model = SchemeWorkbenchModel()
    model.bind(db_path, root)
    return model


def _setup_dual_with_shared_shortcut(
    tmp_path: Path,
    *,
    with_local_copy: bool,
    with_source: bool = True,
    with_scheme_custom_shortcut: bool = False,
) -> tuple[SchemeWorkbenchModel, Path, Path]:
    """双机芯目标 + 可选 L36 来源；平台 defaults 含快捷键，方案无定制快捷键（除非指定）。"""
    workspace = tmp_path / "workspace"
    source_root = workspace / "L36程序"
    target_root = workspace / "L36双机芯-上3D-下2D程序"

    _write(
        target_root / "平台配置.toml",
        "\n".join(
            [
                "[[platform]]",
                'name = "标准单机芯3D"',
                "[platform.defaults]",
                '"主板程序" = "量产_默认"',
                '"快捷键程序" = ""',
            ]
        ),
    )
    _write(target_root / "通用" / "主板程序" / "量产_默认" / "main.bin")
    if with_local_copy:
        _write(target_root / "通用" / "快捷键" / "本地变体" / "local.hex")

    scheme = target_root / "定制" / "方案A"
    _write(scheme / "方案配置.toml", 'name = "方案A"\nplatform = "标准单机芯3D"\n')
    _write(scheme / "主板程序" / "custom-main.bin")
    if with_scheme_custom_shortcut:
        _write(scheme / "快捷键" / "custom-key.hex")

    save_model_id(target_root, "l36-dual")
    if with_source:
        _write(source_root / "通用" / "快捷键" / "贝乐" / "k.hex")
        save_model_id(source_root, "l36")
        save_shared_module(
            target_root,
            SharedModuleRef(
                module_key="快捷键程序",
                source_model_id="l36",
                source_group="l36-common",
                source_module="快捷键程序",
                source_relative_path="L36程序/通用/快捷键/贝乐",
            ),
        )
    else:
        save_shared_module(
            target_root,
            SharedModuleRef(
                module_key="快捷键程序",
                source_model_id="l36",
                source_group="l36-common",
                source_module="快捷键程序",
                source_relative_path="L36程序/通用/快捷键/贝乐",
            ),
        )

    model = _bind(workspace, tmp_path / "index.db")
    return model, target_root, source_root


def _scheme_labels(model: SchemeWorkbenchModel, model_name: str, scheme: str) -> set[str]:
    tree = model.get_scheme_module_tree(model_name, scheme)
    labels = {row.label for row in tree}
    for row in tree:
        labels.update(str(v.asset.get("firmware_label", "")) for v in row.variants)
        labels.update(v.name for v in row.variants)
    cards = model.get_scheme_modules(model_name, scheme)
    labels.update(str(c.asset.get("firmware_label", "")) for c in cards)
    return {x for x in labels if x}


def test_scheme_skips_local_fallback_when_shared_hit_with_local_copy(tmp_path: Path) -> None:
    """B4b：有共享 + 有本地副本 + 方案无定制 → 方案树无该模块。"""
    model, _target, _source = _setup_dual_with_shared_shortcut(tmp_path, with_local_copy=True)
    labels = _scheme_labels(model, "L36双机芯-上3D-下2D", "方案A")
    assert not any("快捷键" in x for x in labels)
    assert not any(c.shared_state != "local" for c in model.get_scheme_modules("L36双机芯-上3D-下2D", "方案A"))


def test_scheme_skips_module_when_shared_without_local(tmp_path: Path) -> None:
    """有共享 + 无本地 + 方案无定制 → 方案树仍无该模块。"""
    model, _target, _source = _setup_dual_with_shared_shortcut(tmp_path, with_local_copy=False)
    labels = _scheme_labels(model, "L36双机芯-上3D-下2D", "方案A")
    assert not any("快捷键" in x for x in labels)


def test_scheme_keeps_custom_exclusive_despite_shared(tmp_path: Path) -> None:
    """有共享 + 方案有定制专属 → 仍显示定制专属。"""
    model, _target, _source = _setup_dual_with_shared_shortcut(
        tmp_path, with_local_copy=True, with_scheme_custom_shortcut=True
    )
    cards = model.get_scheme_modules("L36双机芯-上3D-下2D", "方案A")
    shortcut = [c for c in cards if "快捷键" in str(c.asset.get("firmware_label", ""))]
    assert len(shortcut) == 1
    assert shortcut[0].source_kind == "custom"
    assert shortcut[0].source_label == "定制专属"
    assert shortcut[0].shared_state == "local"


def test_shared_missing_does_not_fall_back_in_list_or_scheme(tmp_path: Path) -> None:
    """B6：共享 missing + 有本地 → 列表 shared_missing；方案亦不回落本地。"""
    model, _target, _source = _setup_dual_with_shared_shortcut(
        tmp_path, with_local_copy=True, with_source=False
    )
    cards = model.get_all_modules("L36双机芯-上3D-下2D")
    shortcut = next(c for c in cards if "快捷键" in str(c.asset.get("firmware_label", "")))
    assert shortcut.shared_state == "shared_missing"
    assert shortcut.effective_asset is None

    labels = _scheme_labels(model, "L36双机芯-上3D-下2D", "方案A")
    assert not any("快捷键" in x for x in labels)


def test_clear_shared_restores_scheme_fallback_and_local_list(tmp_path: Path) -> None:
    """取消共享后：列表恢复 local；方案可再回源本地通用。"""
    model, target_root, _source = _setup_dual_with_shared_shortcut(tmp_path, with_local_copy=True)
    local_file = target_root / "通用" / "快捷键" / "本地变体" / "local.hex"
    assert local_file.exists()

    result = model.unregister_shared_module("L36双机芯-上3D-下2D", "快捷键程序")
    assert result["ok"] is True
    assert local_file.exists()

    cards = model.get_all_modules("L36双机芯-上3D-下2D")
    shortcut = next(c for c in cards if "快捷键" in str(c.asset.get("firmware_label", "")))
    assert shortcut.shared_state == "local"
    assert shortcut.effective_asset is None

    scheme_cards = model.get_scheme_modules("L36双机芯-上3D-下2D", "方案A")
    scheme_shortcut = [c for c in scheme_cards if "快捷键" in str(c.asset.get("firmware_label", ""))]
    assert len(scheme_shortcut) == 1
    assert scheme_shortcut[0].is_fallback is True
    assert scheme_shortcut[0].source_kind == "common"
    assert "快捷键" in str(scheme_shortcut[0].asset.get("path", ""))
