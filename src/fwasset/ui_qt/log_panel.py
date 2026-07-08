from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QPlainTextEdit, QVBoxLayout, QWidget

from qfluentwidgets import BodyLabel, PushButton


class LogPanel(QWidget):
    """可折叠运行日志（对齐 ui/panels/log_panel.py 行为：默认折叠）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._collapsed = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        header.addWidget(BodyLabel("运行日志", self))
        header.addStretch(1)
        self.toggle_btn = PushButton("展开日志", self)
        self.toggle_btn.clicked.connect(self.toggle)
        header.addWidget(self.toggle_btn)
        layout.addLayout(header)

        self.log_text = QPlainTextEdit(self)
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumBlockCount(2000)
        self.log_text.setFixedHeight(140)
        layout.addWidget(self.log_text)
        self._apply_collapsed_state()

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self._apply_collapsed_state()

    def toggle(self) -> None:
        self.set_collapsed(not self._collapsed)

    def write(self, message: str) -> None:
        self.log_text.appendPlainText((message or "").rstrip("\n"))

    def _apply_collapsed_state(self) -> None:
        self.log_text.setVisible(not self._collapsed)
        self.toggle_btn.setText("展开日志" if self._collapsed else "折叠日志")
