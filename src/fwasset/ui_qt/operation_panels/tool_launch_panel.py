from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QMessageBox

from qfluentwidgets import BodyLabel, CaptionLabel, PrimaryPushButton, StrongBodyLabel

from fwasset.core.firmware_catalog import load_firmware_catalog
from fwasset.core.tool_discovery import discover_tool_path, launch_tool
from fwasset.ui_qt.operation_panels.base import BaseOperationPanel
from fwasset.ui_qt.operation_panels.registry import register


@register("tool_launch")
class ToolLaunchPanel(BaseOperationPanel):
    """tool_launch 类型操作面板：展示并启动外部烧录工具。"""

    def build(self):
        fw_type = str(self.asset.get("firmware_type", ""))
        tool_name = str(self.asset.get("tool_name", "")) or "烧录工具"
        tool_dir = str(self.asset.get("tool_dir", ""))

        catalog = load_firmware_catalog()
        tool_path = ""
        dir_keywords: list[str] = []
        for item in catalog.get("firmware_types", []):
            if item.get("key") == fw_type:
                tool_path = item.get("tool_path", "")
                tool_dir = item.get("tool_dir", tool_dir)
                dir_keywords = item.get("dir_keywords", [])
                break

        if not tool_path:
            tool_path = discover_tool_path(
                fw_type,
                tool_name,
                tool_dir=tool_dir,
                dir_keywords=dir_keywords,
            )

        self._current_tool_path = tool_path

        row = QHBoxLayout()
        row.addWidget(StrongBodyLabel(tool_name, self))

        self.launch_btn = PrimaryPushButton("打开烧录工具", self)
        self.launch_btn.setEnabled(bool(tool_path))
        self.launch_btn.clicked.connect(self._launch_current_tool)
        row.addWidget(self.launch_btn)

        self.tool_path_label = CaptionLabel(tool_path if tool_path else "未配置工具路径", self)
        row.addWidget(self.tool_path_label)
        row.addStretch(1)
        self.body.addLayout(row)

        if not tool_path:
            self.body.addWidget(
                BodyLabel("提示: 将烧录工具放在程序同目录的 tools 文件夹中，程序会自动发现。", self)
            )

    def _launch_current_tool(self):
        """启动当前选中的工具。"""
        tool_path = getattr(self, "_current_tool_path", "")
        if not tool_path:
            QMessageBox.warning(
                self,
                "提示",
                "工具路径未配置\n\n请将烧录工具放在程序同目录的 tools 文件夹中，或手动配置工具路径。",
            )
            return

        result = launch_tool(tool_path)
        if result.get("ok"):
            self._log(f"✓ {result.get('message')}")
        else:
            QMessageBox.critical(self, "启动失败", result.get("message", ""))
            self._log(f"✗ {result.get('message')}")

    def _launch_tool_and_open_asset_dir(self):
        self._launch_current_tool()
        self._panel_host._open_current_asset_dir()
