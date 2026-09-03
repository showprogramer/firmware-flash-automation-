"""TASK-20260901-r8-reference-integrity 人工验证场景（不经 UI，直接驱动 core API）。

在隔离的 .scenario/r8/ 目录搭建双型号工作区 + 独立配置，不触碰本机真实固件
目录与真实 TOML。按「无 UI 的人工验证等效规则」由 Agent 执行，用户确认后提交。

用法（Windows PowerShell，开发模式）:

    uv run python scripts\\verify_r8_reference_integrity.py

四类场景：
  1. 反查     find_references_to 三类引用命中 + 删除预检 issue 阻止
  2. 迁移     follow_default → follow_asset 幂等迁移与失败保留
  3. 级联     rename/update 级联改写 + CAS 回滚 + 阻止码
  4. 收口     ensure_model_ids 未配置零写 + 越界整批零写
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from fwasset.core.config_io import atomic_write_text
from fwasset.core.model_config import (
    MODEL_CONFIG_FILENAME,
    SharedModuleRef,
    load_shared_modules,
    save_model_id,
    save_shared_module,
)
from fwasset.core.platform_config import PlatformDefaults, save_platform_config
from fwasset.core.services.model_id_service import ensure_model_ids
from fwasset.core.services.reference_service import (
    apply_rewrite_plan,
    build_rewrite_plan,
    migrate_follow_default_refs,
)
from fwasset.core.shared_module_resolver import resolve_shared_module
from fwasset.core.types import ReferenceSemantics, RewriteRequest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCENARIO = REPO_ROOT / ".scenario" / "r8"
WS = SCENARIO / "工作区"

failures: list[str] = []


def check(name: str, ok: bool) -> None:
    mark = "OK  " if ok else "FAIL"
    print(f"  [{mark}] {name}")
    if not ok:
        failures.append(name)


def write_file(p: Path, content: str = "x") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def borrow(target: Path, key: str, rel: str, mode: str, sid: str = "l36") -> None:
    save_shared_module(
        target,
        SharedModuleRef(
            module_key=key,
            source_model_id=sid,
            source_group=sid,
            source_module=key,
            source_relative_path=rel,
            mode=mode,  # type: ignore[arg-type]
        ),
    )


def prepare() -> Path:
    if SCENARIO.exists():
        shutil.rmtree(SCENARIO)
    l36 = WS / "L36程序"
    l50 = WS / "L50程序"
    l36.mkdir(parents=True)
    l50.mkdir(parents=True)
    save_model_id(l36, "l36")
    save_model_id(l50, "l50")
    save_platform_config(
        l36,
        [PlatformDefaults("标准单机芯3D", {"快捷键程序": "贝乐", "主板程序": "v1"})],
    )
    write_file(l36 / "通用" / "快捷键" / "贝乐" / "key.hex")
    write_file(l36 / "通用" / "快捷键" / "量产_默认" / "key.hex")
    write_file(l36 / "通用" / "主板程序" / "v1" / "rom.bin")
    write_file(l50 / "通用" / "主板程序" / "v9" / "rom.bin")
    print(f"准备：隔离工作区 {WS}")
    return WS


def scenario_lookup(ws: Path) -> None:
    print("\n场景 1：反查（三类引用命中 + issue 阻止）")
    from fwasset.core.reference_lookup import find_dangling_anchors, find_references_to

    borrow(ws / "L50程序", "快捷键程序", "L36程序/通用/快捷键/贝乐", "follow_asset")
    target = ws / "L36程序" / "通用" / "快捷键" / "贝乐"
    res = find_references_to(str(ws), str(ws), str(target), "asset")
    hits = res["payload"]["result"].hits
    check("借用锚定命中（follow_asset）", any(h.kind == "shared_follow_asset" for h in hits))
    # 平台默认命中（模块级）
    res = find_references_to(
        str(ws), str(ws), str(ws / "L36程序" / "通用" / "快捷键"), "module"
    )
    hits = res["payload"]["result"].hits
    check(
        "平台默认命中（defaults 键）",
        any(h.kind == "platform_default" and h.raw_value == "贝乐" for h in hits),
    )
    # 悬空锚点：路径删除后仍可反查（支撑 path_identity_conflict）
    shutil.rmtree(target)
    res = find_dangling_anchors(str(ws), str(ws), str(target))
    check(
        "悬空锚点检查命中",
        any(h.kind == "shared_follow_asset" for h in res["payload"]["result"].hits),
    )
    # 还原被删目录（模拟回收站撤销），供后续场景使用
    write_file(target / "key.hex")
    # 配置损坏 → 反查报告 issue（删除预检将阻止）
    (ws / "L50程序" / MODEL_CONFIG_FILENAME).write_text("[[broken\n", encoding="utf-8")
    res = find_references_to(
        str(ws), str(ws), str(ws / "L36程序" / "通用" / "快捷键"), "module"
    )
    issues = res["payload"]["result"].issues
    check("损坏配置进入 issues（不静默）", any(i.category == "model_config_parse_error" for i in issues))
    # 还原损坏文件供后续场景（save_model_id 会拒绝覆盖损坏文件，需直接重写）
    (ws / "L50程序" / MODEL_CONFIG_FILENAME).write_text(
        "model_id = 'l50'\n", encoding="utf-8"
    )
    borrow(ws / "L50程序", "快捷键程序", "L36程序/通用/快捷键/贝乐", "follow_asset")


def scenario_migrate(ws: Path) -> None:
    print("\n场景 2：follow_default → follow_asset 迁移")
    borrow(
        ws / "L50程序",
        "主板程序",
        "L36程序/通用/主板程序",
        "follow_default",
    )
    res = migrate_follow_default_refs(str(ws), str(ws))
    check("迁移报告 converted=1", res["payload"]["converted"] == 1)
    refs = {r.module_key: r for r in load_shared_modules(ws / "L50程序")}
    ref = refs["主板程序"]
    check("mode 变为 follow_asset", ref.mode == "follow_asset")
    check("锚定到迁移时默认程序", ref.source_relative_path == "L36程序/通用/主板程序/v1")
    check("解析仍命中", resolve_shared_module(ref, ws).status == "hit")
    second = migrate_follow_default_refs(str(ws), str(ws))
    check("二次运行为零改动（幂等）", second["payload"]["converted"] == 0)


def scenario_cascade(ws: Path) -> None:
    print("\n场景 3：级联改写（rename/update + CAS 回滚）")
    # rename：级联改写借用与 defaults，解析命中
    old = ws / "L36程序" / "通用" / "快捷键" / "贝乐"
    new = ws / "L36程序" / "通用" / "快捷键" / "贝乐改"
    req = RewriteRequest(
        operation="rename", target_kind="asset", old_path=str(old), new_path=str(new)
    )
    res = build_rewrite_plan(str(ws), str(ws), req)
    check("rename 计划就绪", res["ok"] is True)
    plan = res["payload"]["plan"]
    check("计划含 model_config 与 platform_config", len(plan.files) == 2)
    old.rename(new)
    res = apply_rewrite_plan(plan, str(ws))
    check("apply 成功", res["ok"] is True)
    refs = {r.module_key: r for r in load_shared_modules(ws / "L50程序")}
    check("借用改写到新路径", refs["快捷键程序"].source_relative_path == "L36程序/通用/快捷键/贝乐改")
    check("解析命中新路径", resolve_shared_module(refs["快捷键程序"], ws).status == "hit")
    import tomllib

    with open(ws / "L36程序" / "平台配置.toml", "rb") as f:
        defaults = tomllib.load(f)["platform"][0]["defaults"]
    check("defaults value 改写", defaults["快捷键程序"] == "贝乐改")

    # update：follow_asset 跟随 replacement；语义变更阻止
    replacement = ws / "L36程序" / "通用" / "快捷键" / "贝乐v3"
    write_file(replacement / "key.hex")
    req = RewriteRequest(
        operation="update",
        target_kind="asset",
        old_path=str(new),
        replacement_path=str(replacement),
        old_semantics=ReferenceSemantics("l36", "快捷键程序", "l36"),
        new_semantics=ReferenceSemantics("l36", "快捷键程序", "l36"),
    )
    res = build_rewrite_plan(str(ws), str(ws), req)
    check("update 计划就绪", res["ok"] is True)
    res = apply_rewrite_plan(res["payload"]["plan"], str(ws))
    check("update apply 成功", res["ok"] is True)
    refs = {r.module_key: r for r in load_shared_modules(ws / "L50程序")}
    check("follow_asset 跟随 replacement", refs["快捷键程序"].source_relative_path == "L36程序/通用/快捷键/贝乐v3")

    # 改类型 → unsupported_semantic_change
    bad_replacement = ws / "L36程序" / "通用" / "主板程序" / "v2b"
    write_file(bad_replacement / "rom.bin")
    bad_req = RewriteRequest(
        operation="update",
        target_kind="asset",
        old_path=str(replacement),
        replacement_path=str(bad_replacement),
        old_semantics=ReferenceSemantics("l36", "快捷键程序", "l36"),
        new_semantics=ReferenceSemantics("l36", "主板程序", "l36"),
    )
    res = build_rewrite_plan(str(ws), str(ws), bad_req)
    check("改类型被阻止（unsupported_semantic_change）", res["code"] == "unsupported_semantic_change")

    # stale plan：build 后第三方改动 → 零写入
    old2 = ws / "L36程序" / "通用" / "快捷键" / "贝乐v3"
    new2 = ws / "L36程序" / "通用" / "快捷键" / "贝乐v4"
    req = RewriteRequest(
        operation="rename", target_kind="asset", old_path=str(old2), new_path=str(new2)
    )
    plan = build_rewrite_plan(str(ws), str(ws), req)["payload"]["plan"]
    old2.rename(new2)
    (ws / "L36程序" / "平台配置.toml").write_text("# tampered\n", encoding="utf-8")
    res = apply_rewrite_plan(plan, str(ws))
    check("stale plan 零写入", res["ok"] is False and res["code"] == "stale_plan")


def scenario_gate(ws: Path) -> None:
    print("\n场景 4：ensure_model_ids 门闩收口")
    fresh = WS / "L70程序"
    fresh.mkdir(parents=True)
    res = ensure_model_ids([fresh], None, log_fn=lambda _m: None)
    check("未配置 → not_configured 零写盘", res["code"] == "not_configured" and not (fresh / MODEL_CONFIG_FILENAME).exists())
    outside = SCENARIO / "外部" / "L80程序"
    outside.mkdir(parents=True)
    res = ensure_model_ids([fresh, outside], str(WS), log_fn=lambda _m: None)
    check("越界 → 整批零写", res["code"] == "out_of_workspace" and not (fresh / MODEL_CONFIG_FILENAME).exists())
    res = ensure_model_ids([fresh], str(WS), log_fn=lambda _m: None)
    check("合法批次正常分配", res["ok"] is True and res["payload"]["assigned"].get("L70程序") == "l70")


def main() -> int:
    ws = prepare()
    scenario_lookup(ws)
    scenario_migrate(ws)
    scenario_cascade(ws)
    scenario_gate(ws)

    print("\n========== 验证结果 ==========")
    if failures:
        print(f"失败 {len(failures)} 项：{'、'.join(failures)}")
        return 1
    print("四类场景全部通过（OK）：反查 / 迁移 / 级联 / 收口")
    print(f"现场保留在 {SCENARIO}，可人工核查后删除")
    return 0


if __name__ == "__main__":
    _ = atomic_write_text  # 保持导入面与实现一致（场景内 monkeypatch 不需要）
    sys.exit(main())
