from app import App


class FakeVar:
    def __init__(self, value=""):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


class FakeListbox:
    def __init__(self):
        self.items = []
        self.colors = {}

    def delete(self, _start, _end):
        self.items = []

    def insert(self, _where, text):
        self.items.append(text)

    def itemconfig(self, idx, **kwargs):
        self.colors[idx] = kwargs

    def size(self):
        return len(self.items)


def _mk_app_stub():
    app = App.__new__(App)
    app.root_dir = FakeVar("D:/root")
    app.excel_path = FakeVar("a.xlsx")
    app.folders = []
    app.current_idx = FakeVar(0)
    app.listbox = FakeListbox()
    app.logs = []
    app.log = app.logs.append
    app._update_listbox_color = lambda *args, **kwargs: None
    app._upsert_preview_row = lambda row: app.logs.append(f"UPSERT:{row.get('model','')}")
    app.field_logo = FakeVar("logo")
    app.field_language = FakeVar("lang")
    app.field_salesman = FakeVar("sale")
    app._current_info = lambda: {"model": "L36", "version": "V1.0.0", "path": "D:/root/x", "rom_file": "a.ROM"}
    return app


def test_scan_uses_service_result(monkeypatch):
    app = _mk_app_stub()

    monkeypatch.setattr(
        "app.build_scan_result",
        lambda root, excel, sheet, log_fn: {
            "ok": True,
            "code": "ok",
            "message": "done",
            "payload": {
                "folders": [{"model": "L36", "version": "V1.0.0", "label": "L36 V1"}],
                "status_map": {("L36", "V1.0.0"): "测试通过"},
                "tested": 1,
                "pending": 0,
            },
        },
    )

    def immediate_run(_name, fn, on_done):
        on_done(fn(lambda _m: None))

    app._run_task = immediate_run

    App._scan(app)

    assert len(app.folders) == 1
    assert app.listbox.items == ["001. L36 V1"]
    assert any("共找到" in m for m in app.logs)


def test_write_excel_uses_service_result(monkeypatch):
    app = _mk_app_stub()

    monkeypatch.setattr(
        "app.write_record",
        lambda **kwargs: {
            "ok": True,
            "code": "ok",
            "message": "ok",
            "payload": {
                "excel_result": {"ok": True},
                "preview_row": {
                    "model": "L36",
                    "version": "V1.0.0",
                    "remark": "待确认",
                },
            },
        },
    )

    def immediate_run(_name, fn, on_done):
        on_done(fn(lambda _m: None))

    app._run_task = immediate_run

    App._write_excel(app, "待确认")

    assert any(m.startswith("UPSERT:L36") for m in app.logs)

