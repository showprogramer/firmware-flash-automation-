"""R8 反查测试：命中矩阵、kind 验证、悬空锚点、严格加载 issue。"""

from __future__ import annotations

from pathlib import Path

import pytest

from fwasset.core.model_config import (
    SharedModuleRef,
    save_model_id,
    save_shared_module,
)
from fwasset.core.platform_config import PlatformDefaults, save_platform_config
from fwasset.core.reference_lookup import (
    check_reference_gate,
    find_dangling_anchors,
    find_references_to,
)


def _write(p: Path, content: str = "x") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _result(payload: dict):
    return payload["result"]


@pytest.fixture()
def ws(tmp_path: Path) -> Path:
    """多型号布局工作区：L36/L50 两型号，各含 id、平台配置与通用程序。"""
    root = tmp_path / "ws"
    l36 = root / "L36程序"
    l50 = root / "L50程序"
    l36.mkdir(parents=True)
    l50.mkdir(parents=True)
    save_model_id(l36, "l36")
    save_model_id(l50, "l50")
    save_platform_config(
        l36,
        [PlatformDefaults("标准单机芯3D", {"快捷键程序": "贝乐", "主板程序": "量产_默认"})],
    )
    _write(l36 / "通用" / "快捷键" / "贝乐" / "key.hex")
    _write(l36 / "通用" / "快捷键" / "量产_默认" / "key.hex")
    _write(l36 / "通用" / "主板程序" / "v1" / "rom.bin")
    _write(l50 / "通用" / "主板程序" / "v1" / "rom.bin")
    return root


def _borrow(
    target_root: Path,
    key: str,
    source_rel: str,
    mode: str = "static",
    sid: str = "l36",
    source_platform: str = "",
) -> None:
    save_shared_module(
        target_root,
        SharedModuleRef(
            module_key=key,
            source_model_id=sid,
            source_group=sid,
            source_module=key,
            source_relative_path=source_rel,
            mode=mode,  # type: ignore[arg-type]
            source_platform=source_platform,
        ),
    )


# ---------------------------------------------------------------------------
# gate 与 kind 验证
# ---------------------------------------------------------------------------


def test_gate_not_configured(ws: Path):
    res = find_references_to(None, ws, ws / "L36程序", "model")
    assert res["ok"] is False and res["code"] == "not_configured"


def test_gate_root_changed(ws: Path, tmp_path: Path):
    other = tmp_path / "other"
    other.mkdir()
    res = find_references_to(str(other), ws, ws / "L36程序", "model")
    assert res["ok"] is False and res["code"] == "root_changed"


def test_check_reference_gate_ok(ws: Path):
    assert check_reference_gate(str(ws), ws) is None


def test_target_out_of_workspace(ws: Path):
    res = find_references_to(str(ws), ws, Path("C:/outside"), "asset")
    assert res["ok"] is False and res["code"] == "out_of_workspace"


def test_target_missing_is_invalid_target(ws: Path):
    res = find_references_to(str(ws), ws, ws / "L36程序" / "通用" / "nope", "asset")
    assert res["ok"] is False and res["code"] == "invalid_target"


@pytest.mark.parametrize(
    ("target_rel", "kind"),
    [
        ("L36程序", "asset"),  # 型号根不是程序
        ("L36程序/通用/快捷键/贝乐", "module"),  # 程序不是模块
        ("L36程序/通用/快捷键/贝乐", "scheme"),  # 方案必须直接在定制下
        ("L36程序/通用", "model"),  # 无型号标志
    ],
)
def test_kind_mismatch_invalid_target(ws: Path, target_rel: str, kind: str):
    res = find_references_to(str(ws), ws, ws / target_rel, kind)  # type: ignore[arg-type]
    assert res["ok"] is False and res["code"] == "invalid_target"


def test_kind_module_ok(ws: Path):
    res = find_references_to(str(ws), ws, ws / "L36程序" / "通用" / "快捷键", "module")
    assert res["ok"] is True


# ---------------------------------------------------------------------------
# 命中矩阵
# ---------------------------------------------------------------------------


def test_asset_hit_static_and_cross_not_hit(ws: Path):
    _borrow(ws / "L50程序", "快捷键程序", "L36程序/通用/快捷键/贝乐")
    res = find_references_to(
        str(ws), ws, ws / "L36程序" / "通用" / "快捷键" / "贝乐", "asset"
    )
    assert res["ok"] is True
    hits = _result(res["payload"]).hits
    assert any(h.kind == "shared_static" for h in hits)


def test_asset_same_module_ab_no_cross_hit(ws: Path):
    """默认=A 时：查 A 命中 follow_default、查同模块 B 不命中。"""
    _borrow(
        ws / "L50程序",
        "快捷键程序",
        "L36程序/通用/快捷键",
        mode="follow_default",
    )
    res_a = find_references_to(
        str(ws), ws, ws / "L36程序" / "通用" / "快捷键" / "贝乐", "asset"
    )
    hits_a = [h for h in _result(res_a["payload"]).hits if h.kind == "shared_follow_default"]
    assert len(hits_a) == 1
    res_b = find_references_to(
        str(ws), ws, ws / "L36程序" / "通用" / "快捷键" / "量产_默认", "asset"
    )
    hits_b = [h for h in _result(res_b["payload"]).hits if h.kind == "shared_follow_default"]
    assert hits_b == []


def test_module_hit_static_and_defaults(ws: Path):
    _borrow(ws / "L50程序", "快捷键程序", "L36程序/通用/快捷键/贝乐")
    res = find_references_to(str(ws), ws, ws / "L36程序" / "通用" / "快捷键", "module")
    hits = _result(res["payload"]).hits
    kinds = {h.kind for h in hits}
    assert kinds == {"shared_static", "platform_default"}
    defaults_hit = next(h for h in hits if h.kind == "platform_default")
    assert defaults_hit.raw_key == "快捷键程序"
    assert defaults_hit.block_index == 0


def test_defaults_alias_key_hits_canonical_module(ws: Path, tmp_path: Path):
    """defaults 用别名键「快捷键」也能命中实际目录「快捷键」。"""
    l36 = ws / "L36程序"
    save_platform_config(l36, [PlatformDefaults("标准单机芯3D", {"快捷键": "贝乐"})])
    res = find_references_to(str(ws), ws, l36 / "通用" / "快捷键", "module")
    hits = [h for h in _result(res["payload"]).hits if h.kind == "platform_default"]
    assert len(hits) == 1 and hits[0].raw_key == "快捷键"


def test_scheme_subtree_hit(ws: Path):
    _write(ws / "L36程序" / "定制" / "以色列-Royal-Z9" / "主板程序" / "v2" / "rom.bin")
    _borrow(ws / "L50程序", "主板程序", "L36程序/定制/以色列-Royal-Z9/主板程序/v2")
    res = find_references_to(
        str(ws), ws, ws / "L36程序" / "定制" / "以色列-Royal-Z9", "scheme"
    )
    hits = [h for h in _result(res["payload"]).hits if h.kind == "shared_static"]
    assert len(hits) == 1


def test_model_level_cross_model_ref_hit(ws: Path):
    _borrow(ws / "L50程序", "快捷键程序", "L36程序/通用/快捷键/贝乐")
    res = find_references_to(str(ws), ws, ws / "L36程序", "model")
    hits = [h for h in _result(res["payload"]).hits if h.kind == "shared_static"]
    assert len(hits) == 1


def test_model_level_own_defaults_not_hit(ws: Path):
    res = find_references_to(str(ws), ws, ws / "L36程序", "model")
    hits = [h for h in _result(res["payload"]).hits if h.kind == "platform_default"]
    assert hits == []


def test_multi_platform_blocks_precise(ws: Path):
    save_platform_config(
        ws / "L36程序",
        [
            PlatformDefaults("标准单机芯3D", {"主板程序": "v1"}),
            PlatformDefaults("双2D", {"主板程序": "v1"}),
        ],
    )
    res = find_references_to(
        str(ws), ws, ws / "L36程序" / "通用" / "主板程序", "module"
    )
    hits = [h for h in _result(res["payload"]).hits if h.kind == "platform_default"]
    assert {h.block_index for h in hits} == {0, 1}
    assert {h.platform_name for h in hits} == {"标准单机芯3D", "双2D"}


def test_single_model_root_layout(tmp_path: Path):
    root = tmp_path / "ws"
    root.mkdir(parents=True)
    save_model_id(root, "l36")
    _write(root / "通用" / "快捷键" / "贝乐" / "k.hex")
    _borrow(root, "快捷键程序", "通用/快捷键/贝乐")
    res = find_references_to(
        str(root), root, root / "通用" / "快捷键" / "贝乐", "asset"
    )
    assert res["ok"] is True
    hits = [h for h in _result(res["payload"]).hits if h.kind == "shared_static"]
    assert len(hits) == 1


# ---------------------------------------------------------------------------
# 严格加载 issue
# ---------------------------------------------------------------------------


def test_plain_dir_ignored_no_issue(ws: Path):
    (ws / "说明文档").mkdir()
    (ws / "工具").mkdir()
    res = find_references_to(str(ws), ws, ws / "L36程序" / "通用" / "快捷键", "module")
    assert res["ok"] is True
    assert _result(res["payload"]).issues == []


def test_model_without_id_reports_missing_model_id(ws: Path):
    bare = ws / "L70程序"
    _write(bare / "通用" / "主板程序" / "v1" / "rom.bin")
    res = find_references_to(str(ws), ws, ws / "L36程序" / "通用" / "快捷键", "module")
    issues = _result(res["payload"]).issues
    assert any(i.category == "missing_model_id" for i in issues)


def test_parse_error_reported_not_silent(ws: Path):
    bad = ws / "L50程序"
    (bad / "型号配置.toml").write_text("[[broken\n", encoding="utf-8")
    res = find_references_to(str(ws), ws, ws / "L36程序" / "通用" / "快捷键", "module")
    issues = _result(res["payload"]).issues
    assert any(i.category == "model_config_parse_error" for i in issues)


def test_invalid_shared_entry_reported(ws: Path):
    cfg = ws / "L50程序" / "型号配置.toml"
    cfg.write_text(
        cfg.read_text(encoding="utf-8")
        + '\n[shared_modules."主板程序"]\nsource_model_id = "l36"\n',
        encoding="utf-8",
    )
    res = find_references_to(str(ws), ws, ws / "L36程序" / "通用" / "快捷键", "module")
    issues = _result(res["payload"]).issues
    assert any(i.category == "invalid_shared_entry" for i in issues)


def test_duplicate_model_id_reported(ws: Path):
    save_model_id(ws / "L50程序", "l36")  # 与 L36 重复
    res = find_references_to(str(ws), ws, ws / "L36程序" / "通用" / "快捷键", "module")
    issues = _result(res["payload"]).issues
    assert any(i.category == "duplicate_model_id" for i in issues)


# ---------------------------------------------------------------------------
# find_dangling_anchors
# ---------------------------------------------------------------------------


def test_anchor_shared_missing_path(ws: Path):
    _borrow(ws / "L50程序", "快捷键程序", "L36程序/通用/快捷键/贝乐")
    (ws / "L36程序" / "通用" / "快捷键" / "贝乐").rename(
        ws / "L36程序" / "通用" / "快捷键" / "_gone"
    )
    res = find_dangling_anchors(str(ws), ws, ws / "L36程序" / "通用" / "快捷键" / "贝乐")
    hits = [h for h in _result(res["payload"]).hits if h.kind == "shared_static"]
    assert len(hits) == 1


def test_anchor_platform_default_variant_reuse(ws: Path):
    """删除默认变体后复用该路径前仍命中 platform_default。"""
    victim = ws / "L36程序" / "通用" / "快捷键" / "贝乐"
    victim.rename(ws / "_trash")
    res = find_dangling_anchors(str(ws), ws, victim)
    hits = [h for h in _result(res["payload"]).hits if h.kind == "platform_default"]
    assert len(hits) == 1 and hits[0].raw_value == "贝乐"


def test_anchor_platform_default_module_leaf_alias(tmp_path: Path):
    """模块叶子（value=""）整体删除后，用历史 alias 路径复用仍按 canonical 命中。"""
    root = tmp_path / "ws"
    model = root / "L36程序"
    model.mkdir(parents=True)
    save_model_id(model, "l36")
    save_platform_config(model, [PlatformDefaults("标准单机芯3D", {"快捷键": ""})])
    leaf = model / "通用" / "快捷键"
    _write(leaf / "k.hex")
    leaf_removed = model / "通用" / "快捷按键"  # TOML 已归一为「快捷键程序」，历史 alias
    # 删除真实目录后，用另一个 alias 名复用该路径
    res = find_dangling_anchors(str(root), root, leaf_removed)
    hits = [h for h in _result(res["payload"]).hits if h.kind == "platform_default"]
    assert len(hits) == 1 and hits[0].raw_value == ""


def test_anchor_follow_default_not_fixed_anchor(ws: Path):
    _borrow(
        ws / "L50程序",
        "快捷键程序",
        "L36程序/通用/快捷键",
        mode="follow_default",
    )
    res = find_dangling_anchors(
        str(ws), ws, ws / "L36程序" / "通用" / "快捷键" / "贝乐"
    )
    hits = [h for h in _result(res["payload"]).hits if h.kind.startswith("shared_")]
    assert hits == []


def test_anchor_overlapping_candidate_under_anchor(ws: Path):
    _borrow(ws / "L50程序", "快捷键程序", "L36程序/通用/快捷键/贝乐")
    res = find_dangling_anchors(
        str(ws), ws, ws / "L36程序" / "通用" / "快捷键" / "贝乐" / "子目录"
    )
    hits = [h for h in _result(res["payload"]).hits if h.kind == "shared_static"]
    assert len(hits) == 1


def test_follow_asset_registered_and_resolved(ws: Path):
    _borrow(
        ws / "L50程序",
        "快捷键程序",
        "L36程序/通用/快捷键/贝乐",
        mode="follow_asset",
    )
    res = find_references_to(
        str(ws), ws, ws / "L36程序" / "通用" / "快捷键" / "贝乐", "asset"
    )
    hits = [h for h in _result(res["payload"]).hits if h.kind == "shared_follow_asset"]
    assert len(hits) == 1
