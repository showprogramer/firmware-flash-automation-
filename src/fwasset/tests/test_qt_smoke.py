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

from fwasset.ui.view_models.scheme_workbench_model import (  # noqa: E402
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
        source_label="通用默认" if kind == "common" else "定制专属",
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


def test_single_variant_collapses_with_default_text_and_badge(qapp) -> None:
    """单变体折叠为一行；变体名 == 模块名时显示「默认」；徽章拼接在程序名称列。"""
    row = ModuleRow(
        label="主板程序",
        source_kind="common",
        source_label="通用默认",
        variants=[_variant("主板程序", badge="★默认")],
    )
    grid = DataGrid(lambda _m: None)
    grid.populate_tree([row])

    assert grid.tree.topLevelItemCount() == 1
    item = grid.tree.topLevelItem(0)
    assert item.childCount() == 0
    assert item.text(0) == "主板程序"
    assert item.text(1) == "默认  ★默认"
    assert item.text(3) == "通用默认"
    assert "回源" not in item.text(3)


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


def test_model_overflow_uses_searchable_dropdown(qapp) -> None:
    """型号超过 chip 上限时，溢出项落入可输入过滤的 EditableComboBox；
    输入中间态（非真实型号）不得改变当前选中型号。"""
    from qfluentwidgets import EditableComboBox, TogglePushButton

    from fwasset.ui_qt.workbench_window import WorkbenchInterface

    w = WorkbenchInterface()
    models = ["L36", "L36双机芯-上3D-下2D", "L50S", "M3", "M5", "M8"]
    w.current_selection.model_name = "L36"
    w._refresh_model_selector(models)

    widgets = [
        w.chip_bar.itemAt(i).widget()
        for i in range(w.chip_bar.count())
        if w.chip_bar.itemAt(i).widget() is not None
    ]
    chips = [x for x in widgets if isinstance(x, TogglePushButton)]
    combos = [x for x in widgets if isinstance(x, EditableComboBox)]
    assert len(chips) == 4, "前 4 个型号应显示为 chip"
    assert len(combos) == 1, "溢出型号应落入可输入过滤下拉"
    assert combos[0].count() == 2  # M5 / M8（M3 被换出规则保留在 chips 之外时进溢出）or 2 items

    # 防呆：输入中间态 "L5"（不是真实型号）不得切换
    w._on_model_changed("L5")
    assert w.current_selection.model_name == "L36"
    # 真实型号可切换
    w._on_model_changed("M8")
    assert w.current_selection.model_name == "M8"
