from typing import Literal, Optional, TypedDict


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
