from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QHBoxLayout

from qfluentwidgets import PushButton

if TYPE_CHECKING:
    from fwasset.ui_qt.operation_panels.base import BaseOperationPanel
    from fwasset.ui_qt.operation_panels.host_types import PanelHost


def build_handoff_actions(
    panel: "BaseOperationPanel", panel_host: "PanelHost", include_tool_combo: bool = False
) -> None:
    """通用交接操作按钮组（打开目录、复制路径等）。

    Qt 操作区高度有限，按钮横排排列。
    """
    row = QHBoxLayout()
    actions = [
        ("打开程序目录", panel_host._open_current_asset_dir),
        ("复制目录路径", panel_host._copy_asset_dir_path),
        ("复制主文件路径", panel_host._copy_primary_file_path),
    ]
    if include_tool_combo:
        actions.append(("打开工具 + 打开程序目录", panel_host._launch_tool_and_open_asset_dir))
    for title, command in actions:
        btn = PushButton(title, panel)
        btn.clicked.connect(command)
        row.addWidget(btn)
    row.addStretch(1)
    panel.body.addLayout(row)
