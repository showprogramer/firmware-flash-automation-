"""Tests for resolve_shared_module (Phase B1)."""
from __future__ import annotations

from pathlib import Path

from fwasset.core.model_config import SharedModuleRef, save_model_id
from fwasset.core.shared_module_resolver import resolve_shared_module


def _write(p: Path, content: str = "x") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _ref(
    path: str,
    sid: str = "l36",
    key: str = "快捷键程序",
) -> SharedModuleRef:
    return SharedModuleRef(
        module_key=key,
        source_model_id=sid,
        source_group="l36-single",
        source_module=key,
        source_relative_path=path,
    )


def _id_lookup(ws: Path) -> dict[str, Path]:
    """Build id → root from 型号配置.toml under workspace children + root."""
    mapping: dict[str, Path] = {}
    for child in [ws, *list(ws.iterdir())]:
        if not child.is_dir():
            continue
        from fwasset.core.model_config import load_model_config

        mid, status, _ = load_model_config(child)
        if status == "ok" and mid:
            mapping[mid] = child
    return mapping


def test_hit_leaf_variant(tmp_path: Path):
    ws = tmp_path / "ws"
    src = ws / "L36程序"
    leaf = src / "通用" / "快捷键" / "贝乐"
    _write(leaf / "key.hex")
    save_model_id(src, "l36")
    lookup = _id_lookup(ws)
    res = resolve_shared_module(
        _ref("L36程序/通用/快捷键/贝乐"),
        ws,
        lambda i: lookup.get(i),
    )
    assert res.status == "hit"
    assert res.resolved_path == leaf.resolve()
    assert res.variants == [leaf.resolve()]


def test_hit_module_multi_variant(tmp_path: Path):
    ws = tmp_path / "ws"
    src = ws / "L36程序"
    mod = src / "通用" / "快捷键"
    _write(mod / "贝乐" / "a.hex")
    _write(mod / "量产_默认" / "b.hex")
    save_model_id(src, "l36")
    lookup = _id_lookup(ws)
    res = resolve_shared_module(
        _ref("L36程序/通用/快捷键"),
        ws,
        lambda i: lookup.get(i),
    )
    assert res.status == "hit"
    names = [p.name for p in res.variants]
    assert names == ["贝乐", "量产_默认"]


def test_hit_module_files_only(tmp_path: Path):
    ws = tmp_path / "ws"
    src = ws / "L36程序"
    mod = src / "通用" / "腿部程序"
    _write(mod / "leg.hex")
    save_model_id(src, "l36")
    lookup = _id_lookup(ws)
    res = resolve_shared_module(
        _ref("L36程序/通用/腿部程序", key="腿部程序"),
        ws,
        lambda i: lookup.get(i),
    )
    assert res.status == "hit"
    assert res.variants == [mod.resolve()]


def test_variants_skip_noise_dirs(tmp_path: Path):
    ws = tmp_path / "ws"
    src = ws / "L36程序"
    mod = src / "通用" / "快捷键"
    _write(mod / "贝乐" / "a.hex")
    _write(mod / "backup" / "old.hex")
    _write(mod / "旧" / "old2.hex")
    save_model_id(src, "l36")
    lookup = _id_lookup(ws)
    res = resolve_shared_module(
        _ref("L36程序/通用/快捷键"),
        ws,
        lambda i: lookup.get(i),
    )
    assert [p.name for p in res.variants] == ["贝乐"]


def test_missing_path_not_found(tmp_path: Path):
    ws = tmp_path / "ws"
    src = ws / "L36程序"
    src.mkdir(parents=True)
    save_model_id(src, "l36")
    lookup = _id_lookup(ws)
    res = resolve_shared_module(
        _ref("L36程序/通用/不存在"),
        ws,
        lambda i: lookup.get(i),
    )
    assert res.status == "missing"
    assert res.reason == "path_not_found"


def test_missing_source_not_imported(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    res = resolve_shared_module(
        _ref("L50程序/通用/手控"),
        ws,
        lambda _i: None,
    )
    assert res.status == "missing"
    assert res.reason == "source_not_imported"


def test_missing_id_mismatch(tmp_path: Path):
    ws = tmp_path / "ws"
    src = ws / "L36程序"
    leaf = src / "通用" / "快捷键" / "贝乐"
    _write(leaf / "a.hex")
    save_model_id(src, "l36")
    lookup = _id_lookup(ws)
    res = resolve_shared_module(
        _ref("L36程序/通用/快捷键/贝乐", sid="other-id"),
        ws,
        lambda i: lookup.get(i),
    )
    assert res.status == "missing"
    assert res.reason == "id_mismatch"


def test_out_of_workspace(tmp_path: Path):
    ws = tmp_path / "ws"
    outside = tmp_path / "outside" / "secret"
    _write(outside / "x.bin")
    src = ws / "L36程序"
    src.mkdir(parents=True)
    save_model_id(src, "l36")
    lookup = _id_lookup(ws)
    res = resolve_shared_module(
        _ref("../outside/secret"),
        ws,
        lambda i: lookup.get(i),
    )
    assert res.status == "missing"
    assert res.reason == "out_of_workspace"


def test_no_cross_model_search(tmp_path: Path):
    """源段缺失时不落到另一型号同名路径。"""
    ws = tmp_path / "ws"
    other = ws / "L50程序" / "通用" / "快捷键" / "贝乐"
    _write(other / "a.hex")
    save_model_id(ws / "L50程序", "l50")
    # 引用声称 l36 但 L36 根不存在
    res = resolve_shared_module(
        _ref("L36程序/通用/快捷键/贝乐", sid="l36"),
        ws,
        lambda _i: None,
    )
    assert res.status == "missing"
    assert res.reason == "source_not_imported"
    assert res.resolved_path is None
