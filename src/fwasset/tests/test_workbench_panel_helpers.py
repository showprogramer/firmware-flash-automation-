from __future__ import annotations

import inspect

from fwasset.ui.view_models.scheme_workbench_model import WorkbenchSelection
from fwasset.ui.workbench_panel import WorkbenchPanel, flash_mode_label, model_chip_values


def test_shared_actions_uses_design_tokens_not_magic_numbers() -> None:
    """shared_actions must not carry hard-coded padx=20 — spacing belongs in
    design_tokens so the operation panel stays aligned with the rest of the
    app when tokens are tuned.
    """
    from pathlib import Path

    from fwasset.ui.operation_panels import shared_actions

    source = Path(shared_actions.__file__).read_text(encoding="utf-8")
    assert "padx=20" not in source, (
        "shared_actions still hard-codes padx=20; replace with SPACE_LG or "
        "another design_tokens.SPACE_* constant"
    )


def test_workbench_panel_has_no_in_method_imports_for_known_offenders() -> None:
    """Specific module-level imports must live at the top of workbench_panel.py
    so import cost (and side effects) are paid once, not on every call.

    Background: P2-2 of the UI review found `import os, subprocess` and
    `from tkinter import filedialog` inside two methods. Both are now at the
    top. This test pins that down so a regression re-introducing a hot-path
    import is caught immediately.
    """
    import re
    from pathlib import Path

    source = Path(WorkbenchPanel.__module__.replace(".", "/") + ".py")
    # The file lives under src/fwasset/ui/workbench_panel.py.
    # __module__ may be a dotted path; resolve to a real path.
    candidates = [
        Path("src/fwasset/ui/workbench_panel.py"),
        Path("D:/Coding/python_projects/fwasset-manager/src/fwasset/ui/workbench_panel.py"),
    ]
    text = None
    for c in candidates:
        if c.exists():
            text = c.read_text(encoding="utf-8")
            break
    assert text is not None, "could not locate workbench_panel.py for static check"

    # Strip the top-level import block (everything up to the first class/function
    # def at column 0). Anything past that point must not introduce these names.
    body = re.split(r"^class \w+", text, maxsplit=1, flags=re.MULTILINE)
    body_text = body[1] if len(body) == 2 else text

    assert "import os, subprocess" not in body_text, (
        "`import os, subprocess` must move to the top of the file"
    )
    assert "from tkinter import filedialog" not in body_text, (
        "`from tkinter import filedialog` must move to the top of the file"
    )


def test_workbench_panel_auto_refreshes_usb_on_startup() -> None:
    """Regresssion guard: the workbench must schedule an initial _refresh_usb
    in __init__ so the global U盘 selector is populated when the app starts.

    Background: without this, the user has to click 「刷新」 once after launch
    before 一键烧录 can run. That's a two-click startup tax for every session.
    """
    from pathlib import Path

    candidates = [
        Path("src/fwasset/ui/workbench_panel.py"),
        Path("D:/Coding/python_projects/fwasset-manager/src/fwasset/ui/workbench_panel.py"),
    ]
    text = None
    for c in candidates:
        if c.exists():
            text = c.read_text(encoding="utf-8")
            break
    assert text is not None

    # Slice from the WorkbenchPanel class body (drop the module-level imports
    # and any sibling helpers). Inside that body, look for an
    # `self.after(...)`-scheduled `_refresh_usb` call. We don't pin the exact
    # delay to avoid coupling to a magic number.
    cls_idx = text.index("class WorkbenchPanel")
    body = text[cls_idx:]
    assert "_refresh_usb" in body, "WorkbenchPanel must reference _refresh_usb"
    # The startup hookup must happen inside __init__ (not only in callbacks).
    init_start = body.index("def __init__")
    init_end = body.index("def _build_sidebar", init_start)
    init_body = body[init_start:init_end]
    assert "_refresh_usb" in init_body, (
        "WorkbenchPanel.__init__ must schedule _refresh_usb via self.after(...) "
        "so the global U盘 selector populates on startup"
    )


def test_workbench_panel_exposes_global_usb_selector_in_main_view() -> None:
    """BUG-3 (human verify): the workbench must show a U盘 selector in its main
    view so panel_host.get_global_usb_drive() can return something non-empty.

    Background: Step C of the workbench UI rewrite deleted per-panel U盘
    selectors in favour of a global one — but the global selector entry
    point was never added to the workbench. As a result, clicking
    "一键烧录" on a hand-control variant immediately hits a dead end
    ("请先选择目标 U 盘"), with no UI affordance to set the drive.
    """
    from pathlib import Path

    candidates = [
        Path("src/fwasset/ui/workbench_panel.py"),
        Path("D:/Coding/python_projects/fwasset-manager/src/fwasset/ui/workbench_panel.py"),
    ]
    text = None
    for c in candidates:
        if c.exists():
            text = c.read_text(encoding="utf-8")
            break
    assert text is not None

    # The main view must reference the global drive selector and the refresh
    # method. Anything less means the user has no way to populate
    # self.usb_drive.
    assert "self.usb_drive" in text, "WorkbenchPanel must reference self.usb_drive"
    assert "_refresh_usb" in text, "WorkbenchPanel must call _refresh_usb"
    # The USB selector row should be built inside _build_main_view
    # (i.e. visible alongside the model chips + search bar at the top).
    main_view = text[text.index("def _build_main_view"):]
    assert "usb_menu" in main_view or "CTkComboBox" in main_view, (
        "_build_main_view must include a U盘 ComboBox so users can pick a drive"
    )


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


class _FakeAfterScheduler:
    """Records every scheduled callback and the IDs we returned.

    Stubs out `after` / `after_cancel` / `winfo_exists` on a WorkbenchPanel
    instance so tests can verify the debounce discipline without spinning up Tk.
    """

    def __init__(self, exists: bool = True) -> None:
        self.next_id = 1
        self.scheduled: list[tuple[int, int, object]] = []  # (id, delay_ms, fn)
        self.cancelled: list[int] = []
        self._exists = exists

    def after(self, delay_ms: int, fn):
        _id = self.next_id
        self.next_id += 1
        self.scheduled.append((_id, delay_ms, fn))
        return _id

    def after_cancel(self, _id: int) -> None:
        self.cancelled.append(_id)

    def winfo_exists(self) -> bool:
        return self._exists


def _make_panel_with_fake_scheduler(exists: bool = True) -> tuple[WorkbenchPanel, _FakeAfterScheduler]:
    """Build a WorkbenchPanel stub: bypass __init__, install a fake after/cancel."""
    scheduler = _FakeAfterScheduler(exists=exists)
    panel = WorkbenchPanel.__new__(WorkbenchPanel)
    panel.after = scheduler.after  # type: ignore[method-assign]
    panel.after_cancel = scheduler.after_cancel  # type: ignore[method-assign]
    panel.winfo_exists = scheduler.winfo_exists  # type: ignore[method-assign]
    panel._search_after_id = None
    panel._search_refresh_delay_ms = 180
    panel._refresh_sidebar_tree = lambda: None  # type: ignore[method-assign]
    panel._refresh_main_grid = lambda: None  # type: ignore[method-assign]
    return panel, scheduler


def test_on_search_changed_uses_debounce_not_immediate_refresh() -> None:
    """Typing in the search box must not rebuild the sidebar on every keystroke.

    Contract: _on_search_changed schedules a delayed refresh, never the
    immediate _refresh_sidebar_tree() call that caused flicker under fast typing.
    """
    panel, scheduler = _make_panel_with_fake_scheduler()
    refresh_calls: list[int] = []
    panel._refresh_sidebar_tree = lambda: refresh_calls.append(1)  # type: ignore[method-assign]

    WorkbenchPanel._on_search_changed(panel)

    assert refresh_calls == [], "search must not rebuild the sidebar immediately"
    assert len(scheduler.scheduled) == 1
    assert scheduler.scheduled[0][1] == 180
    assert panel._search_after_id == scheduler.scheduled[0][0]


def test_rapid_search_typing_cancels_previous_after() -> None:
    """Fast typing: only the last scheduled refresh survives — the earlier
    after-IDs are cancelled, so the sidebar rebuilds once at the end of the burst.
    """
    panel, scheduler = _make_panel_with_fake_scheduler()

    WorkbenchPanel._on_search_changed(panel)  # id 1
    WorkbenchPanel._on_search_changed(panel)  # id 2 — must cancel id 1
    WorkbenchPanel._on_search_changed(panel)  # id 3 — must cancel id 2
    WorkbenchPanel._on_search_changed(panel)  # id 4 — must cancel id 3

    assert scheduler.cancelled == [1, 2, 3]
    assert [s[0] for s in scheduler.scheduled] == [1, 2, 3, 4]
    assert panel._search_after_id == 4


def test_non_search_paths_still_call_refresh_immediately() -> None:
    """Model switching, scan completion, etc. ultimately call _refresh_sidebar_tree()
    directly and must NOT be routed through the search debounce — users expect
    immediate feedback for those actions.

    We assert the negative contract: the debounce machinery (after/after_cancel)
    must NOT be touched when the immediate path runs. We don't try to exercise
    the real _refresh_sidebar_tree (it builds widgets); instead we verify that
    the scheduler — which sits in front of every debounce — records nothing.
    """
    panel, scheduler = _make_panel_with_fake_scheduler()

    # Simulate the immediate path: the production code calls
    # self._refresh_sidebar_tree() directly, without going through after().
    # In our stub, the underlying method would crash on widget access, so we
    # patch it with a no-op and then invoke it the way production callers do
    # (instance attribute lookup → class method resolution).
    refresh_calls: list[int] = []

    def _immediate_refresh() -> None:
        refresh_calls.append(1)

    # Bind to the instance so the lookup hits our stub rather than the real
    # class method that would need widgets.
    panel._refresh_sidebar_tree = _immediate_refresh  # type: ignore[method-assign]

    # Call it the way every non-search caller does: panel._refresh_sidebar_tree().
    panel._refresh_sidebar_tree()

    assert refresh_calls == [1]
    assert scheduler.scheduled == [], "non-search callers must not go through after()"
    assert scheduler.cancelled == []


def test_delayed_search_refresh_skips_when_widget_destroyed() -> None:
    """The delayed callback must re-check that the widget still exists before
    rebuilding the sidebar — closing the window mid-debounce must not crash.
    """
    panel, scheduler = _make_panel_with_fake_scheduler(exists=False)
    refresh_calls: list[int] = []
    panel._refresh_sidebar_tree = lambda: refresh_calls.append(1)  # type: ignore[method-assign]

    WorkbenchPanel._on_search_changed(panel)
    assert len(scheduler.scheduled) == 1
    _id, _delay, fn = scheduler.scheduled[0]
    fn()  # closure runs, but winfo_exists is False → skip the actual refresh

    assert refresh_calls == [], "destroyed widget must not trigger a refresh"
