from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import (
    CaptionLabel,
    FluentIcon,
    PushSettingCard,
    SettingCardGroup,
    SubtitleLabel,
)

from fwasset.ui_qt.design_tokens import SETTINGS_CARD_MAX_WIDTH, SPACE_LG, SPACE_MD

_UNSET_TEXT = "未配置"
# 低于此宽度卡片内容会互相挤压，不再跟随窗口继续收窄。
_CARD_MIN_WIDTH = 320
# contentLabel 宽度小于此值时视为「布局尚未完成」，暂不省略。
_ELIDE_MIN_WIDTH = 40


class SettingsInterface(QWidget):
    """应用级设置页：当前只承载程序文件夹配置。"""

    configure_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("settingsInterface")
        # 保留完整路径原文：省略只影响显示，重新排版时需按新宽度重算。
        self._root_dir = ""
        self._tool_root = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_LG, SPACE_LG, SPACE_LG, SPACE_LG)
        layout.setSpacing(SPACE_MD)

        layout.addWidget(SubtitleLabel("设置", self))
        layout.addWidget(CaptionLabel("程序文件夹与烧录工具路径", self))

        # ExpandLayout 按控件自身宽度排版：只设 maximumWidth 而不给宽度，
        # 配合 AlignLeft 会塌缩到最小宽度（标题被截断成「固」「工」）。
        # 故显式设定宽度，并在 resizeEvent 中跟随窗口收窄。
        self.card_group = SettingCardGroup("程序文件夹", self)
        group = self.card_group
        group.setFixedWidth(SETTINGS_CARD_MAX_WIDTH)

        self.root_card = PushSettingCard(
            "更改",
            FluentIcon.FOLDER,
            "固件根目录",
            _UNSET_TEXT,
            group,
        )
        self.tool_card = PushSettingCard(
            "更改",
            FluentIcon.DEVELOPER_TOOLS,
            "工具根目录",
            _UNSET_TEXT,
            group,
        )
        # 两张卡共用同一个配置向导：向导内可分别修改两个路径。
        self.root_card.clicked.connect(self.configure_requested.emit)
        self.tool_card.clicked.connect(self.configure_requested.emit)

        group.addSettingCard(self.root_card)
        group.addSettingCard(self.tool_card)

        layout.addWidget(group, alignment=Qt.AlignmentFlag.AlignLeft)
        hint = CaptionLabel("配置完成后，软件会读取所选程序文件夹并更新程序列表。", self)
        layout.addWidget(hint, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)

    def set_paths(self, root_dir: str, tool_root: str) -> None:
        """刷新当前配置路径的显示。"""
        self._root_dir = root_dir.strip()
        self._tool_root = tool_root.strip()
        self._elide_paths()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """窗口收窄时同步卡片宽度，并按新宽度重新省略路径。"""
        super().resizeEvent(event)
        available = max(self.width() - SPACE_LG * 2, _CARD_MIN_WIDTH)
        self.card_group.setFixedWidth(min(SETTINGS_CARD_MAX_WIDTH, available))
        self._elide_paths()

    def _elide_paths(self) -> None:
        """按 contentLabel 的当前可用宽度重新省略两张卡的路径。

        `PushSettingCard` 自身不省略过长内容，且当前 QFluentWidgets 版本
        无 `ElidedLabel`，故手动截断。
        """
        self._apply_path(self.root_card, self._root_dir)
        self._apply_path(self.tool_card, self._tool_root)

    @staticmethod
    def _apply_path(card: PushSettingCard, value: str) -> None:
        """更新单张卡的路径显示；完整路径始终可通过 tooltip 查看。"""
        if not value:
            card.setContent(_UNSET_TEXT)
            card.setToolTip("")
            return

        # 仅在控件已完成布局、且确实放不下时才省略。
        # 未显示的控件 contentLabel 宽度是默认值（约 100px），据此省略会把
        # 「D:/firmware」这类短路径误截成「D:/…are」。
        label = card.contentLabel
        width = label.width()
        shown = value
        if (
            card.isVisible()
            and width > _ELIDE_MIN_WIDTH
            and label.fontMetrics().horizontalAdvance(value) > width
        ):
            shown = label.fontMetrics().elidedText(
                value, Qt.TextElideMode.ElideMiddle, width
            )
        card.setContent(shown)
        # tooltip 始终是完整路径，截断后仍可查看
        card.setToolTip(value)
