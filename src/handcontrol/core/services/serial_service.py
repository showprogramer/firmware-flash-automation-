from __future__ import annotations

import time
from typing import Any

from handcontrol.core.types import SerialCommandResult, SerialPortInfo


def _import_serial_modules():
    try:
        import serial  # type: ignore
        import serial.tools.list_ports as list_ports  # type: ignore

        return serial, list_ports, ""
    except ModuleNotFoundError as exc:
        return None, None, f"pyserial 未安装: {exc}"


def _ensure_crlf(command: str) -> str:
    text = str(command or "")
    if text.endswith("\r\n"):
        return text
    return text.rstrip("\r\n") + "\r\n"


def scan_serial_ports(log_fn=print) -> dict:
    serial, list_ports, import_error = _import_serial_modules()
    if not serial or not list_ports:
        return {
            "ok": False,
            "code": "serial_missing",
            "message": import_error or "pyserial 未安装",
            "payload": {"ports": []},
        }

    try:
        ports: list[SerialPortInfo] = []
        for item in list_ports.comports():
            ports.append(
                {
                    "device": str(getattr(item, "device", "")),
                    "description": str(getattr(item, "description", "")),
                    "hwid": str(getattr(item, "hwid", "")),
                }
            )
        return {
            "ok": True,
            "code": "ok",
            "message": f"已扫描到 {len(ports)} 个串口",
            "payload": {"ports": ports},
        }
    except Exception as exc:
        log_fn(f"串口扫描失败: {exc}")
        return {
            "ok": False,
            "code": "scan_failed",
            "message": str(exc),
            "payload": {"ports": []},
        }


def connect_port(device: str, baudrate: int = 115200, timeout_sec: float = 1.0, log_fn=print) -> dict:
    serial, _, import_error = _import_serial_modules()
    if not serial:
        return {
            "ok": False,
            "code": "serial_missing",
            "message": import_error or "pyserial 未安装",
            "payload": {},
        }

    try:
        connection = serial.Serial(device, int(baudrate), timeout=float(timeout_sec))
        return {
            "ok": True,
            "code": "ok",
            "message": "串口连接成功",
            "payload": {
                "connection": connection,
                "device": str(device),
                "baudrate": int(baudrate),
            },
        }
    except Exception as exc:
        log_fn(f"串口连接失败: {exc}")
        return {
            "ok": False,
            "code": "connect_failed",
            "message": str(exc),
            "payload": {"device": str(device), "baudrate": int(baudrate)},
        }


def disconnect_port(connection: Any, log_fn=print) -> dict:
    if connection is None:
        return {
            "ok": True,
            "code": "ok",
            "message": "连接已释放",
            "payload": {},
        }

    try:
        if getattr(connection, "is_open", False):
            connection.close()
        return {
            "ok": True,
            "code": "ok",
            "message": "串口已断开",
            "payload": {},
        }
    except Exception as exc:
        log_fn(f"串口断开失败: {exc}")
        return {
            "ok": False,
            "code": "disconnect_failed",
            "message": str(exc),
            "payload": {},
        }


def send_serial_command(
    connection: Any,
    command: str,
    *,
    wait_sec: float = 0.8,
    encoding: str = "gbk",
    clear_input: bool = True,
    log_fn=print,
) -> SerialCommandResult:
    if connection is None or not getattr(connection, "is_open", False):
        return {
            "ok": False,
            "code": "not_connected",
            "message": "串口未连接",
            "payload": {"command": str(command or ""), "response": ""},
        }

    wire_command = _ensure_crlf(command)
    try:
        if clear_input and hasattr(connection, "reset_input_buffer"):
            connection.reset_input_buffer()
        connection.write(wire_command.encode("ascii", errors="ignore"))
        if hasattr(connection, "flush"):
            connection.flush()
        time.sleep(max(0.0, float(wait_sec)))
        raw = connection.read_all() if hasattr(connection, "read_all") else b""
        text = raw.decode(encoding, errors="ignore").strip()
        return {
            "ok": True,
            "code": "ok",
            "message": "发送成功",
            "payload": {
                "command": wire_command.rstrip(),
                "raw_response": raw,
                "response": text,
            },
        }
    except Exception as exc:
        log_fn(f"串口发送失败: {exc}")
        return {
            "ok": False,
            "code": "io_error",
            "message": str(exc),
            "payload": {"command": wire_command.rstrip(), "response": ""},
        }


def read_serial_messages(
    connection: Any,
    *,
    encoding: str = "utf-8",
    log_fn=print,
) -> dict:
    if connection is None or not getattr(connection, "is_open", False):
        return {
            "ok": False,
            "code": "not_connected",
            "message": "串口未连接",
            "payload": {"lines": []},
        }

    try:
        waiting = int(getattr(connection, "in_waiting", 0) or 0)
        if waiting <= 0:
            return {
                "ok": True,
                "code": "ok",
                "message": "无新消息",
                "payload": {"lines": [], "raw": b""},
            }
        raw = connection.read(waiting) if hasattr(connection, "read") else b""
        text = raw.decode(encoding, errors="ignore")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return {
            "ok": True,
            "code": "ok",
            "message": "读取成功",
            "payload": {"lines": lines, "raw": raw},
        }
    except Exception as exc:
        log_fn(f"串口读取失败: {exc}")
        return {
            "ok": False,
            "code": "read_failed",
            "message": str(exc),
            "payload": {"lines": []},
        }


def probe_device_baudrate(
    device: str,
    baudrate: int,
    *,
    probe_command: str = "AT",
    success_tokens: tuple[str, ...] = ("OK", "BT"),
    log_fn=print,
) -> SerialCommandResult:
    connect_result = connect_port(device, baudrate=baudrate, timeout_sec=1.0, log_fn=log_fn)
    if not connect_result.get("ok"):
        return {
            "ok": False,
            "code": str(connect_result.get("code", "connect_failed")),
            "message": str(connect_result.get("message", "串口连接失败")),
            "payload": {
                "device": str(device),
                "expected_baud": int(baudrate),
                "response": "",
            },
        }

    connection = (connect_result.get("payload") or {}).get("connection")
    if connection is None:
        return {
            "ok": False,
            "code": "connect_failed",
            "message": "串口连接失败",
            "payload": {
                "device": str(device),
                "expected_baud": int(baudrate),
                "response": "",
            },
        }

    try:
        send_result = send_serial_command(connection, probe_command, wait_sec=1.0, log_fn=log_fn)
        response = str((send_result.get("payload") or {}).get("response", "") or "")
        upper = response.upper()
        matched = bool(response) and any(token in upper for token in success_tokens)
        if matched:
            return {
                "ok": True,
                "code": "ok",
                "message": f"波特率 {baudrate} 匹配",
                "payload": {
                    "device": str(device),
                    "expected_baud": int(baudrate),
                    "matched_baud": int(baudrate),
                    "response": response,
                },
            }
        if not send_result.get("ok"):
            return {
                "ok": False,
                "code": str(send_result.get("code", "probe_failed")),
                "message": str(send_result.get("message", "探测失败")),
                "payload": {
                    "device": str(device),
                    "expected_baud": int(baudrate),
                    "response": response,
                },
            }
        return {
            "ok": False,
            "code": "no_match",
            "message": f"波特率 {baudrate} 未命中响应特征",
            "payload": {
                "device": str(device),
                "expected_baud": int(baudrate),
                "response": response,
            },
        }
    finally:
        disconnect_port(connection, log_fn=log_fn)
