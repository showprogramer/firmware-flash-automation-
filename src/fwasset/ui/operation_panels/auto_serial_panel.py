from __future__ import annotations

import customtkinter as ctk

from fwasset.ui.operation_panels.base import BaseOperationPanel
from fwasset.ui.operation_panels.registry import register
from fwasset.ui.serial_control import SerialControl


@register("auto_serial")
class AutoSerialPanel(BaseOperationPanel):
    """auto_serial 类型操作面板：串口控制。"""

    def build(self):
        serial_control = SerialControl(self, log_fn=self._log)
        serial_control.pack(fill="both", expand=True)
        if getattr(self._panel_host, "_polling_active", False):
            serial_control.activate()
        # 将 serial_control 引用存到 panel_host 上，以便 activate/deactivate 生命周期管理
        self._panel_host.serial_control = serial_control