import os
from pathlib import Path
from tkinter import messagebox

from fwasset.ui.handcontrol_panel import HandcontrolPanel as App
from fwasset.ui import shell
from fwasset.ui.shell import UnifiedFlashPlatform

from fwasset.core.diagnostics import build_diagnostic_bundle
from fwasset.core.services.at_command_service import apply_baudrate_command
from fwasset.core.services.flash_service import run_one_click
from fwasset.core.services.music_flash_service import run_music_flash
from fwasset.core.services.scan_service import build_scan_result
from fwasset.core.services.serial_service import connect_port, disconnect_port, scan_serial_ports
from fwasset.core.services.usb_repair_service import diagnose_drive, repair_drive
from fwasset.core.usb_ops import get_usb_drives


def _open_in_explorer(self, folder_path: str, model: str = "", version: str = ""):
    try:
        os.startfile(folder_path)
        logger = self.__dict__.get("log") or self.__dict__.get("_log") or getattr(self, "_log", None) or getattr(self, "log", None)
        if callable(logger):
            logger(f"快速定位已打开: {model} {version} -> {folder_path}")
    except OSError as exc:
        messagebox.showerror("打开失败", f"打开目录失败: {exc}")


def _open_folder_from_listbox(self, event=None):
    selection = list(getattr(self.listbox, "curselection", lambda: ())())
    idx = selection[0] if selection else None
    if idx is None and event is not None and hasattr(self.listbox, "nearest"):
        idx = int(self.listbox.nearest(event.y))
        if hasattr(self.listbox, "selection_clear"):
            self.listbox.selection_clear(0, "end")
        if hasattr(self.listbox, "selection_set"):
            self.listbox.selection_set(idx)
    if idx is None or idx < 0 or idx >= len(getattr(self, "folders", [])):
        return

    if hasattr(self, "current_idx") and hasattr(self.current_idx, "set"):
        self.current_idx.set(idx)
    on_select = getattr(self, "_on_select", None)
    if callable(on_select):
        on_select(None)

    folder = self.folders[idx]
    folder_path = str(folder.get("path", "") or "")
    if not Path(folder_path).exists():
        messagebox.showwarning("目录不存在", f"目录不存在: {folder_path}")
        return
    self._open_in_explorer(folder_path, str(folder.get("model", "")), str(folder.get("version", "")))


App._open_in_explorer = _open_in_explorer
App._open_folder_from_listbox = _open_folder_from_listbox


def main():
    shell.main()


if __name__ == "__main__":
    main()
