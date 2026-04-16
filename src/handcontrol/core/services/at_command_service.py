from __future__ import annotations

from typing import Any

from handcontrol.core.services.serial_service import disconnect_port, probe_device_baudrate, send_serial_command
from handcontrol.core.types import SerialCommandResult


def send_at_command(
    connection: Any,
    prefix: str,
    value: str,
    *,
    success_tokens: tuple[str, ...] = ("OK",),
    log_fn=print,
) -> SerialCommandResult:
    command = f"{prefix}={value}".strip()
    send_result = send_serial_command(connection, command, wait_sec=0.8, log_fn=log_fn)
    if not send_result.get("ok"):
        return {
            "ok": False,
            "code": str(send_result.get("code", "io_error")),
            "message": str(send_result.get("message", "发送失败")),
            "payload": dict(send_result.get("payload") or {}),
        }

    payload = dict(send_result.get("payload") or {})
    response = str(payload.get("response", "") or "")
    upper = response.upper()
    if response and any(token.upper() in upper for token in success_tokens):
        return {
            "ok": True,
            "code": "ok",
            "message": "AT 指令执行成功",
            "payload": payload,
        }
    return {
        "ok": False,
        "code": "at_rejected",
        "message": "模块未返回成功响应",
        "payload": payload,
    }


def apply_baudrate_command(
    connection: Any,
    *,
    new_baud: int,
    device: str | None = None,
    old_baud: int | None = None,
    log_fn=print,
) -> SerialCommandResult:
    resolved_device = str(device or getattr(connection, "port", "") or "")
    resolved_old_baud = int(old_baud or getattr(connection, "baudrate", 0) or 0)
    if not resolved_device:
        return {
            "ok": False,
            "code": "missing_device",
            "message": "缺少串口设备名",
            "payload": {"new_baud": int(new_baud), "old_baud": resolved_old_baud},
        }

    send_result = send_serial_command(connection, f"AT+BD={int(new_baud)}", wait_sec=0.8, log_fn=log_fn)
    if not send_result.get("ok"):
        return {
            "ok": False,
            "code": str(send_result.get("code", "io_error")),
            "message": str(send_result.get("message", "波特率指令发送失败")),
            "payload": {
                "device": resolved_device,
                "old_baud": resolved_old_baud,
                "new_baud": int(new_baud),
                "response": str((send_result.get("payload") or {}).get("response", "") or ""),
            },
        }

    disconnect_port(connection, log_fn=log_fn)
    verify_new = probe_device_baudrate(resolved_device, int(new_baud), log_fn=log_fn)
    if verify_new.get("ok"):
        return {
            "ok": True,
            "code": "ok",
            "message": f"波特率已切换到 {int(new_baud)}",
            "payload": {
                "device": resolved_device,
                "old_baud": resolved_old_baud,
                "new_baud": int(new_baud),
                "matched_baud": int(new_baud),
                "response": str((verify_new.get("payload") or {}).get("response", "") or ""),
            },
        }

    if resolved_old_baud > 0:
        verify_old = probe_device_baudrate(resolved_device, resolved_old_baud, log_fn=log_fn)
        if verify_old.get("ok"):
            return {
                "ok": False,
                "code": "baud_unchanged",
                "message": f"模块仍工作在旧波特率 {resolved_old_baud}",
                "payload": {
                    "device": resolved_device,
                    "old_baud": resolved_old_baud,
                    "new_baud": int(new_baud),
                    "matched_baud": resolved_old_baud,
                    "warning": "新波特率验证失败，旧波特率仍可通信",
                    "response": str((verify_old.get("payload") or {}).get("response", "") or ""),
                },
            }

    return {
        "ok": False,
        "code": "baud_unknown",
        "message": "新旧波特率均未确认，模块状态未知",
        "payload": {
            "device": resolved_device,
            "old_baud": resolved_old_baud,
            "new_baud": int(new_baud),
            "warning": "新旧波特率均未命中响应",
            "response": str((verify_new.get("payload") or {}).get("response", "") or ""),
        },
    }
