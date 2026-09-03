"""型号持久 id：ensure_model_ids（先读全量已有 id，再为无 id 者生成）。

R1/R10 门闩收口（TASK-20260901-r8-reference-integrity 规则 6）：
``configured_root`` 为权威写操作根；未配置不写盘（model_id 映射为空、功能降级）；
整批先校验归属，任一越界/非法 → 整批零写。
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from fwasset.core.model_config import (
    load_model_config,
    save_model_id,
    slugify_model_id,
)
from fwasset.core.path_guard import PathGuardError, assert_within_workspace
from fwasset.core.types import ServiceResult

__all__ = ["ensure_model_ids"]


def _allocate_id(base: str, occupied: set[str]) -> str:
    candidate = base
    n = 2
    while candidate in occupied:
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def ensure_model_ids(
    workspace_roots: Sequence[str | Path],
    configured_root: str | Path | None,
    log_fn: Callable[..., None] = print,
) -> ServiceResult:
    """为各型号根确保 ``型号配置.toml`` 中有 model_id。

    门闩（规则 6）：
    - ``configured_root`` 为空 → ``not_configured``，**不写任何盘**（调用方
      仅按已有 id 只读降级；scan_meta 兜底恢复出的根不得当作配置根传入）；
    - 先校验整批再动作，禁止静默过滤：非空、绝对路径、归属工作区、存在且为
      目录任一不过 → 整批失败（``out_of_workspace`` / ``invalid_root``）零写，
      payload 分列 ``valid_roots`` / ``rejected_roots``。

    两遍扫描：
    1. 读全量已有合法 id → occupied；
    2. 仅对 missing/no_id 的根 slug + 碰撞后缀 + 写入。

    损坏根跳过不覆盖，其余继续；若有损坏则整体 ``code=parse_error``。
    写盘失败立即返回 ``write_failed``（已成功写入的根保留）。
    既有重复 model_id 计入 ``payload["duplicates"]`` 报告，不阻断扫描。
    """
    configured = str(configured_root or "").strip()
    if not configured:
        return {
            "ok": False,
            "code": "not_configured",
            "message": "尚未配置程序文件夹，型号 id 保持只读",
            "payload": {
                "assigned": {},
                "existing": {},
                "damaged": [],
                "duplicates": [],
            },
        }

    raw_roots = list(workspace_roots or [])
    valid_roots: list[Path] = []
    rejected_roots: list[dict[str, str]] = []
    saw_out_of_workspace = False
    for raw in raw_roots:
        raw_str = str(raw or "").strip()
        if not raw_str:
            rejected_roots.append({"root": raw_str, "reason": "empty"})
            continue
        if not Path(raw_str).is_absolute():
            rejected_roots.append({"root": raw_str, "reason": "not_absolute"})
            continue
        try:
            resolved = assert_within_workspace(raw_str, configured)
        except PathGuardError as exc:
            rejected_roots.append({"root": raw_str, "reason": str(exc)})
            saw_out_of_workspace = True
            continue
        if not resolved.is_dir():
            rejected_roots.append({"root": raw_str, "reason": "not_a_directory"})
            continue
        valid_roots.append(resolved)

    if rejected_roots:
        # 越界 → out_of_workspace；其余结构问题 → invalid_root（P2-1）
        code = "out_of_workspace" if saw_out_of_workspace else "invalid_root"
        message = (
            f"存在越界的型号根（{len(rejected_roots)} 个），本批次零写入"
            if saw_out_of_workspace
            else f"存在非法的型号根（{len(rejected_roots)} 个），本批次零写入"
        )
        log_fn(message)
        return {
            "ok": False,
            "code": code,
            "message": message,
            "payload": {
                "valid_roots": [str(r) for r in valid_roots],
                "rejected_roots": rejected_roots,
                "assigned": {},
                "existing": {},
                "damaged": [],
                "duplicates": [],
            },
        }

    occupied: set[str] = set()
    existing: dict[str, str] = {}
    damaged: list[str] = []
    duplicates: list[str] = []
    need_assign: list[Path] = []

    for root in valid_roots:
        mid, status, error = load_model_config(root)
        key = root.name
        if status == "ok" and mid:
            if mid in occupied:
                duplicates.append(mid)
            occupied.add(mid)
            existing[key] = mid
        elif status in ("missing", "no_id"):
            need_assign.append(root)
        elif status in ("parse_error", "parser_missing"):
            damaged.append(key)
            log_fn(f"型号配置读取失败，跳过写入: {root} ({error})")
        else:
            need_assign.append(root)

    assigned: dict[str, str] = {}
    for root in need_assign:
        base = slugify_model_id(root.name)
        candidate = _allocate_id(base, occupied)
        try:
            save_model_id(root, candidate)
        except Exception as exc:  # noqa: BLE001
            message = f"写入型号配置失败: {exc}"
            log_fn(message)
            return {
                "ok": False,
                "code": "write_failed",
                "message": message,
                "payload": {
                    "assigned": assigned,
                    "existing": existing,
                    "damaged": damaged,
                    "duplicates": duplicates,
                },
            }
        occupied.add(candidate)
        assigned[root.name] = candidate

    payload = {
        "assigned": assigned,
        "existing": existing,
        "damaged": damaged,
        "duplicates": duplicates,
    }
    if damaged:
        message = "部分型号配置读取失败，已跳过损坏文件并保留原内容"
        log_fn(message)
        return {
            "ok": False,
            "code": "parse_error",
            "message": message,
            "payload": payload,
        }
    return {
        "ok": True,
        "code": "ok",
        "message": "型号 id 已就绪",
        "payload": payload,
    }
