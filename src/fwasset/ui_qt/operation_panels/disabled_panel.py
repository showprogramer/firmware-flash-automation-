from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout

from qfluentwidgets import BodyLabel, PushButton

from fwasset.ui_qt.operation_panels.base import BaseOperationPanel
from fwasset.ui_qt.operation_panels.registry import register
from fwasset.ui_qt.operation_panels.shared_actions import build_handoff_actions


@register("disabled")
class DisabledPanel(BaseOperationPanel):
    """flash_mode 为空或未知时的默认操作面板。"""

    def build(self):
        row = QHBoxLayout()
        row.addWidget(
            BodyLabel(f"{self.asset.get('firmware_label', '该类型')}当前不可自动化操作。", self)
        )
        stub = PushButton("暂不可操作", self)
        stub.setEnabled(False)
        row.addWidget(stub)
        row.addStretch(1)
        self.body.addLayout(row)
        build_handoff_actions(self, self._panel_host)
