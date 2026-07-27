"""型号根下 ``型号配置.toml``：model_id + shared_modules（B0/B1）。

读用 tomllib；写用 dict 合并 + tomli-w + atomic_write_text。
"""
from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import tomli_w

from fwasset.core.config_io import atomic_write_text
from fwasset.core.services.platform_default_service import canonical_module_dir

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

MODEL_CONFIG_FILENAME = "型号配置.toml"

MODEL_CONFIG_HEADER = (
    "# 本文件由 fwasset 管理（型号 id + 共享引用）。用户无需手写。\n"
    "# display_name 不落盘（永远由目录名现推）。\n"
)

ModelConfigStatus = Literal[
    "ok",
    "missing",
    "no_id",
    "parse_error",
    "parser_missing",
]

_DANGEROUS = set('/\\:*?"<>|')

_SHARED_FIELDS = (
    "source_model_id",
    "source_group",
    "source_module",
    "source_relative_path",
)


@dataclass
class SharedModuleRef:
    """目标型号上的一条共享引用（Phase B/C）。

    mode 默认 ``"static"``（固定版本，Phase B 行为）；``"follow_default"`` 自动跟随源默认。
    ``source_platform`` 仅 follow_default 有效。
    """

    module_key: str
    source_model_id: str
    source_group: str
    source_module: str
    source_relative_path: str
    mode: Literal["static", "follow_default"] = "static"
    source_platform: str = ""


def slugify_model_id(dir_name: str) -> str:
    """目录名 → 候选 model_id（纯函数，不做碰撞处理）。"""
    s = str(dir_name or "").strip()
    for suffix in ("程序", "目录"):
        if s.endswith(suffix):
            s = s[: -len(suffix)].strip()
            break
    out: list[str] = []
    for ch in s:
        if ord(ch) < 32 or ch in _DANGEROUS:
            continue
        if ch.isascii() and ch.isalnum():
            out.append(ch.lower())
        elif ch.isascii() and (ch.isspace() or ch == "-"):
            out.append("-")
        elif not ch.isascii():
            out.append(ch)
    result = "".join(out)
    while "--" in result:
        result = result.replace("--", "-")
    result = result.strip("-")
    return result or "model"


def _load_raw_dict(model_root: Path) -> tuple[dict[str, Any], ModelConfigStatus, str]:
    """读全量 dict。missing → ({}, missing)；损坏 → ({}, parse_error)。"""
    path = Path(model_root) / MODEL_CONFIG_FILENAME
    if not path.exists():
        return {}, "missing", ""
    if tomllib is None:
        return {}, "parser_missing", "TOML 解析组件不可用（需要 tomllib 或 tomli）"
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except Exception as exc:  # noqa: BLE001
        return {}, "parse_error", f"型号配置 TOML 解析失败: {exc}"
    if not isinstance(data, dict):
        return {}, "parse_error", "型号配置顶层必须是 table"
    return dict(data), "ok", ""


def load_model_config(
    model_root: Path,
) -> tuple[str, ModelConfigStatus, str]:
    """严格读取型号根下的 ``型号配置.toml`` 中的 model_id。"""
    data, status, error = _load_raw_dict(model_root)
    if status == "missing":
        return "", "missing", ""
    if status == "parser_missing":
        return "", "parser_missing", error
    if status == "parse_error":
        return "", "parse_error", error
    mid = str(data.get("model_id", "") or "").strip()
    if not mid:
        return "", "no_id", ""
    return mid, "ok", ""


def load_shared_modules(model_root: Path) -> list[SharedModuleRef]:
    """读取共享引用列表；缺失/损坏/缺字段条目容错，不抛。"""
    data, status, _error = _load_raw_dict(model_root)
    if status != "ok":
        # missing / parse_error / parser_missing：只读容错
        return []
    shared = data.get("shared_modules")
    if not isinstance(shared, dict):
        return []
    out: list[SharedModuleRef] = []
    for raw_key, entry in shared.items():
        if not isinstance(entry, dict):
            continue
        module_key = canonical_module_dir(str(raw_key))
        if not module_key:
            continue
        fields = {k: str(entry.get(k, "") or "").strip() for k in _SHARED_FIELDS}
        if any(not fields[k] for k in _SHARED_FIELDS):
            continue
        # Phase C 可选字段：缺失或无效值容错回退
        raw_mode = str(entry.get("mode", "") or "").strip()
        mode: Literal["static", "follow_default"] = (
            raw_mode  # type: ignore[assignment]
            if raw_mode in ("static", "follow_default")
            else "static"
        )
        source_platform = str(entry.get("source_platform", "") or "").strip()
        out.append(
            SharedModuleRef(
                module_key=module_key,
                source_model_id=fields["source_model_id"],
                source_group=fields["source_group"],
                source_module=canonical_module_dir(fields["source_module"])
                or fields["source_module"],
                source_relative_path=fields["source_relative_path"],
                mode=mode,
                source_platform=source_platform,
            )
        )
    out.sort(key=lambda r: r.module_key)
    return out


def _serialize_model_config(data: dict[str, Any]) -> str:
    """固定文件头 + tomli-w dumps。"""
    body = tomli_w.dumps(data)
    if body and not body.endswith("\n"):
        body += "\n"
    return MODEL_CONFIG_HEADER + "\n" + body if body else MODEL_CONFIG_HEADER


def _merge_write_model_config(
    model_root: Path,
    mutate: Callable[[dict[str, Any]], None],
) -> Path:
    """读全量 dict → mutate 局部改键 → 整 dict 写回（禁止只输出局部字段）。

    解析失败（parse_error / parser_missing）时**不**当空 dict 覆盖。
    """
    root = Path(model_root)
    path = root / MODEL_CONFIG_FILENAME
    data, status, error = _load_raw_dict(root)
    if status in ("parse_error", "parser_missing"):
        raise OSError(error or f"型号配置不可读: {status}")
    # _load_raw_dict 只返回 missing / ok（损坏已在上面抛）；missing → 空 dict 起写
    if status == "ok":
        working = deepcopy(data)
    else:
        working = {}
    mutate(working)
    atomic_write_text(path, _serialize_model_config(working))
    return path


def save_model_id(model_root: Path, model_id: str) -> Path:
    """写入/更新 model_id；保留 shared_modules 与未知键。"""
    mid = str(model_id or "").strip()
    if not mid:
        raise ValueError("model_id 不能为空")

    def _mut(data: dict[str, Any]) -> None:
        data["model_id"] = mid

    return _merge_write_model_config(Path(model_root), _mut)


def save_shared_module(model_root: Path, ref: SharedModuleRef) -> Path:
    """写入/覆盖一条共享引用；保留 model_id 与其它 shared 段。"""
    key = canonical_module_dir(ref.module_key)
    if not key:
        raise ValueError("module_key 不能为空")
    source_module = canonical_module_dir(ref.source_module) or str(
        ref.source_module or ""
    ).strip()
    entry: dict[str, Any] = {
        "source_model_id": str(ref.source_model_id or "").strip(),
        "source_group": str(ref.source_group or "").strip(),
        "source_module": source_module,
        "source_relative_path": str(ref.source_relative_path or "").strip(),
    }
    if any(not v for v in entry.values()):
        raise ValueError("共享引用四字段均不能为空")
    # Phase C 可选字段：只在非默认值时写入，保持 Phase B toml 格式兼容
    if ref.mode != "static":
        entry["mode"] = ref.mode
    if ref.source_platform:
        entry["source_platform"] = ref.source_platform

    def _mut(data: dict[str, Any]) -> None:
        shared = data.setdefault("shared_modules", {})
        if not isinstance(shared, dict):
            shared = {}
            data["shared_modules"] = shared
        shared[key] = entry

    return _merge_write_model_config(Path(model_root), _mut)


def remove_shared_module(model_root: Path, module_key: str) -> Path:
    """删除一条共享引用（仅 toml）；不删固件文件。

    文件缺失时短路返回，不凭空创建仅含头注释的空配置（审查 #1）。
    """
    root = Path(model_root)
    path = root / MODEL_CONFIG_FILENAME
    if not path.exists():
        return path
    key = canonical_module_dir(module_key)

    def _mut(data: dict[str, Any]) -> None:
        shared = data.get("shared_modules")
        if not isinstance(shared, dict):
            return
        shared.pop(key, None)
        if not shared:
            data.pop("shared_modules", None)

    return _merge_write_model_config(root, _mut)
