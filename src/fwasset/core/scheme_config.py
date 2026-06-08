from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

_CUSTOM_DIR_NAME = "定制"
_SCHEME_CONFIG_FILENAME = "方案配置.toml"


@dataclass
class SchemeConfig:
    """单个定制方案的元数据。"""

    name: str       # 方案名，如 "以色列-Royal-Z9"
    platform: str   # 所属平台，如 "标准单机芯3D"
    path: Path      # 方案目录的绝对路径


def discover_schemes(model_root: Path) -> list[SchemeConfig]:
    """
    扫描型号根目录下 `定制/` 子目录中的所有定制方案。
    每个含有 `方案配置.toml` 的子目录视为一个方案。
    子目录不含 TOML 时，也识别为方案但元数据留默认值（向后兼容）。
    `定制/单模块变体/` 目录跳过（不是整机方案）。
    """
    custom_root = model_root / _CUSTOM_DIR_NAME
    if not custom_root.exists() or not custom_root.is_dir():
        return []

    results: list[SchemeConfig] = []
    for scheme_dir in sorted(custom_root.iterdir()):
        if not scheme_dir.is_dir():
            continue
        # 跳过单模块变体汇总目录
        if scheme_dir.name in ("单模块变体",):
            continue

        toml_path = scheme_dir / _SCHEME_CONFIG_FILENAME
        name = scheme_dir.name
        platform = ""

        if toml_path.exists() and tomllib is not None:
            try:
                with open(toml_path, "rb") as f:
                    data = tomllib.load(f)
                name = str(data.get("name", scheme_dir.name)).strip() or scheme_dir.name
                platform = str(data.get("platform", "")).strip()
            except Exception:
                pass

        results.append(SchemeConfig(name=name, platform=platform, path=scheme_dir))
    return results


def scheme_for_path(schemes: list[SchemeConfig], asset_path: Path) -> SchemeConfig | None:
    """
    根据资产路径，找到它所属的定制方案（如果有）。
    通过检查资产路径是否以方案目录路径为前缀来判断。
    """
    for scheme in schemes:
        try:
            asset_path.relative_to(scheme.path)
            return scheme
        except ValueError:
            continue
    return None
