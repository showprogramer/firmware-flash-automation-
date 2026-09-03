"""统一工作区路径守卫（REVIEW R5）。

所有文件写操作（现有 TOML 写入口与未来 CRUD）都必须先经过
``assert_within_workspace`` 校验目标路径在工作区根之下，不允许自行实现
第二套路径归属判断。
"""

from __future__ import annotations

import os
from pathlib import Path


class PathGuardError(ValueError):
    """路径守卫拒绝：目标不在工作区内或输入不合法。"""


def _normalize_for_compare(p: Path) -> str:
    """统一大小写与路径分隔符，供前缀边界比较使用。

    顺序敏感：必须先在原始分隔符形式上 ``normcase``（Windows 的 C 实现会把
    ``/`` 也规范化为 ``\\``），再统一为正斜杠比较；先转斜杠再 normcase
    会让前缀边界比较永不匹配（2026-08-03 回归）。
    """
    value = os.path.normcase(str(p))
    return value.replace("\\", "/").rstrip("/")


def normalize_workspace_path(value: str | Path | None) -> str:
    """返回用于工作区路径比较的规范化值；空值返回空字符串。"""
    raw_value = str(value or "").strip()
    if not raw_value:
        return ""
    return _normalize_for_compare(Path(raw_value).resolve())


def assert_within_workspace(path: str | Path, workspace_root: str | Path) -> Path:
    """断言 ``path`` 解析后位于 ``workspace_root`` 之下（允许相等），返回 resolve 后的 Path。

    最低契约（REVIEW R5）：
    1. 工作区根未配置（空字符串）直接拒绝；
    2. 目标必须是绝对路径——相对路径按进程 cwd 解析会误判归属；
    3. resolve 前对原始路径段的显式 ``..`` 拒绝（``.`` 无害且会被 Path 折叠，
       不作为拒绝理由）；
    4. resolve 后按 ``normcase`` + 正斜杠统一比较，确认目标仍在工作区内；
    5. Windows 大小写差异经 ``os.path.normcase`` 归一，避免误判越界。
    """
    raw_root = str(workspace_root or "").strip()
    if not raw_root:
        raise PathGuardError("工作区根目录未配置，请先在设置中配置程序文件夹")

    raw_path = str(path)
    if not Path(raw_path).is_absolute():
        raise PathGuardError(f"路径必须为绝对路径，已拒绝写入：{raw_path}")
    if any(seg == ".." for seg in Path(raw_path).parts):
        raise PathGuardError(f"路径含越界段「..」，已拒绝写入：{raw_path}")

    candidate = Path(raw_path).resolve()
    root = Path(raw_root).resolve()

    cand = _normalize_for_compare(candidate)
    base = _normalize_for_compare(root)
    if cand != base and not cand.startswith(base + "/"):
        raise PathGuardError(
            f"路径不在工作区内，已拒绝写入：{raw_path}（工作区根：{raw_root}）"
        )
    return candidate


def is_same_or_under(path: str | Path, boundary: str | Path) -> bool:
    """规范化后判断 ``path`` 是否等于或在 ``boundary`` 之下。

    纯字符串比较（normcase + 正斜杠归一），不触碰文件系统，供数据库中
    存量路径（hidden_items、assets.path）做边界归属判断使用；禁止业务代码
    用裸 ``startswith`` 自行判断（会把 ``...\\A`` 与 ``...\\AB`` 混淆）。
    """
    p = _normalize_for_compare(Path(str(path)))
    b = _normalize_for_compare(Path(str(boundary)))
    if not b:
        return False
    return p == b or p.startswith(b + "/")


def contained_subpath(path: str | Path, boundary: str | Path) -> Path | None:
    """resolved 归属判定：``path`` 解析后在 ``boundary``（含相等）内返回
    resolved Path，否则返回 ``None``。

    归属判定用 :meth:`pathlib.Path.relative_to`（Windows 路径语义大小写与
    分隔符不敏感），供写入口校验子树成员关系；与 :func:`is_same_or_under`
    的区别是会真正 resolve（跟随符号链接、折叠 ``..``）。
    """
    try:
        resolved = Path(str(path)).resolve()
        base = Path(str(boundary)).resolve()
        resolved.relative_to(base)
    except (OSError, ValueError):
        return None
    return resolved


def is_within_boundary(path: str | Path, boundary: str | Path) -> bool:
    """祖先/后代判定（R8）：词法（normcase）或 resolved 归属任一命中。

    junction 经 resolve 指向的真实后代也能命中；与 R3 asset_index 的
    ``_within_boundary`` 语义一致。引用反查、级联改写与锚点检查统一使用，
    禁止业务代码只用词法 ``is_same_or_under`` 自行判断。
    """
    if is_same_or_under(path, boundary):
        return True
    return contained_subpath(path, boundary) is not None


def same_path_identity(a: str | Path, b: str | Path) -> bool:
    """物理/词法身份判定：``a`` 与 ``b`` 是否指同一路径（R8）。

    两层任一命中即同一身份：
    1. 词法层：原始串 normcase + 分隔符归一后相等（大小写/``/`` vs ``\\`` 变体）；
    2. resolved 层：resolve 后 normcase 归一相等（junction/符号链接折叠）。

    纯函数，不依赖数据库；asset_index 的等价 path 匹配与引用反查共用，
    禁止业务代码各写第三套路径比较。
    """
    raw_a = str(a or "").strip()
    raw_b = str(b or "").strip()
    if not raw_a or not raw_b:
        return False
    if _normalize_for_compare(Path(raw_a)) == _normalize_for_compare(Path(raw_b)):
        return True
    try:
        res_a = _normalize_for_compare(Path(raw_a).resolve())
        res_b = _normalize_for_compare(Path(raw_b).resolve())
    except OSError:
        return False
    return bool(res_a) and res_a == res_b
