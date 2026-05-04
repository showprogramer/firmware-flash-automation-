from __future__ import annotations

import customtkinter as ctk

from fwasset.ui.design_tokens import BG_APP
from fwasset.ui.firmware_list_panel import FirmwareListPanel
from fwasset.ui.shared_widgets import apply_treeview_modern_style


class UnifiedFlashPlatform(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("按摩椅程序资产管理系统 | Massage Chair Firmware Asset Manager")
        self.geometry("1400x850")
        self.minsize(1200, 750)
        self.configure(fg_color=BG_APP)

        apply_treeview_modern_style()

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.asset_panel = FirmwareListPanel(self.container)
        self.asset_panel.grid(row=0, column=0, sticky="nsew")
        self.asset_panel.activate()


def main():
    ctk.set_appearance_mode("System")
    app = UnifiedFlashPlatform()
    app.mainloop()


if __name__ == "__main__":
    main()
