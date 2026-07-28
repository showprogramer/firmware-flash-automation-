from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QHBoxLayout, QMessageBox

from qfluentwidgets import BodyLabel, CheckBox, PrimaryPushButton

from fwasset.core.asset_helpers import asset_rom_pkg_files, asset_usb_flow
from fwasset.core.services.flash_service import run_one_click
from fwasset.core.services.music_flash_service import run_music_flash
from fwasset.ui_qt.operation_panels.base import BaseOperationPanel
from fwasset.ui_qt.operation_panels.registry import register


@register("auto_usb")
class AutoUsbPanel(BaseOperationPanel):
    """auto_usb 类型操作面板：U 盘刷机流程。"""

    def build(self):
        usb_flow = asset_usb_flow(self.asset)
        if usb_flow == "directory_copy":
            self._build_directory_copy_usb_ops()
            return

        rom_file, pkg_file = asset_rom_pkg_files(self.asset)
        if usb_flow == "paired_files" and rom_file and pkg_file:
            btn = PrimaryPushButton("一键烧录", self)
            btn.clicked.connect(self._one_click_handcontrol)
            self.body.addWidget(btn)
            return

        if usb_flow == "paired_files":
            missing = []
            if not rom_file:
                missing.append("ROM")
            if not pkg_file:
                missing.append("PKG")
            self.body.addWidget(
                BodyLabel(f"当前手控资源缺少 {' / '.join(missing)} 文件，无法执行手控刷机。", self)
            )
            return

        self.body.addWidget(BodyLabel("当前 USB 流程未配置，无法确定刷写方式。", self))

    def _build_directory_copy_usb_ops(self):
        row = QHBoxLayout()
        self.format_first = CheckBox("格式化", self)
        self.format_first.setChecked(True)
        row.addWidget(self.format_first)
        self.eject_after = CheckBox("完成后弹出", self)
        self.eject_after.setChecked(True)
        row.addWidget(self.eject_after)

        run_btn = PrimaryPushButton("执行目录刷机流程", self)
        run_btn.clicked.connect(self._run_directory_flash)
        row.addWidget(run_btn)
        row.addWidget(BodyLabel("该资源按目录复制到 U 盘，仅适用于音乐文件资源。", self))
        row.addStretch(1)
        self.body.addLayout(row)

    # -- USB 操作方法 --
    def _resolve_drive(self) -> str:
        """取全局选择的 U 盘盘符；为空则提示并返回空串。"""
        drive = (self._panel_host.get_global_usb_drive() or "").strip()
        if not drive:
            QMessageBox.warning(self, "未选择 U 盘", "请先选择目标 U 盘后再烧录。")
        return drive

    def _one_click_handcontrol(self):
        asset = self._panel_host._selected_asset()
        drive = self._resolve_drive()
        if not asset or not drive:
            return
        rom_file, pkg_file = asset_rom_pkg_files(asset)
        if not rom_file or not pkg_file:
            return

        # 格式化确认弹窗（防误操作）
        reply = QMessageBox.question(
            self,
            "确认格式化",
            f"将格式化 U 盘 {drive}（FAT32），所有现有内容将被清除。\n\n确定继续吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        rom_path = str(Path(asset["path"]) / rom_file)
        pkg_path = str(Path(asset["path"]) / pkg_file)
        self._panel_host._run_task(
            "一键执行",
            lambda log_fn: run_one_click(
                drive, asset["model"], asset["version"], rom_path, pkg_path, log_fn=log_fn
            ),
        )

    def _run_directory_flash(self):
        asset = self._panel_host._selected_asset()
        drive = self._resolve_drive()
        if not asset or not drive:
            return
        format_first = self.format_first.isChecked()
        eject_after = self.eject_after.isChecked()
        self._panel_host._run_task(
            "目录刷机",
            lambda log_fn: run_music_flash(
                asset["path"], drive, format_first=format_first, eject_after=eject_after, log_fn=log_fn
            ),
            lambda result: self._log(f"结果: {result.get('message')}"),
        )
