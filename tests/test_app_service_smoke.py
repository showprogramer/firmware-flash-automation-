import queue
import threading
import tkinter as tk
from pathlib import Path
import customtkinter as ctk
from handcontrol.ui.handcontrol_panel import HandcontrolPanel
from handcontrol.ui.music_panel import MusicPanel


class FakeVar:
    def __init__(self, value=""):
        self._value = value
    def get(self): return self._value
    def set(self, value): self._value = value
    def trace_add(self, *args, **kwargs): pass


class FakeWidget:
    def __init__(self, master=None, **kwargs):
        self.master = master
        self.text = kwargs.get("text", "")
        self.pack_count = 0
        self.pack_forget_count = 0
        self.grid_count = 0
        self.raise_count = 0
        self.bindings = {}
        for k, v in kwargs.items(): setattr(self, k, v)
    def configure(self, **kwargs):
        if "text" in kwargs: self.text = kwargs["text"]
        for k, v in kwargs.items(): setattr(self, k, v)
    def pack(self, **kwargs): self.pack_count += 1
    def pack_forget(self): self.pack_forget_count += 1
    def grid(self, **kwargs): self.grid_count += 1
    def grid_rowconfigure(self, *args, **kwargs): pass
    def grid_columnconfigure(self, *args, **kwargs): pass
    def tkraise(self): self.raise_count += 1
    def destroy(self): pass
    def winfo_children(self): return []
    def bind(self, event, handler, *args, **kwargs): self.bindings[event] = handler
    def pack_propagate(self, *args, **kwargs): pass


class FakeText:
    def __init__(self, **kwargs): self.value = ""
    def insert(self, _idx, text): self.value += text
    def see(self, _idx): pass
    def delete(self, _start, _end): self.value = ""
    def pack(self, **kwargs): pass


class FakeAppBase(FakeWidget):
    def title(self, _value): pass
    def geometry(self, _value): pass
    def minsize(self, *_args): pass


class FakeTree:
    def __init__(self, **kwargs):
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
        if values is not None: self.items[item_id]["values"] = list(values)
        if option == "values": return self.items[item_id]["values"]
        return self.items[item_id]
    def get_children(self): return list(self.order)
    def delete(self, item_id):
        self.items.pop(item_id, None)
        self.order = [x for x in self.order if x != item_id]
    def selection(self): return tuple(self.sel)
    def bind(self, *args, **kwargs): pass


def _mk_hand_stub(monkeypatch):
    # Monkeypatch ctk components to avoid real UI initialization
    monkeypatch.setattr(ctk, "CTkFrame", FakeWidget)
    monkeypatch.setattr(ctk, "CTkLabel", FakeWidget)
    monkeypatch.setattr(ctk, "CTkButton", FakeWidget)
    monkeypatch.setattr(ctk, "CTkEntry", FakeWidget)
    monkeypatch.setattr(ctk, "CTkComboBox", FakeWidget)
    monkeypatch.setattr(ctk, "CTkSegmentedButton", FakeWidget)
    monkeypatch.setattr(ctk, "CTkScrollableFrame", FakeWidget)
    monkeypatch.setattr(ctk, "CTkTabview", FakeWidget)
    monkeypatch.setattr(ctk, "CTkTextbox", FakeText)

    panel = HandcontrolPanel.__new__(HandcontrolPanel)
    panel.root_dir = FakeVar("D:/root")
    panel.excel_path = FakeVar("a.xlsx")
    panel.usb_drive = FakeVar("")
    panel.search_var = FakeVar("")
    panel.status_filter_var = FakeVar("全部状态")
    panel.sort_key_var = FakeVar("默认(名称)")
    panel.sort_asc_var = FakeVar(True)
    panel.field_logo = FakeVar("logo")
    panel.field_language = FakeVar("lang")
    panel.field_salesman = FakeVar("sale")
    panel.field_attachment = FakeVar("可通用")
    panel.review_status = FakeVar("测试通过")
    panel.preview_search_var = FakeVar("")
    panel.folders = []
    panel._all_folders = []
    panel._folder_status_map = {}
    panel._preview_rows = []
    panel._editing_preview_key = None
    panel._selected_idx = -1
    panel._task_queue = queue.Queue()
    panel._busy = False
    panel.manual_open = False
    
    # UI stubs
    panel.list_scroll = FakeWidget()
    panel.header_model_label = FakeWidget(text="-")
    panel.header_version_badge = FakeWidget(text="-")
    panel.header_status_badge = FakeWidget(text="未选择")
    panel.usb_menu = FakeWidget()
    panel.remark_entry = FakeText()
    panel.preview_tree = FakeTree()
    panel.log_text = FakeText()
    panel.after = lambda _ms, _fn: None
    panel._folder_card_widgets = []
    
    panel._log = lambda msg: panel.log_text.insert("end", str(msg))
    return panel


def test_hand_scan_uses_service_result(monkeypatch):
    panel = _mk_hand_stub(monkeypatch)
    monkeypatch.setattr(
        "handcontrol.ui.handcontrol_panel.build_scan_result",
        lambda *args, **kwargs: {
            "ok": True,
            "payload": {
                "folders": [{"model": "L36", "version": "V1.0.0", "path": "D:/a"}],
                "status_map": {("L36", "V1.0.0"): "测试通过"}
            }
        }
    )
    panel._run_task = lambda _name, fn, on_done: on_done(fn(panel._log))
    
    panel._scan()
    
    assert len(panel.folders) == 1
    assert panel.folders[0]["model"] == "L36"


def test_choose_root_and_scan_always_opens_directory_picker(monkeypatch):
    panel = _mk_hand_stub(monkeypatch)
    called = {"scan": 0}

    monkeypatch.setattr(
        "handcontrol.ui.handcontrol_panel.filedialog.askdirectory",
        lambda **kwargs: "D:/new-root",
    )
    panel._scan = lambda: called.__setitem__("scan", called["scan"] + 1)

    panel._choose_root_and_scan()

    assert panel.root_dir.get() == "D:/new-root"
    assert called["scan"] == 1


def test_hand_filter_folders_by_keyword(monkeypatch):
    panel = _mk_hand_stub(monkeypatch)
    panel._all_folders = [
        {"model": "L36", "version": "V1.0.0", "path": "D:/a"},
        {"model": "L50S", "version": "V2.0.0", "path": "D:/b"}
    ]
    panel.search_var.set("L50")
    
    panel._filter_folders()
    
    assert len(panel.folders) == 1
    assert panel.folders[0]["model"] == "L50S"


def test_hand_default_sort_matches_natural_explorer_like_order(monkeypatch):
    panel = _mk_hand_stub(monkeypatch)
    panel._all_folders = [
        {"model": "L100", "version": "V1.0.0", "path": "D:/root/L100"},
        {"model": "L20", "version": "V1.0.0", "path": "D:/root/L20"},
        {"model": "L3", "version": "V1.0.0", "path": "D:/root/L3"},
    ]

    panel._filter_folders()

    assert [item["path"] for item in panel.folders] == ["D:/root/L3", "D:/root/L20", "D:/root/L100"]


def test_hand_select_folder_updates_ui(monkeypatch):
    panel = _mk_hand_stub(monkeypatch)
    panel.folders = [{"model": "L36", "version": "V1.0.0", "path": "D:/a"}]
    
    # Mock load_excel_row
    import handcontrol.ui.handcontrol_panel as hp
    monkeypatch.setattr(hp, "load_excel_row", lambda *args: {"logo": "NEW", "language": "CN"})
    
    panel._select_folder(0)
    assert panel.field_logo.get() == "NEW"
    assert panel.header_model_label.text == "L36"


def test_hand_select_folder_does_not_rebuild_full_card_list(monkeypatch):
    panel = _mk_hand_stub(monkeypatch)
    panel.folders = [
        {"model": "L36", "version": "V1.0.0", "path": "D:/a"},
        {"model": "L50S", "version": "V2.0.0", "path": "D:/b"},
    ]
    panel._render_folder_cards()
    original_refs = [widgets["card"] for widgets in panel._folder_card_widgets]

    import handcontrol.ui.handcontrol_panel as hp
    monkeypatch.setattr(hp, "load_excel_row", lambda *args: {})

    panel._select_folder(1)

    assert [widgets["card"] for widgets in panel._folder_card_widgets] == original_refs


def test_hand_preview_double_click_restores_remark_and_status(monkeypatch):
    panel = _mk_hand_stub(monkeypatch)
    item_id = panel.preview_tree.insert(
        "",
        "end",
        values=["1", "L36", "中性", "张三", "中、英", "V1.0.0", "2026-04-17", "可通用", "待确认"],
    )
    panel.preview_tree.sel = [item_id]

    panel._on_preview_double_click()

    assert panel._editing_preview_key == ("L36", "V1.0.0")
    assert panel.remark_entry.value == "待确认"
    assert panel.review_status.get() == "待确认"


def test_hand_double_click_opens_selected_folder(monkeypatch):
    panel = _mk_hand_stub(monkeypatch)
    panel.folders = [{"model": "L36", "version": "V1.0.0", "path": "D:/a"}]
    panel._render_folder_cards()
    opened = []

    monkeypatch.setattr("handcontrol.ui.handcontrol_panel.Path.exists", lambda _self: True)
    monkeypatch.setattr("handcontrol.ui.handcontrol_panel.os.startfile", lambda path: opened.append(path), raising=False)

    handler = panel._folder_card_widgets[0]["card"].bindings["<Double-Button-1>"]
    handler(None)

    assert opened


def test_music_scan_ports_updates_ui(monkeypatch):
    monkeypatch.setattr(ctk, "CTkFrame", FakeWidget)
    monkeypatch.setattr(ctk, "CTkLabel", FakeWidget)
    monkeypatch.setattr(ctk, "CTkScrollableFrame", FakeWidget)
    monkeypatch.setattr(ctk, "CTkComboBox", FakeWidget)
    
    # Mock MusicPanel
    panel = MusicPanel.__new__(MusicPanel)
    panel.serial_port = FakeVar("")
    panel.serial_menu = FakeWidget()
    panel.port_list_frame = FakeWidget()
    panel.log_text = FakeText()
    panel._log = lambda msg: None
    
    monkeypatch.setattr(
        "handcontrol.ui.music_panel.scan_serial_ports",
        lambda **kwargs: {"ok": True, "payload": {"ports": [{"device": "COM1", "description": "X"}]}}
    )
    
    MusicPanel._scan_ports(panel)
    assert panel.serial_port.get() == "COM1 X"


def test_music_pollers_skip_when_deactivated(monkeypatch):
    panel = MusicPanel.__new__(MusicPanel)
    panel._polling_active = False
    panel._task_queue = queue.Queue()
    panel._connected = True
    panel._serial_conn = object()
    panel.after = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not schedule"))
    panel._log = lambda msg: None

    called = {"serial": 0}
    monkeypatch.setattr(
        "handcontrol.ui.music_panel.read_serial_messages",
        lambda *args, **kwargs: called.__setitem__("serial", called["serial"] + 1),
    )

    MusicPanel._poll_task_queue(panel)
    MusicPanel._poll_serial_messages(panel)

    assert called["serial"] == 0


def test_hand_pollers_skip_when_deactivated(monkeypatch):
    panel = _mk_hand_stub(monkeypatch)
    panel._polling_active = False
    panel._task_queue.put(("done", "任务", {}, None))
    panel.after = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not schedule"))

    HandcontrolPanel._poll_task_queue(panel)

    assert panel._busy is False


def test_one_click_runs_service(monkeypatch):
    panel = _mk_hand_stub(monkeypatch)
    panel._selected_idx = 0
    panel.folders = [{"model": "L36", "version": "V1.0.0", "path": "D:/a", "rom_file": "r", "pkg_file": "p"}]
    panel.usb_drive.set("E:\\")
    
    called = {"one_click": False}
    def mock_one_click(*args, **kwargs):
        called["one_click"] = True
        return {"ok": True, "payload": {"copy_ok": True}}
    
    monkeypatch.setattr("handcontrol.ui.handcontrol_panel.run_one_click", mock_one_click)
    panel._run_task = lambda _name, fn, on_done: on_done(fn(panel._log))
    
    panel._one_click()
    assert called["one_click"] is True


def test_shell_lazy_creates_music_panel_and_activates_visible_panel(monkeypatch):
    import handcontrol.ui.shell as shell_module

    monkeypatch.setattr(ctk, "CTk", FakeAppBase)
    monkeypatch.setattr(ctk, "CTkFrame", FakeWidget)
    monkeypatch.setattr(shell_module, "apply_treeview_modern_style", lambda: None)

    class FakeHandPanel(FakeWidget):
        def __init__(self, master, switch_view):
            super().__init__(master)
            self.switch_view = switch_view
            self.activate_count = 0
            self.deactivate_count = 0
            self.synced_modes = []
        def activate(self):
            self.activate_count += 1
        def deactivate(self):
            self.deactivate_count += 1
        def sync_mode_switch(self, mode):
            self.synced_modes.append(mode)

    class FakeMusicPanel(FakeWidget):
        instances = 0
        def __init__(self, master, switch_view):
            super().__init__(master)
            self.switch_view = switch_view
            self.activate_count = 0
            self.deactivate_count = 0
            self.synced_modes = []
            FakeMusicPanel.instances += 1
        def activate(self):
            self.activate_count += 1
        def deactivate(self):
            self.deactivate_count += 1
        def sync_mode_switch(self, mode):
            self.synced_modes.append(mode)

    monkeypatch.setattr(shell_module, "HandcontrolPanel", FakeHandPanel)
    monkeypatch.setattr(shell_module, "MusicPanel", FakeMusicPanel)

    app = shell_module.UnifiedFlashPlatform()

    assert app.music_panel is None
    assert app.hand_panel.grid_count == 1
    assert app.hand_panel.activate_count == 1
    assert app.hand_panel.synced_modes[-1] == "handcontrol"
    assert app.hand_panel.raise_count == 1
    app.switch_view("music")
    assert FakeMusicPanel.instances == 1
    assert app.music_panel.grid_count == 1
    assert app.music_panel.raise_count == 1
    assert app.music_panel.activate_count == 1
    assert app.hand_panel.deactivate_count == 1
    assert app.hand_panel.synced_modes[-1] == "music"
    assert app.music_panel.synced_modes[-1] == "music"

    app.switch_view("handcontrol")
    assert app.music_panel.deactivate_count == 1
    assert app.hand_panel.activate_count == 2
    assert app.hand_panel.raise_count == 2
    assert app.hand_panel.synced_modes[-1] == "handcontrol"
    assert app.music_panel.synced_modes[-1] == "handcontrol"
