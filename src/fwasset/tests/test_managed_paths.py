"""子任务 1a：受管路径判定、写授权守卫与工作区布局识别。"""

from __future__ import annotations

import pytest

from fwasset.core.managed_paths import (
    MANAGED_ROOT_DIRNAME,
    assert_managed_root_not_redirected,
    assert_managed_write,
    detect_workspace_layout,
    is_managed_root_owned,
    managed_path_reason,
    managed_root,
    should_exclude_managed_path,
)
from fwasset.core.path_guard import PathGuardError, is_same_or_under


def _own(workspace_root, kind):
    """在测试中把受管根标记为「应用已初始化」（1b 才有真正的创建流程）。"""
    from fwasset.core.managed_paths import MANAGED_OWNER_MARKER

    root = managed_root(workspace_root, kind)
    root.mkdir(parents=True, exist_ok=True)
    (root / MANAGED_OWNER_MARKER).write_text(f"kind={kind}\n", encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# 旧版本/ 目录段判定（D4.3 ①）
# ---------------------------------------------------------------------------


def test_retired_versions_directory_is_managed(tmp_path):
    target = tmp_path / "通用" / "主板程序" / "V1.0" / "旧版本"
    assert managed_path_reason(target, is_dir=True) == "retired_versions"


def test_nested_under_retired_versions_is_managed(tmp_path):
    # 排除语义是整枝不要：子孙同样命中
    target = tmp_path / "旧版本" / "主板-V1.0" / "firmware.bin"
    assert managed_path_reason(target, is_dir=False) == "retired_versions"


def test_retired_versions_case_and_separator_variants(tmp_path):
    # Windows 大小写不敏感 + 正/反斜杠混用都必须命中
    assert managed_path_reason(f"{tmp_path}\\通用\\旧版本\\a", is_dir=True) == (
        "retired_versions"
    )
    assert managed_path_reason(f"{tmp_path}/通用/旧版本/a", is_dir=True) == (
        "retired_versions"
    )


def test_file_named_retired_versions_is_not_excluded(tmp_path):
    # 同名「文件」不是保留目录段，不得误排
    target = tmp_path / "通用" / "旧版本"
    assert managed_path_reason(target, is_dir=False) is None


def test_retired_versions_prefix_directory_is_not_excluded(tmp_path):
    # 精确段比较：旧版本说明 / 旧版本备份 都是普通用户目录
    assert managed_path_reason(tmp_path / "旧版本说明", is_dir=True) is None
    assert managed_path_reason(tmp_path / "旧版本备份" / "x", is_dir=True) is None


def test_retired_versions_substring_inside_name_is_not_excluded(tmp_path):
    assert managed_path_reason(tmp_path / "我的旧版本", is_dir=True) is None


# ---------------------------------------------------------------------------
# 程序信息.toml（D4.3 ②）
# ---------------------------------------------------------------------------


def test_asset_metadata_file_is_managed(tmp_path):
    target = tmp_path / "通用" / "主板程序" / "V1.0" / "程序信息.toml"
    assert managed_path_reason(target, is_dir=False) == "asset_metadata"


def test_directory_named_asset_metadata_is_not_managed(tmp_path):
    # 元数据是「文件」；同名目录不按元数据处理
    assert managed_path_reason(tmp_path / "程序信息.toml", is_dir=True) is None


def test_other_toml_is_not_managed(tmp_path):
    assert managed_path_reason(tmp_path / "型号配置.toml", is_dir=False) is None


# ---------------------------------------------------------------------------
# 应用内部受管根（D4.3 ③④）：身份必须靠工作区锚定，不能只看名字
# ---------------------------------------------------------------------------


def test_managed_roots_are_reported_by_kind(tmp_path):
    for kind in ("staging", "quarantine", "incomplete_candidate", "workspace_state"):
        root = managed_root(tmp_path, kind)
        assert managed_path_reason(root, is_dir=True, workspace_root=tmp_path) == kind
        child = root / "job-1"
        assert managed_path_reason(child, is_dir=True, workspace_root=tmp_path) == kind


def test_managed_root_requires_workspace_root(tmp_path):
    # 不给工作区根就无法判定内部区域归属，不得靠路径形状猜测
    staging = managed_root(tmp_path, "staging")
    assert managed_path_reason(staging, is_dir=True) is None


def test_user_directory_with_same_name_outside_workspace_is_not_managed(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    outsider = tmp_path / "other" / MANAGED_ROOT_DIRNAME / "staging"
    outsider.mkdir(parents=True)
    assert managed_path_reason(outsider, is_dir=True, workspace_root=workspace) is None


def test_user_staging_directory_inside_workspace_is_not_managed(tmp_path):
    # 用户自建的 staging/（不在 .fwasset 下）是普通业务目录
    user_dir = tmp_path / "通用" / "staging"
    assert managed_path_reason(user_dir, is_dir=True, workspace_root=tmp_path) is None


def test_managed_root_rejects_unknown_kind(tmp_path):
    with pytest.raises(ValueError):
        managed_root(tmp_path, "nope")  # type: ignore[arg-type]


def test_managed_root_rejects_empty_workspace(tmp_path):
    with pytest.raises(PathGuardError):
        managed_root("", "staging")


# ---------------------------------------------------------------------------
# should_exclude_managed_path 是 reason 的薄包装
# ---------------------------------------------------------------------------


def test_should_exclude_matches_reason(tmp_path):
    assert should_exclude_managed_path(tmp_path / "旧版本", is_dir=True) is True
    assert should_exclude_managed_path(tmp_path / "程序信息.toml", is_dir=False) is True
    assert should_exclude_managed_path(tmp_path / "通用", is_dir=True) is False


# ---------------------------------------------------------------------------
# 写授权：排除判定不能替代写授权（D8.2）
# ---------------------------------------------------------------------------


def test_assert_managed_write_accepts_target_inside_expected_root(tmp_path):
    _own(tmp_path, "staging")
    target = managed_root(tmp_path, "staging") / "job-1" / "payload"
    assert assert_managed_write(target, tmp_path, expect="staging") == target.resolve()


def test_assert_managed_write_rejects_other_managed_root(tmp_path):
    # 被排除 ≠ 被授权：候选区路径不能拿 staging 授权写入
    target = managed_root(tmp_path, "incomplete_candidate") / "job-1"
    with pytest.raises(PathGuardError, match="受管目录"):
        assert_managed_write(target, tmp_path, expect="staging")


def test_assert_managed_write_rejects_quarantine_under_staging_grant(tmp_path):
    # 隔离根在工作区外，拿 staging 授权写入同样被拒（此处由工作区校验拦下）
    target = managed_root(tmp_path, "quarantine") / "job-1"
    with pytest.raises(PathGuardError):
        assert_managed_write(target, tmp_path, expect="staging")


def test_assert_managed_write_rejects_business_path(tmp_path):
    # 工作区内的普通业务路径也不是受管写入目标
    target = tmp_path / "通用" / "主板程序"
    with pytest.raises(PathGuardError, match="受管目录"):
        assert_managed_write(target, tmp_path, expect="staging")


def test_assert_managed_write_rejects_outside_workspace(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    outsider = tmp_path / "other" / MANAGED_ROOT_DIRNAME / "staging" / "x"
    with pytest.raises(PathGuardError):
        assert_managed_write(outsider, workspace, expect="staging")


def test_assert_managed_write_rejects_dotdot_escape(tmp_path):
    staging = managed_root(tmp_path, "staging")
    with pytest.raises(PathGuardError):
        assert_managed_write(staging / ".." / "quarantine", tmp_path, expect="staging")


def test_excluded_path_is_not_automatically_writable(tmp_path):
    # 旧版本/ 会被扫描排除，但它不是受管写入区
    retired = tmp_path / "通用" / "V1.0" / "旧版本"
    assert should_exclude_managed_path(retired, is_dir=True) is True
    with pytest.raises(PathGuardError):
        assert_managed_write(retired, tmp_path, expect="staging")


# ---------------------------------------------------------------------------
# 工作区布局识别（D9.0）
# ---------------------------------------------------------------------------


def _make_model(root, name=None):
    target = root if name is None else root / name
    (target / "通用").mkdir(parents=True)
    return target


def test_layout_single_model_when_root_has_marker(tmp_path):
    _make_model(tmp_path)
    assert detect_workspace_layout(tmp_path) == "single_model"


def test_layout_single_model_via_config_marker(tmp_path):
    (tmp_path / "型号配置.toml").write_text("", encoding="utf-8")
    assert detect_workspace_layout(tmp_path) == "single_model"


def test_layout_multi_model_with_one_model(tmp_path):
    # multi_model 指结构，不是数量：只有一个型号子目录仍是 multi_model
    _make_model(tmp_path, "L36")
    assert detect_workspace_layout(tmp_path) == "multi_model"


def test_layout_multi_model_with_several_models(tmp_path):
    _make_model(tmp_path, "L36")
    _make_model(tmp_path, "L50")
    assert detect_workspace_layout(tmp_path) == "multi_model"


def test_layout_empty_workspace(tmp_path):
    assert detect_workspace_layout(tmp_path) == "empty"


def test_layout_empty_ignores_managed_directories(tmp_path):
    # 受管目录不计入型号数量，也不让空工作区变成 invalid
    managed_root(tmp_path, "staging").mkdir(parents=True)
    managed_root(tmp_path, "workspace_state").mkdir(parents=True)
    assert detect_workspace_layout(tmp_path) == "empty"


def test_layout_multi_model_ignores_managed_directories(tmp_path):
    _make_model(tmp_path, "L36")
    managed_root(tmp_path, "quarantine").mkdir(parents=True)
    assert detect_workspace_layout(tmp_path) == "multi_model"


def test_layout_invalid_when_unknown_directory_present(tmp_path):
    # 无法归类的一级内容 → invalid，不得当空工作区初始化
    _make_model(tmp_path, "L36")
    (tmp_path / "随手放的资料").mkdir()
    assert detect_workspace_layout(tmp_path) == "invalid"


def test_layout_invalid_when_only_unknown_directory(tmp_path):
    (tmp_path / "随手放的资料").mkdir()
    assert detect_workspace_layout(tmp_path) == "invalid"


def test_layout_invalid_when_stray_file_present(tmp_path):
    (tmp_path / "笔记.txt").write_text("x", encoding="utf-8")
    assert detect_workspace_layout(tmp_path) == "invalid"


def test_layout_empty_allows_managed_metadata_file(tmp_path):
    (tmp_path / "程序信息.toml").write_text("", encoding="utf-8")
    assert detect_workspace_layout(tmp_path) == "empty"


def test_layout_invalid_when_root_unreadable(tmp_path):
    missing = tmp_path / "does-not-exist"
    assert detect_workspace_layout(missing) == "invalid"


def test_layout_invalid_for_empty_root_value():
    assert detect_workspace_layout("") == "invalid"


def test_layout_ignores_scan_excluded_directory(tmp_path):
    # 被 scanner 排除的目录不算未知内容（legacy "旧" 关键词现状）
    _make_model(tmp_path, "L36")
    (tmp_path / "接线图").mkdir()
    assert detect_workspace_layout(tmp_path) == "multi_model"


def test_layout_does_not_depend_on_asset_index(tmp_path):
    # 空白型号：只有配置、没有任何程序文件，仍须识别为型号
    model = tmp_path / "L36"
    model.mkdir()
    (model / "型号配置.toml").write_text("", encoding="utf-8")
    assert detect_workspace_layout(tmp_path) == "multi_model"


def test_managed_path_reason_handles_empty_path():
    assert managed_path_reason("", is_dir=True) is None


def test_layout_invalid_when_iterdir_fails(tmp_path, monkeypatch):
    # 根存在但不可枚举（权限等）→ invalid，不得当空工作区
    def _boom(self):
        raise OSError("denied")

    monkeypatch.setattr("pathlib.Path.iterdir", _boom)
    assert detect_workspace_layout(tmp_path) == "invalid"


def test_layout_invalid_when_root_is_a_file(tmp_path):
    target = tmp_path / "not-a-dir.txt"
    target.write_text("x", encoding="utf-8")
    assert detect_workspace_layout(target) == "invalid"


# ---------------------------------------------------------------------------
# Codex 审查修复（2026-09-05）
# ---------------------------------------------------------------------------


def test_quarantine_root_is_workspace_sibling(tmp_path):
    """D2.5 / D8.2：隔离根必须在工作区同卷的兄弟目录，不能落在工作区内。"""
    workspace = tmp_path / "L36程序"
    workspace.mkdir()
    root = managed_root(workspace, "quarantine")
    assert root.parent == workspace.parent.resolve()
    assert not is_same_or_under(root, workspace)


def test_quarantine_reason_is_reported_outside_workspace(tmp_path):
    workspace = tmp_path / "L36程序"
    workspace.mkdir()
    target = managed_root(workspace, "quarantine") / "job-1"
    assert (
        managed_path_reason(target, is_dir=True, workspace_root=workspace)
        == "quarantine"
    )


def test_quarantine_write_is_authorized_outside_workspace(tmp_path):
    workspace = tmp_path / "L36程序"
    workspace.mkdir()
    _own(workspace, "quarantine")
    target = managed_root(workspace, "quarantine") / "job-1"
    assert assert_managed_write(target, workspace, expect="quarantine") == (
        target.resolve()
    )


def test_quarantine_write_still_rejects_foreign_path(tmp_path):
    workspace = tmp_path / "L36程序"
    workspace.mkdir()
    with pytest.raises(PathGuardError, match="受管目录"):
        assert_managed_write(tmp_path / "别处", workspace, expect="quarantine")


def test_managed_reason_uses_resolved_identity_for_dotdot(tmp_path):
    """staging/../../X 折叠后已在受管根外，不得判为 staging。"""
    staging = managed_root(tmp_path, "staging")
    escaped = staging / ".." / ".." / "L36"
    assert managed_path_reason(escaped, is_dir=True, workspace_root=tmp_path) is None


def test_managed_reason_follows_junction_into_staging(tmp_path):
    """junction 指向受管区域时必须命中，否则调用方会漏掉真实受管内容。"""
    staging = managed_root(tmp_path, "staging")
    staging.mkdir(parents=True)
    link = tmp_path / "别名"
    try:
        link.symlink_to(staging, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("当前环境不支持创建目录链接")
    assert managed_path_reason(link, is_dir=True, workspace_root=tmp_path) == "staging"


def test_managed_container_name_is_case_insensitive(tmp_path):
    """Windows 大小写不敏感：.FWASSET 与 .fwasset 等价。"""
    (tmp_path / ".FWASSET" / "staging").mkdir(parents=True)
    assert detect_workspace_layout(tmp_path) == "empty"


def test_layout_invalid_when_root_marker_mixed_with_model_subdir(tmp_path):
    """混合布局：根自带标志又有型号子目录 → invalid，不得判 single_model。"""
    (tmp_path / "通用").mkdir()
    (tmp_path / "L36" / "通用").mkdir(parents=True)
    assert detect_workspace_layout(tmp_path) == "invalid"


def test_layout_single_model_allows_own_content(tmp_path):
    """single_model 下 通用/ 定制/ 与根配置是自身内容，不算未知项。"""
    (tmp_path / "通用").mkdir()
    (tmp_path / "定制").mkdir()
    (tmp_path / "型号配置.toml").write_text("", encoding="utf-8")
    assert detect_workspace_layout(tmp_path) == "single_model"


def test_layout_invalid_when_root_marker_mixed_with_unknown_dir(tmp_path):
    (tmp_path / "通用").mkdir()
    (tmp_path / "随手放的资料").mkdir()
    assert detect_workspace_layout(tmp_path) == "invalid"


def test_layout_invalid_for_stray_file_matching_scan_keyword(tmp_path):
    """扫描排除关键词只对目录生效；根下散落文件仍是未知内容。"""
    (tmp_path / "接线图.txt").write_text("x", encoding="utf-8")
    assert detect_workspace_layout(tmp_path) == "invalid"


def test_layout_invalid_for_stray_file_inside_managed_container(tmp_path):
    """.fwasset 容器本身可忽略，但它不该让工作区凭空变成 empty 之外的判断。"""
    (tmp_path / ".fwasset").mkdir()
    (tmp_path / ".fwasset" / "个人资料.txt").write_text("x", encoding="utf-8")
    # 容器内内容属应用自身区域，不计入未知项
    assert detect_workspace_layout(tmp_path) == "empty"


# ---------------------------------------------------------------------------
# Codex 复核第二轮修复（2026-09-05）
# ---------------------------------------------------------------------------


def test_managed_root_ownership_requires_marker(tmp_path):
    """路径形状不证明所有权：用户预建的同名目录不得获得写授权。"""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    squatted = managed_root(workspace, "quarantine")
    squatted.mkdir(parents=True)
    (squatted / "personal.txt").write_text("私人文件", encoding="utf-8")

    assert is_managed_root_owned(workspace, "quarantine") is False
    with pytest.raises(PathGuardError, match="尚未由应用初始化或已被占用"):
        assert_managed_write(squatted / "personal.txt", workspace, expect="quarantine")


def test_occupied_root_is_not_owned(tmp_path):
    """用户预建的同名目录不算应用所有，写授权必须拒绝。"""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    squatted = managed_root(workspace, "staging")
    squatted.mkdir(parents=True)
    (squatted / "用户资料.txt").write_text("x", encoding="utf-8")

    assert is_managed_root_owned(workspace, "staging") is False
    with pytest.raises(PathGuardError, match="尚未由应用初始化或已被占用"):
        assert_managed_write(squatted / "x", workspace, expect="staging")
    # 判定是只读的，不得删除或改动用户内容
    assert (squatted / "用户资料.txt").read_text(encoding="utf-8") == "x"


def test_managed_reason_hits_when_managed_root_is_redirected(tmp_path):
    """受管根本身被换成 junction 时，词法身份仍须命中，不得整片漏排。"""
    import _winapi

    workspace = tmp_path / "ws"
    workspace.mkdir()
    real = workspace / "真实目录"
    (real / "staging").mkdir(parents=True)
    try:
        _winapi.CreateJunction(str(real), str(workspace / MANAGED_ROOT_DIRNAME))
    except (OSError, AttributeError, NotImplementedError):
        pytest.skip("当前环境不支持创建 junction")

    target = workspace / MANAGED_ROOT_DIRNAME / "staging"
    assert (
        managed_path_reason(target, is_dir=True, workspace_root=workspace) == "staging"
    )


def test_redirected_managed_root_does_not_capture_target_directory(tmp_path):
    """staging junction 指向真实资产目录时，该目录不得被判为受管。

    否则扫描会因为一条链接静默丢掉正常资产（Codex 第三轮 P1）。
    """
    import _winapi

    workspace = tmp_path / "ws"
    workspace.mkdir()
    normal = workspace / "语音板"
    normal.mkdir()
    (workspace / MANAGED_ROOT_DIRNAME).mkdir()
    try:
        _winapi.CreateJunction(
            str(normal), str(workspace / MANAGED_ROOT_DIRNAME / "staging")
        )
    except (OSError, AttributeError, NotImplementedError):
        pytest.skip("当前环境不支持创建 junction")

    assert managed_path_reason(normal, is_dir=True, workspace_root=workspace) is None


def test_redirected_root_is_rejected_and_not_owned(tmp_path):
    """受管根被重定向属不可信现场：前置校验拒绝，且不视为应用所有。"""
    import _winapi

    workspace = tmp_path / "ws"
    workspace.mkdir()
    outside = tmp_path / "外部"
    outside.mkdir()
    try:
        _winapi.CreateJunction(str(outside), str(workspace / MANAGED_ROOT_DIRNAME))
    except (OSError, AttributeError, NotImplementedError):
        pytest.skip("当前环境不支持创建 junction")

    with pytest.raises(PathGuardError, match="被重定向"):
        assert_managed_root_not_redirected(workspace, "staging")
    assert is_managed_root_owned(workspace, "staging") is False
    # 判定是只读的，不得在外部目录落盘
    assert not (outside / "staging").exists()


def test_layout_invalid_when_model_config_is_a_directory(tmp_path):
    """名为 型号配置.toml 的目录不是型号标志，后续配置读取用不了它。"""
    (tmp_path / "型号配置.toml").mkdir()
    assert detect_workspace_layout(tmp_path) == "invalid"


def test_layout_invalid_when_common_dir_is_a_file(tmp_path):
    (tmp_path / "型号配置.toml").write_text("", encoding="utf-8")
    (tmp_path / "通用").write_text("这是文件", encoding="utf-8")
    assert detect_workspace_layout(tmp_path) == "invalid"


def test_layout_invalid_for_stray_file_in_single_model_root(tmp_path):
    """single_model 下散落文件仍是未知内容，不得整片放行。"""
    (tmp_path / "通用").mkdir()
    (tmp_path / "personal.txt").write_text("x", encoding="utf-8")
    assert detect_workspace_layout(tmp_path) == "invalid"


def test_layout_single_model_allows_own_config_files(tmp_path):
    (tmp_path / "通用").mkdir()
    (tmp_path / "定制").mkdir()
    (tmp_path / "型号配置.toml").write_text("", encoding="utf-8")
    (tmp_path / "平台配置.toml").write_text("", encoding="utf-8")
    assert detect_workspace_layout(tmp_path) == "single_model"


def test_managed_root_rejects_unresolvable_workspace(tmp_path):
    with pytest.raises(PathGuardError):
        managed_root("\x00非法", "staging")


def test_module_exposes_no_root_creation_api():
    """受管根的创建需要持锁与失败恢复，属子任务 1b；1a 只提供只读判定。

    单纯在检查后 mkdir 无法消除竞争窗口（检查与创建之间目标仍可被替换或
    抢占），因此本模块刻意不提供创建入口。
    """
    import fwasset.core.managed_paths as mp

    assert not hasattr(mp, "ensure_managed_root")


def test_model_marker_rule_matches_reference_lookup(tmp_path):
    """布局判定与引用反查必须对同一目录给出一致的型号归属。"""
    from fwasset.core.managed_paths import _has_model_marker as layout_marker
    from fwasset.core.reference_lookup import _has_model_marker as lookup_marker

    plain = tmp_path / "普通目录"
    plain.mkdir()
    config_dir = tmp_path / "配置是目录"
    (config_dir / "型号配置.toml").mkdir(parents=True)
    real = tmp_path / "真型号"
    real.mkdir()
    (real / "型号配置.toml").write_text("", encoding="utf-8")

    for target in (plain, config_dir, real):
        assert layout_marker(target) == lookup_marker(target), target
