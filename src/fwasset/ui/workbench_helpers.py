"""工作台纯函数助手（CTk 与 Qt 双壳共用，禁止引入任何 UI 框架依赖）。"""
from __future__ import annotations

MODEL_CHIP_LIMIT = 4


def model_chip_values(
    models: list[str], selected: str = "", limit: int = MODEL_CHIP_LIMIT
) -> tuple[list[str], list[str]]:
    """Split models into visible chips and overflow while keeping selected visible."""
    clean_models = [model for model in models if model]
    if len(clean_models) <= limit:
        return clean_models, []

    chips = clean_models[:limit]
    overflow = clean_models[limit:]
    if selected and selected in clean_models and selected not in chips:
        displaced = chips[-1]
        chips[-1] = selected
        overflow = [item for item in clean_models if item not in chips]
        if displaced not in overflow:
            overflow.insert(0, displaced)
    return chips, overflow


def flash_mode_label(mode: str) -> str:
    labels = {
        "auto_usb": "USB刷机",
        "tool_launch": "工具烧录",
        "manual_doc": "说明操作",
        "disabled": "不可烧录",
    }
    return labels.get(mode, mode or "-")
