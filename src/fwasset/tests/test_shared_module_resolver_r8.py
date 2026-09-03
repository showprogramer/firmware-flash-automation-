"""R8 follow_asset 解析分支测试（TASK-20260901-r8-reference-integrity）。"""

from __future__ import annotations

from pathlib import Path

from fwasset.core.model_config import SharedModuleRef, save_model_id
from fwasset.core.shared_module_resolver import resolve_shared_module


def _write(p: Path, content: str = "x") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _ref(rel: str, sid: str = "l36", key: str = "快捷键程序") -> SharedModuleRef:
    return SharedModuleRef(
        module_key=key,
        source_model_id=sid,
        source_group=sid,
        source_module=key,
        source_relative_path=rel,
        mode="follow_asset",
    )


def test_follow_asset_hit_no_variant_expansion(tmp_path: Path):
    ws = tmp_path / "ws"
    src = ws / "L36程序"
    variant = src / "通用" / "快捷键" / "贝乐"
    _write(variant / "key.hex")
    save_model_id(src, "l36")
    res = resolve_shared_module(_ref("L36程序/通用/快捷键/贝乐"), ws)
    assert res.status == "hit"
    assert res.resolved_path == variant.resolve()
    # 跟随指定程序：锚点本身，不展开子变体
    assert res.variants == [variant.resolve()]


def test_follow_asset_missing_when_anchor_gone(tmp_path: Path):
    ws = tmp_path / "ws"
    src = ws / "L36程序"
    src.mkdir(parents=True)
    save_model_id(src, "l36")
    res = resolve_shared_module(_ref("L36程序/通用/快捷键/贝乐"), ws)
    assert res.status == "missing" and res.reason == "path_not_found"


def test_follow_asset_id_mismatch(tmp_path: Path):
    ws = tmp_path / "ws"
    src = ws / "L36程序"
    variant = src / "通用" / "快捷键" / "贝乐"
    _write(variant / "key.hex")
    save_model_id(src, "l50")
    res = resolve_shared_module(_ref("L36程序/通用/快捷键/贝乐"), ws)
    assert res.status == "missing" and res.reason == "id_mismatch"


def test_follow_asset_out_of_workspace(tmp_path: Path):
    ws = tmp_path / "ws"
    src = ws / "L36程序"
    src.mkdir(parents=True)
    save_model_id(src, "l36")
    res = resolve_shared_module(_ref("L36程序/../其他/贝乐"), ws)
    assert res.status == "missing" and res.reason == "out_of_workspace"
