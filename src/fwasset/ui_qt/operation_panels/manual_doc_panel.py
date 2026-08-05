from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QMessageBox
from qfluentwidgets import BodyLabel, PushButton

from fwasset.ui_qt.operation_panels.base import BaseOperationPanel
from fwasset.ui_qt.operation_panels.registry import register
from fwasset.ui_qt.operation_panels.shared_actions import build_handoff_actions


@register("manual_doc")
class ManualDocPanel(BaseOperationPanel):
    """manual_doc 类型操作面板：显示说明提示。"""

    def build(self):
        row = QHBoxLayout()
        row.addWidget(BodyLabel("该类型需要按说明人工处理。", self))
        doc_btn = PushButton("查看说明", self)
        doc_btn.clicked.connect(lambda: self._show_manual_doc(self.asset))
        row.addWidget(doc_btn)
        row.addStretch(1)
        self.body.addLayout(row)
        build_handoff_actions(self, self._panel_host)

    def _show_manual_doc(self, asset):
        message = (
            f"固件类型: {asset.get('firmware_label', '-')}\n"
            f"型号: {asset.get('model', '-')}\n"
            f"版本: {asset.get('version', '-')}\n"
            f"目录: {asset.get('path', '-')}\n\n"
            "当前类型暂未接入自动烧录工具，请按对应工艺说明处理。"
        )
        QMessageBox.information(self, "操作说明", message)
