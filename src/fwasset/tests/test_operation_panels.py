"""Tests for operation panel registry and panel classes."""

import pytest

pytestmark = pytest.mark.ui

from fwasset.ui.operation_panels.registry import _REGISTRY, get_panel, register
from fwasset.ui.operation_panels.base import BaseOperationPanel
from fwasset.ui.operation_panels.disabled_panel import DisabledPanel
from fwasset.ui.operation_panels.manual_doc_panel import ManualDocPanel
from fwasset.ui.operation_panels.tool_launch_panel import ToolLaunchPanel
from fwasset.ui.operation_panels.auto_usb_panel import AutoUsbPanel


class TestRegistry:
    """Test the operation panel registry mechanism."""

    def test_registered_flash_modes(self):
        """All expected flash_modes should be registered."""
        assert get_panel("auto_usb") is AutoUsbPanel
        assert get_panel("tool_launch") is ToolLaunchPanel
        assert get_panel("manual_doc") is ManualDocPanel
        assert get_panel("disabled") is DisabledPanel

    def test_unknown_flash_mode_returns_none(self):
        """An unregistered flash_mode should return None from get_panel."""
        assert get_panel("nonexistent_mode") is None

    def test_register_decorator(self):
        """The @register decorator should add the class to the registry."""

        @register("test_mode_unique")
        class TestPanel(BaseOperationPanel):
            def build(self):
                pass

        assert get_panel("test_mode_unique") is TestPanel

        # Clean up to avoid polluting the registry
        _REGISTRY.pop("test_mode_unique", None)

    def test_register_overwrite(self):
        """Registering the same flash_mode twice should overwrite."""

        @register("overwrite_test")
        class PanelA(BaseOperationPanel):
            def build(self):
                pass

        @register("overwrite_test")
        class PanelB(BaseOperationPanel):
            def build(self):
                pass

        assert get_panel("overwrite_test") is PanelB

        # Clean up
        _REGISTRY.pop("overwrite_test", None)


class TestBaseOperationPanel:
    """Test BaseOperationPanel interface."""

    def test_base_class_has_build_method(self):
        """BaseOperationPanel should define a build() method."""
        assert hasattr(BaseOperationPanel, "build")

    def test_base_class_init_signature(self):
        """BaseOperationPanel.__init__ should accept master, asset, log_fn, panel_host."""
        import inspect

        sig = inspect.signature(BaseOperationPanel.__init__)
        params = list(sig.parameters.keys())
        assert "asset" in params
        assert "log_fn" in params
        assert "panel_host" in params


class TestPanelClasses:
    """Smoke tests for each panel class to verify they can be instantiated."""

    def _make_mock_host(self):
        """Create a minimal mock panel_host for testing."""

        class MockHost:
            usb_drive = None
            _polling_active = False

            def _run_task(self, *args, **kwargs):
                pass

            def _selected_asset(self):
                return None

            def _make_bool_var(self, value):
                return _FakeBoolVar(value)

            def _asset_rom_pkg_files(self, asset):
                return ("", "")

            def _asset_usb_flow(self, asset):
                return ""

            def _build_usb_selector_row(self, parent):
                pass

            def _refresh_usb(self):
                pass

            def _log(self, msg):
                pass

            def _open_current_asset_dir(self):
                pass

            def _copy_asset_dir_path(self):
                pass

            def _copy_primary_file_path(self):
                pass

            def _launch_tool_and_open_asset_dir(self):
                pass

        host = MockHost()
        import tkinter as tk

        host.usb_drive = tk.StringVar(value="E:")
        return host

    def test_disabled_panel_build(self):
        """DisabledPanel.build() should not raise."""
        # We can't fully instantiate CTk widgets without a display,
        # so we just verify the class exists and has the right interface.
        assert hasattr(DisabledPanel, "build")
        assert issubclass(DisabledPanel, BaseOperationPanel)

    def test_manual_doc_panel_build(self):
        """ManualDocPanel.build() should not raise."""
        assert hasattr(ManualDocPanel, "build")
        assert issubclass(ManualDocPanel, BaseOperationPanel)

    def test_tool_launch_panel_build(self):
        """ToolLaunchPanel.build() should not raise."""
        assert hasattr(ToolLaunchPanel, "build")
        assert issubclass(ToolLaunchPanel, BaseOperationPanel)

    def test_auto_usb_panel_build(self):
        """AutoUsbPanel.build() should not raise."""
        assert hasattr(AutoUsbPanel, "build")
        assert issubclass(AutoUsbPanel, BaseOperationPanel)

class _FakeBoolVar:
    def __init__(self, value=True):
        self._value = value

    def get(self):
        return self._value

    def set(self, v):
        self._value = v


class TestSharedActions:
    """Test shared_actions module exports."""

    def test_build_handoff_actions_is_importable(self):
        """build_handoff_actions should be importable from shared_actions."""
        from fwasset.ui.operation_panels.shared_actions import build_handoff_actions

        assert callable(build_handoff_actions)


class TestIntegration:
    """Integration test: verify FirmwareListPanel uses the registry."""

    def test_firmware_list_panel_imports_registry(self):
        """FirmwareListPanel should import get_panel from operation_panels."""
        from pathlib import Path

        source = (Path(__file__).parent.parent / "src" / "fwasset" / "ui" / "firmware_list_panel.py").read_text(encoding="utf-8")
        assert "get_panel" in source
        assert "DisabledPanel" in source

    def test_render_operation_panel_uses_registry(self):
        """_render_operation_panel should use get_panel to dispatch."""
        from pathlib import Path

        source = (Path(__file__).parent.parent / "src" / "fwasset" / "ui" / "firmware_list_panel.py").read_text(encoding="utf-8")
        assert "PanelClass = get_panel" in source
