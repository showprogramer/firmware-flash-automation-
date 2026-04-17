from pathlib import Path
from handcontrol.app import App


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
        self.selected = None
        self.selection_cleared = False

    def delete(self, _start, _end):
        self.items = []

    def insert(self, _where, text):
        self.items.append(text)

    def itemconfig(self, idx, **kwargs):
        self.colors[idx] = kwargs

    def size(self):
        return len(self.items)

    def selection_clear(self, _start, _end):
        self.selection_cleared = True
        self.selected = None

    def selection_set(self, idx):
        self.selected = idx

    def see(self, _idx):
        return None


class FakeCombo:
    def __init__(self):
        self.values = []

    def __setitem__(self, key, value):
        if key == "values":
            self.values = list(value)


class FakeText:
    def __init__(self):
        self.value = ""
        self.state = "normal"

    def configure(self, **kwargs):
        self.state = kwargs.get("state", self.state)

    def delete(self, _start, _end):
        self.value = ""

    def insert(self, _idx, text):
        self.value += text

    def get(self, _start, _end):
        return self.value

    def see(self, _idx):
        return None


class FakeLabel:
    def __init__(self):
        self.text = ""

    def config(self, **kwargs):
        self.text = kwargs.get("text", self.text)


class FakeButton:
    def __init__(self):
        self.text = ""

    def configure(self, **kwargs):
        self.text = kwargs.get("text", self.text)


class FakePreview:
    def __init__(self):
        self.items = {}
        self.order = []
        self.sel = []
        self.idx = 0

    def insert(self, _parent, _where, values=None, tags=()):
        self.idx += 1
        item_id = f"i{self.idx}"
        self.items[item_id] = {"values": list(values or []), "tags": tuple(tags)}
        self.order.append(item_id)
        return item_id

    def item(self, item_id, option=None, values=None, tags=None):
        if values is not None:
            self.items[item_id]["values"] = list(values)
        if tags is not None:
            self.items[item_id]["tags"] = tuple(tags)
        if option == "values":
            return self.items[item_id]["values"]
        return self.items[item_id]

    def get_children(self):
        return list(self.order)

    def delete(self, item_id):
        if item_id in self.items:
            self.items.pop(item_id)
        self.order = [x for x in self.order if x != item_id]

    def selection(self):
        return tuple(self.sel)

    def selection_set(self, item_id):
        self.sel = [item_id]


def _mk_app_stub():
    app = App.__new__(App)
    app.root_dir = FakeVar("D:/root")
    app.excel_path = FakeVar("a.xlsx")
    app.usb_drive = FakeVar("")
    app.status_text = FakeVar("就绪")
    app.busy = FakeVar(False)
    app.search_var = FakeVar("")
    app.folder_search_var = FakeVar("")
    app.folder_status_filter_var = FakeVar("全部状态")
    app.usb_combo = FakeCombo()
    app.music_usb_combo = FakeCombo()
    app.music_serial_combo = FakeCombo()
    app.music_usb_drive = FakeVar("")
    app.music_source_dir = FakeVar("D:/music")
    app.music_serial_port = FakeVar("")
    app.music_baudrate = FakeVar("115200")
    app.music_custom_cmd = FakeVar("AT+TEST")
    app.music_connect_btn = FakeButton()
    app.music_log_text = FakeText()
    app._music_serial_connection = None
    app._music_connected = False
    app._music_at_presets = ["AT+NM=Premium XZ8", "AT+BD=38400"]
    app.folders = []
    app._all_folders = []
    app._folder_status_map = {}
    app._folder_sort_key = "path"
    app._folder_sort_ascending = True
    app._folder_header_buttons = {}
    app.current_idx = FakeVar(0)
    app.listbox = FakeListbox()
    app.preview = FakePreview()
    app.logs = []
    app.log = app.logs.append
    app._known_usb_drives = set()
    app._usb_diag_inflight = set()
    app._preview_rows = []
    app._preview_by_key = {}
    app._preview_item_by_key = {}
    app._editing_preview_key = None
    app._update_listbox_color = lambda *args, **kwargs: None
    app.field_logo = FakeVar("logo")
    app.field_language = FakeVar("lang")
    app.field_salesman = FakeVar("sale")
    app.field_attachment = FakeVar("可通用")
    app.review_status = FakeVar("测试通过")
    app.remark_text = FakeText()
    app.remark_text.value = ""
    app.lbl_model = FakeLabel()
    app.lbl_ver = FakeLabel()
    app.lbl_rom = FakeLabel()
    app.lbl_pkg = FakeLabel()
    app._current_info = lambda: {"model": "L36", "version": "V1.0.0", "path": "D:/root/x", "rom_file": "a.ROM"}
    app.after = lambda _ms, _fn: None
    return app


def _folder_row(app, idx, folder):
    return App._folder_row_text(app, idx, folder)

def test_scan_uses_service_result(monkeypatch):
    app = _mk_app_stub()

    monkeypatch.setattr(
        "handcontrol.app.build_scan_result",
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
    assert app.listbox.items == [_folder_row(app, 1, app.folders[0])]
    assert any("共找到" in m for m in app.logs)


def test_filter_folder_list_by_keyword():
    app = _mk_app_stub()
    app._all_folders = [
        {"model": "L36", "version": "V1.0.0", "label": "L36 V1", "path": "D:/a", "rom_file": "a.ROM", "pkg_file": "a.PKG"},
        {"model": "L50S", "version": "V2.0.0", "label": "L50S V2", "path": "D:/b", "rom_file": "b.ROM", "pkg_file": "b.PKG"},
    ]
    app.folder_search_var.set("L50")

    App._filter_folder_list(app)

    assert len(app.folders) == 1
    assert app.folders[0]["model"] == "L50S"
    assert app.listbox.items == [_folder_row(app, 1, app.folders[0])]


def test_scan_applies_folder_filter_keyword(monkeypatch):
    app = _mk_app_stub()
    app.folder_search_var.set("L50")

    monkeypatch.setattr(
        "handcontrol.app.build_scan_result",
        lambda root, excel, sheet, log_fn: {
            "ok": True,
            "code": "ok",
            "message": "done",
            "payload": {
                "folders": [
                    {"model": "L36", "version": "V1.0.0", "label": "L36 V1", "path": "D:/a", "rom_file": "a.ROM", "pkg_file": "a.PKG"},
                    {"model": "L50S", "version": "V2.0.0", "label": "L50S V2", "path": "D:/b", "rom_file": "b.ROM", "pkg_file": "b.PKG"},
                ],
                "status_map": {},
                "tested": 0,
                "pending": 0,
            },
        },
    )

    app._run_task = lambda _name, fn, on_done: on_done(fn(lambda _m: None))

    App._scan(app)

    assert len(app.folders) == 1
    assert app.listbox.items == [_folder_row(app, 1, app.folders[0])]
    assert any("过滤后显示 1 个" in m for m in app.logs)

def test_filter_folder_list_by_status():
    app = _mk_app_stub()
    app._all_folders = [
        {"model": "L36", "version": "V1.0.0", "label": "L36 V1", "path": "D:/a", "rom_file": "a.ROM", "pkg_file": "a.PKG"},
        {"model": "L50S", "version": "V2.0.0", "label": "L50S V2", "path": "D:/b", "rom_file": "b.ROM", "pkg_file": "b.PKG"},
    ]
    app._folder_status_map = {
        app._preview_key("L36", "V1.0.0"): "测试通过",
        app._preview_key("L50S", "V2.0.0"): "待确认",
    }
    app.folder_status_filter_var.set("待确认")

    App._filter_folder_list(app)

    assert len(app.folders) == 1
    assert app.folders[0]["model"] == "L50S"
    assert app.listbox.items == [_folder_row(app, 1, app.folders[0])]


def test_filter_folder_list_sort_by_model_desc():
    app = _mk_app_stub()
    app._all_folders = [
        {"model": "L36", "version": "V1.0.0", "label": "L36 V1", "path": "D:/a", "rom_file": "a.ROM", "pkg_file": "a.PKG"},
        {"model": "L50S", "version": "V2.0.0", "label": "L50S V2", "path": "D:/b", "rom_file": "b.ROM", "pkg_file": "b.PKG"},
    ]
    App._on_folder_header_click(app, "model")
    App._on_folder_header_click(app, "model")

    App._filter_folder_list(app)

    assert [item["model"] for item in app.folders] == ["L50S", "L36"]
    assert app.listbox.items == [_folder_row(app, 1, app.folders[0]), _folder_row(app, 2, app.folders[1])]


def test_filter_folder_list_sort_by_status():
    app = _mk_app_stub()
    app._all_folders = [
        {"model": "L36", "version": "V1.0.0", "label": "L36 V1", "path": "D:/a", "rom_file": "a.ROM", "pkg_file": "a.PKG"},
        {"model": "L50S", "version": "V2.0.0", "label": "L50S V2", "path": "D:/b", "rom_file": "b.ROM", "pkg_file": "b.PKG"},
        {"model": "L66", "version": "V3.0.0", "label": "L66 V3", "path": "D:/c", "rom_file": "c.ROM", "pkg_file": "c.PKG"},
    ]
    app._folder_status_map = {
        app._preview_key("L36", "V1.0.0"): "测试通过",
        app._preview_key("L50S", "V2.0.0"): "待确认",
    }
    App._on_folder_header_click(app, "status")

    App._filter_folder_list(app)

    assert [item["model"] for item in app.folders] == ["L50S", "L36", "L66"]


def test_folder_header_click_toggles_sort_direction():
    app = _mk_app_stub()

    assert App._current_folder_sort_key(app).value == "path"
    assert App._current_folder_sort_ascending(app) is True

    App._on_folder_header_click(app, "model")
    assert App._current_folder_sort_key(app).value == "model"
    assert App._current_folder_sort_ascending(app) is True

    App._on_folder_header_click(app, "model")
    assert App._current_folder_sort_key(app).value == "model"
    assert App._current_folder_sort_ascending(app) is False


def test_folder_row_text_hides_status_text():
    app = _mk_app_stub()
    app._folder_status_map = {app._preview_key("L36", "V1.0.0"): "测试通过"}

    row_text = App._folder_row_text(
        app,
        1,
        {"model": "L36", "version": "V1.0.0", "label": "L36 V1", "path": "D:/a/L36 V1"},
    )

    assert "测试通过" not in row_text
    assert "待确认" not in row_text
def test_report_callback_exception_logs_and_shows_error(monkeypatch):
    app = _mk_app_stub()
    app.log_text = FakeText()
    app.log = App.log.__get__(app, App)

    class FakeLogger:
        def __init__(self):
            self.events = []

        def log(self, message, level="INFO"):
            self.events.append((level, message))

        def exception(self, context, exc_text):
            self.events.append(("ERROR", context, exc_text))

    app._file_logger = FakeLogger()
    errors = []
    monkeypatch.setattr("handcontrol.app.messagebox.showerror", lambda title, message: errors.append((title, message)))

    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        App.report_callback_exception(app, RuntimeError, exc, exc.__traceback__)

    assert any(event[0] == "ERROR" and event[1] == "UI回调异常" for event in app._file_logger.events)
    assert "UI回调异常: boom" in app.log_text.value
    assert errors and errors[0][0] == "程序异常"


def test_write_excel_uses_service_result(monkeypatch):
    app = _mk_app_stub()

    monkeypatch.setattr(
        "handcontrol.app.write_record",
        lambda **kwargs: {
            "ok": True,
            "code": "ok",
            "message": "ok",
            "payload": {
                "excel_result": {"ok": True},
                "preview_row": {
                    "model": "L36",
                    "version": "V1.0.0",
                    "attachment": "可通用",
                    "remark": "待确认",
                },
            },
        },
    )

    def immediate_run(_name, fn, on_done):
        on_done(fn(lambda _m: None))

    app._run_task = immediate_run

    App._write_excel(app, "待确认")

    key = app._preview_key("L36", "V1.0.0")
    assert app._preview_by_key[key]["remark"] == "待确认"



def test_one_click_advances_to_next_folder_on_success(monkeypatch):
    app = _mk_app_stub()
    app.usb_drive.set("E:\\")
    app.folders = [
        {"model": "L36", "version": "V1.0.0", "label": "L36 V1", "path": "D:/root/x", "rom_file": "a.ROM", "pkg_file": "a.PKG"},
        {"model": "L50S", "version": "V2.0.0", "label": "L50S V2", "path": "D:/root/y", "rom_file": "b.ROM", "pkg_file": "b.PKG"},
    ]
    app.current_idx.set(0)
    app._all_folders = list(app.folders)
    on_select_calls = {"count": 0}
    app._on_select = lambda _event=None: (app.current_idx.set(app.listbox.selected), on_select_calls.__setitem__("count", on_select_calls["count"] + 1))
    app._current_info = lambda: app.folders[app.current_idx.get()]

    monkeypatch.setattr(
        "handcontrol.app.run_one_click",
        lambda **kwargs: {
            "ok": True,
            "code": "ok",
            "message": "ok",
            "payload": {
                "copy_ok": True,
                "excel_result": {"ok": True},
                "preview_row": {"model": "L36", "version": "V1.0.0", "remark": "待确认", "attachment": "可通用"},
            },
        },
    )

    app._run_task = lambda _name, fn, on_done: on_done(fn(lambda _m: None))

    App._one_click(app)

    assert app.current_idx.get() == 1
    assert app.listbox.selection_cleared is True
    assert app.listbox.selected == 1
    assert on_select_calls["count"] == 1
    assert any("切换到下一个" in msg for msg in app.logs)


def test_one_click_does_not_advance_when_excel_write_fails(monkeypatch):
    app = _mk_app_stub()
    app.usb_drive.set("E:\\")
    app.folders = [
        {"model": "L36", "version": "V1.0.0", "label": "L36 V1", "path": "D:/root/x", "rom_file": "a.ROM", "pkg_file": "a.PKG"},
        {"model": "L50S", "version": "V2.0.0", "label": "L50S V2", "path": "D:/root/y", "rom_file": "b.ROM", "pkg_file": "b.PKG"},
    ]
    app.current_idx.set(0)
    app._all_folders = list(app.folders)
    app._on_select = lambda _event=None: None
    app._current_info = lambda: app.folders[app.current_idx.get()]
    errors = []

    monkeypatch.setattr(
        "handcontrol.app.run_one_click",
        lambda **kwargs: {
            "ok": False,
            "code": "write_failed",
            "message": "boom",
            "payload": {
                "copy_ok": True,
                "excel_result": {"ok": False, "error": "boom"},
            },
        },
    )
    monkeypatch.setattr("handcontrol.app.messagebox.showerror", lambda title, message: errors.append((title, message)))

    app._run_task = lambda _name, fn, on_done: on_done(fn(lambda _m: None))

    App._one_click(app)

    assert app.current_idx.get() == 0
    assert app.listbox.selected is None
    assert errors


def test_export_diagnostics_builds_bundle_and_shows_message(monkeypatch, tmp_path: Path):
    app = _mk_app_stub()
    app.current_idx.set(0)
    app.folders = [{"model": "L36", "version": "V1.0.0", "label": "L36 V1", "path": "D:/root/x", "rom_file": "a.ROM", "pkg_file": "a.PKG"}]
    app._all_folders = list(app.folders)
    app._preview_rows = [{"model": "L36", "version": "V1.0.0", "remark": "待确认", "attachment": "可通用", "serial": "1"}]
    app._folder_status_map = {app._preview_key("L36", "V1.0.0"): "待确认"}
    app.log_text = FakeText()
    app.log_text.value = "line1\nline2\n"
    app._file_logger = type("Logger", (), {"path": tmp_path / "logs" / "app.log"})()
    output = tmp_path / "diag.zip"
    calls = {}
    infos = []

    monkeypatch.setattr("handcontrol.app.filedialog.asksaveasfilename", lambda **kwargs: str(output))

    def fake_build_diagnostic_bundle(**kwargs):
        calls.update(kwargs)
        return {"ok": True, "output_path": str(output), "entries": ["meta.json"]}

    monkeypatch.setattr("handcontrol.app.build_diagnostic_bundle", fake_build_diagnostic_bundle)
    monkeypatch.setattr("handcontrol.app.messagebox.showinfo", lambda title, message: infos.append((title, message)))
    app._run_task = lambda _name, fn, on_done: on_done(fn(lambda _m: None))

    App._export_diagnostics(app)

    assert calls["output_path"] == str(output)
    assert calls["config_path"]
    assert Path(calls["log_path"]).name == "app.log"
    assert calls["app_state"]["summary"]["preview_row_count"] == 1
    assert calls["app_state"]["current_folder"]["model"] == "L36"
    assert infos and infos[0][0] == "导出完成"

def test_refresh_usb_returns_inserted_and_updates_combo(monkeypatch):
    app = _mk_app_stub()

    seq = [["E:\\"], ["E:\\", "F:\\"]]

    def fake_get_usb_drives():
        return seq.pop(0)

    monkeypatch.setattr("handcontrol.app.get_usb_drives", fake_get_usb_drives)

    first = App._refresh_usb(app, log_events=False, detect_insert=False)
    second = App._refresh_usb(app, log_events=False, detect_insert=True)

    assert first == []
    assert second == ["F:\\"]
    assert app.usb_combo.values == ["E:\\", "F:\\"]
    assert app.music_usb_combo.values == ["E:\\", "F:\\"]


def test_music_scan_ports_updates_combo(monkeypatch):
    app = _mk_app_stub()
    monkeypatch.setattr(
        "handcontrol.app.scan_serial_ports",
        lambda **kwargs: {
            "ok": True,
            "code": "ok",
            "message": "ok",
            "payload": {
                "ports": [
                    {"device": "COM5", "description": "USB Serial"},
                    {"device": "COM7", "description": "CH340"},
                ]
            },
        },
    )

    App._music_scan_ports(app)

    assert app.music_serial_combo.values == ["COM5  USB Serial", "COM7  CH340"]
    assert app.music_serial_port.get() == "COM5  USB Serial"


def test_music_toggle_connect_connects_and_disconnects(monkeypatch):
    app = _mk_app_stub()
    app.music_serial_port.set("COM9  USB Serial")

    monkeypatch.setattr(
        "handcontrol.app.connect_port",
        lambda *args, **kwargs: {
            "ok": True,
            "code": "ok",
            "message": "ok",
            "payload": {"connection": object()},
        },
    )
    monkeypatch.setattr("handcontrol.app.disconnect_port", lambda *args, **kwargs: {"ok": True})

    App._music_toggle_connect(app)
    assert app._music_connected is True
    assert app.music_connect_btn.text == "断开"

    App._music_toggle_connect(app)
    assert app._music_connected is False
    assert app.music_connect_btn.text == "连接"


def test_music_send_preset_calls_baud_service(monkeypatch):
    app = _mk_app_stub()
    app._music_connected = True
    app._music_serial_connection = type("Conn", (), {"is_open": True, "port": "COM5", "baudrate": 115200})()

    monkeypatch.setattr(
        "handcontrol.app.apply_baudrate_command",
        lambda *args, **kwargs: {"ok": True, "code": "ok", "message": "done", "payload": {}},
    )
    monkeypatch.setattr("handcontrol.app.disconnect_port", lambda *args, **kwargs: {"ok": True})

    App._music_send_preset(app, "AT+BD=38400")

    assert app._music_connected is False
    assert any("AT+BD" in msg for msg in app.music_log_text.value.splitlines())


def test_music_prepare_usb_runs_service(monkeypatch):
    app = _mk_app_stub()
    app.music_usb_drive.set("E:\\")
    calls = {"count": 0}
    monkeypatch.setattr(
        "handcontrol.app.run_music_flash",
        lambda **kwargs: (calls.__setitem__("count", calls["count"] + 1) or {"ok": True, "code": "ok", "message": "ok", "payload": {"ejected": True}}),
    )
    app._run_task = lambda _name, fn, on_done: on_done(fn(lambda _m: None))

    App._music_prepare_usb(app)

    assert calls["count"] == 1
    assert any("音乐模式流程完成" in msg for msg in app.logs)


def test_diagnose_usb_inserted_sets_warning_status(monkeypatch):
    app = _mk_app_stub()

    monkeypatch.setattr(
        "handcontrol.app.diagnose_drive",
        lambda drive, log_fn: {"ok": False, "code": "volume_check_failed", "message": "bad drive"},
    )

    app._run_non_blocking_task = lambda _name, fn, on_done: on_done(fn(lambda _m: None))

    App._diagnose_usb_inserted(app, "E:\\")

    assert app.status_text.get() == "U盘可能异常，请点驱动修复"
    assert any("bad drive" in m for m in app.logs)


def test_repair_usb_driver_success(monkeypatch):
    app = _mk_app_stub()
    app.usb_drive.set("E:\\")

    monkeypatch.setattr("handcontrol.app.repair_drive", lambda drive, log_fn: {"ok": True, "code": "ok", "message": "done"})
    monkeypatch.setattr("handcontrol.app.messagebox.askyesno", lambda *_args, **_kwargs: True)

    called = {"info": 0}
    monkeypatch.setattr("handcontrol.app.messagebox.showinfo", lambda *_args, **_kwargs: called.__setitem__("info", called["info"] + 1))

    app._run_task = lambda _name, fn, on_done: on_done(fn(lambda _m: None))

    App._repair_usb_driver(app)

    assert called["info"] == 1
    assert app.status_text.get() == "U盘驱动修复完成"


def test_save_review_uses_preview_editing_key(monkeypatch):
    app = _mk_app_stub()
    app._editing_preview_key = ("L50S", "V2.0.0")
    app._preview_by_key[("L50S", "V2.0.0")] = {
        "model": "L50S",
        "version": "V2.0.0",
        "logo": "旧",
        "salesman": "旧",
        "language": "旧",
        "attachment": "可通用",
        "date": "2026.03.21",
        "remark": "待确认",
        "serial": "2",
    }
    app.field_logo.set("新品牌")
    app.field_salesman.set("新业务")
    app.field_language.set("中、英")
    app.field_attachment.set("定制")
    app.review_status.set("测试通过")
    app.remark_text.value = ""

    monkeypatch.setattr(
        "handcontrol.app.update_record_fields",
        lambda **kwargs: {
            "ok": True,
            "code": "ok",
            "message": "ok",
            "payload": {
                "preview_row": {
                    "model": "L50S",
                    "version": "V2.0.0",
                    "logo": "新品牌",
                    "salesman": "新业务",
                    "language": "中、英",
                    "attachment": "定制",
                    "remark": "测试通过",
                    "date": "",
                    "serial": "",
                }
            },
        },
    )

    app._run_task = lambda _name, fn, on_done: on_done(fn(lambda _m: None))

    App._save_review(app)

    key = app._preview_key("L50S", "V2.0.0")
    assert app._preview_by_key[key]["logo"] == "新品牌"
    assert app._preview_by_key[key]["remark"] == "测试通过"


def test_delete_selected_preview_row_reindexes_cache(monkeypatch):
    app = _mk_app_stub()
    app._preview_rows = [
        {"serial": "1", "model": "L36", "version": "V1.0.0", "logo": "", "salesman": "", "language": "", "attachment": "", "date": "", "remark": "待确认"},
        {"serial": "2", "model": "L50S", "version": "V2.0.0", "logo": "", "salesman": "", "language": "", "attachment": "", "date": "", "remark": "待确认"},
    ]
    app._preview_by_key = {
        app._preview_key("L36", "V1.0.0"): app._preview_rows[0],
        app._preview_key("L50S", "V2.0.0"): app._preview_rows[1],
    }
    app._rebuild_preview_tree()
    target_key = app._preview_key("L36", "V1.0.0")
    app.preview.selection_set(app._preview_item_by_key[target_key])

    monkeypatch.setattr("handcontrol.app.messagebox.askyesno", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        "handcontrol.app.delete_record",
        lambda *args, **kwargs: {"ok": True, "code": "ok", "message": "删除成功", "payload": {}},
    )

    app._run_task = lambda _name, fn, on_done: on_done(fn(lambda _m: None))

    App._delete_selected_preview_row(app)

    assert len(app._preview_rows) == 1
    assert app._preview_rows[0]["model"] == "L50S"
    assert app._preview_rows[0]["serial"] == "1"






def test_merge_backup_excel_success_refreshes_preview(monkeypatch):
    app = _mk_app_stub()
    app.excel_path.set('D:/root/records.xlsx')
    refreshed = {'count': 0}
    infos = []

    monkeypatch.setattr('handcontrol.app.filedialog.askopenfilename', lambda **kwargs: 'D:/root/records_刷机记录_待导入.xlsx')
    monkeypatch.setattr(
        'handcontrol.app.merge_backup_records',
        lambda **kwargs: {
            'ok': True,
            'code': 'ok',
            'message': '已合并 1 行',
            'payload': {'merge_result': {'merged_count': 1, 'skipped_count': 2}},
        },
    )
    monkeypatch.setattr('handcontrol.app.messagebox.showinfo', lambda title, message: infos.append((title, message)))

    app._manual_refresh_preview = lambda: refreshed.__setitem__('count', refreshed['count'] + 1)
    app._run_task = lambda _name, fn, on_done: on_done(fn(lambda _m: None))

    App._merge_backup_excel(app)

    assert refreshed['count'] == 1
    assert infos and infos[0][0] == '合并完成'
    assert any('备用文件合并完成' in msg for msg in app.logs)


def test_merge_backup_excel_no_rows_shows_info(monkeypatch):
    app = _mk_app_stub()
    app.excel_path.set('D:/root/records.xlsx')
    infos = []

    monkeypatch.setattr('handcontrol.app.filedialog.askopenfilename', lambda **kwargs: 'D:/root/records_刷机记录_待导入.xlsx')
    monkeypatch.setattr(
        'handcontrol.app.merge_backup_records',
        lambda **kwargs: {
            'ok': False,
            'code': 'no_rows',
            'message': '没有可合并的新行',
            'payload': {'merge_result': {'merged_count': 0, 'skipped_count': 3}},
        },
    )
    monkeypatch.setattr('handcontrol.app.messagebox.showinfo', lambda title, message: infos.append((title, message)))

    app._manual_refresh_preview = lambda: None
    app._run_task = lambda _name, fn, on_done: on_done(fn(lambda _m: None))

    App._merge_backup_excel(app)

    assert infos and infos[0][0] == '无需合并'
