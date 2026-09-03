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


# --- R3：边界归属 helper -----------------------------------------------------


def test_is_same_or_under_boundary_cases(tmp_path):
    base = tmp_path / "型号A"
    inside = base / "手控UI" / "v1"
    sibling = tmp_path / "型号AB" / "v1"

    assert path_guard.is_same_or_under(base, base)  # 等于边界
    assert path_guard.is_same_or_under(inside, base)  # 边界之内
    assert not path_guard.is_same_or_under(sibling, base)  # 兄弟前缀（A vs AB）
    assert not path_guard.is_same_or_under(inside, "")
    assert not path_guard.is_same_or_under("", base)


def test_is_same_or_under_mixed_separators_and_case(tmp_path, monkeypatch):
    monkeypatch.setattr(path_guard.os.path, "normcase", _fake_win_normcase)

    assert path_guard.is_same_or_under("D:/Root/L36/手控UI", "d:\\root\\l36")
    assert not path_guard.is_same_or_under("D:/Root/L36B/x", "d:/root/l36")


def test_is_same_or_under_lexical_dotdot_is_prefix_matched(tmp_path):
    # 字符串比较不做 resolve：含 ".." 的串按词法前缀命中边界。
    # ".." 防越界由 assert_within_workspace 的词法段拒绝负责，
    # is_same_or_under 只服务扫描产物等无 ".." 的存量路径。
    base = tmp_path / "型号A"
    traversal = base / ".." / "型号B"
    assert path_guard.is_same_or_under(traversal, base) is True


def test_contained_subpath_returns_resolved_inside(tmp_path):
    base = tmp_path / "型号A"
    inside = base / "手控UI"
    inside.mkdir(parents=True)
    result = path_guard.contained_subpath(inside, tmp_path)
    assert result == inside.resolve()
    assert result is not None and result.is_absolute()


def test_contained_subpath_equal_to_boundary(tmp_path):
    assert path_guard.contained_subpath(tmp_path, tmp_path) == tmp_path.resolve()


def test_contained_subpath_none_outside_or_dotdot(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}_外部"
    outside.mkdir(exist_ok=True)
    assert path_guard.contained_subpath(outside, tmp_path) is None
    assert path_guard.contained_subpath(tmp_path / "..", tmp_path) is None


def test_same_path_identity_case_and_separator_variants(tmp_path):
    """大小写与分隔符变体 → 同一身份（R8 公开 helper）。"""
    target = tmp_path / "L36程序" / "通用"
    assert path_guard.same_path_identity(target, tmp_path / "l36程序" / "通用") is True
    assert (
        path_guard.same_path_identity(
            str(target).replace("\\", "/"), str(target)
        )
        is True
    )


def test_same_path_identity_lexical_dotdot(tmp_path):
    """含 ``..`` 的串经 resolve 折叠后与折叠目标同一身份。"""
    assert (
        path_guard.same_path_identity(
            tmp_path / "型号A" / ".." / "型号B", tmp_path / "型号B"
        )
        is True
    )


def test_same_path_identity_different_paths(tmp_path):
    a = tmp_path / "型号A"
    b = tmp_path / "型号AB"
    assert path_guard.same_path_identity(a, b) is False


def test_same_path_identity_empty_or_nonexistent(tmp_path):
    assert path_guard.same_path_identity("", tmp_path) is False
    assert path_guard.same_path_identity(tmp_path, "") is False
    # 不存在的路径仍可做词法/resolved 比较（悬空锚点检查依赖）
    ghost = tmp_path / "不存在" / "目录"
    assert path_guard.same_path_identity(ghost, tmp_path / "不存在" / "目录") is True
