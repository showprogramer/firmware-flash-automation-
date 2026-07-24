from __future__ import annotations

import customtkinter as ctk

from fwasset.ui.design_tokens import BG_WINDOW
from fwasset.ui.workbench_panel import WorkbenchPanel


DEFAULT_WINDOW_WIDTH = 1400
DEFAULT_WINDOW_HEIGHT = 850
MIN_WINDOW_WIDTH = 1000
MIN_WINDOW_HEIGHT = 680
SCREEN_MARGIN = 72


class UnifiedFlashPlatform(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("按摩椅程序资产管理系统 | Massage Chair Firmware Asset Manager")
        self._apply_startup_geometry()
        self.configure(fg_color=BG_WINDOW)

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.asset_panel = WorkbenchPanel(self.container)
        self.asset_panel.grid(row=0, column=0, sticky="nsew")
        self.asset_panel.activate()

    def _apply_startup_geometry(self):
        self.update_idletasks()
        screen_width = int(self.winfo_screenwidth())
        screen_height = int(self.winfo_screenheight())

        available_width = max(640, screen_width - SCREEN_MARGIN)
        available_height = max(480, screen_height - SCREEN_MARGIN)
        width = min(DEFAULT_WINDOW_WIDTH, available_width)
        height = min(DEFAULT_WINDOW_HEIGHT, available_height)
        min_width = min(MIN_WINDOW_WIDTH, width)
        min_height = min(MIN_WINDOW_HEIGHT, height)

        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        self.minsize(min_width, min_height)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.after(50, self._ensure_visible_window)

    def _ensure_visible_window(self):
        self.update_idletasks()
        screen_width = int(self.winfo_screenwidth())
        screen_height = int(self.winfo_screenheight())
        width = int(self.winfo_width())
        height = int(self.winfo_height())
        x = int(self.winfo_x())
        y = int(self.winfo_y())

        if x < 0 or y < 0 or x + width > screen_width or y + height > screen_height:
            width = min(width, max(640, screen_width - SCREEN_MARGIN))
            height = min(height, max(480, screen_height - SCREEN_MARGIN))
            x = max(0, (screen_width - width) // 2)
            y = max(0, (screen_height - height) // 2)
            self.geometry(f"{width}x{height}+{x}+{y}")


def main():
    ctk.set_appearance_mode("System")
    app = UnifiedFlashPlatform()
    app.mainloop()


if __name__ == "__main__":
    main()
