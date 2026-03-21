import pytest

from core.services.scan_service import build_scan_result


def test_build_scan_result_ok(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("core.services.scan_service.find_handcontrol_folders", lambda root: [{"model": "L36", "version": "V1.0.0", "label": "x"}])
    monkeypatch.setattr("core.services.scan_service.load_excel_status", lambda p, s: {("L36", "V1.0.0"): "测试通过"})

    result = build_scan_result("D:/x", "a.xlsx", "Sheet1", log_fn=lambda _m: None)

    assert result["ok"] is True
    assert result["code"] == "ok"
    assert len(result["payload"]["folders"]) == 1
    assert result["payload"]["tested"] == 1
    assert result["payload"]["pending"] == 0


def test_build_scan_result_failed(monkeypatch: pytest.MonkeyPatch):
    def raise_scan(_root):
        raise RuntimeError("scan boom")

    monkeypatch.setattr("core.services.scan_service.find_handcontrol_folders", raise_scan)

    result = build_scan_result("D:/x", "a.xlsx", "Sheet1", log_fn=lambda _m: None)

    assert result["ok"] is False
    assert result["code"] == "scan_failed"
    assert "scan boom" in result["message"]
