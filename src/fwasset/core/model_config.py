"""型号根下 ``型号配置.toml``：model_id 读写（B0；保留未知键为 B1 打底）。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from fwasset.core.config_io import atomic_write_text

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

MODEL_CONFIG_FILENAME = "型号配置.toml"

ModelConfigStatus = Literal[
    "ok",
    "missing",
    "no_id",
    "parse_error",
    "parser_missing",
]

_DANGEROUS = set('/\\:*?"<>|')
_MODEL_ID_LINE = re.compile(r"(?m)^model_id\s*=\s*.*$")


def _toml_str(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


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
        # 其它 ASCII 标点丢弃
    result = "".join(out)
    while "--" in result:
        result = result.replace("--", "-")
    result = result.strip("-")
    return result or "model"


def load_model_config(
    model_root: Path,
) -> tuple[str, ModelConfigStatus, str]:
    """严格读取型号根下的 ``型号配置.toml`` 中的 model_id。"""
    path = Path(model_root) / MODEL_CONFIG_FILENAME
    if not path.exists():
        return "", "missing", ""
    if tomllib is None:
        return "", "parser_missing", "TOML 解析组件不可用（需要 tomllib 或 tomli）"
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except Exception as exc:  # noqa: BLE001
        return "", "parse_error", f"型号配置 TOML 解析失败: {exc}"
    if not isinstance(data, dict):
        return "", "parse_error", "型号配置顶层必须是 table"
    mid = str(data.get("model_id", "") or "").strip()
    if not mid:
        return "", "no_id", ""
    return mid, "ok", ""


def save_model_id(model_root: Path, model_id: str) -> Path:
    """写入/更新 model_id；读-合并-写回，保留未知行与 shared_modules 等表。

    使用行级替换 ``model_id = ...``，避免整文件只输出 model_id 而丢掉 B1 段。
    """
    root = Path(model_root)
    path = root / MODEL_CONFIG_FILENAME
    mid = str(model_id or "").strip()
    if not mid:
        raise ValueError("model_id 不能为空")
    line = f"model_id = {_toml_str(mid)}"
    if path.exists():
        text = path.read_text(encoding="utf-8")
        if _MODEL_ID_LINE.search(text):
            new_text = _MODEL_ID_LINE.sub(line, text, count=1)
        else:
            # 插在文件开头（注释之后更自然：若全文以 # 开头则插在注释块后）
            lines = text.splitlines(keepends=True)
            insert_at = 0
            for i, ln in enumerate(lines):
                if ln.lstrip().startswith("#") or not ln.strip():
                    insert_at = i + 1
                    continue
                break
            lines.insert(insert_at, line + "\n")
            new_text = "".join(lines)
        if not new_text.endswith("\n"):
            new_text += "\n"
    else:
        new_text = (
            "# 本文件由 fwasset 管理（型号 id + 未来共享引用）。用户无需手写。\n"
            "# display_name 不落盘（永远由目录名现推）。\n"
            f"{line}\n"
        )
    atomic_write_text(path, new_text)
    return path
