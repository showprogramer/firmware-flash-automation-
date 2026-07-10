"""Tests for BaseFlashPanel._poll_task_queue destruction guards.

Background: a background worker (started by _run_task) may complete AFTER the
window has been destroyed. Without protection, the polling loop calls
self.after(120, ...) on a destroyed widget, raising TclError. It also calls
user-supplied on_done() callbacks without guarding against widget teardown.

These tests pin down the destruction guard contract: the polling method must
return early when the widget no longer exists, must not re-arm `self.after`,
and must guard user callbacks so a single throwing callback doesn't kill the
polling chain.
"""

from __future__ import annotations

import queue
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.ui


def _make_panel_stub(*, exists: bool, raise_in_after: bool = False):
    """Build a BaseFlashPanel subclass that bypasses CTkFrame.__init__.

    Returns an instance with just enough state for _poll_task_queue to run:
    _polling_active, _busy, _task_queue, plus the tkinter-style after/winfo_exists
    surface.
    """
    from fwasset.ui.base_panel import BaseFlashPanel

    # Skip CTkFrame.__init__ — we're testing pure logic, not widgets.
    panel = BaseFlashPanel.__new__(BaseFlashPanel)
    panel._polling_active = True
    panel._busy = True
    panel._task_queue = queue.Queue()
    panel._log = lambda msg: None  # noqa: ARG005

    after_calls: list = []
    if raise_in_after:

        def _after(_ms, _fn):
            after_calls.append((_ms, _fn))
            raise RuntimeError("simulated TclError on destroyed widget")

    else:

        def _after(_ms, _fn):
            after_calls.append((_ms, _fn))

    panel.after = _after
    panel.winfo_exists = MagicMock(return_value=exists)
    return panel, after_calls


class TestPollTaskQueueDestructionGuard:
    def test_returns_immediately_when_widget_destroyed(self) -> None:
        """If the widget no longer exists, _poll_task_queue must NOT drain the queue
        and must NOT call self.after — the Tk widget tree is gone, scheduling a
        callback raises TclError."""
        panel, after_calls = _make_panel_stub(exists=False)
        panel._task_queue.put(("done", "task", None, lambda _: None))

        panel._poll_task_queue()

        # Queue was never drained; no after was scheduled; busy flag untouched.
        assert not panel._task_queue.empty(), "queue should be left for the next poll"
        assert after_calls == []
        assert panel._busy is True, "busy must not flip when widget is gone"

    def test_does_not_schedule_after_when_widget_destroyed(self) -> None:
        """Even with an empty queue, a destroyed widget must not get self.after."""
        panel, after_calls = _make_panel_stub(exists=False)

        panel._poll_task_queue()

        assert after_calls == [], "self.after must not be called on a destroyed widget"

    def test_polls_normally_when_widget_alive(self) -> None:
        """Sanity check: a live widget drains the queue and re-arms the polling loop."""
        panel, after_calls = _make_panel_stub(exists=True)
        seen = []
        panel._task_queue.put(("done", "task", "ok", lambda p: seen.append(p)))

        panel._poll_task_queue()

        assert seen == ["ok"], "on_done must run when the widget is alive"
        assert panel._busy is False, "busy must clear after a successful drain"
        assert after_calls == [(120, panel._poll_task_queue)]

    def test_drain_loop_stops_if_widget_disappears_mid_poll(self) -> None:
        """If the widget exists when the loop starts but is destroyed between
        iterations, the loop must not keep draining or re-arm after."""
        panel, after_calls = _make_panel_stub(exists=True)
        # First item: simulate widget teardown happening during on_done by flipping
        # winfo_exists to False before the second iteration.
        panel._task_queue.put(("done", "first", "ok", lambda _p: panel.winfo_exists.configure_mock(return_value=False)))
        panel._task_queue.put(("done", "second", "ok", lambda _p: None))

        panel._poll_task_queue()

        # after() must not be called because the widget was gone before scheduling.
        assert after_calls == [], "after must not be scheduled once widget disappears"

    def test_throwing_on_done_does_not_break_polling(self) -> None:
        """A user callback raising must not leave busy=True and must not skip the
        next on_done. The contract: callback exceptions are caught, busy clears,
        and a live widget still re-arms the polling loop."""
        panel, after_calls = _make_panel_stub(exists=True)
        good_calls: list = []

        def bad(_p):
            raise RuntimeError("user callback blew up")

        def good(p):
            good_calls.append(p)

        panel._task_queue.put(("done", "first", None, bad))
        panel._task_queue.put(("done", "second", "ok", good))

        panel._poll_task_queue()

        assert good_calls == ["ok"], "second on_done must still run after first raised"
        assert panel._busy is False
        assert after_calls == [(120, panel._poll_task_queue)]

    def test_service_result_ok_false_logs_failure_not_done(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ServiceResult ok=False must not log 「完成」."""
        from fwasset.ui import base_panel as base_mod

        panel, after_calls = _make_panel_stub(exists=True)
        logs: list[str] = []
        panel._log = logs.append
        monkeypatch.setattr(base_mod.messagebox, "showerror", lambda *a, **k: None)

        panel._task_queue.put(
            (
                "done",
                "一键执行",
                {"ok": False, "code": "copy_failed", "message": "复制失败", "payload": {}},
                None,
            )
        )

        panel._poll_task_queue()

        assert any("失败" in m and "复制失败" in m for m in logs)
        assert not any(m.endswith("完成") for m in logs)
        assert panel._busy is False
        assert after_calls == [(120, panel._poll_task_queue)]
