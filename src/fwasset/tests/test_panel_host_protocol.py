"""Tests for the PanelHost protocol contract.

The PanelHost protocol is the surface that operation panels depend on. Any host
implementation (WorkbenchPanel in production, mocks in tests) must satisfy it.
Adding/removing a method here is a contract change — keep the test aligned with
host_types.py.
"""

from __future__ import annotations

import inspect

import pytest


class TestPanelHostProtocol:
    def test_panel_host_is_runtime_checkable(self) -> None:
        """PanelHost must be runtime_checkable so isinstance(host, PanelHost) works."""
        from fwasset.ui_qt.operation_panels.host_types import PanelHost

        assert hasattr(PanelHost, "_is_runtime_protocol")
        assert PanelHost._is_runtime_protocol is True

    def test_panel_host_declares_get_global_usb_drive(self) -> None:
        """PanelHost must declare get_global_usb_drive so AutoUsbPanel can rely on it.

        Background: AutoUsbPanel._resolve_drive() calls panel_host.get_global_usb_drive().
        If the method is missing from the protocol, mypy/IDEs can't catch a host
        that omits it. The contract must be visible at the Protocol level.
        """
        from fwasset.ui_qt.operation_panels.host_types import PanelHost

        assert hasattr(PanelHost, "get_global_usb_drive")
        method = getattr(PanelHost, "get_global_usb_drive")
        assert callable(method)

    def test_panel_host_get_global_usb_drive_signature(self) -> None:
        """get_global_usb_drive must be a no-arg method returning str."""
        from fwasset.ui_qt.operation_panels.host_types import PanelHost

        method = getattr(PanelHost, "get_global_usb_drive")
        sig = inspect.signature(method)
        # Protocol-stub methods show as `(self)` only; callable with one arg.
        params = list(sig.parameters.values())
        assert len(params) == 1
        assert params[0].name == "self"

    def test_minimal_host_satisfies_protocol(self) -> None:
        """A host that exposes every PanelHost method must pass isinstance() check."""

        from fwasset.ui_qt.operation_panels.host_types import PanelHost

        class _FakeVar:
            def __init__(self, value: str = "") -> None:
                self._value = value

            def get(self) -> str:
                return self._value

            def set(self, v: str) -> None:
                self._value = v

        class _MinimalHost:
            usb_drive = _FakeVar("E:")

            def _build_usb_selector_row(self, parent): ...
            def _refresh_usb(self) -> None: ...
            def _run_task(self, name, fn, on_done=None) -> None: ...
            def _selected_asset(self): ...
            def _open_current_asset_dir(self) -> None: ...
            def _copy_asset_dir_path(self) -> None: ...
            def _copy_primary_file_path(self) -> None: ...
            def _launch_tool_and_open_asset_dir(self) -> None: ...
            def get_global_usb_drive(self) -> str:
                return "E:"

        # _is_runtime_protocol requires concrete method names — for Protocol,
        # isinstance checks for presence of the named methods.
        assert isinstance(_MinimalHost(), PanelHost)
