import pytest

from fwasset.core.services.serial_service import (
    connect_port,
    probe_device_baudrate,
    read_serial_messages,
    scan_serial_ports,
    send_serial_command,
)


class _FakePort:
    def __init__(self, device: str, description: str, hwid: str):
        self.device = device
        self.description = description
        self.hwid = hwid


class _FakeSerialConn:
    def __init__(self, response: bytes = b"OK\r\n"):
        self.response = response
        self.written = []
        self.is_open = True
        self.port = "COM5"
        self.baudrate = 115200

    def reset_input_buffer(self):
        return None

    def write(self, data: bytes):
        self.written.append(data)

    def flush(self):
        return None

    def read_all(self):
        return self.response

    @property
    def in_waiting(self):
        return len(self.response)

    def read(self, size: int):
        return self.response[:size]

    def close(self):
        self.is_open = False


def test_scan_serial_ports_missing_dependency(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "fwasset.core.services.serial_service._import_serial_modules",
        lambda: (None, None, "pyserial missing"),
    )

    result = scan_serial_ports(log_fn=lambda _m: None)

    assert result["ok"] is False
    assert result["code"] == "serial_missing"


def test_scan_serial_ports_ok(monkeypatch: pytest.MonkeyPatch):
    class _FakeListPorts:
        @staticmethod
        def comports():
            return [
                _FakePort("COM3", "USB Serial", "USB\\VID_1A86"),
                _FakePort("COM5", "CH340", "USB\\VID_1A86&PID_7523"),
            ]

    monkeypatch.setattr(
        "fwasset.core.services.serial_service._import_serial_modules",
        lambda: (object(), _FakeListPorts, ""),
    )

    result = scan_serial_ports(log_fn=lambda _m: None)

    assert result["ok"] is True
    assert len(result["payload"]["ports"]) == 2
    assert result["payload"]["ports"][1]["device"] == "COM5"


def test_connect_port_ok(monkeypatch: pytest.MonkeyPatch):
    class _FakeSerialModule:
        @staticmethod
        def Serial(device, baudrate, timeout):
            conn = _FakeSerialConn()
            conn.port = device
            conn.baudrate = baudrate
            conn.timeout = timeout
            return conn

    monkeypatch.setattr(
        "fwasset.core.services.serial_service._import_serial_modules",
        lambda: (_FakeSerialModule, object(), ""),
    )

    result = connect_port("COM9", baudrate=38400, timeout_sec=2.0, log_fn=lambda _m: None)

    assert result["ok"] is True
    assert result["payload"]["device"] == "COM9"
    assert result["payload"]["baudrate"] == 38400


def test_send_serial_command_appends_crlf():
    conn = _FakeSerialConn(response=b"OK\r\n")
    result = send_serial_command(conn, "AT", log_fn=lambda _m: None)

    assert result["ok"] is True
    assert conn.written[-1] == b"AT\r\n"
    assert result["payload"]["response"] == "OK"


def test_probe_device_baudrate_no_match(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "fwasset.core.services.serial_service.connect_port",
        lambda *args, **kwargs: {"ok": True, "code": "ok", "message": "ok", "payload": {"connection": _FakeSerialConn(b"??")}},
    )
    monkeypatch.setattr("fwasset.core.services.serial_service.disconnect_port", lambda *_args, **_kwargs: {"ok": True})

    result = probe_device_baudrate("COM3", 115200, log_fn=lambda _m: None)

    assert result["ok"] is False
    assert result["code"] == "no_match"


def test_read_serial_messages_ok():
    conn = _FakeSerialConn(response=b"BT_OK\r\n123\r\n")

    result = read_serial_messages(conn, log_fn=lambda _m: None)

    assert result["ok"] is True
    assert result["payload"]["lines"] == ["BT_OK", "123"]
