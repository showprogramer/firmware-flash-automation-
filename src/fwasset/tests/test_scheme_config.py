"""scheme_config：方案发现与路径绑定。"""

from __future__ import annotations

from pathlib import Path

from fwasset.core.scheme_config import SchemeConfig, scheme_for_path


def test_scheme_for_path_prefers_longest_prefix(tmp_path: Path) -> None:
    """嵌套/重叠方案目录时绑定最深（最长前缀）方案。"""
    outer = tmp_path / "定制" / "方案A"
    inner = outer / "变体"
    outer.mkdir(parents=True)
    inner.mkdir()
    asset = inner / "主板程序" / "x"
    asset.mkdir(parents=True)

    schemes = [
        SchemeConfig(name="方案A", platform="", path=outer),
        SchemeConfig(name="变体", platform="", path=inner),
    ]
    # 列表顺序 outer 在前时，最长前缀仍应命中 inner
    assert scheme_for_path(schemes, asset).name == "变体"
    assert scheme_for_path(list(reversed(schemes)), asset).name == "变体"


def test_scheme_for_path_returns_none_when_outside(tmp_path: Path) -> None:
    scheme_dir = tmp_path / "定制" / "西班牙"
    scheme_dir.mkdir(parents=True)
    other = tmp_path / "通用" / "主板程序" / "量产"
    other.mkdir(parents=True)
    schemes = [SchemeConfig(name="西班牙", platform="", path=scheme_dir)]
    assert scheme_for_path(schemes, other) is None
