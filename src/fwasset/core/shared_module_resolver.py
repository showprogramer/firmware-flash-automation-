"""共享引用解析器：一套路径覆盖命中 / 缺失（Phase B1）。"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from fwasset.core.model_config import SharedModuleRef, load_model_config
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
