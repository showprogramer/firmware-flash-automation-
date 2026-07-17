"""型号持久 id：ensure_model_ids（先读全量已有 id，再为无 id 者生成）。"""
from __future__ import annotations

from pathlib import Path

from fwasset.core.model_config import (
    load_model_config,
    save_model_id,
    slugify_model_id,
)

__all__ = ["ensure_model_ids"]


def _allocate_id(base: str, occupied: set[str]) -> str:
    candidate = base
    n = 2
    while candidate in occupied:
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def ensure_model_ids(
    workspace_roots: list[str | Path],
    log_fn=print,
) -> dict:
    """为各型号根确保 ``型号配置.toml`` 中有 model_id。

    两遍扫描：
    1. 读全量已有合法 id → occupied；
    2. 仅对 missing/no_id 的根 slug + 碰撞后缀 + 写入。

    损坏根跳过不覆盖，其余继续；若有损坏则整体 ``code=parse_error``。
    写盘失败立即返回 ``write_failed``（已成功写入的根保留）。
    """
    roots = [Path(r) for r in (workspace_roots or []) if r and Path(r).is_dir()]
    occupied: set[str] = set()
    existing: dict[str, str] = {}
    damaged: list[str] = []
    need_assign: list[Path] = []

    for root in roots:
        mid, status, error = load_model_config(root)
        key = root.name
        if status == "ok" and mid:
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
                },
            }
        occupied.add(candidate)
        assigned[root.name] = candidate

    payload = {
        "assigned": assigned,
        "existing": existing,
        "damaged": damaged,
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
