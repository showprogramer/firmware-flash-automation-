from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CaptionLabel, PrimaryPushButton, SubtitleLabel

from fwasset.ui_qt.design_tokens import SPACE_LG, SPACE_MD, SPACE_SM, SPACE_XS


class SettingsInterface(QWidget):
    """应用级设置页：当前只承载程序文件夹配置。"""

    configure_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("settingsInterface")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_LG, SPACE_LG, SPACE_LG, SPACE_LG)
        layout.setSpacing(SPACE_MD)

        layout.addWidget(SubtitleLabel("设置", self))
        layout.addWidget(CaptionLabel("程序文件夹与烧录工具路径", self))

        card = QFrame(self)
        card.setMaximumWidth(760)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(SPACE_LG, SPACE_MD, SPACE_LG, SPACE_MD)
        card_layout.setSpacing(SPACE_SM)
        card_layout.addWidget(BodyLabel("程序文件夹", card))
        card_layout.addWidget(
            CaptionLabel(
                "配置完成后，软件会读取所选程序文件夹并更新程序列表。",
                card,
            )
        )

        self.root_path_label = CaptionLabel("未配置", card)
        self.tool_path_label = CaptionLabel("未配置", card)
        card_layout.addLayout(self._path_row("固件根目录", self.root_path_label, card))
        card_layout.addLayout(self._path_row("工具根目录", self.tool_path_label, card))

        button_row = QHBoxLayout()
        self.configure_button = PrimaryPushButton("更改…", card)
        self.configure_button.clicked.connect(self.configure_requested.emit)
        button_row.addWidget(self.configure_button)
        button_row.addStretch(1)
        card_layout.addLayout(button_row)

        layout.addWidget(card, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)

    @staticmethod
    def _path_row(label_text: str, value_label: CaptionLabel, parent: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(SPACE_XS)
        row.addWidget(BodyLabel(label_text, parent))
        row.addStretch(1)
        value_label.setWordWrap(True)
        row.addWidget(value_label, stretch=2)
        return row

    def set_paths(self, root_dir: str, tool_root: str) -> None:
        """刷新当前配置路径的显示。"""
        self.root_path_label.setText(root_dir.strip() or "未配置")
        self.tool_path_label.setText(tool_root.strip() or "未配置")
