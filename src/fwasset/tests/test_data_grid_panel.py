"""Tests for DataGridPanel rendering ModuleRow trees (七程序可展开层级).

These are pure data-mapping tests over the panel's *non-widget* logic: we drive
`populate_tree()` against a real ttk.Treeview but only assert on tree structure
and the panel's selection bookkeeping — no event loop, no visible window. Marked
ui because instantiating the panel needs a Tk root.
"""

from __future__ import annotations

import pytest

from fwasset.ui.view_models.scheme_workbench_model import ModuleRow, ModuleVariant


@pytest.fixture(scope="module")
def tk_root():
    """One hidden (withdrawn) Tk root for the whole module.

    Creating/destroying a CustomTkinter root repeatedly inside pytest is flaky
    (CTk leaves scaling-tracker `after` callbacks that fire post-destroy and a
    fresh root can fail to re-init Tcl). A single module-scoped root avoids that;
    each test clears the tree via a fresh panel. No mainloop → headless-safe.
    """
    import customtkinter as ctk

    root = ctk.CTk()
    root.withdraw()
    try:
        yield root
    finally:
        root.destroy()


def _variant(path: str, name: str, version: str, kind: str) -> ModuleVariant:
    return ModuleVariant(
        asset={"path": path, "directory_name": name, "version": version, "flash_mode": "auto_usb"},
        name=name,
        version=version,
        source_kind=kind,
        source_label="定制专属" if kind == "custom" else "通用默认",
    )


def _rows() -> list[ModuleRow]:
    mainboard = ModuleRow(
        label="主板程序",
        source_kind="custom",
        source_label="定制专属",
        variants=[_variant("/L36/定制/马来/主板程序", "主板程序", "V40", "custom")],
    )
    handui = ModuleRow(
        label="手控UI",
        source_kind="custom",
        source_label="定制专属",
        variants=[
            _variant("/L36/定制/马来/手控UI/A", "手控UI-A", "V1", "custom"),
            _variant("/L36/定制/马来/手控UI/B", "手控UI-B", "V2", "custom"),
            _variant("/L36/定制/马来/手控UI/C", "手控UI-C", "V3", "custom"),
        ],
    )
    leg = ModuleRow(
        label="腿部程序",
        source_kind="common",
        source_label="通用默认",
        variants=[_variant("/L36/通用/腿部程序", "腿部程序", "V5", "common")],
    )
    return [mainboard, handui, leg]


@pytest.fixture()
def panel(tk_root):
    from fwasset.ui.panels.data_grid_panel import DataGridPanel

    captured = []
    p = DataGridPanel(tk_root, on_selection_changed=captured.append, on_log=lambda *_: None)
    p._captured = captured  # type: ignore[attr-defined]
    return p


@pytest.mark.ui
def test_populate_tree_top_level_is_module_rows(panel):
    panel.populate_tree(_rows())
    top = panel.tree.get_children("")
    assert len(top) == 3


@pytest.mark.ui
def test_multi_variant_module_collapses_under_one_row(panel):
    panel.populate_tree(_rows())
    top = panel.tree.get_children("")
    # locate the 手控UI row and assert it has 3 children, not flattened at top
    handui = next(i for i in top if "手控UI" in panel.tree.item(i, "text"))
    assert len(panel.tree.get_children(handui)) == 3


@pytest.mark.ui
def test_single_variant_module_is_a_leaf_row(panel):
    """单变体模块应折叠成一行叶子，不建子节点，选中即拿到变体。"""
    panel.populate_tree(_rows())
    top = panel.tree.get_children("")
    mainboard = next(i for i in top if "主板程序" in panel.tree.item(i, "text"))
    # 单变体：没有子节点
    assert panel.tree.get_children(mainboard) == ()
    # 版本落在该行上
    assert panel.tree.item(mainboard, "values")[1] == "V40"
    # 选中该模块行即可直接拿到变体（无需展开）
    panel.tree.selection_set(mainboard)
    sel = panel.get_selected_variant()
    assert sel is not None
    assert sel.asset["path"] == "/L36/定制/马来/主板程序"


@pytest.mark.ui
def test_single_variant_name_blank_only_when_equal_to_module_label(panel):
    """变体名只在 == 模块类型名时才留空（消除 `主板程序/主板程序` 重复）；
    若变体名有区分信息（如 `主板程序-减少灯光`）则照常显示，否则看不出是哪一份。"""
    rows = [
        # 变体名 == 模块名 → 留空（真重复）
        ModuleRow(
            label="主板程序",
            source_kind="custom",
            source_label="定制专属",
            variants=[_variant("/p/mb", "主板程序", "V40", "custom")],
        ),
        # 变体名 ≠ 模块名 → 照常显示（有用的区分信息）
        ModuleRow(
            label="主板程序",  # 用相同 label 测分支，但实际是另一行；改用不同 label 避免 iid 撞
            source_kind="custom",
            source_label="定制专属",
            variants=[_variant("/p/mb2", "主板程序-减少灯光", "V41", "custom")],
        ),
    ]
    # 两行 label 相同会撞 iid，单独各测一次更干净
    panel.populate_tree([rows[0]])
    top = panel.tree.get_children("")[0]
    assert panel.tree.item(top, "values")[0] == ""  # 重复名 → 留空

    panel.populate_tree([rows[1]])
    top = panel.tree.get_children("")[0]
    assert panel.tree.item(top, "values")[0] == "主板程序-减少灯光"  # 有区分信息 → 显示


@pytest.mark.ui
def test_program_column_shows_primary_firmware_filename(panel):
    """「程序名称」列显示主固件文件名（手控显示 rom）。"""
    v = ModuleVariant(
        asset={
            "path": "/L36/定制/马来/手控UI/A",
            "directory_name": "手控UI-A",
            "version": "V12",
            "files": ["hc_v12.pkg", "hc_v12.rom"],
        },
        name="手控UI-A",
        version="V12",
        source_kind="custom",
        source_label="定制专属",
    )
    row = ModuleRow(label="手控UI-单", source_kind="custom", source_label="定制专属", variants=[v])
    panel.populate_tree([row])
    top = panel.tree.get_children("")[0]
    # values = (变体名, 版本, 来源, 程序名称) → 程序名列是 rom
    assert panel.tree.item(top, "values")[3] == "hc_v12.rom"


@pytest.mark.ui
def test_multi_variant_parent_row_is_not_selectable_leaf(panel):
    """多变体父行仍不可直接选中变体（保持展开后再选）。"""
    panel.populate_tree(_rows())
    top = panel.tree.get_children("")
    handui = next(i for i in top if "手控UI" in panel.tree.item(i, "text"))
    panel.tree.selection_set(handui)
    assert panel.get_selected_variant() is None


@pytest.mark.ui
def test_selecting_variant_returns_variant_data(panel):
    panel.populate_tree(_rows())
    top = panel.tree.get_children("")
    handui = next(i for i in top if "手控UI" in panel.tree.item(i, "text"))
    child = panel.tree.get_children(handui)[1]  # variant B
    panel.tree.selection_set(child)
    data = panel.get_selected_variant()
    assert data is not None
    assert data.name == "手控UI-B"
    assert data.asset["path"] == "/L36/定制/马来/手控UI/B"


@pytest.mark.ui
def test_selecting_module_parent_returns_none(panel):
    """Selecting a multi-variant parent row must not pick a variant — user expands first."""
    panel.populate_tree(_rows())
    top = panel.tree.get_children("")
    handui = next(i for i in top if "手控UI" in panel.tree.item(i, "text"))
    panel.tree.selection_set(handui)
    assert panel.get_selected_variant() is None


@pytest.mark.ui
def test_populate_groups_same_label_cards_into_one_row(panel):
    """通用/全部视图：同类型多张卡片必须归到一行，不能产生重复 mod:: iid。"""
    from fwasset.ui.view_models.scheme_workbench_model import ModuleCardData

    def card(path: str, name: str) -> ModuleCardData:
        return ModuleCardData(
            asset={"path": path, "firmware_label": "手控UI", "directory_name": name, "version": "V1"},
            source_type="common_variant",
            source_label="通用默认",
            is_fallback=True,
        )

    # three 手控UI cards — previously each became mod::手控UI → TclError
    panel.populate([card("/p/A", "A"), card("/p/B", "B"), card("/p/C", "C")])
    top = panel.tree.get_children("")
    assert len(top) == 1
    assert len(panel.tree.get_children(top[0])) == 3


@pytest.mark.ui
def test_source_label_never_contains_huiyuan(panel):
    panel.populate_tree(_rows())
    for top in panel.tree.get_children(""):
        vals = panel.tree.item(top, "values")
        assert all("回源" not in str(v) for v in vals)
        for child in panel.tree.get_children(top):
            cvals = panel.tree.item(child, "values")
            assert all("回源" not in str(v) for v in cvals)
