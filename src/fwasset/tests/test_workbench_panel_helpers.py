from __future__ import annotations

import inspect

from fwasset.ui.view_models.scheme_workbench_model import WorkbenchSelection
from fwasset.ui.workbench_panel import WorkbenchPanel, flash_mode_label, model_chip_values


def test_model_chip_values_keeps_first_models_visible_when_within_limit() -> None:
    chips, overflow = model_chip_values(["L36", "L30", "X8"], selected="L36", limit=5)

    assert chips == ["L36", "L30", "X8"]
    assert overflow == []


def test_model_chip_values_moves_selected_overflow_model_into_chips() -> None:
    models = ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]

    chips, overflow = model_chip_values(models, selected="L7", limit=5)

    assert chips == ["L1", "L2", "L3", "L4", "L7"]
    assert overflow == ["L5", "L6"]


def test_flash_mode_label_uses_operator_facing_text() -> None:
    assert flash_mode_label("auto_usb") == "USB刷机"
    assert flash_mode_label("tool_launch") == "工具烧录"
    assert flash_mode_label("unknown") == "unknown"


def test_sidebar_no_longer_exposes_tool_center_button() -> None:
    sidebar_source = inspect.getsource(WorkbenchPanel._build_sidebar)

    assert "工具中心" not in sidebar_source
    assert "_open_tool_center" not in sidebar_source


class FakeModelFrame:
    def __init__(self, children: list[object]) -> None:
        self.children = children

    def winfo_children(self) -> list[object]:
        return list(self.children)


class FakeHint:
    def __init__(self) -> None:
        self.destroyed = False
        self.grid_count = 0
        self.grid_remove_count = 0

    def destroy(self) -> None:
        self.destroyed = True

    def grid(self, **_kwargs) -> None:
        self.grid_count += 1

    def grid_remove(self) -> None:
        self.grid_remove_count += 1


class FakeDynamicWidget:
    def __init__(self, master=None, **_kwargs) -> None:
        self.destroyed = False
        self.grid_count = 0
        if hasattr(master, "children"):
            master.children.append(self)

    def destroy(self) -> None:
        self.destroyed = True

    def grid(self, **_kwargs) -> None:
        self.grid_count += 1

    def set(self, _value: str) -> None:
        pass


def test_refresh_model_selector_keeps_hint_widget_alive(monkeypatch) -> None:
    import fwasset.ui.workbench_panel as module

    monkeypatch.setattr(module.ctk, "CTkButton", FakeDynamicWidget)
    monkeypatch.setattr(module.ctk, "CTkComboBox", FakeDynamicWidget)

    hint = FakeHint()
    stale = FakeDynamicWidget()
    panel = WorkbenchPanel.__new__(WorkbenchPanel)
    panel.model_chip_frame = FakeModelFrame([hint, stale])
    panel.model_hint = hint
    panel.current_selection = WorkbenchSelection(model_name="L36")
    panel._available_models = []
    panel._model_buttons = {}
    panel._more_model_combo = None

    WorkbenchPanel._refresh_model_selector(panel, ["L36", "L50"])
    WorkbenchPanel._refresh_model_selector(panel, [])

    assert hint.destroyed is False
    assert stale.destroyed is True
    assert hint.grid_remove_count == 1
    assert hint.grid_count == 1
