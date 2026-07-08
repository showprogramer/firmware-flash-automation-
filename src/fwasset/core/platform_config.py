from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]


@dataclass
class PlatformDefaults:
    """单个平台的默认模块变体声明。"""

    platform_name: str
    defaults: dict[str, str] = field(default_factory=dict)  # module_dir_name -> variant_name


def load_platform_config(model_root: Path) -> list[PlatformDefaults]:
    """
    读取型号根目录下的 `平台配置.toml`。
    文件不存在或无法解析时静默返回空列表，保证向后兼容。

    TOML 格式示例：
        [[platform]]
        name = "标准单机芯3D"
        [platform.defaults]
        主板程序 = "量产_默认"
        手控UI = "量产中性_默认"
    """
    toml_path = model_root / "平台配置.toml"
    if not toml_path.exists():
        return []
    if tomllib is None:
        return []
    try:
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        return []

    results: list[PlatformDefaults] = []
    for entry in data.get("platform", []):
        name = str(entry.get("name", "")).strip()
        if not name:
            continue
        defaults = {
            str(k): str(v)
            for k, v in entry.get("defaults", {}).items()
        }
        results.append(PlatformDefaults(platform_name=name, defaults=defaults))
    return results


def default_variant_for(
    platforms: list[PlatformDefaults],
    platform_name: str,
    module_dir: str,
) -> str:
    """
    根据平台名和模块目录名，查找该模块的默认变体子目录名。
    找不到时返回空字符串。
    """
    for p in platforms:
        if p.platform_name == platform_name:
            return p.defaults.get(module_dir, "")
    return ""


def _toml_str(value: str) -> str:
    """Serialize a string as a TOML basic string (quotes/backslash escaped)."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def save_platform_config(model_root: Path, platforms: list[PlatformDefaults]) -> Path:
    """把平台默认配置写回型号根目录下的 `平台配置.toml`。

    以规范格式整体重写（应用托管该文件）；写入失败向上抛异常，由服务层
    包装为 ServiceResult。返回写入的文件路径。
    """
    lines: list[str] = [
        "# 本文件由 fwasset 管理（工作台「设为平台默认」会改写它）。",
        "# defaults 键 = 通用区模块目录名，值 = 默认变体子目录名（空串表示该模块唯一）。",
    ]
    for p in platforms:
        lines.append("")
        lines.append("[[platform]]")
        lines.append(f"name = {_toml_str(p.platform_name)}")
        lines.append("[platform.defaults]")
        for module_dir, variant_name in p.defaults.items():
            lines.append(f"{_toml_str(module_dir)} = {_toml_str(variant_name)}")
    toml_path = model_root / "平台配置.toml"
    toml_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return toml_path
