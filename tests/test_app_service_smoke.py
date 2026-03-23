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


class FakeCombo:
    def __init__(self):
        self.values = []

    def __setitem__(self, key, value):
        if key == "values":
            self.values = list(value)


def _mk_app_stub():
    app = App.__new__(App)
    app.root_dir = FakeVar("D:/root")
    app.excel_path = FakeVar("a.xlsx")
    app.usb_drive = FakeVar("")
    app.status_text = FakeVar("就绪")
    app.usb_combo = FakeCombo()
    app.folders = []
    app.current_idx = FakeVar(0)
    app.listbox = FakeListbox()
    app.logs = []
    app.log = app.logs.append
    app._known_usb_drives = set()
    app._usb_diag_inflight = set()
    app._update_listbox_color = lambda *args, **kwargs: None
    app._upsert_preview_row = lambda row: app.logs.append(f"UPSERT:{row.get('model','')}")
    app.field_logo = FakeVar("logo")
    app.field_language = FakeVar("lang")
    app.field_salesman = FakeVar("sale")
    app._current_info = lambda: {"model": "L36", "version": "V1.0.0", "path": "D:/root/x", "rom_file": "a.ROM"}
    app.after = lambda _ms, _fn: None
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


def test_refresh_usb_returns_inserted_and_updates_combo(monkeypatch):
    app = _mk_app_stub()

    seq = [["E:\\"], ["E:\\", "F:\\"]]

    def fake_get_usb_drives():
        return seq.pop(0)

    monkeypatch.setattr("app.get_usb_drives", fake_get_usb_drives)

    first = App._refresh_usb(app, log_events=False, detect_insert=False)
    second = App._refresh_usb(app, log_events=False, detect_insert=True)

    assert first == []
    assert second == ["F:\\"]
    assert app.usb_combo.values == ["E:\\", "F:\\"]


def test_diagnose_usb_inserted_sets_warning_status(monkeypatch):
    app = _mk_app_stub()

    monkeypatch.setattr(
        "app.diagnose_drive",
        lambda drive, log_fn: {"ok": False, "code": "volume_check_failed", "message": "bad drive"},
    )

    app._run_non_blocking_task = lambda _name, fn, on_done: on_done(fn(lambda _m: None))

    App._diagnose_usb_inserted(app, "E:\\")

    assert app.status_text.get() == "U盘可能异常，请点驱动修复"
    assert any("bad drive" in m for m in app.logs)


def test_repair_usb_driver_success(monkeypatch):
    app = _mk_app_stub()
    app.usb_drive.set("E:\\")

    monkeypatch.setattr("app.repair_drive", lambda drive, log_fn: {"ok": True, "code": "ok", "message": "done"})
    monkeypatch.setattr("app.messagebox.askyesno", lambda *_args, **_kwargs: True)

    called = {"info": 0}
    monkeypatch.setattr("app.messagebox.showinfo", lambda *_args, **_kwargs: called.__setitem__("info", called["info"] + 1))

    app._run_task = lambda _name, fn, on_done: on_done(fn(lambda _m: None))

    App._repair_usb_driver(app)

    assert called["info"] == 1
    assert app.status_text.get() == "U盘驱动修复完成"
