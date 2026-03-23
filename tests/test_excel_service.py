import pytest

from core.services.excel_service import delete_record, update_record_fields, write_record


def test_write_record_ok(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "core.services.excel_service.write_excel_record",
        lambda **kwargs: {
            "ok": True,
            "reason": "ok",
            "tmp_path": "",
            "error": "",
            "written_row": {
                "model": "L36",
                "logo": "A",
                "salesman": "S",
                "language": "CN",
                "version": "V1.0.0",
                "date": "2026.03.21",
                "remark": "待确认",
            },
        },
    )

    result = write_record("a.xlsx", "Sheet1", "L36", "V1.0.0", "待确认", "r.ROM", log_fn=lambda _m: None)

    assert result["ok"] is True
    assert result["payload"]["preview_row"]["model"] == "L36"


def test_write_record_locked(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "core.services.excel_service.write_excel_record",
        lambda **kwargs: {"ok": False, "reason": "locked", "tmp_path": "tmp.xlsx", "error": "", "written_row": None},
    )

    result = write_record("a.xlsx", "Sheet1", "L36", "V1.0.0", "待确认", "r.ROM", log_fn=lambda _m: None)

    assert result["ok"] is False
    assert result["code"] == "locked"
    assert result["payload"]["preview_row"] == {}


def test_write_record_exception(monkeypatch: pytest.MonkeyPatch):
    def raise_write(**kwargs):
        raise RuntimeError("svc boom")

    monkeypatch.setattr("core.services.excel_service.write_excel_record", raise_write)

    result = write_record("a.xlsx", "Sheet1", "L36", "V1.0.0", "待确认", "r.ROM", log_fn=lambda _m: None)

    assert result["ok"] is False
    assert result["code"] == "service_exception"


def test_update_record_fields_ok(monkeypatch: pytest.MonkeyPatch):
    calls = []

    def fake_update(**kwargs):
        calls.append((kwargs["field"], kwargs["value"]))
        return {"ok": True, "reason": "ok", "error": ""}

    monkeypatch.setattr("core.services.excel_service.update_excel_field", fake_update)

    result = update_record_fields(
        excel_path="a.xlsx",
        sheet_name="Sheet1",
        model="L36",
        version="V1.0.0",
        logo="品牌A",
        salesman="张三",
        language="中、英",
        remark="测试通过",
        log_fn=lambda _m: None,
    )

    assert result["ok"] is True
    assert result["code"] == "ok"
    assert result["payload"]["preview_row"]["model"] == "L36"
    assert calls == [
        ("logo", "品牌A"),
        ("salesman", "张三"),
        ("language", "中、英"),
        ("remark", "测试通过"),
    ]


def test_update_record_fields_locked(monkeypatch: pytest.MonkeyPatch):
    def fake_update(**kwargs):
        if kwargs["field"] == "language":
            return {"ok": False, "reason": "locked", "error": "文件占用"}
        return {"ok": True, "reason": "ok", "error": ""}

    monkeypatch.setattr("core.services.excel_service.update_excel_field", fake_update)

    result = update_record_fields(
        excel_path="a.xlsx",
        sheet_name="Sheet1",
        model="L36",
        version="V1.0.0",
        logo="品牌A",
        salesman="张三",
        language="中、英",
        remark="测试通过",
        log_fn=lambda _m: None,
    )

    assert result["ok"] is False
    assert result["code"] == "locked"


def test_update_record_fields_exception(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("core.services.excel_service.update_excel_field", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    result = update_record_fields(
        excel_path="a.xlsx",
        sheet_name="Sheet1",
        model="L36",
        version="V1.0.0",
        logo="",
        salesman="",
        language="",
        remark="",
        log_fn=lambda _m: None,
    )

    assert result["ok"] is False
    assert result["code"] == "service_exception"


def test_delete_record_ok(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "core.services.excel_service.delete_excel_row",
        lambda **kwargs: {"ok": True, "reason": "ok", "error": ""},
    )

    result = delete_record("a.xlsx", "Sheet1", "L36", "V1.0.0", log_fn=lambda _m: None)

    assert result["ok"] is True
    assert result["code"] == "ok"


def test_delete_record_not_found(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "core.services.excel_service.delete_excel_row",
        lambda **kwargs: {"ok": False, "reason": "not_found", "error": "未找到"},
    )

    result = delete_record("a.xlsx", "Sheet1", "L36", "V1.0.0", log_fn=lambda _m: None)

    assert result["ok"] is False
    assert result["code"] == "not_found"


def test_delete_record_exception(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("core.services.excel_service.delete_excel_row", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    result = delete_record("a.xlsx", "Sheet1", "L36", "V1.0.0", log_fn=lambda _m: None)

    assert result["ok"] is False
    assert result["code"] == "service_exception"
