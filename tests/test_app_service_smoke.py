import queue
from pathlib import Path

import customtkinter as ctk

from fwasset.ui.firmware_list_panel import FirmwareListPanel
from fwasset.ui.serial_control import SerialControl


class FakeVar:
    def __init__(self, value=""):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value

    def trace_add(self, *args, **kwargs):
        pass


class FakeWidget:
    def __init__(self, master=None, **kwargs):
        self.master = master
        self.text = kwargs.get("text", "")
        self.values = kwargs.get("values", [])
        self.pack_count = 0
        self.grid_count = 0
        self.raise_count = 0
        self.bindings = {}
        for key, value in kwargs.items():
            setattr(self, key, value)

    def configure(self, **kwargs):
        if "text" in kwargs:
            self.text = kwargs["text"]
        if "values" in kwargs:
            self.values = kwargs["values"]
        for key, value in kwargs.items():
            setattr(self, key, value)

    def pack(self, **kwargs):
        self.pack_count += 1

    def grid(self, **kwargs):
        self.grid_count += 1

    def grid_rowconfigure(self, *args, **kwargs):
        pass

    def grid_columnconfigure(self, *args, **kwargs):
        pass

    def grid_propagate(self, *args, **kwargs):
        pass

    def pack_propagate(self, *args, **kwargs):
        pass

    def tkraise(self):
        self.raise_count += 1

    def destroy(self):
        pass

    def winfo_children(self):
        return []

    def bind(self, event, handler, *args, **kwargs):
        self.bindings[event] = handler


class FakeText:
    def __init__(self, **kwargs):
        self.value = ""

    def insert(self, _idx, text):
        self.value += text

    def see(self, _idx):
        pass

    def delete(self, _start, _end):
        self.value = ""

    def pack(self, **kwargs):
        pass


class FakeAppBase(FakeWidget):
    def title(self, _value):
        pass

    def geometry(self, _value):
        pass

    def minsize(self, *_args):
        pass


def _patch_ctk(monkeypatch):
    monkeypatch.setattr(ctk, "CTkFrame", FakeWidget)
    monkeypatch.setattr(ctk, "CTkLabel", FakeWidget)
    monkeypatch.setattr(ctk, "CTkButton", FakeWidget)
    monkeypatch.setattr(ctk, "CTkEntry", FakeWidget)
    monkeypatch.setattr(ctk, "CTkComboBox", FakeWidget)
    monkeypatch.setattr(ctk, "CTkOptionMenu", FakeWidget)
    monkeypatch.setattr(ctk, "CTkScrollableFrame", FakeWidget)
    monkeypatch.setattr(ctk, "CTkTextbox", FakeText)
    monkeypatch.setattr(ctk, "CTkCheckBox", FakeWidget)


def _mk_asset_stub(monkeypatch):
    _patch_ctk(monkeypatch)
    panel = FirmwareListPanel.__new__(FirmwareListPanel)
    panel.root_dir = FakeVar("D:/root")
    panel.usb_drive = FakeVar("")
    panel.search_var = FakeVar("")
    panel.sort_key_var = FakeVar("默认(名称)")
    panel.sort_asc_var = FakeVar(True)
    panel.type_filter_vars = {
        "handcontrol_ui": FakeVar(True),
        "music_bt": FakeVar(True),
    }
    panel.assets = []
    panel.folders = []
    panel._all_assets = []
    panel._selected_idx = -1
    panel._task_queue = queue.Queue()
    panel._busy = False
    panel._polling_active = False
    panel.list_scroll = FakeWidget()
    panel.ops_body = FakeWidget()
    panel.usb_menu = FakeWidget()
    panel.log_text = FakeText()
    panel.after = lambda _ms, _fn: None
    panel._asset_card_widgets = []
    panel.serial_control = None
    panel.header_model_label = FakeWidget(text="-")
    panel.header_version_badge = FakeWidget(text="-")
    panel.header_type_badge = FakeWidget(text="未选择")
    panel.detail_values = {
        key: FakeWidget(text="-")
        for key in ["model", "version", "firmware_type", "flash_mode", "directory_name", "path", "files", "modified_time"]
    }
    panel._log = lambda msg: panel.log_text.insert("end", str(msg))
    return panel


def test_asset_scan_uses_service_assets(monkeypatch):
    panel = _mk_asset_stub(monkeypatch)
    monkeypatch.setattr(
        "fwasset.ui.firmware_list_panel.build_scan_result",
        lambda *args, **kwargs: {
            "ok": True,
            "payload": {
                "assets": [
                    {
                        "model": "L36",
                        "version": "V1.0.0",
                        "path": "D:/a",
                        "directory_name": "a",
                        "firmware_type": "handcontrol_ui",
                        "firmware_label": "手控UI",
                        "flash_mode": "auto_usb",
                        "files": ["ui.rom", "ui.pkg"],
                        "modified_time": 0,
                    }
                ]
            },
        },
    )
    panel._run_task = lambda _name, fn, on_done: on_done(fn(panel._log))

    panel._scan()

    assert len(panel.assets) == 1
    assert panel.assets[0]["model"] == "L36"


def test_choose_root_and_scan_always_opens_directory_picker(monkeypatch):
    panel = _mk_asset_stub(monkeypatch)
    called = {"scan": 0}
    monkeypatch.setattr("fwasset.ui.firmware_list_panel.filedialog.askdirectory", lambda **kwargs: "D:/new-root")
    panel._scan = lambda: called.__setitem__("scan", called["scan"] + 1)

    panel._choose_root_and_scan()

    assert panel.root_dir.get() == "D:/new-root"
    assert called["scan"] == 1


def test_asset_filter_supports_keyword_and_type(monkeypatch):
    panel = _mk_asset_stub(monkeypatch)
    panel._all_assets = [
        {
            "model": "L36",
            "version": "V1.0.0",
            "path": "D:/a",
            "directory_name": "手控目录",
            "firmware_type": "handcontrol_ui",
            "firmware_label": "手控UI",
            "flash_mode": "auto_usb",
            "files": ["ui.rom", "ui.pkg"],
            "modified_time": 0,
        },
        {
            "model": "L50S",
            "version": "V2.0.0",
            "path": "D:/b",
            "directory_name": "蓝牙目录",
            "firmware_type": "music_bt",
            "firmware_label": "蓝牙程序",
            "flash_mode": "auto_usb",
            "files": ["song.mp3"],
            "modified_time": 0,
        },
    ]
    panel.search_var.set("L50")
    panel.type_filter_vars["handcontrol_ui"].set(False)

    panel._filter_assets()

    assert len(panel.assets) == 1
    assert panel.assets[0]["firmware_type"] == "music_bt"


def test_asset_default_sort_matches_natural_explorer_like_order(monkeypatch):
    panel = _mk_asset_stub(monkeypatch)
    panel._all_assets = [
        {"model": "L100", "version": "V1.0.0", "path": "D:/root/L100", "directory_name": "L100", "firmware_type": "handcontrol_ui", "firmware_label": "手控UI", "flash_mode": "auto_usb", "files": [], "modified_time": 0},
        {"model": "L20", "version": "V1.0.0", "path": "D:/root/L20", "directory_name": "L20", "firmware_type": "handcontrol_ui", "firmware_label": "手控UI", "flash_mode": "auto_usb", "files": [], "modified_time": 0},
        {"model": "L3", "version": "V1.0.0", "path": "D:/root/L3", "directory_name": "L3", "firmware_type": "handcontrol_ui", "firmware_label": "手控UI", "flash_mode": "auto_usb", "files": [], "modified_time": 0},
    ]

    panel._filter_assets()

    assert [item["path"] for item in panel.assets] == ["D:/root/L3", "D:/root/L20", "D:/root/L100"]


def test_asset_select_updates_detail_panel(monkeypatch):
    panel = _mk_asset_stub(monkeypatch)
    panel.assets = [
        {
            "model": "L36",
            "version": "V1.0.0",
            "path": "D:/a",
            "directory_name": "a",
            "firmware_type": "handcontrol_ui",
            "firmware_label": "手控UI",
            "flash_mode": "auto_usb",
            "files": ["ui.rom", "ui.pkg"],
            "modified_time": 0,
        }
    ]

    panel._select_asset(0)

    assert panel.header_model_label.text == "L36"
    assert panel.detail_values["firmware_type"].text == "手控UI"
    assert panel.header_type_badge.text == "手控UI"


def test_asset_select_does_not_rebuild_full_card_list(monkeypatch):
    panel = _mk_asset_stub(monkeypatch)
    panel.assets = [
        {"model": "L36", "version": "V1.0.0", "path": "D:/a", "directory_name": "a", "firmware_type": "handcontrol_ui", "firmware_label": "手控UI", "flash_mode": "auto_usb", "files": ["ui.rom", "ui.pkg"], "modified_time": 0},
        {"model": "L50S", "version": "V2.0.0", "path": "D:/b", "directory_name": "b", "firmware_type": "music_bt", "firmware_label": "蓝牙程序", "flash_mode": "auto_usb", "files": ["song.mp3"], "modified_time": 0},
    ]
    panel._render_asset_cards()
    original_refs = [widgets["card"] for widgets in panel._asset_card_widgets]

    panel._select_asset(1)

    assert [widgets["card"] for widgets in panel._asset_card_widgets] == original_refs


def test_asset_double_click_opens_selected_folder(monkeypatch):
    panel = _mk_asset_stub(monkeypatch)
    panel.assets = [
        {"model": "L36", "version": "V1.0.0", "path": "D:/a", "directory_name": "a", "firmware_type": "handcontrol_ui", "firmware_label": "手控UI", "flash_mode": "auto_usb", "files": ["ui.rom", "ui.pkg"], "modified_time": 0}
    ]
    panel._render_asset_cards()
    opened = []
    monkeypatch.setattr("fwasset.ui.firmware_list_panel.Path.exists", lambda _self: True)
    monkeypatch.setattr("fwasset.ui.firmware_list_panel.os.startfile", lambda path: opened.append(path), raising=False)

    handler = panel._asset_card_widgets[0]["card"].bindings["<Double-Button-1>"]
    handler(None)

    assert opened


def test_panel_pollers_skip_when_deactivated(monkeypatch):
    panel = _mk_asset_stub(monkeypatch)
    panel._polling_active = False
    panel._task_queue.put(("done", "任务", {}, None))
    panel.after = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not schedule"))

    FirmwareListPanel._poll_task_queue(panel)

    assert panel._busy is False


def test_handcontrol_one_click_runs_service(monkeypatch):
    panel = _mk_asset_stub(monkeypatch)
    panel._selected_idx = 0
    panel.assets = [
        {"model": "L36", "version": "V1.0.0", "path": "D:/a", "directory_name": "a", "firmware_type": "handcontrol_ui", "firmware_label": "手控UI", "flash_mode": "auto_usb", "files": ["r.rom", "p.pkg"], "modified_time": 0}
    ]
    panel.usb_drive.set("E:\\")
    called = {"one_click": False}

    def mock_one_click(*args, **kwargs):
        called["one_click"] = True
        return {"ok": True, "payload": {"copy_ok": True}}

    monkeypatch.setattr("fwasset.ui.firmware_list_panel.run_one_click", mock_one_click)
    panel._run_task = lambda _name, fn, on_done=None: fn(panel._log)

    panel._one_click_handcontrol()

    assert called["one_click"] is True


def test_directory_flash_runs_music_service(monkeypatch):
    panel = _mk_asset_stub(monkeypatch)
    panel._selected_idx = 0
    panel.assets = [
        {"model": "L50S", "version": "V2.0.0", "path": "D:/music", "directory_name": "music", "firmware_type": "music_bt", "firmware_label": "蓝牙程序", "flash_mode": "auto_usb", "files": ["song.mp3"], "modified_time": 0}
    ]
    panel.usb_drive.set("E:\\")
    panel.format_first = FakeVar(True)
    panel.eject_after = FakeVar(False)
    called = {"music": False}

    def mock_music_flash(*args, **kwargs):
        called["music"] = True
        return {"ok": True, "message": "done"}

    monkeypatch.setattr("fwasset.ui.firmware_list_panel.run_music_flash", mock_music_flash)
    panel._run_task = lambda _name, fn, on_done=None: (on_done(fn(panel._log)) if on_done else fn(panel._log))

    panel._run_directory_flash()

    assert called["music"] is True


def test_copy_handoff_paths_to_clipboard(monkeypatch):
    panel = _mk_asset_stub(monkeypatch)
    panel._selected_idx = 0
    panel.assets = [
        {
            "model": "L36",
            "version": "V1.0.0",
            "path": "D:/fw/L36",
            "directory_name": "L36",
            "firmware_type": "mainboard",
            "firmware_label": "主板程序",
            "flash_mode": "tool_launch",
            "files": ["readme.txt", "main.bin"],
            "modified_time": 0,
        }
    ]
    copied = []
    panel.clipboard_clear = lambda: copied.clear()
    panel.clipboard_append = lambda text: copied.append(text)

    panel._copy_asset_dir_path()
    assert copied == ["D:/fw/L36"]

    panel._copy_primary_file_path()
    assert Path(copied[0]) == Path("D:/fw/L36/main.bin")


def test_tool_launch_combo_opens_tool_and_asset_dir(monkeypatch):
    panel = _mk_asset_stub(monkeypatch)
    panel._selected_idx = 0
    panel.assets = [
        {"model": "L36", "version": "V1.0.0", "path": "D:/fw/L36", "directory_name": "L36", "firmware_type": "mainboard", "firmware_label": "主板程序", "flash_mode": "tool_launch", "files": ["main.bin"], "modified_time": 0}
    ]
    calls = []
    panel._launch_current_tool = lambda: calls.append("tool")
    panel._open_current_asset_dir = lambda: calls.append("dir")

    panel._launch_tool_and_open_asset_dir()

    assert calls == ["tool", "dir"]


def test_operation_panel_renders_manual_and_disabled_modes(monkeypatch):
    panel = _mk_asset_stub(monkeypatch)
    built = []
    panel._build_manual_doc_ops = lambda asset: built.append(("manual", asset["firmware_type"]))
    panel._build_disabled_ops = lambda asset: built.append(("disabled", asset["firmware_type"]))

    panel._render_operation_panel(
        {"model": "L1", "version": "V1", "path": "D:/a", "directory_name": "a", "firmware_type": "seat_occupancy", "firmware_label": "占座提醒", "flash_mode": "manual_doc", "files": [], "modified_time": 0}
    )
    panel._render_operation_panel(
        {"model": "L2", "version": "V1", "path": "D:/b", "directory_name": "b", "firmware_type": "aging", "firmware_label": "老化程序", "flash_mode": "disabled", "files": [], "modified_time": 0}
    )

    assert built == [("manual", "seat_occupancy"), ("disabled", "aging")]


def test_serial_control_scan_ports_updates_ui(monkeypatch):
    _patch_ctk(monkeypatch)
    control = SerialControl.__new__(SerialControl)
    control.serial_port = FakeVar("")
    control.serial_menu = FakeWidget()
    control._log = lambda msg: None

    monkeypatch.setattr(
        "fwasset.ui.serial_control.scan_serial_ports",
        lambda **kwargs: {"ok": True, "payload": {"ports": [{"device": "COM1", "description": "X"}]}},
    )

    SerialControl._scan_ports(control)

    assert control.serial_port.get() == "COM1 X"


def test_serial_control_pollers_skip_when_deactivated(monkeypatch):
    control = SerialControl.__new__(SerialControl)
    control._polling_active = False
    control._connected = True
    control._serial_conn = object()
    control.after = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not schedule"))
    control._log = lambda msg: None
    called = {"serial": 0}
    monkeypatch.setattr(
        "fwasset.ui.serial_control.read_serial_messages",
        lambda *args, **kwargs: called.__setitem__("serial", called["serial"] + 1),
    )

    SerialControl._poll_serial_messages(control)

    assert called["serial"] == 0


def test_shell_hosts_single_asset_panel(monkeypatch):
    import fwasset.ui.shell as shell_module

    monkeypatch.setattr(ctk, "CTk", FakeAppBase)
    monkeypatch.setattr(ctk, "CTkFrame", FakeWidget)
    monkeypatch.setattr(shell_module, "apply_treeview_modern_style", lambda: None)

    class FakeAssetPanel(FakeWidget):
        def __init__(self, master):
            super().__init__(master)
            self.activate_count = 0

        def activate(self):
            self.activate_count += 1

    monkeypatch.setattr(shell_module, "FirmwareListPanel", FakeAssetPanel)

    app = shell_module.UnifiedFlashPlatform()

    assert app.asset_panel.grid_count == 1
    assert app.asset_panel.activate_count == 1
