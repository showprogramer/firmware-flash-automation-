"""R8：set_shared_module 支持 follow_asset 登记测试。"""

from __future__ import annotations

from pathlib import Path

from fwasset.core.model_config import load_shared_modules, save_model_id
from fwasset.core.services.shared_module_service import set_shared_module
from fwasset.core.types import FirmwareAsset


def _asset(path: Path, label: str = "快捷键程序") -> FirmwareAsset:
    return FirmwareAsset(
        series="",
        firmware_type="shortcut_key",
        firmware_label=label,
        flash_mode="disabled",
        usb_flow="",
        model="",
        version="",
        model_directory_name="L36",
        model_directory_path=str(path.parent.parent.parent),
        path=str(path),
        directory_name=path.name,
        files=[],
        modified_time=0.0,
        tool_name="",
        tool_path="",
        tool_dir="",
        label="",
        category="common",
        platform="",
        scheme_name="",
        scheme_path="",
    )


def test_set_shared_module_follow_asset(tmp_path: Path):
    ws = tmp_path / "ws"
    src_root = ws / "L36程序"
    tgt_root = ws / "L50程序"
    src_root.mkdir(parents=True)
    tgt_root.mkdir(parents=True)
    save_model_id(src_root, "l36")
    save_model_id(tgt_root, "l50")
    variant = src_root / "通用" / "快捷键" / "贝乐"
    variant.mkdir(parents=True)

    res = set_shared_module(
        tgt_root,
        _asset(variant),
        ws,
        mode="follow_asset",
        log_fn=lambda _m: None,
    )
    assert res["ok"] is True, res["message"]
    refs = {r.module_key: r for r in load_shared_modules(tgt_root)}
    ref = refs["快捷键程序"]
    assert ref.mode == "follow_asset"
    assert ref.source_relative_path == "L36程序/通用/快捷键/贝乐"
    assert ref.source_platform == ""
    # 落盘格式：mode 键存在（非 static）
    text = (tgt_root / "型号配置.toml").read_text(encoding="utf-8")
    assert 'mode = "follow_asset"' in text


def test_set_shared_module_invalid_mode_falls_back_static(tmp_path: Path):
    ws = tmp_path / "ws"
    src_root = ws / "L36程序"
    tgt_root = ws / "L50程序"
    src_root.mkdir(parents=True)
    tgt_root.mkdir(parents=True)
    save_model_id(src_root, "l36")
    save_model_id(tgt_root, "l50")
    variant = src_root / "通用" / "快捷键" / "贝乐"
    variant.mkdir(parents=True)

    res = set_shared_module(
        tgt_root,
        _asset(variant),
        ws,
        mode="follow_nonsense",
        log_fn=lambda _m: None,
    )
    assert res["ok"] is True
    refs = {r.module_key: r for r in load_shared_modules(tgt_root)}
    assert refs["快捷键程序"].mode == "static"
