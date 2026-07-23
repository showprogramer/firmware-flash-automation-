"""Tests for shared_module_service — set/clear shared module registration (Phase B2)."""
from __future__ import annotations

from pathlib import Path

from fwasset.core.model_config import (
    load_model_config,
    load_shared_modules,
    save_model_id,
)
from fwasset.core.services import shared_module_service as sms
from fwasset.core.services.shared_module_service import (
    clear_shared_module,
    set_shared_module,
)
from fwasset.core.types import FirmwareAsset


def make_asset(
    asset_dir: Path,
    *,
    firmware_type: str = "shortcut_key",
    firmware_label: str = "快捷键程序",
    model: str = "L36",
) -> FirmwareAsset:
    asset_dir.mkdir(parents=True, exist_ok=True)
    (asset_dir / "firmware.bin").write_bytes(b"BIN")
    model_dir = asset_dir.parents[1] if "通用" in asset_dir.parts or "定制" in asset_dir.parts else asset_dir.parent
    return {
        "series": model,
        "firmware_type": firmware_type,  # type: ignore[typeddict-item]
        "firmware_label": firmware_label,
        "flash_mode": "tool_launch",
        "usb_flow": "",
        "model": model,
        "version": "V1.0.0",
        "model_directory_name": model_dir.name,
        "model_directory_path": str(model_dir),
        "path": str(asset_dir),
        "directory_name": asset_dir.name,
        "files": ["firmware.bin"],
        "modified_time": 123.0,
        "tool_name": "writer",
        "tool_path": "D:/tools/writer.exe",
        "tool_dir": "writer",
        "label": f"{model} V1.0.0 [{asset_dir.name}]",
        "category": "common",
        "platform": "",
        "scheme_name": "",
        "scheme_path": "",
    }


def _setup_multi_model_workspace(tmp_path: Path) -> tuple[Path, Path, Path, FirmwareAsset]:
    """Multi-model root: ws / L36程序/通用/快捷键/贝乐  +  ws / 双机芯程序/."""
    ws = tmp_path / "ws"
    src_root = ws / "L36程序"
    src_variant = src_root / "通用" / "快捷键" / "贝乐"
    tgt_root = ws / "双机芯程序"
    src_variant.mkdir(parents=True, exist_ok=True)
    tgt_root.mkdir(parents=True, exist_ok=True)
    (src_variant / "key.hex").write_bytes(b"X")
    save_model_id(src_root, "l36")
    asset = make_asset(src_variant, model="L36")
    return ws, src_root, tgt_root, asset


# ---------- Task 1: set_shared_module ----------


def test_set_shared_module_writes_ref(tmp_path: Path):
    ws, src_root, tgt_root, asset = _setup_multi_model_workspace(tmp_path)
    result = set_shared_module(tgt_root, asset, ws)
    assert result["ok"] is True
    assert result["code"] == "ok"
    refs = load_shared_modules(tgt_root)
    assert len(refs) == 1
    ref = refs[0]
    assert ref.module_key == "快捷键程序"
    assert ref.source_model_id == "l36"
    assert ref.source_module == "快捷键程序"
    assert ref.source_relative_path == "L36程序/通用/快捷键/贝乐"
    # target config preserves nothing else but exists
    assert (tgt_root / "型号配置.toml").exists()


def test_source_relative_path_format(tmp_path: Path):
    ws, src_root, tgt_root, asset = _setup_multi_model_workspace(tmp_path)
    set_shared_module(tgt_root, asset, ws)
    refs = load_shared_modules(tgt_root)
    assert refs[0].source_relative_path == "L36程序/通用/快捷键/贝乐"
    # 含源型号目录段；统一正斜杠
    assert "/" in refs[0].source_relative_path
    assert "\\" not in refs[0].source_relative_path


def test_source_no_id(tmp_path: Path):
    ws, src_root, tgt_root, asset = _setup_multi_model_workspace(tmp_path)
    # 删除源型号根的 model_id（删掉 型号配置.toml）
    (src_root / "型号配置.toml").unlink()
    result = set_shared_module(tgt_root, asset, ws)
    assert result["ok"] is False
    assert result["code"] == "source_no_id"
    # 不写
    assert not (tgt_root / "型号配置.toml").exists()


def test_out_of_workspace(tmp_path: Path):
    ws, src_root, tgt_root, asset = _setup_multi_model_workspace(tmp_path)
    # 资产路径在工作区外
    outside = tmp_path / "outside" / "L36程序" / "通用" / "快捷键" / "贝乐"
    outside.mkdir(parents=True, exist_ok=True)
    (outside / "key.hex").write_bytes(b"Y")
    bad_asset = make_asset(outside, model="L36")
    result = set_shared_module(tgt_root, bad_asset, ws)
    assert result["ok"] is False
    assert result["code"] == "out_of_workspace"
    assert not (tgt_root / "型号配置.toml").exists()


def test_conflict_no_overwrite(tmp_path: Path):
    ws, src_root, tgt_root, asset = _setup_multi_model_workspace(tmp_path)
    # 首次写入
    set_shared_module(tgt_root, asset, ws)
    # 第二次同模块、不同来源（改 path），overwrite=False → 冲突，不写
    other_variant = src_root / "通用" / "快捷键" / "量产_默认"
    other_variant.mkdir(parents=True, exist_ok=True)
    (other_variant / "key.hex").write_bytes(b"Z")
    other_asset = make_asset(other_variant, model="L36")
    result = set_shared_module(tgt_root, other_asset, ws, overwrite=False)
    assert result["ok"] is False
    assert result["code"] == "conflict"
    # payload 带现有引用
    existing = result["payload"].get("existing")
    assert existing is not None
    # 原引用不变
    refs = load_shared_modules(tgt_root)
    assert len(refs) == 1
    assert refs[0].source_relative_path == "L36程序/通用/快捷键/贝乐"


def test_conflict_overwrite(tmp_path: Path):
    ws, src_root, tgt_root, asset = _setup_multi_model_workspace(tmp_path)
    set_shared_module(tgt_root, asset, ws)
    other_variant = src_root / "通用" / "快捷键" / "量产_默认"
    other_variant.mkdir(parents=True, exist_ok=True)
    (other_variant / "key.hex").write_bytes(b"Z")
    other_asset = make_asset(other_variant, model="L36")
    result = set_shared_module(tgt_root, other_asset, ws, overwrite=True)
    assert result["ok"] is True
    refs = load_shared_modules(tgt_root)
    assert len(refs) == 1
    assert refs[0].source_relative_path == "L36程序/通用/快捷键/量产_默认"


def test_module_key_inferred_from_asset(tmp_path: Path):
    ws, src_root, tgt_root, asset = _setup_multi_model_workspace(tmp_path)
    result = set_shared_module(tgt_root, asset, ws, module_key="")
    assert result["ok"] is True
    refs = load_shared_modules(tgt_root)
    assert refs[0].module_key == "快捷键程序"  # 来自 firmware_label 规范化


def test_module_key_canonicalization(tmp_path: Path):
    """键规范化：传「机芯版」→ 落盘为「机芯板」。"""
    ws = tmp_path / "ws"
    src_root = ws / "L36程序"
    src_mod = src_root / "通用" / "机芯板" / "V1"
    tgt_root = ws / "双机芯程序"
    src_mod.mkdir(parents=True, exist_ok=True)
    tgt_root.mkdir(parents=True, exist_ok=True)
    (src_mod / "a.hex").write_bytes(b"X")
    save_model_id(src_root, "l36")
    asset = make_asset(src_mod, firmware_type="movement_3d", firmware_label="机芯版", model="L36")
    result = set_shared_module(tgt_root, asset, ws, module_key="机芯版")
    assert result["ok"] is True
    refs = load_shared_modules(tgt_root)
    assert refs[0].module_key == "机芯板"


def test_write_failed_keeps_original(tmp_path: Path, monkeypatch):
    ws, src_root, tgt_root, asset = _setup_multi_model_workspace(tmp_path)
    # 先正常写一次，建立原文件
    set_shared_module(tgt_root, asset, ws)
    original_text = (tgt_root / "型号配置.toml").read_text(encoding="utf-8")

    def _boom(*_a, **_kw):
        raise OSError("disk full")

    monkeypatch.setattr(sms, "save_shared_module", _boom)
    other_variant = src_root / "通用" / "快捷键" / "量产_默认"
    other_variant.mkdir(parents=True, exist_ok=True)
    (other_variant / "key.hex").write_bytes(b"Z")
    other_asset = make_asset(other_variant, model="L36")
    result = set_shared_module(tgt_root, other_asset, ws, overwrite=True)
    assert result["ok"] is False
    assert result["code"] == "write_failed"
    # 原文件不变
    assert (tgt_root / "型号配置.toml").read_text(encoding="utf-8") == original_text


def test_invalid_args_empty_target(tmp_path: Path):
    ws, src_root, tgt_root, asset = _setup_multi_model_workspace(tmp_path)
    result = set_shared_module("", asset, ws)
    assert result["ok"] is False
    assert result["code"] == "invalid_args"


def test_invalid_args_empty_asset(tmp_path: Path):
    ws, src_root, tgt_root, asset = _setup_multi_model_workspace(tmp_path)
    empty_asset = make_asset(src_root / "通用" / "快捷键" / "贝乐", model="L36")
    empty_asset["path"] = ""
    result = set_shared_module(tgt_root, empty_asset, ws)
    assert result["ok"] is False
    assert result["code"] == "invalid_args"


# ---------- Task 2: clear_shared_module ----------


def test_clear_shared_module_removes_ref(tmp_path: Path):
    ws, src_root, tgt_root, asset = _setup_multi_model_workspace(tmp_path)
    set_shared_module(tgt_root, asset, ws)
    # 预存 model_id 以验证删除后保留
    save_model_id(tgt_root, "dual")
    result = clear_shared_module(tgt_root, "快捷键程序")
    assert result["ok"] is True
    assert result["code"] == "ok"
    refs = load_shared_modules(tgt_root)
    assert len(refs) == 0
    # model_id 保留
    mid, status, _ = load_model_config(tgt_root)
    assert status == "ok" and mid == "dual"


def test_clear_nonexistent_key_idempotent(tmp_path: Path):
    ws, src_root, tgt_root, asset = _setup_multi_model_workspace(tmp_path)
    # 无 型号配置.toml 的根
    result = clear_shared_module(tgt_root, "蓝牙程序")
    assert result["ok"] is True
    # 不建空文件
    assert not (tgt_root / "型号配置.toml").exists()


def test_clear_does_not_delete_firmware_files(tmp_path: Path):
    """B4b：取消共享只删 toml 条目，不删固件文件。"""
    ws, src_root, tgt_root, asset = _setup_multi_model_workspace(tmp_path)
    set_shared_module(tgt_root, asset, ws)
    # 目标型号本地有同模块 bin 文件
    local_mod = tgt_root / "通用" / "快捷键" / "本地变体"
    local_mod.mkdir(parents=True, exist_ok=True)
    local_file = local_mod / "local.hex"
    local_file.write_bytes(b"LOCAL")
    clear_shared_module(tgt_root, "快捷键程序")
    # 本地固件文件仍在磁盘
    assert local_file.exists()
    assert local_file.read_bytes() == b"LOCAL"