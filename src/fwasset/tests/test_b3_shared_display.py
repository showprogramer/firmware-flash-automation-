from __future__ import annotations

from pathlib import Path

from fwasset.core.asset_index import save_assets
from fwasset.core.file_scan import scan_firmware_assets
from fwasset.core.model_config import SharedModuleRef, save_shared_module
from fwasset.core.types import FirmwareAsset
from fwasset.ui_common.view_models.scheme_workbench_model import SchemeWorkbenchModel


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _asset(path: Path, *, model_root: Path, model_name: str) -> FirmwareAsset:
    return {
        "series": "L36",
        "firmware_type": "shortcut_key",
        "firmware_label": "快捷键程序",
        "flash_mode": "auto_usb",
        "usb_flow": "directory_copy",
        "model": model_name,
        "version": "V1",
        "model_directory_name": model_root.name,
        "model_directory_path": str(model_root),
        "path": str(path),
        "directory_name": path.name,
        "files": [path.name + ".bin"],
        "modified_time": 0.0,
        "tool_name": "",
        "tool_path": "",
        "tool_dir": "",
        "label": "快捷键程序",
        "category": "common",
        "platform": "",
        "scheme_name": "",
        "scheme_path": "",
    }


def _bind_workspace(root: Path, db_path: Path) -> SchemeWorkbenchModel:
    assets, errors = scan_firmware_assets(str(root))
    assert not errors
    save_assets(assets, str(root), path=db_path)
    model = SchemeWorkbenchModel()
    model.bind(db_path, root)
    return model


def test_all_modules_decorate_existing_row_with_shared_source(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    source_root = workspace / "L36程序"
    target_root = workspace / "L36双机芯-上3D-下2D程序"
    _write(source_root / "型号配置.toml", 'model_id = "l36"\n')
    _write(target_root / "型号配置.toml", 'model_id = "l36-dual"\n')
    source_path = source_root / "通用" / "快捷键程序"
    target_path = target_root / "通用" / "快捷键程序"
    _write(source_path / "shortcut.bin")
    _write(target_path / "shortcut-local.bin")
    save_shared_module(
        target_root,
        SharedModuleRef(
            module_key="快捷键程序",
            source_model_id="l36",
            source_group="l36-common",
            source_module="快捷键程序",
            source_relative_path="L36程序/通用/快捷键程序",
        ),
    )

    model = _bind_workspace(workspace, tmp_path / "index.db")
    cards = model.get_all_modules("L36双机芯-上3D-下2D")
    shortcut = [card for card in cards if card.asset["firmware_label"] == "快捷键程序"]

    assert len(shortcut) == 1
    card = shortcut[0]
    assert card.shared_state == "shared_hit"
    assert card.shared_source_label == "L36"
    assert card.asset["path"] == str(target_path)
    assert card.effective_asset is not None
    assert card.effective_asset["path"] == str(source_path)


def test_missing_shared_source_does_not_fall_back_to_local(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    target_root = workspace / "L36双机芯-上3D-下2D程序"
    _write(target_root / "型号配置.toml", 'model_id = "l36-dual"\n')
    target_path = target_root / "通用" / "快捷键程序"
    _write(target_path / "shortcut-local.bin")
    save_shared_module(
        target_root,
        SharedModuleRef(
            module_key="快捷键程序",
            source_model_id="l36",
            source_group="l36-common",
            source_module="快捷键程序",
            source_relative_path="L36程序/通用/快捷键程序",
        ),
    )

    model = _bind_workspace(workspace, tmp_path / "index.db")
    cards = model.get_all_modules("L36双机芯-上3D-下2D")
    card = next(card for card in cards if card.asset["firmware_label"] == "快捷键程序")

    assert card.shared_state == "shared_missing"
    assert card.shared_reason == "source_not_imported"
    assert card.effective_asset is None