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
        self.selected = None

    def delete(self, _start, _end):
        self.items = []

    def insert(self, _where, text):
        self.items.append(text)

    def itemconfig(self, idx, **kwargs):
        self.colors[idx] = kwargs

    def size(self):
        return len(self.items)

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

    def delete(self, _start, _end):
        self.value = ""

    def insert(self, _idx, text):
        self.value = text

    def get(self, _start, _end):
        return self.value


class FakeLabel:
    def __init__(self):
        self.text = ""

    def config(self, **kwargs):
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
    app.search_var = FakeVar("")
    app.folder_search_var = FakeVar("")
    app.folder_status_filter_var = FakeVar("全部状态")
    app.usb_combo = FakeCombo()
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
        "app.build_scan_result",
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
        "app.update_record_fields",
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

    monkeypatch.setattr("app.messagebox.askyesno", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        "app.delete_record",
        lambda *args, **kwargs: {"ok": True, "code": "ok", "message": "删除成功", "payload": {}},
    )

    app._run_task = lambda _name, fn, on_done: on_done(fn(lambda _m: None))

    App._delete_selected_preview_row(app)

    assert len(app._preview_rows) == 1
    assert app._preview_rows[0]["model"] == "L50S"
    assert app._preview_rows[0]["serial"] == "1"
