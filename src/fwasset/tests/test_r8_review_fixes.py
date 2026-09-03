"""R8 第二轮审查修复的回归测试（TASK-20260901-r8-reference-integrity P2-3）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from fwasset.core.config_io import atomic_write_text
from fwasset.core.model_config import (
    MODEL_CONFIG_FILENAME,
    SharedModuleRef,
    load_shared_modules,
    save_model_id,
    save_shared_module,
)
from fwasset.core.platform_config import PlatformDefaults, save_platform_config
from fwasset.core.reference_lookup import (
    find_references_to,
)
from fwasset.core.services.reference_service import (
    RewritePlan,
    apply_rewrite_plan,
    build_rewrite_plan,
    migrate_follow_default_refs,
)
from fwasset.core.shared_module_resolver import resolve_shared_module
from fwasset.core.types import ReferenceSemantics, RewriteRequest


def _write(p: Path, content: str = "x") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _borrow(
    target: Path,
    key: str,
    rel: str,
    mode: str = "static",
    sid: str = "l36",
    source_platform: str = "",
) -> None:
    save_shared_module(
        target,
        SharedModuleRef(
            module_key=key,
            source_model_id=sid,
            source_group=sid,
            source_module=key,
            source_relative_path=rel,
            mode=mode,  # type: ignore[arg-type]
            source_platform=source_platform,
        ),
    )


@pytest.fixture()
def ws(tmp_path: Path) -> Path:
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


# ---------------------------------------------------------------------------
# P1-1：伪造 plan → invalid_plan 零写
# ---------------------------------------------------------------------------


def test_forged_plan_rejected(ws: Path):
    from fwasset.core.services.reference_service import (
        FileRewrite,
        _sha256,
    )

    victim = ws / "L50程序" / MODEL_CONFIG_FILENAME
    plan = RewritePlan(
        configured_root=str(ws),
        workspace_root=str(ws),
        request=RewriteRequest(
            operation="rename",
            target_kind="asset",
            old_path=str(ws / "L36程序" / "通用" / "快捷键" / "贝乐"),
            new_path=str(ws / "L36程序" / "通用" / "快捷键" / "b2"),
        ),
        files=[
            FileRewrite(
                kind="model_config",
                pre_path=victim,
                post_path=victim,
                owner_root=str(ws / "L50程序"),
                original_bytes=victim.read_bytes(),
                original_sha256=_sha256(victim.read_bytes()),
                new_content="# forged\n",
                new_sha256=_sha256(b"# forged\n"),
            )
        ],
    )
    res = apply_rewrite_plan(plan, str(ws))
    assert res["ok"] is False and res["code"] == "invalid_plan"
    # 文件未被篡改
    assert victim.read_text(encoding="utf-8") != "# forged\n"


def test_tampered_new_content_rejected(ws: Path):
    _borrow(ws / "L50程序", "快捷键程序", "L36程序/通用/快捷键/贝乐")
    old = ws / "L36程序" / "通用" / "快捷键" / "贝乐"
    new = ws / "L36程序" / "通用" / "快捷键" / "贝乐改"
    req = RewriteRequest(
        operation="rename", target_kind="asset", old_path=str(old), new_path=str(new)
    )
    plan = build_rewrite_plan(str(ws), str(ws), req)["payload"]["plan"]
    plan.files[0].new_content = "# tampered\n"
    res = apply_rewrite_plan(plan, str(ws))
    assert res["ok"] is False and res["code"] == "invalid_plan"


# ---------------------------------------------------------------------------
# P0-2：型号改名回滚恢复 post_path，不重建旧根
# ---------------------------------------------------------------------------


def test_model_rename_rollback_restores_post_path(
    ws: Path, monkeypatch: pytest.MonkeyPatch
):
    # 自引用：L36 借用自己的程序，使型号自身配置进入计划
    _borrow(ws / "L36程序", "快捷键程序", "L36程序/通用/快捷键/贝乐", sid="l36")
    _borrow(ws / "L50程序", "快捷键程序", "L36程序/通用/快捷键/贝乐")
    old = ws / "L36程序"
    new = ws / "L36改名程序"
    req = RewriteRequest(
        operation="rename", target_kind="model", old_path=str(old), new_path=str(new)
    )
    plan = build_rewrite_plan(str(ws), str(ws), req)["payload"]["plan"]
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
    res = apply_rewrite_plan(plan, str(ws))
    assert res["ok"] is False and res["code"] == "rolled_back"
    own = plan.files[0]
    assert own.pre_path != own.post_path
    # 恢复发生在当前物理位置（新根），旧根不重建
    assert own.post_path.read_bytes() == own.original_bytes
    assert not own.pre_path.exists()


# ---------------------------------------------------------------------------
# P1-1：owner 限定与联合身份
# ---------------------------------------------------------------------------


def test_defaults_module_hit_not_cross_model(ws: Path):
    """L50 有同名 canonical defaults，查 L36 模块不得命中 L50。"""
    save_platform_config(
        ws / "L50程序", [PlatformDefaults("标准双2D", {"快捷键程序": "别的"})]
    )
    res = find_references_to(
        str(ws), ws, ws / "L36程序" / "通用" / "快捷键", "module"
    )
    hits = [h for h in res["payload"]["result"].hits if h.kind == "platform_default"]
    assert {Path(h.owner_root).name for h in hits} == {"L36程序"}


def test_dangling_follow_default_semantic_hit_on_module(ws: Path):
    """follow_default 默认缺失时，module 级仍按来源根+canonical 语义命中。"""
    _borrow(
        ws / "L50程序",
        "快捷键程序",
        "L36程序/通用/快捷键",
        mode="follow_default",
    )
    res = find_references_to(
        str(ws), ws, ws / "L36程序" / "通用" / "快捷键", "module"
    )
    hits = [h for h in res["payload"]["result"].hits if h.kind == "shared_follow_default"]
    assert len(hits) == 1


def test_follow_default_semantic_hit_requires_source_model_id(ws: Path):
    """路径首段指向 L36 但 id 写成 L50 的损坏引用 → 不算命中。"""
    _borrow(
        ws / "L50程序",
        "快捷键程序",
        "L36程序/通用/快捷键",
        mode="follow_default",
        sid="l50",
    )
    res = find_references_to(
        str(ws), ws, ws / "L36程序" / "通用" / "快捷键", "module"
    )
    hits = [h for h in res["payload"]["result"].hits if h.kind == "shared_follow_default"]
    assert hits == []


# ---------------------------------------------------------------------------
# P1-2：asset kind 领域校验
# ---------------------------------------------------------------------------


def test_variant_container_rejected_as_asset(ws: Path):
    res = find_references_to(
        str(ws), ws, ws / "L36程序" / "通用" / "快捷键", "asset"
    )
    assert res["ok"] is False and res["code"] == "invalid_target"


def test_variant_accepted_as_asset(ws: Path):
    res = find_references_to(
        str(ws), ws, ws / "L36程序" / "通用" / "快捷键" / "贝乐", "asset"
    )
    assert res["ok"] is True


# ---------------------------------------------------------------------------
# P1-4：strict loader 非法组合
# ---------------------------------------------------------------------------


def test_strict_loader_flags_illegal_mode_and_platform(ws: Path):
    cfg = ws / "L50程序" / MODEL_CONFIG_FILENAME
    text = cfg.read_text(encoding="utf-8")
    cfg.write_text(
        text
        + '\n[shared_modules."主板程序"]\n'
        'source_model_id = "l36"\n'
        'source_group = "l36"\n'
        'source_module = "主板程序"\n'
        'source_relative_path = "L36程序/通用/主板程序/v1"\n'
        'mode = "follow_asst"\n',
        encoding="utf-8",
    )
    res = find_references_to(
        str(ws), ws, ws / "L36程序" / "通用" / "快捷键", "module"
    )
    issues = res["payload"]["result"].issues
    assert any(i.category == "invalid_shared_entry" for i in issues)


def test_strict_loader_flags_follow_asset_with_platform(ws: Path):
    _borrow(
        ws / "L50程序",
        "主板程序",
        "L36程序/通用/主板程序/v1",
        mode="follow_asset",
        source_platform="标准单机芯3D",
    )
    res = find_references_to(
        str(ws), ws, ws / "L36程序" / "通用" / "快捷键", "module"
    )
    issues = res["payload"]["result"].issues
    assert any(i.category == "invalid_shared_entry" for i in issues)


# ---------------------------------------------------------------------------
# P1-6：canonical 作用域与合并
# ---------------------------------------------------------------------------


def test_asset_level_canonical_conflict_blocks(ws: Path):
    """两个异值别名分别指向 A/B：操作 A 仍阻止（完整别名组参与判定）。"""
    save_platform_config(
        ws / "L36程序",
        [
            PlatformDefaults(
                "标准单机芯3D", {"快捷键程序": "贝乐", "快捷按键": "量产_默认"}
            )
        ],
    )
    old = ws / "L36程序" / "通用" / "快捷键" / "贝乐"
    new = ws / "L36程序" / "通用" / "快捷键" / "贝乐改"
    req = RewriteRequest(
        operation="rename", target_kind="asset", old_path=str(old), new_path=str(new)
    )
    res = build_rewrite_plan(str(ws), str(ws), req)
    assert res["ok"] is False and res["code"] == "canonical_conflict"


def test_same_value_alias_merged_to_single_canonical(ws: Path):
    save_platform_config(
        ws / "L36程序",
        [
            PlatformDefaults(
                "标准单机芯3D", {"快捷键程序": "贝乐", "快捷按键": "贝乐"}
            )
        ],
    )
    old = ws / "L36程序" / "通用" / "快捷键" / "贝乐"
    new = ws / "L36程序" / "通用" / "快捷键" / "贝乐改"
    req = RewriteRequest(
        operation="rename", target_kind="asset", old_path=str(old), new_path=str(new)
    )
    res = build_rewrite_plan(str(ws), str(ws), req)
    assert res["ok"] is True
    assert apply_rewrite_plan(res["payload"]["plan"], str(ws))["ok"] is True
    from fwasset.core.platform_config import load_platform_config

    defaults = load_platform_config(ws / "L36程序")[0].defaults
    assert list(defaults).count("快捷键程序") == 1
    assert "快捷按键" not in defaults
    assert defaults["快捷键程序"] == "贝乐改"


def test_unrelated_model_canonical_conflict_does_not_block(ws: Path):
    """无关型号的同 canonical 异值冲突不阻止本次命中其它型号的操作。"""
    save_platform_config(
        ws / "L50程序",
        [
            PlatformDefaults(
                "标准双2D", {"快捷键程序": "别的A", "快捷按键": "别的B"}
            )
        ],
    )
    old = ws / "L36程序" / "通用" / "快捷键" / "贝乐"
    new = ws / "L36程序" / "通用" / "快捷键" / "贝乐改"
    req = RewriteRequest(
        operation="rename", target_kind="asset", old_path=str(old), new_path=str(new)
    )
    res = build_rewrite_plan(str(ws), str(ws), req)
    assert res["ok"] is True


# ---------------------------------------------------------------------------
# P1-7：迁移来源阻断传播 + 继续处理后续文件
# ---------------------------------------------------------------------------


def test_migrate_source_blocked_skips_only_that_borrower(tmp_path: Path):
    root = tmp_path / "ws"
    src = root / "L36程序"
    b1 = root / "L50程序"
    b2 = root / "L60程序"
    src.mkdir(parents=True)
    b1.mkdir()
    b2.mkdir()
    save_model_id(src, "l36")
    save_model_id(b1, "l50")
    save_model_id(b2, "l60")
    _write(src / "通用" / "主板程序" / "v1" / "rom.bin")
    _borrow(b1, "主板程序", "L36程序/通用/主板程序", mode="follow_default")
    _borrow(b2, "主板程序", "L36程序/通用/主板程序", mode="follow_default")
    # 来源型号配置损坏 → b1、b2 的来源均为损坏型号，双双计入 failed
    (src / MODEL_CONFIG_FILENAME).write_text("[[broken\n", encoding="utf-8")
    res = migrate_follow_default_refs(str(root), str(root))
    assert res["ok"] is False
    assert res["payload"]["converted"] == 0
    # src 自身 + 两个借入方（来源侧阻断传播）各计一条 failed
    assert len(res["payload"]["failed"]) == 3
    assert res["payload"]["failed"][0]["reason"].startswith("model_config_parse_error")


def test_migrate_source_blocked_continues_other_borrower(tmp_path: Path):
    """来源侧阻断只跳过当前借入方：来源损坏但另一借入方条目可解析。"""
    root = tmp_path / "ws"
    src = root / "L36程序"
    b1 = root / "L50程序"
    b2 = root / "L60程序"
    src.mkdir(parents=True)
    b1.mkdir()
    b2.mkdir()
    save_model_id(src, "l36")
    save_model_id(b1, "l50")
    save_model_id(b2, "l60")
    _write(src / "通用" / "主板程序" / "v1" / "rom.bin")
    _write(src / "通用" / "快捷键" / "贝乐" / "k.hex")
    _borrow(b1, "主板程序", "L36程序/通用/主板程序", mode="follow_default")
    # b2 借用「快捷键程序」，其来源是另一个正常型号
    other = root / "L70程序"
    other.mkdir()
    save_model_id(other, "l70")
    _write(other / "通用" / "快捷键" / "量产_默认" / "k.hex")
    save_platform_config(other, [PlatformDefaults("标准单机芯3D", {"快捷键程序": "量产_默认"})])
    _borrow(b2, "快捷键程序", "L70程序/通用/快捷键", mode="follow_default", sid="l70")
    # 破坏 src（b1 的来源）
    (src / MODEL_CONFIG_FILENAME).write_text("[[broken\n", encoding="utf-8")
    res = migrate_follow_default_refs(str(root), str(root))
    assert res["ok"] is False
    # b2 迁移成功
    assert res["payload"]["converted"] == 1
    assert Path(res["payload"]["changed"][0]).name == "L60程序"


def test_migrate_unresolved_reported_per_entry(ws: Path):
    _borrow(
        ws / "L50程序",
        "快捷键程序",
        "L36程序/通用/不存在模块",
        mode="follow_default",
    )
    res = migrate_follow_default_refs(str(ws), str(ws))
    assert res["payload"]["unresolved"], res["payload"]
    entry = res["payload"]["unresolved"][0]
    assert entry["raw_key"] == "快捷键程序"
    assert entry["reason"]


# ---------------------------------------------------------------------------
# P1-7：单型号布局 resolver / migrate
# ---------------------------------------------------------------------------


def test_single_model_layout_resolver_and_migrate(tmp_path: Path):
    root = tmp_path / "ws"
    root.mkdir(parents=True)
    save_model_id(root, "l36")
    _write(root / "通用" / "主板程序" / "v1" / "rom.bin")
    save_platform_config(root, [PlatformDefaults("标准单机芯3D", {"主板程序": "v1"})])
    ref = SharedModuleRef(
        module_key="主板程序",
        source_model_id="l36",
        source_group="l36",
        source_module="主板程序",
        source_relative_path="通用/主板程序",
        mode="follow_default",
    )
    save_shared_module(root, ref)
    # 单型号布局：首段 通用 → source root = 工作区根
    assert resolve_shared_module(ref, root).status == "hit"
    res = migrate_follow_default_refs(str(root), str(root))
    assert res["ok"] is True and res["payload"]["converted"] == 1
    refs = {r.module_key: r for r in load_shared_modules(root)}
    assert refs["主板程序"].mode == "follow_asset"
    assert refs["主板程序"].source_relative_path == "通用/主板程序/v1"
    assert resolve_shared_module(refs["主板程序"], root).status == "hit"


# ---------------------------------------------------------------------------
# P1-8：junction 物理后代命中（词法前缀不同）
# ---------------------------------------------------------------------------


def test_junction_physical_descendant_hit(ws: Path, tmp_path: Path):
    """锚点经 junction 指向真实模块子目录：module 反查仍命中。"""
    link_parent = tmp_path / "links"
    link_parent.mkdir()
    link = link_parent / "快捷键alias"
    real = ws / "L36程序" / "通用" / "快捷键"
    import subprocess

    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(real)],
        check=True,
        capture_output=True,
    )
    _borrow(ws / "L50程序", "快捷键程序", "L36程序/通用/快捷键/贝乐")
    # 通过 junction 的路径作为锚点（词法上与真实模块无前缀关系）
    junction_rel = f"../{link.parent.name}/{link.name}/贝乐"
    cfg = ws / "L50程序" / MODEL_CONFIG_FILENAME
    text = cfg.read_text(encoding="utf-8").replace(
        "L36程序/通用/快捷键/贝乐", junction_rel
    )
    cfg.write_text(text, encoding="utf-8")
    res = find_references_to(str(ws), ws, real, "module")
    hits = [h for h in res["payload"]["result"].hits if h.kind.startswith("shared_")]
    assert len(hits) == 1


# ---------------------------------------------------------------------------
# P2-1：_load_model_ids 门闩分支
# ---------------------------------------------------------------------------


def test_load_model_ids_skips_mapping_on_out_of_workspace(tmp_path: Path):
    from fwasset.ui_common.view_models.scheme_workbench_model import (
        SchemeWorkbenchModel,
    )

    root = tmp_path / "L36程序"
    root.mkdir(parents=True)
    _write(root / "通用" / "主板程序" / "v1" / "rom.bin")
    other = tmp_path.parent / f"{tmp_path.name}_外"
    other.mkdir(exist_ok=True)
    model = SchemeWorkbenchModel()
    model.bind(None, root, other)  # 配置根与扫描根不同
    model._load_model_ids()
    # 门闩拒绝：不建立映射
    assert model._model_id_by_dir == {}
    assert not (root / MODEL_CONFIG_FILENAME).exists()


# ---------------------------------------------------------------------------
# 第三轮 P1-1：junction rename 词法尾段保留 + 反斜杠/大小写改写
# ---------------------------------------------------------------------------


def test_rename_rewrites_case_variant_ref(ws: Path):
    """存量引用大小写与磁盘目录不一致（normcase 身份命中）：rename 后精确落新路径。"""
    _borrow(ws / "L50程序", "主板程序", "L36程序/通用/主板程序/V1")  # 磁盘目录为 v1
    old = ws / "L36程序" / "通用" / "主板程序" / "v1"
    new = ws / "L36程序" / "通用" / "主板程序" / "v2"
    req = RewriteRequest(
        operation="rename", target_kind="asset", old_path=str(old), new_path=str(new)
    )
    res = build_rewrite_plan(str(ws), str(ws), req)
    assert res["ok"] is True
    old.rename(new)
    assert apply_rewrite_plan(res["payload"]["plan"], str(ws))["ok"] is True
    refs = {r.module_key: r for r in load_shared_modules(ws / "L50程序")}
    assert refs["主板程序"].source_relative_path == "L36程序/通用/主板程序/v2"
    assert resolve_shared_module(refs["主板程序"], ws).status == "hit"


def test_rename_rewrites_backslash_ref_via_serializer(ws: Path):
    """反斜杠引用（经 tomli-w 合法转义落盘）：rename 后统一归一为 ``/``。"""
    _borrow(ws / "L50程序", "主板程序", "L36程序\\通用\\主板程序\\v1")
    old = ws / "L36程序" / "通用" / "主板程序" / "v1"
    new = ws / "L36程序" / "通用" / "主板程序" / "v2"
    req = RewriteRequest(
        operation="rename", target_kind="asset", old_path=str(old), new_path=str(new)
    )
    res = build_rewrite_plan(str(ws), str(ws), req)
    assert res["ok"] is True
    old.rename(new)
    assert apply_rewrite_plan(res["payload"]["plan"], str(ws))["ok"] is True
    refs = {r.module_key: r for r in load_shared_modules(ws / "L50程序")}
    assert refs["主板程序"].source_relative_path == "L36程序/通用/主板程序/v2"
    assert resolve_shared_module(refs["主板程序"], ws).status == "hit"


def test_rename_unplaceable_ref_blocked(ws: Path, tmp_path: Path):
    """``..`` 构造的锚点被越界检查拦下（invalid_shared_entry → lookup_blocked）。"""
    _borrow(ws / "L50程序", "快捷键程序", "L50程序/../L36程序/通用/快捷键/贝乐")
    old = ws / "L36程序" / "通用" / "主板程序" / "v1"
    new = ws / "L36程序" / "通用" / "主板程序" / "v2"
    req = RewriteRequest(
        operation="rename", target_kind="asset", old_path=str(old), new_path=str(new)
    )
    res = build_rewrite_plan(str(ws), str(ws), req)
    assert res["ok"] is False and res["code"] == "lookup_blocked"
    issues = res["payload"]["issues"]
    assert any(i["category"] == "invalid_shared_entry" for i in issues)


def test_junction_anchor_update_overlap_blocked(ws: Path, tmp_path: Path):
    """junction 物理指向 static 锚点之内：update overlap 双向判定阻止。"""
    link_parent = tmp_path / "links"
    link_parent.mkdir()
    link = link_parent / "alias"
    real = ws / "L36程序" / "通用" / "快捷键" / "贝乐"
    import subprocess

    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(real)],
        check=True,
        capture_output=True,
    )
    _borrow(ws / "L50程序", "快捷键程序", "L36程序/通用/快捷键/贝乐")
    replacement = link  # junction：词法在 old 外、物理 == 锚点
    req = RewriteRequest(
        operation="update",
        target_kind="asset",
        old_path=str(real),
        replacement_path=str(replacement),
        old_semantics=ReferenceSemantics("l36", "快捷键程序", "l36"),
        new_semantics=ReferenceSemantics("l36", "快捷键程序", "l36"),
    )
    res = build_rewrite_plan(str(ws), str(ws), req)
    assert res["ok"] is False and res["code"] == "invalid_operation"


# ---------------------------------------------------------------------------
# 第三轮 P1-3：同文件未命中 platform 块零改动
# ---------------------------------------------------------------------------


def test_unmatched_platform_block_untouched_by_dedupe(ws: Path):
    """块 A 命中并合并同值别名；块 B 未命中且含同值别名 → 键集合保持不变。"""
    save_platform_config(
        ws / "L36程序",
        [
            PlatformDefaults(
                "标准单机芯3D", {"快捷键程序": "贝乐", "快捷按键": "贝乐"}
            ),
            PlatformDefaults(
                "双2D", {"快捷键程序": "量产_默认", "快捷按键": "量产_默认"}
            ),
        ],
    )
    old = ws / "L36程序" / "通用" / "快捷键" / "贝乐"
    new = ws / "L36程序" / "通用" / "快捷键" / "贝乐改"
    req = RewriteRequest(
        operation="rename", target_kind="asset", old_path=str(old), new_path=str(new)
    )
    res = build_rewrite_plan(str(ws), str(ws), req)
    assert res["ok"] is True
    assert apply_rewrite_plan(res["payload"]["plan"], str(ws))["ok"] is True
    from fwasset.core.platform_config import load_platform_config

    blocks = load_platform_config(ws / "L36程序")
    # 块 0（命中）：别名合并为唯一 canonical
    assert list(blocks[0].defaults) == ["快捷键程序"]
    assert blocks[0].defaults["快捷键程序"] == "贝乐改"
    # 块 1（未命中）：零改动
    assert list(blocks[1].defaults) == ["快捷键程序", "快捷按键"]
    assert blocks[1].defaults["快捷键程序"] == "量产_默认"
    assert blocks[1].defaults["快捷按键"] == "量产_默认"


# ---------------------------------------------------------------------------
# 第三轮 P1-2：catalog fail-closed 与未知目录
# ---------------------------------------------------------------------------


def test_unknown_dir_under_module_rejected_as_asset(ws: Path, monkeypatch):
    """合法 label 下无匹配文件的子目录 → invalid_target（不猜 asset 身份）。"""
    empty = ws / "L36程序" / "通用" / "快捷键" / "空目录"
    empty.mkdir(parents=True)
    res = find_references_to(str(ws), ws, empty, "asset")
    assert res["ok"] is False and res["code"] == "invalid_target"


def test_variant_with_matching_file_accepted(ws: Path):
    res = find_references_to(
        str(ws), ws, ws / "L36程序" / "通用" / "快捷键" / "贝乐", "asset"
    )
    assert res["ok"] is True


def test_dir_keyword_module_accepted(ws: Path):
    """`主板` 是 mainboard 的 dir_keywords：scanner 与 R8 都接受该模块。"""
    variant = ws / "L36程序" / "通用" / "主板" / "v3"
    _write(variant / "rom.bin")
    res = find_references_to(str(ws), ws, variant, "asset")
    assert res["ok"] is True


def test_ascii_case_keyword_module_accepted(ws: Path):
    """`MP3` 是 music_files 的 dir_keywords：ASCII 大小写不影响 R8 判定。"""
    from fwasset.core.file_scan import _match_catalog_type
    from fwasset.core.firmware_catalog import enabled_firmware_types

    types = enabled_firmware_types()
    variant = ws / "L36程序" / "通用" / "MP3" / "v1"
    _write(variant / "song.mp3")
    # scanner 层接受
    assert (
        _match_catalog_type(str(variant), ["song.mp3"], types) is not None
    )
    # R8 层同样接受（keyword 小写 vs 模块名原大写不得误拒）
    res = find_references_to(str(ws), ws, variant, "asset")
    assert res["ok"] is True


def test_handcontrol_requires_rom_and_pkg(ws: Path):
    """仓库硬约束：handcontrol_ui 必须同时有 .rom 与 .pkg。"""
    from fwasset.core.file_scan import _match_catalog_type
    from fwasset.core.firmware_catalog import enabled_firmware_types

    types = enabled_firmware_types()
    rom_only = ws / "L36程序" / "通用" / "手控UI" / "只有rom"
    _write(rom_only / "fw.rom")
    pkg_only = ws / "L36程序" / "通用" / "手控UI" / "只有pkg"
    _write(pkg_only / "fw.pkg")
    both = ws / "L36程序" / "通用" / "手控UI" / "齐全"
    _write(both / "fw.rom")
    _write(both / "fw.pkg")

    # file_scan 层：缺任一不误认，齐全才命中
    assert _match_catalog_type(str(rom_only), ["fw.rom"], types) is None
    assert _match_catalog_type(str(pkg_only), ["fw.pkg"], types) is None
    assert _match_catalog_type(str(both), ["fw.rom", "fw.pkg"], types) is not None

    # R8 层：缺任一 invalid_target，齐全接受
    for p, ok in ((rom_only, False), (pkg_only, False), (both, True)):
        res = find_references_to(str(ws), ws, p, "asset")
        assert res["ok"] is ok, (p, res["code"] if not ok else "")


def test_catalog_unavailable_fail_closed(ws: Path, monkeypatch):
    """catalog 不可用 → invalid_target（fail-closed，不降级为纯结构判断）。"""
    import fwasset.core.reference_lookup as rl

    monkeypatch.setattr(rl, "_catalog_context", lambda: None)
    res = find_references_to(
        str(ws), ws, ws / "L36程序" / "通用" / "快捷键" / "贝乐", "asset"
    )
    assert res["ok"] is False and res["code"] == "invalid_target"
