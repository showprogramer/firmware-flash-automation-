"""flash_mode 操作面板注册表与基类。"""

from fwasset.ui.operation_panels.base import BaseOperationPanel
from fwasset.ui.operation_panels.host_types import PanelHost
from fwasset.ui.operation_panels.registry import get_panel, register

# 提前加载各面板子模块，确保 @register 装饰器执行
from fwasset.ui.operation_panels import (  # noqa: F401
    auto_usb_panel,
    disabled_panel,
    manual_doc_panel,
    tool_launch_panel,
)

__all__ = ["BaseOperationPanel", "PanelHost", "register", "get_panel"]
