"""REVIEW R5：统一工作区路径守卫测试。"""

from __future__ import annotations

import pytest

import fwasset.core.path_guard as path_guard
from fwasset.core.path_guard import (
    PathGuardError,
    assert_within_workspace,
    normalize_workspace_path,
)


def test_accepts_direct_child(tmp_path):
    child = tmp_path / "L36程序"
    child.mkdir()
    assert assert_within_workspace(child, tmp_path) == child.resolve()


def test_accepts_nested_path(tmp_path):
    target = tmp_path / "L36程序" / "蓝牙程序" / "英文-通用_V1.0.0"
    target.mkdir(parents=True)
    assert assert_within_workspace(target, tmp_path) == target.resolve()


def test_accepts_equal_to_root(tmp_path):
    # 单型号根场景：model_root == workspace_root 是合法写法
    assert assert_within_workspace(tmp_path, tmp_path) == tmp_path.resolve()


def test_rejects_relative_path(tmp_path):
    # 相对路径语义依赖进程 cwd，容易误判归属 → 明确拒绝
    with pytest.raises(PathGuardError, match="绝对路径"):
        assert_within_workspace("L36程序", tmp_path)


def test_rejects_empty_workspace_root(tmp_path):
    with pytest.raises(PathGuardError, match="工作区根目录未配置"):
        assert_within_workspace(tmp_path, "")
    with pytest.raises(PathGuardError):
        assert_within_workspace(tmp_path, None)  # type: ignore[arg-type]


def test_rejects_dotdot_within_root(tmp_path):
    # 区域内穿越 ..：词法段必须被拒绝，不能靠 resolve 消解后放行
    a = tmp_path / "L36程序"
    b = tmp_path / "L50程序"
    a.mkdir()
    b.mkdir()
    with pytest.raises(PathGuardError, match="越界段"):
        assert_within_workspace(a / ".." / "L50程序", tmp_path)


def test_rejects_dotdot_string_form(tmp_path):
    (tmp_path / "L36程序").mkdir()
    with pytest.raises(PathGuardError, match="越界段"):
        assert_within_workspace(str(tmp_path / "L36程序" / ".." / "L50程序"), tmp_path)


def test_rejects_escape_outside_root(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}_外部"
    outside.mkdir(exist_ok=True)
    with pytest.raises(PathGuardError, match="不在工作区内"):
        assert_within_workspace(outside, tmp_path)


def test_rejects_dotdot_escape(tmp_path):
    with pytest.raises(PathGuardError):
        assert_within_workspace(tmp_path / "..", tmp_path)


def test_accepts_harmless_dot(tmp_path):
    (tmp_path / "L36程序").mkdir()
    target = tmp_path / "L36程序" / "." / "蓝牙程序"
    target.mkdir(parents=True)
    # Path 构造会折叠 "."，行为等价于无 "." 路径
    assert (
        assert_within_workspace(target, tmp_path)
        == (tmp_path / "L36程序" / "蓝牙程序").resolve()
    )


def test_accepts_missing_target_still_checked(tmp_path):
    # 目标尚不存在（新建场景）也允许在工作区内——守卫管归属，不管存在性
    future = tmp_path / "L36程序" / "英文-通用_V1.0.0"
    assert assert_within_workspace(future, tmp_path) == future.resolve()


def test_return_value_is_resolved_path(tmp_path):
    target = tmp_path / "L36程序"
    target.mkdir()
    result = assert_within_workspace(target, tmp_path)
    assert result.is_absolute()
    assert result == target.resolve()


def test_normalize_workspace_path_returns_empty_for_empty_values():
    assert normalize_workspace_path(None) == ""
    assert normalize_workspace_path("") == ""
    assert normalize_workspace_path("  ") == ""


def test_normalize_workspace_path_matches_windows_case_and_separators(monkeypatch):
    monkeypatch.setattr(path_guard.os.path, "normcase", _fake_win_normcase)

    assert normalize_workspace_path("D:/Root") == normalize_workspace_path("d:\\root")


def _fake_win_normcase(s: str) -> str:
    """模拟 Windows nt._path_normcase（C 实现）：lower 且把 '/' 规范化为 '\\\\'。

    不能调用 ntpath.normcase：Windows 上 os.path 即 ntpath，monkeypatch
    会改写 ntpath.normcase 全局名，此处再调用即无限递归（coverage 的
    路径规范化同样会触发），WSL 上 os.path 是 posixpath 才未暴露。
    """
    return s.lower().replace("/", "\\")


def test_accepts_direct_child_with_windows_normalization(tmp_path, monkeypatch):
    """Windows 的 normcase 会改用反斜杠，比较前必须统一回正斜杠。"""
    child = tmp_path / "L36双机芯-上3D-下2D程序"
    child.mkdir()
    monkeypatch.setattr(path_guard.os.path, "normcase", _fake_win_normcase)

    assert assert_within_workspace(child, tmp_path) == child.resolve()


def test_normalize_for_compare_order_regression(monkeypatch):
    """回归：必须先 normcase 再统一斜杠。

    旧实现是 as_posix() 转正斜杠后再 normcase，Windows C 版 normcase 会把
    斜杠转回反斜杠，导致前缀比较 base + "/" 永不匹配。
    """
    monkeypatch.setattr(path_guard.os.path, "normcase", _fake_win_normcase)

    from pathlib import Path

    assert path_guard._normalize_for_compare(Path("D:/按摩器程序")) == "d:/按摩器程序"
    assert (
        path_guard._normalize_for_compare(Path("D:/按摩器程序/L36双机芯-上3D-下2D程序"))
        == "d:/按摩器程序/l36双机芯-上3d-下2d程序"
    )
