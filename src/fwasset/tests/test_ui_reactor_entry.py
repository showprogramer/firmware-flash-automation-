import pytest

import fwasset.app as app_module
import fwasset.ui.shell as shell_module

pytestmark = pytest.mark.ui


def test_main_routes_to_ui_reactor_when_env_enabled(monkeypatch):
    called = {"ui": 0}

    monkeypatch.setenv("HANDCONTROL_UI_REACTOR", "1")
    monkeypatch.setattr(shell_module, "main", lambda: called.__setitem__("ui", called["ui"] + 1))

    app_module.main()

    assert called["ui"] == 1

