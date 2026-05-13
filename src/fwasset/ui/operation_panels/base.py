from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

from fwasset.core.types import FirmwareAsset

if TYPE_CHECKING:
    from fwasset.ui.operation_panels.host_types import PanelHost


class BaseOperationPanel(ctk.CTkFrame):
    """操作面板基类，所有 flash_mode 操作面板继承此类。"""

    def __init__(self, master, *, asset: FirmwareAsset, log_fn, panel_host: PanelHost, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.asset = asset
        self._log = log_fn
        self._panel_host: PanelHost = panel_host

    def build(self):
        """子类重写此方法构建 UI。"""