"""R8 级联改写与迁移测试：操作矩阵、CAS 回滚、阻止码、幂等。"""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest as _pytest

from fwasset.core.config_io import atomic_write_text
from fwasset.core.model_config import (
    MODEL_CONFIG_FILENAME,
    SharedModuleRef,
    save_model_id,
    save_shared_module,
)
from fwasset.core.platform_config import PlatformDefaults, save_platform_config
from fwasset.core.services.reference_service import (
    apply_rewrite_plan,
    build_rewrite_plan,
    migrate_follow_default_refs,
)
from fwasset.core.shared_module_resolver import resolve_shared_module
from fwasset.core.types import ReferenceSemantics, RewriteRequest


def _write(p: Path, content: str = "x") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


@pytest.fixture()
def ws(tmp_path: Path) -> Path:
    """L36（默认借用来源）/L50（借入方）双型号工作区。"""
    root = tmp_path / "ws"
    l36 = root / "L36程序"
    l50 = root / "L50程序"
    l36.mkdir(parents=True)
    l50.mkdir(parents=True)
    save_model_id(l36, "l36")
    save_model_id(l50, "l50")
    save_platform_config(
        l36,
        [PlatformDefaults("标准单机芯3D", {"快捷键程序": "贝乐", "主板程序": "v1"})],
    )
    _write(l36 / "通用" / "快捷键" / "贝乐" / "key.hex")
    _write(l36 / "通用" / "快捷键" / "量产_默认" / "key.hex")
    _write(l36 / "通用" / "主板程序" / "v1" / "rom.bin")
    _write(l50 / "通用" / "主板程序" / "v9" / "rom.bin")
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


def _plan(cfg: Path, ws: Path, request: RewriteRequest):
    res = build_rewrite_plan(str(cfg), str(ws), request)
    return res


# ---------------------------------------------------------------------------
# rename 矩阵
# ---------------------------------------------------------------------------


def test_rename_asset_rewrites_static_and_defaults(ws: Path):
    _borrow(ws / "L50程序", "快捷键程序", "L36程序/通用/快捷键/贝乐")
    old = ws / "L36程序" / "通用" / "快捷键" / "贝乐"
    new = ws / "L36程序" / "通用" / "快捷键" / "贝乐改"
    # 规格顺序：build（preimage 采集）→ 文件动作 → apply
    req = RewriteRequest(
        operation="rename", target_kind="asset", old_path=str(old), new_path=str(new)
    )
    res = _plan(ws, ws, req)
    assert res["ok"] is True
    plan = res["payload"]["plan"]
    assert any(f.kind == "model_config" for f in plan.files)
    assert any(f.kind == "platform_config" for f in plan.files)
    old.rename(new)
    assert apply_rewrite_plan(plan, str(ws))["ok"] is True
    from fwasset.core.model_config import load_shared_modules
    from fwasset.core.platform_config import load_platform_config

    l50_refs = {r.module_key: r for r in load_shared_modules(ws / "L50程序")}
    assert l50_refs["快捷键程序"].source_relative_path == "L36程序/通用/快捷键/贝乐改"
    # defaults value 同步
    blocks = load_platform_config(ws / "L36程序")
    assert blocks[0].defaults["快捷键程序"] == "贝乐改"
    # 新路径解析命中
    resolution = resolve_shared_module(l50_refs["快捷键程序"], ws)
    assert resolution.status == "hit"


def test_rename_module_rewrites_key_and_refs(ws: Path):
    _borrow(ws / "L50程序", "快捷键程序", "L36程序/通用/快捷键/贝乐")
    old = ws / "L36程序" / "通用" / "快捷键"
    new = ws / "L36程序" / "通用" / "快捷按键"  # alias：canonical 保持「快捷键程序」
    req = RewriteRequest(
        operation="rename", target_kind="module", old_path=str(old), new_path=str(new)
    )
    res = _plan(ws, ws, req)
    assert res["ok"] is True
    plan = res["payload"]["plan"]
    old.rename(new)
    assert apply_rewrite_plan(plan, str(ws))["ok"] is True
    from fwasset.core.model_config import load_shared_modules
    from fwasset.core.platform_config import load_platform_config

    l50_refs = {r.module_key: r for r in load_shared_modules(ws / "L50程序")}
    assert l50_refs["快捷键程序"].source_relative_path == (
        "L36程序/通用/快捷按键/贝乐"
    )
    blocks = load_platform_config(ws / "L36程序")
    # 别名改名 → canonical 键保持不变（规则 4 字段矩阵）
    assert "快捷键程序" in blocks[0].defaults
    assert blocks[0].defaults["快捷键程序"] == "贝乐"


def test_rename_module_cross_canonical_blocked(ws: Path):
    """模块改名导致 canonical 变化 → unsupported_semantic_change。"""
    old = ws / "L36程序" / "通用" / "快捷键"
    new = ws / "L36程序" / "通用" / "主板程序目录"
    req = RewriteRequest(
        operation="rename", target_kind="module", old_path=str(old), new_path=str(new)
    )
    res = _plan(ws, ws, req)
    assert res["ok"] is False and res["code"] == "unsupported_semantic_change"


def test_rename_model_keeps_id_and_group(ws: Path):
    _borrow(ws / "L50程序", "快捷键程序", "L36程序/通用/快捷键/贝乐")
    old = ws / "L36程序"
    new = ws / "L36改名程序"
    req = RewriteRequest(
        operation="rename", target_kind="model", old_path=str(old), new_path=str(new)
    )
    res = _plan(ws, ws, req)
    assert res["ok"] is True
    plan = res["payload"]["plan"]
    old.rename(new)
    assert apply_rewrite_plan(plan, str(ws))["ok"] is True
    from fwasset.core.model_config import load_model_config, load_shared_modules

    l50_refs = {r.module_key: r for r in load_shared_modules(ws / "L50程序")}
    assert l50_refs["快捷键程序"].source_relative_path == "L36改名程序/通用/快捷键/贝乐"
    assert l50_refs["快捷键程序"].source_model_id == "l36"
    assert l50_refs["快捷键程序"].source_group == "l36"
    # 被改名型号自身配置随目录移动且仍可读
    assert load_model_config(ws / "L36改名程序")[0] == "l36"


def test_rename_identity_equal_blocked(ws: Path):
    # ASCII 大小写变体：Windows 下指向同一物理目录（normcase 归一后相等）
    old = ws / "L36程序" / "通用" / "主板程序" / "v1"
    req = RewriteRequest(
        operation="rename",
        target_kind="asset",
        old_path=str(old),
        new_path=str(ws / "L36程序" / "通用" / "主板程序" / "V1"),
    )
    res = _plan(ws, ws, req)
    assert res["ok"] is False and res["code"] == "invalid_operation"


def test_single_model_root_rename_unsupported(tmp_path: Path):
    root = tmp_path / "ws"
    root.mkdir()
    save_model_id(root, "l36")
    req = RewriteRequest(
        operation="rename",
        target_kind="model",
        old_path=str(root),
        new_path=str(tmp_path / "ws2"),
    )
    res = _plan(root, root, req)
    assert res["ok"] is False and res["code"] == "root_rename_unsupported"


# ---------------------------------------------------------------------------
# update 矩阵
# ---------------------------------------------------------------------------


def _sem(model_id: str, module_key: str, scheme: str = "") -> ReferenceSemantics:
    return ReferenceSemantics(
        model_id=model_id, module_key=module_key, source_group=model_id, scheme_name=scheme
    )


def test_update_moves_follow_asset_and_defaults_only(ws: Path):
    _borrow(ws / "L50程序", "快捷键程序", "L36程序/通用/快捷键/贝乐", mode="follow_asset")
    _borrow(ws / "L50程序", "主板程序", "L36程序/通用/主板程序/v1", mode="static")
    old = ws / "L36程序" / "通用" / "快捷键" / "贝乐"
    replacement = ws / "L36程序" / "通用" / "快捷键" / "贝乐v2"
    _write(replacement / "key.hex")
    req = RewriteRequest(
        operation="update",
        target_kind="asset",
        old_path=str(old),
        replacement_path=str(replacement),
        old_semantics=_sem("l36", "快捷键程序"),
        new_semantics=_sem("l36", "快捷键程序"),
    )
    res = _plan(ws, ws, req)
    assert res["ok"] is True
    assert apply_rewrite_plan(res["payload"]["plan"], str(ws))["ok"] is True
    from fwasset.core.model_config import load_shared_modules
    from fwasset.core.platform_config import load_platform_config

    l50_refs = {r.module_key: r for r in load_shared_modules(ws / "L50程序")}
    assert l50_refs["快捷键程序"].source_relative_path == "L36程序/通用/快捷键/贝乐v2"
    # static 不改写（固定旧程序，旧目录已被 CRUD 移除/回收后自然 missing）
    assert l50_refs["主板程序"].source_relative_path == "L36程序/通用/主板程序/v1"
    # defaults 跟随 replacement
    blocks = load_platform_config(ws / "L36程序")
    assert blocks[0].defaults["快捷键程序"] == "贝乐v2"
    assert blocks[0].defaults["主板程序"] == "v1"


def test_update_overlap_with_static_anchor_blocked(ws: Path):
    """旧模块叶子是 static 锚点、replacement 是其子变体 → 双向重叠阻止。"""
    _borrow(ws / "L50程序", "主板程序", "L36程序/通用/主板程序/v1", mode="static")
    old = ws / "L36程序" / "通用" / "主板程序" / "v1"
    replacement = ws / "L36程序" / "通用" / "主板程序" / "v1" / "新变体"
    _write(replacement / "rom.bin")
    req = RewriteRequest(
        operation="update",
        target_kind="asset",
        old_path=str(old),
        replacement_path=str(replacement),
        old_semantics=_sem("l36", "主板程序"),
        new_semantics=_sem("l36", "主板程序"),
    )
    res = _plan(ws, ws, req)
    assert res["ok"] is False and res["code"] == "invalid_operation"


def test_update_semantic_change_blocked(ws: Path):
    old = ws / "L36程序" / "通用" / "快捷键" / "贝乐"
    replacement = ws / "L36程序" / "通用" / "主板程序" / "v1b"
    _write(replacement / "rom.bin")
    req = RewriteRequest(
        operation="update",
        target_kind="asset",
        old_path=str(old),
        replacement_path=str(replacement),
        old_semantics=_sem("l36", "快捷键程序"),
        new_semantics=_sem("l36", "主板程序"),
    )
    res = _plan(ws, ws, req)
    assert res["ok"] is False and res["code"] == "unsupported_semantic_change"


def test_update_forged_old_semantics_invalid_request(ws: Path):
    old = ws / "L36程序" / "通用" / "快捷键" / "贝乐"
    replacement = ws / "L36程序" / "通用" / "快捷键" / "贝乐v2"
    _write(replacement / "key.hex")
    req = RewriteRequest(
        operation="update",
        target_kind="asset",
        old_path=str(old),
        replacement_path=str(replacement),
        # 伪造旧语义：把快捷键伪装成主板程序，企图绕过类型校验
        old_semantics=_sem("l36", "主板程序"),
        new_semantics=_sem("l36", "主板程序"),
    )
    res = _plan(ws, ws, req)
    assert res["ok"] is False and res["code"] == "invalid_request"


# ---------------------------------------------------------------------------
# gate / stale / 阻止
# ---------------------------------------------------------------------------


def test_build_not_configured(ws: Path):
    req = RewriteRequest(
        operation="rename",
        target_kind="asset",
        old_path=str(ws / "L36程序" / "通用" / "快捷键" / "贝乐"),
        new_path=str(ws / "L36程序" / "通用" / "快捷键" / "b2"),
    )
    res = build_rewrite_plan(None, str(ws), req)
    assert res["ok"] is False and res["code"] == "not_configured"


def test_build_root_changed(ws: Path, tmp_path: Path):
    other = tmp_path / "other"
    other.mkdir()
    req = RewriteRequest(
        operation="rename",
        target_kind="asset",
        old_path=str(ws / "L36程序" / "通用" / "快捷键" / "贝乐"),
        new_path=str(ws / "L36程序" / "通用" / "快捷键" / "b2"),
    )
    res = build_rewrite_plan(str(other), str(ws), req)
    assert res["ok"] is False and res["code"] == "root_changed"


def test_apply_rejects_changed_configured_root(ws: Path):
    old = ws / "L36程序" / "通用" / "快捷键" / "贝乐"
    new = ws / "L36程序" / "通用" / "快捷键" / "贝乐改"
    req = RewriteRequest(
        operation="rename", target_kind="asset", old_path=str(old), new_path=str(new)
    )
    res = _plan(ws, ws, req)
    assert res["ok"] is True
    plan = res["payload"]["plan"]
    old.rename(new)
    other = ws.parent / "other-configured"
    other.mkdir()
    res2 = apply_rewrite_plan(plan, str(other))
    assert res2["ok"] is False and res2["code"] == "root_changed"


def test_stale_plan_file_modified(ws: Path):
    _borrow(ws / "L50程序", "快捷键程序", "L36程序/通用/快捷键/贝乐")
    old = ws / "L36程序" / "通用" / "快捷键" / "贝乐"
    new = ws / "L36程序" / "通用" / "快捷键" / "贝乐改"
    req = RewriteRequest(
        operation="rename", target_kind="asset", old_path=str(old), new_path=str(new)
    )
    res = _plan(ws, ws, req)
    plan = res["payload"]["plan"]
    old.rename(new)
    # 文件动作后、apply 前第三方修改了平台配置
    (ws / "L36程序" / "平台配置.toml").write_text("# tampered\n", encoding="utf-8")
    res2 = apply_rewrite_plan(plan, str(ws))
    assert res2["ok"] is False and res2["code"] == "stale_plan"


def test_canonical_conflict_blocks(ws: Path):
    save_platform_config(
        ws / "L36程序",
        [
            PlatformDefaults(
                "标准单机芯3D", {"快捷键程序": "贝乐", "快捷按键": "量产_默认"}
            )
        ],
    )
    old = ws / "L36程序" / "通用" / "快捷键"
    new = ws / "L36程序" / "通用" / "快捷键-旋钮"  # 同 canonical 别名
    req = RewriteRequest(
        operation="rename", target_kind="module", old_path=str(old), new_path=str(new)
    )
    res = _plan(ws, ws, req)
    assert res["ok"] is False and res["code"] == "canonical_conflict"


# ---------------------------------------------------------------------------
# CAS 回滚
# ---------------------------------------------------------------------------


def test_apply_rollback_restores_bytes(ws: Path, monkeypatch: _pytest.MonkeyPatch):
    """第二个文件写失败 → 第一个文件按 preimage 字节完全恢复。"""
    _borrow(ws / "L50程序", "快捷键程序", "L36程序/通用/快捷键/贝乐")
    old = ws / "L36程序" / "通用" / "快捷键" / "贝乐"
    new = ws / "L36程序" / "通用" / "快捷键" / "贝乐改"
    req = RewriteRequest(
        operation="rename", target_kind="asset", old_path=str(old), new_path=str(new)
    )
    res = _plan(ws, ws, req)
    plan = res["payload"]["plan"]
    assert len(plan.files) >= 2
    old.rename(new)

    real_atomic = atomic_write_text
    calls = {"n": 0}

    def flaky(path: Path, content: str) -> None:
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("boom")
        real_atomic(path, content)

    monkeypatch.setattr(
        "fwasset.core.services.reference_service.atomic_write_text", flaky
    )
    res2 = apply_rewrite_plan(plan, str(ws))
    assert res2["ok"] is False
    assert res2["code"] in ("rolled_back", "rollback_conflict")
    assert res2["payload"]["rolled_back"], res2["payload"]
    if res2["code"] == "rolled_back":
        rolled_first = plan.files[0]
        assert Path(rolled_first.pre_path).read_bytes() == rolled_first.original_bytes


def test_apply_rollback_conflict_keeps_concurrent_change(
    ws: Path, monkeypatch: _pytest.MonkeyPatch
):
    """首文件写后被第三方修改、第二文件失败 → rollback_conflict 保留并发内容。"""
    _borrow(ws / "L50程序", "快捷键程序", "L36程序/通用/快捷键/贝乐")
    old = ws / "L36程序" / "通用" / "快捷键" / "贝乐"
    new = ws / "L36程序" / "通用" / "快捷键" / "贝乐改"
    req = RewriteRequest(
        operation="rename", target_kind="asset", old_path=str(old), new_path=str(new)
    )
    plan = _plan(ws, ws, req)["payload"]["plan"]
    assert len(plan.files) >= 2
    old.rename(new)

    real_atomic = atomic_write_text
    calls = {"n": 0}

    def flaky_then_tamper(path: Path, content: str) -> None:
        calls["n"] += 1
        real_atomic(path, content)
        if calls["n"] == 1:
            # 模拟第三方在首文件写入后立即修改
            path.write_text("# concurrent\n", encoding="utf-8")
        if calls["n"] == 2:
            raise OSError("boom")

    monkeypatch.setattr(
        "fwasset.core.services.reference_service.atomic_write_text", flaky_then_tamper
    )
    res = apply_rewrite_plan(plan, str(ws))
    assert res["ok"] is False and res["code"] == "rollback_conflict"
    conflicts = res["payload"]["rollback_conflict"]
    assert conflicts and conflicts[0]["preimage"]
    # 并发修改内容被保留
    assert plan.files[0].post_path.read_text(encoding="utf-8").startswith("# concurrent")


# ---------------------------------------------------------------------------
# follow_default 迁移
# ---------------------------------------------------------------------------


def test_migrate_converts_follow_default_to_follow_asset(ws: Path):
    _borrow(
        ws / "L50程序",
        "快捷键程序",
        "L36程序/通用/快捷键",
        mode="follow_default",
        source_platform="标准单机芯3D",
    )
    res = migrate_follow_default_refs(str(ws), str(ws))
    assert res["ok"] is True
    assert res["payload"]["converted"] == 1
    from fwasset.core.model_config import load_shared_modules

    refs = {r.module_key: r for r in load_shared_modules(ws / "L50程序")}
    ref = refs["快捷键程序"]
    assert ref.mode == "follow_asset"
    assert ref.source_relative_path == "L36程序/通用/快捷键/贝乐"
    assert ref.source_platform == ""
    # 迁移后解析仍命中
    assert resolve_shared_module(ref, ws).status == "hit"
    # TOML 落盘内容：mode=follow_asset、无 source_platform
    text = (ws / "L50程序" / MODEL_CONFIG_FILENAME).read_text(encoding="utf-8")
    assert 'mode = "follow_asset"' in text
    assert "source_platform" not in text


def test_migrate_keeps_unresolvable_entry(ws: Path):
    _borrow(
        ws / "L50程序",
        "快捷键程序",
        "L36程序/通用/不存在模块",
        mode="follow_default",
    )
    res = migrate_follow_default_refs(str(ws), str(ws))
    assert res["ok"] is True
    assert res["payload"]["converted"] == 0 and res["payload"]["kept"] == 1
    from fwasset.core.model_config import load_shared_modules

    ref = load_shared_modules(ws / "L50程序")[0]
    assert ref.mode == "follow_default"


def test_migrate_idempotent_second_run(ws: Path):
    _borrow(
        ws / "L50程序",
        "快捷键程序",
        "L36程序/通用/快捷键",
        mode="follow_default",
    )
    first = migrate_follow_default_refs(str(ws), str(ws))
    assert first["ok"] is True
    second = migrate_follow_default_refs(str(ws), str(ws))
    assert second["payload"]["converted"] == 0
    assert second["payload"]["changed"] == []


def test_migrate_damaged_borrower_failed(ws: Path):
    _borrow(
        ws / "L50程序",
        "快捷键程序",
        "L36程序/通用/快捷键",
        mode="follow_default",
    )
    (ws / "L50程序" / MODEL_CONFIG_FILENAME).write_text("[[broken\n", encoding="utf-8")
    res = migrate_follow_default_refs(str(ws), str(ws))
    assert res["ok"] is False and res["code"] == "migrate_failed"
    assert res["payload"]["failed"] and "parse_error" in res["payload"]["failed"][0]["reason"]


def test_migrate_gate(ws: Path):
    res = migrate_follow_default_refs(None, str(ws))
    assert res["ok"] is False and res["code"] == "not_configured"
