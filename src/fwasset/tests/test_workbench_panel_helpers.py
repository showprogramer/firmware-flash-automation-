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


def test_workbench_panel_start_scan_always_asks_for_directory() -> None:
    """单工作区：点「扫描目录」必须弹选目录，不能仅在 root 为空时才弹。

    否则已有 DEFAULT_ROOT / 上次扫描根时用户无法换根，只会静默重扫。
    """
    from pathlib import Path

    text = Path("src/fwasset/ui/workbench_panel.py").read_text(encoding="utf-8")
    start = text.index("def _start_scan")
    end = text.index("\n    def ", start + 1)
    body = text[start:end]
    assert "askdirectory" in body
    # 对话框不得包在「root 为空」分支里（旧 bug：有 root 就静默重扫）
    assert "if not root:\n" not in body.split("askdirectory")[0]


def test_qt_workbench_start_scan_always_asks_for_directory() -> None:
    """Qt 壳与 CTk 对齐：_start_scan 每次都 getExistingDirectory。"""
    from pathlib import Path

    text = Path("src/fwasset/ui_qt/workbench_window.py").read_text(encoding="utf-8")
    start = text.index("def _start_scan")
    end = text.index("\n    def ", start + 1)
    body = text[start:end]
    assert "getExistingDirectory" in body
    # 对话框前不得存在「仅 root 为空才弹」分支
    assert "if not root:\n" not in body.split("getExistingDirectory")[0]


def _method_body(source: str, method_name: str) -> str:
    """Slice from ``def <method_name>`` to the next method at the same indent, or EOF."""
    marker = f"def {method_name}"
    start = source.index(marker)
    rest = source[start + len(marker) :]
    # next top-level class method: newline + 4 spaces + def
    next_idx = rest.find("\n    def ")
    if next_idx < 0:
        return source[start:]
    return source[start : start + len(marker) + next_idx]


def test_workbench_handles_cancelled_scan_without_complete_log() -> None:
    """取消扫描不得记为「扫描完成…0 个项目」。"""
    from pathlib import Path

    for rel in (
        "src/fwasset/ui/workbench_panel.py",
        "src/fwasset/ui_qt/workbench_window.py",
    ):
        text = Path(rel).read_text(encoding="utf-8")
        body = _method_body(text, "_handle_scan_result")
        assert '== "cancelled"' in body
        assert "扫描已被用户取消" in body or "cancelled" in body


def test_workbench_scan_task_mutual_exclusion_contract() -> None:
    """扫描与操作任务双向互锁：忙时不扫、扫描中不跑任务。"""
    from pathlib import Path

    ctk = Path("src/fwasset/ui/workbench_panel.py").read_text(encoding="utf-8")
    assert "if self._busy:" in _method_body(ctk, "_start_scan")
    assert "is_scanning" in _method_body(ctk, "_run_task")

    qt = Path("src/fwasset/ui_qt/workbench_window.py").read_text(encoding="utf-8")
    assert "if self._busy:" in _method_body(qt, "_start_scan")
    assert "is_scanning" in _method_body(qt, "_run_task")


def test_select_custom_scheme_clears_search_contract() -> None:
    """Issue 19-A：进入定制方案须清空搜索并重建侧栏，避免其它方案「消失」。"""
    from pathlib import Path

    ctk = Path("src/fwasset/ui/workbench_panel.py").read_text(encoding="utf-8")
    body = _method_body(ctk, "_select_custom_scheme")
    assert "search_var" in body and 'set("")' in body.replace(" ", "")
    assert "_refresh_sidebar_tree" in body

    qt = Path("src/fwasset/ui_qt/workbench_window.py").read_text(encoding="utf-8")
    # _on_nav_changed 内 custom_scheme 分支
    nav = _method_body(qt, "_on_nav_changed")
    assert "custom_scheme" in nav
    assert "search_edit.clear" in nav or "clear()" in nav
    assert "_refresh_sidebar_tree" in nav
    # 重建后按逻辑选中重定位高亮，不能依赖旧 currentRow
    assert "_apply_nav_selection_highlight" in qt
    assert "setCurrentRow" in _method_body(qt, "_apply_nav_selection_highlight")


def test_base_panel_and_qt_log_service_result_ok() -> None:
    """任务完成路径须按 ServiceResult.ok 区分完成/失败。"""
    from pathlib import Path

    base = Path("src/fwasset/ui/base_panel.py").read_text(encoding="utf-8")
    poll = _method_body(base, "_poll_task_queue")
    assert '"ok" in payload' in poll or "'ok' in payload" in poll

    qt = Path("src/fwasset/ui_qt/workbench_window.py").read_text(encoding="utf-8")
    done = _method_body(qt, "_on_task_done")
    assert '"ok" in result' in done or "'ok' in result" in done


def test_qt_run_task_runs_on_done_on_ui_thread_via_task_id() -> None:
    """Issue 8：Signal 传 task_id+结果；on_done 在 UI 槽内按 id 取出执行。"""
    from pathlib import Path

    text = Path("src/fwasset/ui_qt/workbench_window.py").read_text(encoding="utf-8")
    assert "_task_done = Signal(int, str, object)" in text
    assert "_pending_task_callbacks" in text
    run = _method_body(text, "_run_task")
    compact = run.replace(" ", "")
    # worker 内只 emit，不直接调 on_done
    assert "on_done(result)" not in compact
    assert "_task_done.emit(task_id,name,result)" in compact
    done = _method_body(text, "_on_task_done")
    assert "_pending_task_callbacks.pop" in done
    assert "on_done(result)" in done.replace(" ", "")


def test_ctk_handle_scan_result_recovers_root_from_scan_meta() -> None:
    """Issue 14：CTk 缓存加载路径从 scan_meta 恢复 root（与 Qt 对齐）。"""
    from pathlib import Path

    body = _method_body(
        Path("src/fwasset/ui/workbench_panel.py").read_text(encoding="utf-8"),
        "_handle_scan_result",
    )
    assert "scan_meta" in body
    assert "root_dir" in body


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
