import pytest

from handcontrol.core.services.at_command_service import apply_baudrate_command, send_at_command


class _FakeConn:
    def __init__(self):
        self.port = "COM7"
        self.baudrate = 115200
        self.is_open = True

    def close(self):
        self.is_open = False


def test_send_at_command_ok(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "handcontrol.core.services.at_command_service.send_serial_command",
        lambda *args, **kwargs: {"ok": True, "code": "ok", "message": "ok", "payload": {"response": "OK"}},
    )

    result = send_at_command(_FakeConn(), "AT+NM", "Premium", log_fn=lambda _m: None)

    assert result["ok"] is True
    assert result["code"] == "ok"


def test_send_at_command_rejected(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "handcontrol.core.services.at_command_service.send_serial_command",
        lambda *args, **kwargs: {"ok": True, "code": "ok", "message": "ok", "payload": {"response": "ERROR"}},
    )

    result = send_at_command(_FakeConn(), "AT+NM", "Premium", log_fn=lambda _m: None)

    assert result["ok"] is False
    assert result["code"] == "at_rejected"


def test_apply_baudrate_command_success(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "handcontrol.core.services.at_command_service.send_serial_command",
        lambda *args, **kwargs: {"ok": True, "code": "ok", "message": "ok", "payload": {"response": "OK"}},
    )
    monkeypatch.setattr(
        "handcontrol.core.services.at_command_service.probe_device_baudrate",
        lambda device, baudrate, **kwargs: {
            "ok": True,
            "code": "ok",
            "message": "match",
            "payload": {"device": device, "matched_baud": baudrate, "response": "OK"},
        },
    )

    result = apply_baudrate_command(_FakeConn(), new_baud=38400, log_fn=lambda _m: None)

    assert result["ok"] is True
    assert result["payload"]["matched_baud"] == 38400


def test_apply_baudrate_command_unchanged(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "handcontrol.core.services.at_command_service.send_serial_command",
        lambda *args, **kwargs: {"ok": True, "code": "ok", "message": "ok", "payload": {"response": "OK"}},
    )

    def _probe(device, baudrate, **kwargs):
        if baudrate == 38400:
            return {"ok": False, "code": "no_match", "message": "fail", "payload": {"response": ""}}
        return {"ok": True, "code": "ok", "message": "match", "payload": {"response": "OK"}}

    monkeypatch.setattr("handcontrol.core.services.at_command_service.probe_device_baudrate", _probe)

    result = apply_baudrate_command(_FakeConn(), new_baud=38400, log_fn=lambda _m: None)

    assert result["ok"] is False
    assert result["code"] == "baud_unchanged"


def test_apply_baudrate_command_unknown(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "handcontrol.core.services.at_command_service.send_serial_command",
        lambda *args, **kwargs: {"ok": True, "code": "ok", "message": "ok", "payload": {"response": "OK"}},
    )
    monkeypatch.setattr(
        "handcontrol.core.services.at_command_service.probe_device_baudrate",
        lambda *args, **kwargs: {"ok": False, "code": "no_match", "message": "fail", "payload": {"response": ""}},
    )

    result = apply_baudrate_command(_FakeConn(), new_baud=38400, log_fn=lambda _m: None)

    assert result["ok"] is False
    assert result["code"] == "baud_unknown"
