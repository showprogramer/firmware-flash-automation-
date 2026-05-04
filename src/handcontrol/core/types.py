from typing import Any, Literal, TypedDict


FirmwareType = Literal["handcontrol_ui", "music_bt"]


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
