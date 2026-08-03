"""共享登记入口服务（Phase B2）。

`set_shared_module`：从工作区内已扫描到的真实来源资产解析出四字段引用，
做工作区归属 + 源型号 id 校验、同键冲突检测，写入目标型号根的 `型号配置.toml`。
`clear_shared_module`：删除目标模块的引用条目（只删 toml 不删文件）。

数据层落盘复用 B1 的 `save_shared_module` / `remove_shared_module`；冲突拦截在
本服务层（先 `load_shared_modules` 查重），`save_shared_module` 自身是幂等覆盖写。
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fwasset.core.model_config import (
    SharedModuleRef,
    load_model_config,
    load_shared_modules,
    remove_shared_module,
    save_shared_module,
)
from fwasset.core.path_guard import PathGuardError, assert_within_workspace
from fwasset.core.platform_config import load_platform_config_with_status
from fwasset.core.services.platform_default_service import canonical_module_dir
from fwasset.core.types import FirmwareAsset

__all__ = [
    "set_shared_module",
    "clear_shared_module",
]


def _resolve_relative(path: Path, workspace_root: Path) -> str | None:
    """绝对路径 → 工作区根相对路径（统一 `/`）；越界/非法返回 None。"""
    try:
        resolved = assert_within_workspace(path, workspace_root)
    except PathGuardError:
        return None
    ws = Path(workspace_root).resolve()
    return "/".join(resolved.relative_to(ws).parts)


def _source_model_root(asset_path: Path, workspace_root: Path) -> Path | None:
    """来源资产所在型号根。

    单型号根（首段为 通用/定制）→ 工作区根本身；
    多型号根（首段为型号目录）→ 工作区根 / 首段。
    越界返回 None。
    """
    rel = _resolve_relative(asset_path, workspace_root)
    if rel is None:
        return None
    parts = rel.split("/")
    first = parts[0]
    if first in ("通用", "定制"):
        return Path(workspace_root).resolve()
    return Path(workspace_root).resolve() / first


def _module_key_for_asset(asset: FirmwareAsset) -> str:
    """资产 → 规范模块键（catalog label 优先；否则空）。"""
    label = str(asset.get("firmware_label", "")).strip()
    if label:
        return canonical_module_dir(label)
    return ""


def _module_dir_rel(
    asset_path: Path,
    workspace_root: Path,
) -> str | None:
    """follow_default 登记：从资产路径派生模块目录的工作区相对路径。

    - parent.name in ("通用", "定制") → 资产路径本身即模块目录（唯一变体）
    - 否则 → 父目录为模块目录（变体子目录）
    """
    parent = asset_path.parent
    if parent.name in ("通用", "定制"):
        module_path = asset_path
    else:
        module_path = parent
    return _resolve_relative(module_path, workspace_root)


def _source_platform_exists(src_root: Path, source_platform: str) -> bool:
    """检查 source_platform 是否存在于源型号的 平台配置.toml 中。"""
    platforms, status, _ = load_platform_config_with_status(src_root)
    if status != "ok":
        return False
    return any(p.platform_name == source_platform for p in platforms)


def _source_has_platform_config(src_root: Path) -> bool:
    """检查源型号是否有可用的 平台配置.toml（至少一个 platform 块）。"""
    platforms, status, _ = load_platform_config_with_status(src_root)
    if status != "ok":
        return False
    return len(platforms) > 0


def set_shared_module(
    target_model_root: str | Path,
    source_asset: FirmwareAsset,
    workspace_root: str | Path,
    module_key: str = "",
    overwrite: bool = False,
    mode: str = "static",
    source_platform: str = "",
    log_fn: Callable[[str], None] = print,
) -> dict:
    """手动登记一条共享引用到目标型号根的 `型号配置.toml`。

    仅接受工作区内已扫描到的真实来源资产；从资产路径反推源型号根并读其
    盘上 `model_id` 作为 `source_model_id`，相对工作区根算 `source_relative_path`。
    """
    root = str(target_model_root or "").strip()
    if not root:
        return {
            "ok": False,
            "code": "invalid_args",
            "message": "登记共享来源失败：目标型号根不能为空",
            "payload": {},
        }
    asset_path_str = str(source_asset.get("path", "") or "").strip()
    if not asset_path_str:
        return {
            "ok": False,
            "code": "invalid_args",
            "message": "登记共享来源失败：来源资产路径不能为空",
            "payload": {},
        }

    source_module = _module_key_for_asset(source_asset)
    key = canonical_module_dir(module_key) if module_key else source_module
    if not source_module:
        message = "登记共享来源失败：来源资产缺少可识别模块名"
        log_fn(message)
        return {
            "ok": False,
            "code": "invalid_args",
            "message": message,
            "payload": {},
        }
    if not key:
        message = "登记共享来源失败：目标模块不能为空"
        log_fn(message)
        return {
            "ok": False,
            "code": "invalid_args",
            "message": message,
            "payload": {},
        }
    if key != source_module:
        message = (
            f"登记共享来源失败：目标模块「{key}」与来源模块「{source_module}」不一致"
        )
        log_fn(message)
        return {
            "ok": False,
            "code": "module_mismatch",
            "message": message,
            "payload": {
                "module_key": key,
                "source_module": source_module,
            },
        }

    ws = Path(workspace_root)
    target_root = Path(root)
    asset_path = Path(asset_path_str)

    # 目标写入路径守卫（R5）：型号配置.toml 必须落在工作区内
    try:
        target_root = assert_within_workspace(target_root, ws)
    except PathGuardError as exc:
        message = f"登记共享来源失败：{exc}"
        log_fn(message)
        return {
            "ok": False,
            "code": "out_of_workspace",
            "message": message,
            "payload": {},
        }

    # 相对路径 + 越界校验
    rel = _resolve_relative(asset_path, ws)
    if rel is None:
        message = "登记共享来源失败：来源资产不在当前工作区内"
        log_fn(message)
        return {
            "ok": False,
            "code": "out_of_workspace",
            "message": message,
            "payload": {},
        }

    # 源型号根 + model_id
    src_root = _source_model_root(asset_path, ws)
    if src_root is None:
        message = "登记共享来源失败：来源资产不在当前工作区内"
        log_fn(message)
        return {
            "ok": False,
            "code": "out_of_workspace",
            "message": message,
            "payload": {},
        }
    mid, status, _ = load_model_config(src_root)
    if status != "ok" or not mid:
        message = "登记共享来源失败：来源型号尚未配置 id，请先扫描来源型号"
        log_fn(message)
        return {
            "ok": False,
            "code": "source_no_id",
            "message": message,
            "payload": {"source_root": str(src_root)},
        }

    # follow_default：派生模块目录路径；其余模式沿用 rel（固定版本）
    clean_mode = mode if mode in ("static", "follow_default") else "static"
    if clean_mode == "follow_default":
        final_rel = _module_dir_rel(asset_path, ws)
        if final_rel is None:
            message = "登记共享来源失败：无法从来源资产路径派生模块目录"
            log_fn(message)
            return {
                "ok": False,
                "code": "out_of_workspace",
                "message": message,
                "payload": {},
            }
        # 显式 source_platform 需存在于源平台配置中
        clean_platform = str(source_platform or "").strip()
        if clean_platform and not _source_platform_exists(src_root, clean_platform):
            message = f"登记共享来源失败：来源型号平台配置中不存在平台「{clean_platform}」"
            log_fn(message)
            return {
                "ok": False,
                "code": "invalid_args",
                "message": message,
                "payload": {"source_platform": clean_platform},
            }
        # 自动检测模式：源型号必须有 平台配置.toml
        if not clean_platform and not _source_has_platform_config(src_root):
            message = "登记共享来源失败：自动更新模式要求来源型号有平台配置，请先在来源型号设置平台默认"
            log_fn(message)
            return {
                "ok": False,
                "code": "no_platform_config",
                "message": message,
                "payload": {"source_root": str(src_root)},
            }
    else:
        final_rel = rel
        clean_platform = ""  # 固定版本不写 source_platform

    # 冲突检测（load 查重；save_shared_module 自身是幂等覆盖）
    existing = load_shared_modules(target_root)
    existing_ref = next((r for r in existing if r.module_key == key), None)
    if existing_ref is not None and not overwrite:
        message = f"模块「{key}」已登记共享来源，是否覆盖？"
        log_fn(message)
        return {
            "ok": False,
            "code": "conflict",
            "message": message,
            "payload": {
                "existing": {
                    "module_key": existing_ref.module_key,
                    "source_model_id": existing_ref.source_model_id,
                    "source_group": existing_ref.source_group,
                    "source_module": existing_ref.source_module,
                    "source_relative_path": existing_ref.source_relative_path,
                },
            },
        }

    ref = SharedModuleRef(
        module_key=key,
        source_model_id=mid,
        source_group=mid,
        source_module=source_module,
        source_relative_path=final_rel,
        mode=clean_mode,  # type: ignore[arg-type]
        source_platform=clean_platform,
    )

    try:
        config_path = save_shared_module(target_root, ref)
    except Exception as exc:  # noqa: BLE001
        message = f"登记共享来源失败：写入型号配置失败 ({exc})"
        log_fn(message)
        return {
            "ok": False,
            "code": "write_failed",
            "message": message,
            "payload": {},
        }

    message = f"已将「{key}」登记为共享来源（来自 {mid}）"
    log_fn(message)
    return {
        "ok": True,
        "code": "ok",
        "message": message,
        "payload": {
            "config_path": str(config_path),
            "module_key": key,
            "source_model_id": mid,
            "source_relative_path": final_rel,
            "overwritten": existing_ref is not None,
        },
    }


def clear_shared_module(
    target_model_root: str | Path,
    module_key: str,
    workspace_root: str | Path,
    log_fn: Callable[[str], None] = print,
) -> dict:
    """取消登记：删除目标型号根 `型号配置.toml` 中的共享引用条目。

    只删 toml 条目，不删任何固件文件（B4b）。不存在的键 → 仍 `ok`（幂等）。
    """
    root = str(target_model_root or "").strip()
    key = canonical_module_dir(module_key) if module_key else ""
    if not root or not key:
        return {
            "ok": False,
            "code": "invalid_args",
            "message": "取消共享失败：型号根与模块名均不能为空",
            "payload": {},
        }

    # 目标写入路径守卫（R5）
    try:
        target_root = assert_within_workspace(root, workspace_root)
    except PathGuardError as exc:
        message = f"取消共享失败：{exc}"
        log_fn(message)
        return {
            "ok": False,
            "code": "out_of_workspace",
            "message": message,
            "payload": {},
        }

    try:
        remove_shared_module(target_root, key)
    except Exception as exc:  # noqa: BLE001
        message = f"取消共享失败：写入型号配置失败 ({exc})"
        log_fn(message)
        return {
            "ok": False,
            "code": "write_failed",
            "message": message,
            "payload": {},
        }

    message = f"已取消「{key}」的共享来源登记"
    log_fn(message)
    return {
        "ok": True,
        "code": "ok",
        "message": message,
        "payload": {"module_key": key},
    }
