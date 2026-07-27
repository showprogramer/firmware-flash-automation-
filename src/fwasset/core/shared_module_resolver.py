"""共享引用解析器：一套路径覆盖命中 / 缺失（Phase B1/C1）。"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from fwasset.core.model_config import SharedModuleRef, load_model_config
from fwasset.core.platform_config import PlatformDefaults, canonical_module_dir, default_variant_for, load_platform_config_with_status
from fwasset.core.scheme_config import _is_excluded_dir


@dataclass
class SharedModuleResolution:
    ref: SharedModuleRef
    status: Literal["hit", "missing"]
    reason: str = ""
    resolved_path: Path | None = None
    variants: list[Path] = field(default_factory=list)


def _is_under_workspace(path: Path, workspace_root: Path) -> bool:
    try:
        path.resolve().relative_to(workspace_root.resolve())
        return True
    except ValueError:
        return False


def _list_variant_dirs(abs_path: Path) -> list[Path]:
    """过滤后的直接子目录；空则视为叶子 → [abs_path]。"""
    if not abs_path.is_dir():
        return [abs_path]
    children: list[Path] = []
    try:
        for child in abs_path.iterdir():
            if not child.is_dir():
                continue
            if _is_excluded_dir(child.name):
                continue
            children.append(child)
    except OSError:
        return [abs_path]
    children.sort(key=lambda p: p.name)
    return children if children else [abs_path]


def resolve_shared_module(
    ref: SharedModuleRef,
    workspace_root: Path,
    root_for_model_id: Callable[[str], Path | None] | None = None,
) -> SharedModuleResolution:
    """解析一条共享引用 → hit 或 missing（同一路径，无第二套逻辑）。

    ``root_for_model_id`` 为兼容保留（B0 bind 映射注入点）；B1 解析以
    ``source_dir`` 盘上 ``model_id`` 为权威，不依赖该映射（审查 #3）。
    """
    ws = Path(workspace_root).resolve()
    rel = str(ref.source_relative_path or "").strip().replace("\\", "/")
    want_id = str(ref.source_model_id or "").strip()
    if not rel:
        return SharedModuleResolution(
            ref=ref, status="missing", reason="path_not_found"
        )

    # 拒绝相对段中的 . / ..，防止「首段型号 id 校验」与 resolve 后真实路径脱节
    # 例：L36程序/../L50程序/... 会解析到 L50，但若只校验 L36 会误 hit
    parts = Path(rel).parts
    if not parts or any(p in (".", "..") for p in parts):
        return SharedModuleResolution(
            ref=ref, status="missing", reason="out_of_workspace"
        )

    abs_path = (ws / rel).resolve()
    if not _is_under_workspace(abs_path, ws):
        return SharedModuleResolution(
            ref=ref, status="missing", reason="out_of_workspace"
        )

    first = parts[0]
    source_dir = (ws / first).resolve()

    if not source_dir.is_dir():
        # id 映射若存在但路径段不在工作区 → 仍按源未导入（路径指向的型号根不存在）
        return SharedModuleResolution(
            ref=ref, status="missing", reason="source_not_imported"
        )

    mid, status, _ = load_model_config(source_dir)
    if status != "ok" or not mid:
        # 目录在但无合法 model_id：无法完成 id 校验 → 视为源未就绪
        return SharedModuleResolution(
            ref=ref, status="missing", reason="source_not_imported"
        )
    if mid != want_id:
        return SharedModuleResolution(
            ref=ref, status="missing", reason="id_mismatch"
        )

    # 权威来源 = source_dir 磁盘上的 model_id（上面已校验）。
    # 不再与 bind 内存映射交叉比对：该映射可能滞后于盘上文件，或因大小写/
    # 规范化差异把同一根解析成不同 Path，导致误判 id_mismatch（审查 #3）。
    # .. 越界由前置段校验与下方 source_dir 归属双保险覆盖。

    # 双保险：resolve 后的目标必须仍落在已校验的 source_dir 下
    # （即使将来放宽对 .. 的拒绝，也不能跨到其它型号根）
    if not _is_under_workspace(abs_path, source_dir):
        return SharedModuleResolution(
            ref=ref, status="missing", reason="out_of_workspace"
        )

    # --- 按 mode 分支 ---
    if ref.mode == "follow_default":
        return _resolve_follow_default(ref, source_dir, abs_path)

    # static（默认）：固定版本，Phase B 行为
    if not abs_path.exists():
        return SharedModuleResolution(
            ref=ref, status="missing", reason="path_not_found"
        )
    variants = _list_variant_dirs(abs_path)
    return SharedModuleResolution(
        ref=ref,
        status="hit",
        reason="",
        resolved_path=abs_path,
        variants=variants,
    )


# ---------------------------------------------------------------------------
# Phase C1 辅助：follow_default 解析
# ---------------------------------------------------------------------------

def _module_in_defaults(block: PlatformDefaults, module: str) -> bool:
    """规范化匹配：platform 块的 defaults 中是否含该模块键。"""
    want = canonical_module_dir(module)
    return any(canonical_module_dir(key) == want for key in block.defaults)


def _resolve_follow_default(
    ref: SharedModuleRef,
    source_dir: Path,
    module_dir: Path,
) -> SharedModuleResolution:
    """follow_default 模式：读源 平台配置.toml 动态查找默认变体。

    ``module_dir`` 是共同前置校验后的 abs_path；
    C2 service 注册时已保证它指向模块目录而非变体目录。
    """
    if not module_dir.is_dir():
        return SharedModuleResolution(
            ref=ref, status="missing", reason="path_not_found"
        )

    platforms, plt_status, _ = load_platform_config_with_status(source_dir)
    if plt_status != "ok" or not platforms:
        return SharedModuleResolution(
            ref=ref, status="missing", reason="no_source_platform"
        )

    if ref.source_platform:
        # 显式 platform：必须找到对应块
        block = next((p for p in platforms if p.platform_name == ref.source_platform), None)
        if block is None:
            return SharedModuleResolution(
                ref=ref, status="missing", reason="no_source_platform"
            )
        if not _module_in_defaults(block, ref.source_module):
            return SharedModuleResolution(
                ref=ref, status="missing", reason="no_source_default"
            )
        variant_name = default_variant_for(platforms, block.platform_name, ref.source_module)
    else:
        # 自动检测：依次试所有 platform，取第一个含该模块默认的
        variant_name = ""
        for p in platforms:
            if _module_in_defaults(p, ref.source_module):
                variant_name = default_variant_for(platforms, p.platform_name, ref.source_module)
                break
        if variant_name == "" and not any(
            _module_in_defaults(p, ref.source_module) for p in platforms
        ):
            return SharedModuleResolution(
                ref=ref, status="missing", reason="no_source_default"
            )

    resolved_path = module_dir / variant_name if variant_name else module_dir

    if not resolved_path.exists():
        return SharedModuleResolution(
            ref=ref, status="missing", reason="path_not_found"
        )

    return SharedModuleResolution(
        ref=ref,
        status="hit",
        reason="",
        resolved_path=resolved_path,
        variants=[resolved_path],  # follow_default 已确定具体变体，不再展开
    )
