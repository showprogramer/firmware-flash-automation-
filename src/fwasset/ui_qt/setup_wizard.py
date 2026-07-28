"""首次配置向导。

冻结 exe 首次启动时，若 AppData 无配置文件，弹出此对话框引导用户
选择固件根目录（必填）和工具根目录（可选）。用户也可跳过，
待进入主界面后从设置页完成配置。
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import BodyLabel, PrimaryPushButton, PushButton, SubtitleLabel


class SetupWizard(QDialog):
    """首次配置向导对话框。

    完成后调用 :meth:`write_config` 将路径写入
    ``settings.CONFIG_PATH``（AppData 位置）。
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("初始配置")
        self.setMinimumWidth(540)
        self._root_edit: QLineEdit
        self._tool_edit: QLineEdit
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(28, 24, 28, 24)

        layout.addWidget(SubtitleLabel("初始配置", self))

        desc = BodyLabel(
            "欢迎使用固件资产管理工具。\n"
            "请选择固件根目录（存放各型号程序文件夹的目录），配置完成后即可开始使用。\n"
            "工具根目录为可选项，留空不影响主要功能。",
            self,
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self._root_edit, root_row = self._make_path_row("固件根目录（必填）")
        layout.addWidget(root_row)

        self._tool_edit, tool_row = self._make_path_row("工具根目录（可选）")
        layout.addWidget(tool_row)

        layout.addSpacing(8)

        # 按钮行
        btn_row = QHBoxLayout()
        skip_btn = PushButton("跳过")
        skip_btn.setFixedWidth(90)
        skip_btn.clicked.connect(self.reject)

        ok_btn = PrimaryPushButton("完成配置")
        ok_btn.setFixedWidth(110)
        ok_btn.clicked.connect(self._on_accept)

        btn_row.addWidget(skip_btn)
        btn_row.addStretch()
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

    def _make_path_row(self, label_text: str) -> tuple[QLineEdit, QWidget]:
        container = QWidget(self)
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)
        v.addWidget(BodyLabel(label_text, container))

        row = QHBoxLayout()
        edit = QLineEdit(container)
        edit.setPlaceholderText("点击「浏览」选择目录…")
        row.addWidget(edit)

        browse_btn = PushButton("浏览", container)
        browse_btn.setFixedWidth(70)
        browse_btn.clicked.connect(lambda: self._browse(edit))
        row.addWidget(browse_btn)

        v.addLayout(row)
        return edit, container

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _browse(self, edit: QLineEdit) -> None:
        start = edit.text().strip() or str(Path.home())
        path = QFileDialog.getExistingDirectory(self, "选择目录", start)
        if path:
            edit.setText(path)

    def _on_accept(self) -> None:
        self.write_config()
        self.accept()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def root_dir(self) -> str:
        return self._root_edit.text().strip()

    def tool_root(self) -> str:
        return self._tool_edit.text().strip()

    def write_config(self) -> None:
        """将向导填写的路径写入 ``settings.CONFIG_PATH``。"""
        from fwasset.core.settings import CONFIG_PATH

        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        root = self.root_dir().replace("\\", "/")
        tool = self.tool_root().replace("\\", "/")
        content = (
            "[paths]\n"
            f'root_dir = "{root}"\n'
            f'tool_root = "{tool}"\n'
        )
        CONFIG_PATH.write_text(content, encoding="utf-8")
