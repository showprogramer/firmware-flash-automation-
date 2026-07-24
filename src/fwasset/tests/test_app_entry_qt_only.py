from __future__ import annotations

import sys
import types

import pytest

import fwasset.app as app_module


def test_main_defaults_to_qt_when_ui_switch_is_unset(monkeypatch):
    called: list[str] = []

    fake_qt = types.ModuleType("fwasset.ui_qt.workbench_window")
    fake_qt.main = lambda: called.append("qt") or 0
    fake_ctk = types.ModuleType("fwasset.ui.shell")

    class UnexpectedCtkLaunch:
        def __init__(self):
            raise AssertionError("default entry must not construct the CTk shell")

    fake_ctk.UnifiedFlashPlatform = UnexpectedCtkLaunch
    monkeypatch.setitem(sys.modules, "fwasset.ui_qt.workbench_window", fake_qt)
    monkeypatch.setitem(sys.modules, "fwasset.ui.shell", fake_ctk)
    monkeypatch.delenv("FWASSET_UI", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        app_module.main()

    assert exc_info.value.code == 0
    assert called == ["qt"]
