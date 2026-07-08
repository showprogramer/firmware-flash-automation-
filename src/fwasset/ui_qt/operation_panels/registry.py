from __future__ import annotations

# Qt 面板专用注册表。与 ui/operation_panels/registry.py 结构相同但必须是
# 独立的模块级字典：两套壳的同名 flash_mode 面板类不能互相覆盖。
_REGISTRY: dict[str, type] = {}


def register(flash_mode: str):
    """将 Panel 类注册到指定 flash_mode 的装饰器。"""

    def decorator(cls):
        _REGISTRY[flash_mode] = cls
        return cls

    return decorator


def get_panel(flash_mode: str):
    """按 flash_mode 查找注册的 Panel 类，未找到返回 None。"""
    return _REGISTRY.get(flash_mode)
