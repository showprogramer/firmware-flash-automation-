import pytest

from core.services.usb_repair_service import diagnose_drive, repair_drive


def test_diagnose_drive_ok(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "core.services.usb_repair_service.diagnose_usb_health",
        lambda drive, log_fn: {"ok": True, "code": "ok", "message": "good", "payload": {"drive": drive}},
    )

    result = diagnose_drive("E:\\", log_fn=lambda _m: None)

    assert result["ok"] is True
    assert result["code"] == "ok"


def test_diagnose_drive_failure(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "core.services.usb_repair_service.diagnose_usb_health",
        lambda drive, log_fn: {
            "ok": False,
            "code": "volume_check_failed",
            "message": "failed",
            "payload": {"drive": drive},
        },
    )

    result = diagnose_drive("E:\\", log_fn=lambda _m: None)

    assert result["ok"] is False
    assert result["code"] == "volume_check_failed"


def test_repair_drive_permission_denied(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "core.services.usb_repair_service.repair_usb_driver",
        lambda drive, log_fn: {
            "ok": False,
            "code": "permission_denied",
            "message": "权限不足",
            "payload": {"drive": drive},
        },
    )

    result = repair_drive("E:\\", log_fn=lambda _m: None)

    assert result["ok"] is False
    assert result["code"] == "permission_denied"


def test_repair_drive_exception(monkeypatch: pytest.MonkeyPatch):
    def raise_repair(drive, log_fn):
        raise RuntimeError("boom")

    monkeypatch.setattr("core.services.usb_repair_service.repair_usb_driver", raise_repair)
    result = repair_drive("E:\\", log_fn=lambda _m: None)

    assert result["ok"] is False
    assert result["code"] == "service_exception"
