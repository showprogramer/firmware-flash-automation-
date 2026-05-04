from typing import Any, Literal, TypedDict


FirmwareType = Literal[
    "mainboard",
    "handcontrol_ui",
    "music_bt",
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
FlashMode = Literal["auto_usb", "auto_serial", "tool_launch", "manual_doc", "disabled"]


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


class FirmwareAsset(TypedDict):
    firmware_type: FirmwareType
    firmware_label: str
    flash_mode: FlashMode
    model: str
    version: str
    path: str
    directory_name: str
    files: list[str]
    modified_time: float
    tool_name: str
    tool_path: str
    label: str
