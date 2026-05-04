from __future__ import annotations

import customtkinter as ctk

from handcontrol.ui.design_tokens import BG_APP
from handcontrol.ui.handcontrol_panel import HandcontrolPanel
from handcontrol.ui.music_panel import MusicPanel
from handcontrol.ui.shared_widgets import apply_treeview_modern_style


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

        self.hand_panel = HandcontrolPanel(self.container, self.switch_view)
        self.hand_panel.grid(row=0, column=0, sticky="nsew")
        self.music_panel = None

        self.current_panel = None
        self.switch_view("handcontrol")

    def switch_view(self, mode: str):
        if self.current_panel:
            if hasattr(self.current_panel, "deactivate"):
                self.current_panel.deactivate()

        if mode == "handcontrol":
            self.hand_panel.tkraise()
            self.current_panel = self.hand_panel
        else:
            if self.music_panel is None:
                self.music_panel = MusicPanel(self.container, self.switch_view)
                self.music_panel.grid(row=0, column=0, sticky="nsew")
            self.music_panel.tkraise()
            self.current_panel = self.music_panel

        self.hand_panel.sync_mode_switch(mode)
        if self.music_panel is not None:
            self.music_panel.sync_mode_switch(mode)

        if hasattr(self.current_panel, "activate"):
            self.current_panel.activate()


def main():
    ctk.set_appearance_mode("System")
    app = UnifiedFlashPlatform()
    app.mainloop()


if __name__ == "__main__":
    main()
