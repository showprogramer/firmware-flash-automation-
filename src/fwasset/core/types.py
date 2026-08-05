from __future__ import annotations

from typing import Any, Literal, TypedDict

FirmwareType = Literal[
    "mainboard",
    "handcontrol_ui",
    "music_bt",
    "music_files",
    "voice",
    "shortcut_key",
    "movement_3d",
    "movement_2d",
    "knob_switch",
    "leg",
    "knee",
    "sonic",
    "health_detection",
    "commercial_mainboard",
    "seat_occupancy",
    "card_reader",
    "leyao_yao",
    "triple_combo",
    "aging",
    "segmented_screen",
]
FlashMode = Literal["auto_usb", "tool_launch", "manual_doc", "disabled"]
UsbFlow = Literal["paired_files", "directory_copy", ""]


class ServiceResult(TypedDict):
    ok: bool
    code: str
    message: str
    payload: dict[str, Any]


class SerialPortInfo(TypedDict):
    device: str
    description: str
    hwid: str


class SerialCommandPayload(TypedDict, total=False):
    device: str
    command: str
    response: str
    raw_response: bytes
    old_baud: int
    new_baud: int
    matched_baud: int
    expected_baud: int
    warning: str


class SerialCommandResult(TypedDict):
    ok: bool
    code: str
    message: str
    payload: SerialCommandPayload


class FlashJobPayload(TypedDict, total=False):
    firmware_type: FirmwareType
    drive: str
    removed_count: int
    copy_ok: bool
    ejected: bool


class FlashJobResult(TypedDict):
    ok: bool
    code: str
    message: str
    payload: FlashJobPayload


class HandcontrolFolder(TypedDict):
    path: str
    rom_file: str
    pkg_file: str
    model: str
    version: str
    label: str


class ToolRegistration(TypedDict):
    name: str
    path: str
    directory: str


class FirmwareAsset(TypedDict):
    series: str
    firmware_type: FirmwareType
    firmware_label: str
    flash_mode: FlashMode
    usb_flow: UsbFlow
    model: str
    version: str
    model_directory_name: str
    model_directory_path: str
    path: str
    directory_name: str
    files: list[str]
    modified_time: float
    tool_name: str
    tool_path: str
    tool_dir: str
    label: str
    # --- L36 新目录结构字段（向后兼容：旧目录留空字符串）---
    category: Literal["common", "custom", ""]  # 通用 / 定制
    platform: str  # 整机平台，如 "双机芯-上3D-下2D"；默认平台留 ""
    scheme_name: str  # 定制方案名，如 "以色列-Royal-Z9"；通用区为 ""
    scheme_path: str  # 定制方案根目录绝对路径；通用区为 ""
