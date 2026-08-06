"""TASK-20260806 R1/R10：写入口门闩纯函数测试。"""

from __future__ import annotations

from fwasset.ui_common.workbench_helpers import write_gate_check


def _win_normcase(s: str) -> str:
    """模拟 Windows nt._path_normcase（C 实现）：lower 且把 '/' 规范化为 '\\\\'。"""
    return s.lower().replace("/", "\\")


# ------------------------------------------------------------------ 空配置根


def test_gate_rejects_empty_configured_root(tmp_path):
    result = write_gate_check("", str(tmp_path), str(tmp_path))
    assert result["ok"] is False
    assert result["code"] == "not_configured"


def test_gate_rejects_none_configured_root(tmp_path):
    result = write_gate_check(None, str(tmp_path), str(tmp_path))
    assert result["ok"] is False
    assert result["code"] == "not_configured"


# ------------------------------------------------------------------ 根一致性


def test_gate_rejects_root_mismatch(tmp_path):
    scanned = tmp_path / "旧根"
    scanned.mkdir()
    result = write_gate_check(str(tmp_path), str(scanned), str(scanned / "a1"))
    assert result["ok"] is False
    assert result["code"] == "root_changed"


def test_gate_rejects_scanned_root_missing(tmp_path):
    # 配置非空但从未扫描（scanned 为 None）→ 视为根不一致，禁止写入
    result = write_gate_check(str(tmp_path), None, str(tmp_path / "a1"))
    assert result["ok"] is False
    assert result["code"] == "root_changed"


# ------------------------------------------------------------------ 路径越界


def test_gate_rejects_out_of_workspace(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}_外部"
    outside.mkdir(exist_ok=True)
    result = write_gate_check(str(tmp_path), str(tmp_path), str(outside))
    assert result["ok"] is False
    assert result["code"] == "out_of_workspace"


def test_gate_rejects_dotdot_escape(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}_外部"
    outside.mkdir(exist_ok=True)
    escape = tmp_path / ".." / outside.name
    result = write_gate_check(str(tmp_path), str(tmp_path), str(escape))
    assert result["ok"] is False
    assert result["code"] == "out_of_workspace"


def test_gate_rejects_dotdot_even_when_the_resolved_path_is_inside_workspace(tmp_path):
    target = tmp_path / "L36程序" / ".." / "L50程序"
    result = write_gate_check(str(tmp_path), str(tmp_path), str(target))
    assert result["ok"] is False
    assert result["code"] == "out_of_workspace"


def test_gate_rejects_empty_target(tmp_path):
    # 资产 path 兜底为 ""（asset.get("path", "")）时也必须被拒绝
    result = write_gate_check(str(tmp_path), str(tmp_path), "")
    assert result["ok"] is False
    assert result["code"] == "out_of_workspace"


# ------------------------------------------------------------------ 放行


def test_gate_allows_inside_workspace(tmp_path):
    target = tmp_path / "通用" / "蓝牙程序" / "英文-通用_V1.0.0"
    result = write_gate_check(str(tmp_path), str(tmp_path), str(target))
    assert result["ok"] is True
    assert result["code"] == "ok"


def test_gate_allows_equal_to_root(tmp_path):
    result = write_gate_check(str(tmp_path), str(tmp_path), str(tmp_path))
    assert result["ok"] is True


def test_gate_allows_missing_target_inside(tmp_path):
    # 目标尚不存在（新建场景）不阻断——门闩管归属，不管存在性
    future = tmp_path / "定制" / "越南-娉娉" / "主板程序" / "量产_V2.1"
    result = write_gate_check(str(tmp_path), str(tmp_path), str(future))
    assert result["ok"] is True


# ------------------------------------------------------------------ Windows 归一


def test_gate_accepts_child_with_windows_normalization(tmp_path, monkeypatch):
    """Windows 的 normcase 归一不得让工作区内的目标被误拒绝。"""
    import fwasset.core.path_guard as path_guard

    monkeypatch.setattr(path_guard.os.path, "normcase", _win_normcase)

    result = write_gate_check(str(tmp_path), str(tmp_path), str(tmp_path / "a1"))
    assert result["ok"] is True
