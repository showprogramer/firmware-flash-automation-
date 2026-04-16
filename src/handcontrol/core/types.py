from typing import Any, Literal, Optional, TypedDict


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
    copied: bool
    ejected: bool
    excel_result: dict[str, Any]


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


class ExcelWrittenRow(TypedDict):
    model: str
    logo: str
    salesman: str
    language: str
    version: str
    date: str
    attachment: str
    remark: str


ExcelWriteReason = Literal["ok", "locked", "write_failed"]


class ExcelWriteResult(TypedDict):
    ok: bool
    reason: ExcelWriteReason
    tmp_path: str
    error: str
    written_row: Optional[ExcelWrittenRow]


MergeExcelReason = Literal["ok", "locked", "source_missing", "no_rows", "write_failed"]


class MergeExcelResult(TypedDict):
    ok: bool
    reason: MergeExcelReason
    merged_count: int
    skipped_count: int
    source_deleted: bool
    error: str
