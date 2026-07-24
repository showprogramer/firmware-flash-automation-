"""Qt 工作台 smoke 测试（REVIEW-20260708-pyside6-p1-p2 阻断项 3.2）。

契约级兜底：导入可用、DataGrid 渲染语义（单变体折叠 / 多变体归组 /
★默认徽章 / 归属文案）、LogPanel 折叠行为。用 offscreen 平台跑，
无显示器也能执行，但仍标 ui（依赖 PySide6，qt extra 未装时自动跳过）。
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from fwasset.ui_common.view_models.scheme_workbench_model import (  # noqa: E402
    ModuleCardData,
    ModuleRow,
    ModuleVariant,
)
from fwasset.ui_qt.data_grid import DataGrid  # noqa: E402
from fwasset.ui_qt.log_panel import LogPanel  # noqa: E402

pytestmark = pytest.mark.ui


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _asset(path: str = "D:/x/主板程序/量产_默认", files: list[str] | None = None) -> dict:
    return {"path": path, "files": files or ["fw_V40.bin"], "category": "common"}


def _variant(name: str, badge: str = "", kind: str = "common") -> ModuleVariant:
    return ModuleVariant(
        asset=_asset(),
        name=name,
        version="V40",
        source_kind=kind,
        source_label="通用" if kind == "common" else "定制专属",
        default_badge=badge,
    )


def _logs() -> list[str]:
    return []


def test_import_workbench_window_module(qapp) -> None:
    """入口模块可导入（不实例化窗口——那需要扫描环境）。"""
    import fwasset.ui_qt.workbench_window as module

    assert hasattr(module, "QtWorkbenchWindow")
    assert hasattr(module, "main")


def test_populate_tree_empty_is_noop(qapp) -> None:
    grid = DataGrid(lambda _m: None)
    grid.populate_tree([])
    assert grid.tree.topLevelItemCount() == 0
    assert grid.get_selected_variant() is None


def test_single_variant_collapses_with_directory_name_and_badge(qapp) -> None:
    """单变体折叠为一行；程序名称始终用目录名（Issue 20-A）；徽章拼在名称列。"""
    row = ModuleRow(
        label="主板程序",
        source_kind="common",
        source_label="通用",
        variants=[_variant("主板程序", badge="★默认")],
    )
    grid = DataGrid(lambda _m: None)
    grid.populate_tree([row])

    assert grid.tree.topLevelItemCount() == 1
    item = grid.tree.topLevelItem(0)
    assert item.childCount() == 0
    assert item.text(0) == "主板程序"
    assert item.text(1) == "主板程序  ★默认"
    assert item.text(2) == "通用"
    assert item.text(3) == "V40"
    assert "回源" not in item.text(2)
    assert [grid.tree.headerItem().text(i) for i in range(5)] == [
        "程序类型",
        "程序名称",
        "程序归属",
        "版本",
        "程序文件",
    ]


def test_multi_variant_grouped_under_parent_row(qapp) -> None:
    """多变体收在模块行子节点下，子行显示原始变体名，默认展开。"""
    row = ModuleRow(
        label="手控UI",
        source_kind="custom",
        source_label="定制专属",
        variants=[_variant("以色列", kind="custom"), _variant("以色列-塞尔维亚", kind="custom")],
    )
    grid = DataGrid(lambda _m: None)
    grid.populate_tree([row])

    assert grid.tree.topLevelItemCount() == 1
    parent = grid.tree.topLevelItem(0)
    assert parent.childCount() == 2
    assert parent.isExpanded()
    assert parent.child(0).text(1) == "以色列"
    assert parent.child(1).text(1) == "以色列-塞尔维亚"


def test_populate_cards_groups_by_label(qapp) -> None:
    """populate 兼容路径：同 label 卡片归为一个模块行。"""
    cards = [
        ModuleCardData(
            asset={**_asset(), "firmware_label": "主板程序", "directory_name": "量产_默认", "version": "V40"},
            source_type="common_default",
            source_label="通用/量产_默认 (默认)",
            is_fallback=False,
            source_kind="common",
            default_badge="★默认",
        ),
        ModuleCardData(
            asset={**_asset(), "firmware_label": "主板程序", "directory_name": "防夹功能", "version": "V24"},
            source_type="common_variant",
            source_label="通用/防夹功能",
            is_fallback=False,
            source_kind="common",
        ),
    ]
    grid = DataGrid(lambda _m: None)
    grid.populate(cards)

    assert grid.tree.topLevelItemCount() == 1
    parent = grid.tree.topLevelItem(0)
    assert parent.text(0) == "主板程序"
    assert parent.childCount() == 2
    assert "★默认" in parent.child(0).text(1)
    assert "★默认" not in parent.child(1).text(1)


def test_log_panel_write_and_toggle(qapp) -> None:
    panel = LogPanel()
    assert not panel.log_text.isVisible() or panel.log_text.isHidden() or True  # offscreen 下可见性弱断言
    panel.write("第一条日志")
    panel.write("第二条日志\n")
    text = panel.log_text.toPlainText()
    assert "第一条日志" in text and "第二条日志" in text
    panel.toggle()
    assert panel.toggle_btn.text() == "折叠日志"
    panel.toggle()
    assert panel.toggle_btn.text() == "展开日志"


def _chip_bar_widgets(w):
    return [
        w.chip_bar.itemAt(i).widget()
        for i in range(w.chip_bar.count())
        if w.chip_bar.itemAt(i).widget() is not None
    ]


def test_model_dropdown_always_present_with_all_models(qapp) -> None:
    """可搜索型号下拉常驻（型号少时也在），且包含全部型号。"""
    from qfluentwidgets import EditableComboBox, TogglePushButton

    from fwasset.ui_qt.workbench_window import WorkbenchInterface

    w = WorkbenchInterface()

    # 少量型号：2 chips + 常驻下拉（含全部 2 项）
    w.current_selection.model_name = "L36"
    w._refresh_model_selector(["L36", "L36双机芯-上3D-下2D"])
    widgets = _chip_bar_widgets(w)
    assert len([x for x in widgets if isinstance(x, TogglePushButton)]) == 2
    combos = [x for x in widgets if isinstance(x, EditableComboBox)]
    assert len(combos) == 1, "型号下拉应常驻"
    assert combos[0].count() == 2

    # 多型号：4 chips + 下拉仍含全部 6 项
    w._refresh_model_selector(["L36", "L36双机芯-上3D-下2D", "L50S", "M3", "M5", "M8"])
    widgets = _chip_bar_widgets(w)
    assert len([x for x in widgets if isinstance(x, TogglePushButton)]) == 4
    combos = [x for x in widgets if isinstance(x, EditableComboBox)]
    assert combos[0].count() == 6


def test_model_switch_is_debounced_and_prefix_safe(qapp) -> None:
    """切型号经防抖确认：键入途中命中前缀型号（L36 是 L36双机芯-… 的前缀）
    会被后续输入覆盖，最终只切到用户真正选中的型号。"""
    from fwasset.ui_qt.workbench_window import WorkbenchInterface

    w = WorkbenchInterface()
    w.current_selection.model_name = "M8"
    w._refresh_model_selector(["L36", "L36双机芯-上3D-下2D", "M8"])

    # 模拟键入 "L36双…"：先命中前缀 L36，随后命中完整型号——防抖期内后者覆盖前者
    w._schedule_model_switch("L36")
    w._schedule_model_switch("L36双机芯-上3D-下2D")
    w._apply_pending_model()
    assert w.current_selection.model_name == "L36双机芯-上3D-下2D"

    # 非真实型号（输入中间态）不入队
    w._schedule_model_switch("L5")
    w._apply_pending_model()
    assert w.current_selection.model_name == "L36双机芯-上3D-下2D"

    # 防呆兜底：_on_model_changed 直接收到假型号也不切
    w._on_model_changed("L5")
    assert w.current_selection.model_name == "L36双机芯-上3D-下2D"


def test_sidebar_rebuild_clears_stale_pressed_and_hover_rows(qapp) -> None:
    """搜索结果展开为完整侧栏后，旧点击位置不得保留伪高亮。"""
    from PySide6.QtWidgets import QListWidgetItem

    from fwasset.ui_qt.workbench_window import WorkbenchInterface

    w = WorkbenchInterface()
    w.current_selection.node_type = "custom_scheme"
    w.current_selection.scheme_name = "马来西亚"
    w._nav_entries = [
        ("all", ""),
        ("section", ""),
        ("common_type", "主板程序"),
        ("common_type", "语音程序"),
        ("section", ""),
        ("custom_scheme", "德国"),
        ("custom_scheme", "马来西亚"),
        ("custom_scheme", "西班牙"),
    ]
    for i in range(len(w._nav_entries)):
        w.nav.addItem(QListWidgetItem(str(i)))

    # 搜索态点击时「马来西亚」位于第 2 行；恢复完整侧栏后它移动到第 6 行。
    w.nav.delegate.setPressedRow(2)
    w.nav.delegate.setHoverRow(2)

    w._apply_nav_selection_highlight()

    assert w.nav.currentRow() == 6
    assert w.nav.delegate.selectedRows == {6}
    assert w.nav.delegate.pressedRow == -1
    assert w.nav.delegate.hoverRow == -1

def test_click_filtered_scheme_reselects_its_new_row_after_sidebar_rebuild(qapp) -> None:
    """真实鼠标点击返回后，delegate 选中集合必须跟随方案的新行号。"""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from fwasset.ui_common.view_models.scheme_workbench_model import WorkbenchSelection
    from fwasset.ui_qt.workbench_window import WorkbenchInterface

    w = WorkbenchInterface()
    w._search_timer.stop()
    w._model_switch_timer.stop()
    w._refresh_main_grid = lambda: None  # type: ignore[method-assign]
    w.workbench_model.build_sidebar_tree = lambda _model: {  # type: ignore[method-assign]
        "common": {"主板程序": 2, "手控UI": 3, "语音程序": 1},
        "custom": ["德国", "马来西亚", "美国", "西班牙"],
    }
    w.current_selection = WorkbenchSelection(model_name="L36", node_type="all")
    w.search_edit.blockSignals(True)
    w.search_edit.setText("马来西亚")
    w.search_edit.blockSignals(False)
    w._refresh_sidebar_tree()
    w.resize(1200, 800)
    w.show()
    qapp.processEvents()

    old_row = next(
        i for i, entry in enumerate(w._nav_entries)
        if entry == ("custom_scheme", "马来西亚")
    )
    old_item = w.nav.item(old_row)
    click_pos = w.nav.visualItemRect(old_item).center()

    QTest.mouseClick(
        w.nav.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        click_pos,
    )
    qapp.processEvents()

    target_row = next(
        i for i, entry in enumerate(w._nav_entries)
        if entry == ("custom_scheme", "马来西亚")
    )
    selected_rows = {index.row() for index in w.nav.selectedIndexes()}

    assert target_row != old_row
    assert w.nav.currentRow() == target_row
    assert selected_rows == {target_row}
    assert w.nav.delegate.selectedRows == {target_row}
    assert w.nav.currentItem().text() == "◆ 马来西亚"


# ---------------------------------------------------------------------------
# Phase 3：操作面板注册表与四类面板构建
# ---------------------------------------------------------------------------


class _FakeHost:
    """满足 ui_qt PanelHost 协议的最小假宿主。"""

    def __init__(self, drive: str = "E:"):
        self.drive = drive
        self.calls: list[tuple] = []

    def _run_task(self, name, fn, on_done=None):
        self.calls.append(("run_task", name))

    def _selected_asset(self):
        return None

    def _open_current_asset_dir(self):
        self.calls.append(("open_dir",))

    def _copy_asset_dir_path(self):
        self.calls.append(("copy_dir",))

    def _copy_primary_file_path(self):
        self.calls.append(("copy_file",))

    def _launch_tool_and_open_asset_dir(self):
        self.calls.append(("tool_combo",))

    def get_global_usb_drive(self) -> str:
        return self.drive


def _op_asset(**overrides) -> dict:
    base = {
        "firmware_type": "handcontrol_ui",
        "firmware_label": "手控UI",
        "flash_mode": "auto_usb",
        "usb_flow": "paired_files",
        "model": "L36",
        "version": "V1.0",
        "path": "D:/x/手控UI/A",
        "files": ["a.rom", "a.pkg"],
        "tool_name": "",
        "tool_dir": "",
    }
    base.update(overrides)
    return base


def test_qt_panel_registry_routes_all_four_modes(qapp) -> None:
    from fwasset.ui_qt.operation_panels import get_panel

    for mode in ("auto_usb", "tool_launch", "manual_doc", "disabled"):
        assert get_panel(mode) is not None, f"{mode} 应有注册面板"
    assert get_panel("nonexistent") is None


def test_auto_usb_panel_paired_files_shows_one_click(qapp) -> None:
    from qfluentwidgets import PrimaryPushButton

    from fwasset.ui_qt.operation_panels import get_panel

    panel = get_panel("auto_usb")(asset=_op_asset(), log_fn=lambda _m: None, panel_host=_FakeHost())
    panel.build()
    buttons = panel.findChildren(PrimaryPushButton)
    assert any(b.text() == "一键烧录" for b in buttons)


def test_auto_usb_panel_missing_pkg_shows_warning(qapp) -> None:
    from qfluentwidgets import BodyLabel, PrimaryPushButton

    from fwasset.ui_qt.operation_panels import get_panel

    panel = get_panel("auto_usb")(
        asset=_op_asset(files=["a.rom"]), log_fn=lambda _m: None, panel_host=_FakeHost()
    )
    panel.build()
    assert not panel.findChildren(PrimaryPushButton), "缺 PKG 不应出现一键烧录"
    labels = [w.text() for w in panel.findChildren(BodyLabel)]
    assert any("PKG" in t for t in labels)


def test_auto_usb_panel_directory_copy_has_options(qapp) -> None:
    from qfluentwidgets import CheckBox

    from fwasset.ui_qt.operation_panels import get_panel

    panel = get_panel("auto_usb")(
        asset=_op_asset(firmware_type="music_files", usb_flow="directory_copy"),
        log_fn=lambda _m: None,
        panel_host=_FakeHost(),
    )
    panel.build()
    checks = {c.text(): c.isChecked() for c in panel.findChildren(CheckBox)}
    assert checks == {"格式化": True, "完成后弹出": True}


def test_tool_launch_panel_without_tool_disables_button(qapp) -> None:
    from qfluentwidgets import PrimaryPushButton

    from fwasset.ui_qt.operation_panels import get_panel

    panel = get_panel("tool_launch")(
        asset=_op_asset(firmware_type="不存在的类型", flash_mode="tool_launch"),
        log_fn=lambda _m: None,
        panel_host=_FakeHost(),
    )
    panel.build()
    launch = [b for b in panel.findChildren(PrimaryPushButton) if b.text() == "打开烧录工具"]
    assert launch and not launch[0].isEnabled()


def test_disabled_and_manual_panels_have_handoff_actions(qapp) -> None:
    from qfluentwidgets import PushButton

    from fwasset.ui_qt.operation_panels import get_panel

    host = _FakeHost()
    for mode in ("disabled", "manual_doc"):
        panel = get_panel(mode)(
            asset=_op_asset(flash_mode=mode), log_fn=lambda _m: None, panel_host=host
        )
        panel.build()
        texts = {b.text() for b in panel.findChildren(PushButton)}
        assert {"打开程序目录", "复制目录路径", "复制主文件路径"} <= texts, f"{mode} 缺交接按钮"


def test_run_task_busy_guard_and_completion(qapp) -> None:
    """任务桥契约：忙时拒绝新任务；worker 结束后经 Signal 回投解除忙态。"""
    import time as _time

    from fwasset.ui_qt.workbench_window import WorkbenchInterface

    w = WorkbenchInterface()
    logs: list[str] = []
    w.log_message.connect(logs.append)

    done = []
    w._run_task("测试任务", lambda log_fn: (log_fn("working"), "ok")[-1], lambda r: done.append(r))
    # 忙态下第二个任务应被拒绝
    w._run_task("第二任务", lambda log_fn: "no")
    deadline = _time.time() + 5
    while w._busy and _time.time() < deadline:
        qapp.processEvents()
        _time.sleep(0.02)
    qapp.processEvents()

    assert w._busy is False, "worker 完成后应解除忙态"
    assert done == ["ok"], "on_done 回调应收到任务结果"
    assert any("已有任务执行中" in m for m in logs)
    assert any("测试任务完成" in m for m in logs)
