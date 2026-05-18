import queue
import threading
from pathlib import Path

import customtkinter as ctk
import pytest

from fwasset.ui.firmware_list_panel import FirmwareListPanel
from fwasset.core.sort_config import SortKey, apply_sort
from fwasset.ui.view_models.tree_expansion_model import TreeExpansionModel

pytestmark = pytest.mark.ui


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


class FakeAssetTree:
    def __init__(self, *, on_select_asset=None, on_open_asset=None, on_context_menu=None):
        self.populate_calls = []
        self.focused = []
        self.on_select_asset = on_select_asset
        self.on_open_asset = on_open_asset
        self.on_context_menu = on_context_menu

    def populate(self, groups, assets, expanded_keys, selected_idx, hidden_indices=None):
        self.populate_calls.append(
            {
                "groups": groups,
                "assets": assets,
                "expanded_keys": set(expanded_keys) if not isinstance(expanded_keys, set) else expanded_keys,
                "selected_idx": selected_idx,
                "hidden_indices": set(hidden_indices or set()),
            }
        )

    def focus_asset(self, idx):
        self.focused.append(idx)

    def select_asset(self, idx):
        if self.on_select_asset:
            self.on_select_asset(idx)

    def double_click_asset(self, idx):
        if self.on_open_asset:
            self.on_open_asset(idx)

    def context_menu(self, event, path, hide_type):
        if self.on_context_menu:
            self.on_context_menu(event, path, hide_type)


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
    panel.show_hidden_var = FakeVar(False)
    panel.type_filter_vars = {
        "handcontrol_ui": FakeVar(True),
        "music_bt": FakeVar(True),
        "music_files": FakeVar(True),
    }
    panel.type_quick_var = FakeVar("全部类型")
    panel._type_label_to_key = {"手控UI": "handcontrol_ui", "蓝牙程序": "music_bt", "音乐文件": "music_files", "主板程序": "mainboard"}
    panel.assets = []
    panel._has_index_assets = False
    panel._selected_idx = -1
    panel._task_queue = queue.Queue()
    panel._busy = False
    panel._polling_active = False
    panel._tree_expansion = TreeExpansionModel()
    panel._hidden_items = {}
    panel._scan_cancel_event = None
    panel.list_scroll = FakeWidget()
    panel.asset_tree = FakeAssetTree(
        on_select_asset=lambda idx: panel._select_asset(idx),
        on_open_asset=lambda idx: panel._open_asset_path(idx),
        on_context_menu=lambda event, path, hide_type: panel._show_hidden_context_menu(event, path, hide_type),
    )
    panel._empty_list_hint = None
    panel.ops_body = FakeWidget()
    panel.usb_menu = FakeWidget()
    panel.header_bar = FakeWidget()
    panel.header_bar.update_from_asset_calls = []
    _orig_update = lambda asset=None: None

    def _header_update(asset=None):
        panel.header_bar.update_from_asset_calls.append(asset or {})
    panel.header_bar.update_from_asset = _header_update
    panel.header_bar.clear = lambda: None
    panel.log_panel = FakeWidget()
    panel.log_panel.write = lambda msg: None
    panel.after = lambda _ms, _fn: None
    panel._asset_card_widgets = []
    panel._log = lambda msg: None
    panel._render_operation_panel = lambda asset: None

    return panel


def _patch_query_assets(monkeypatch, panel, assets):
    items = list(assets)
    panel._has_index_assets = bool(items)
    calls = []

    def fake_query_assets(keyword="", firmware_types=None, sort_key=SortKey.PATH, ascending=True, **_kwargs):
        calls.append(
            {
                "keyword": keyword,
                "firmware_types": set(firmware_types or []),
                "sort_key": sort_key,
                "ascending": ascending,
            }
        )
        selected_types = set(firmware_types or [])
        filtered = [item for item in items if not selected_types or item.get("firmware_type") in selected_types]
        if keyword:
            needle = str(keyword).strip().lower()
            filtered = [
                item
                for item in filtered
                if needle
                in " ".join(
                    [
                        str(item.get("model", "") or ""),
                        str(item.get("series", "") or ""),
                        str(item.get("version", "") or ""),
                        str(item.get("firmware_label", "") or ""),
                        str(item.get("model_directory_name", "") or ""),
                        str(item.get("directory_name", "") or ""),
                        str(item.get("path", "") or ""),
                        str(item.get("flash_mode", "") or ""),
                    ]
                ).lower()
            ]
        try:
            selected_sort_key = SortKey(sort_key)
        except ValueError:
            selected_sort_key = SortKey.PATH
        return apply_sort(filtered, sort_key=selected_sort_key, ascending=ascending)

    monkeypatch.setattr("fwasset.ui.view_models.asset_filter_model.query_assets", fake_query_assets)
    return calls


def test_asset_scan_uses_service_assets(monkeypatch):
    panel = _mk_asset_stub(monkeypatch)
    assets = [
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
    _patch_query_assets(monkeypatch, panel, assets)
    monkeypatch.setattr(
        "fwasset.ui.firmware_list_panel.build_scan_result",
        lambda *args, **kwargs: {
            "ok": True,
            "payload": {
                "assets": assets
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


def test_scan_button_click_cancels_running_scan_without_directory_picker(monkeypatch):
    panel = _mk_asset_stub(monkeypatch)
    panel._scan_cancel_event = threading.Event()
    called = {"scan": 0}
    monkeypatch.setattr(
        "fwasset.ui.firmware_list_panel.filedialog.askdirectory",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("directory picker should not open")),
    )

    def fake_scan():
        called["scan"] += 1
        panel._scan_cancel_event.set()

    panel._scan = fake_scan

    panel._on_scan_button_click()

    assert called["scan"] == 1
    assert panel._scan_cancel_event.is_set()


def test_scan_worker_uses_original_cancel_event_after_panel_state_changes(monkeypatch):
    panel = _mk_asset_stub(monkeypatch)
    panel.scan_btn = FakeWidget(text="scan")
    seen = {}

    def fake_build_scan_result(root, log_fn, cancel_event):
        seen["cancel_event"] = cancel_event
        return {"ok": True, "payload": {"assets": []}}

    def fake_run_task(_name, work_fn, done_fn):
        original_event = panel._scan_cancel_event
        panel._scan_cancel_event = None
        result = work_fn(panel._log)
        done_fn(result)
        seen["original_event"] = original_event

    monkeypatch.setattr("fwasset.ui.firmware_list_panel.build_scan_result", fake_build_scan_result)
    panel._run_task = fake_run_task

    panel._scan()

    assert seen["cancel_event"] is seen["original_event"]


def test_single_type_filter_and_clear_keep_type_selection_explicit(monkeypatch):
    panel = _mk_asset_stub(monkeypatch)
    panel.type_filter_vars["mainboard"] = FakeVar(False)
    called = {"count": 0}
    panel._filter_assets = lambda: called.__setitem__("count", called["count"] + 1)

    panel._select_single_type_filter("主板程序")

    assert panel.type_filter_vars["handcontrol_ui"].get() is False
    assert panel.type_filter_vars["music_bt"].get() is False
    assert panel.type_filter_vars["music_files"].get() is False
    assert panel.type_filter_vars["mainboard"].get() is True
    assert panel._tree_expansion.expanded == set()
    assert called["count"] == 1

    panel._tree_expansion.mark_open("series|L36")
    panel._clear_type_filters()

    assert all(var.get() is False for var in panel.type_filter_vars.values())
    assert panel.type_quick_var.get() == "先选择固件类型"
    assert panel._tree_expansion.expanded == set()
    assert called["count"] == 2

    panel.type_filter_vars["mainboard"].set(True)
    panel._select_single_type_filter("先选择固件类型")

    assert all(var.get() is False for var in panel.type_filter_vars.values())
    assert called["count"] == 3


def test_hidden_model_directory_is_filtered_until_show_hidden(monkeypatch):
    panel = _mk_asset_stub(monkeypatch)
    panel.type_filter_vars["mainboard"] = FakeVar(True)
    _patch_query_assets(monkeypatch, panel, [
        {
            "series": "L36",
            "model": "L36",
            "version": "V1.0.0",
            "path": "D:/root/L36配置/主板/V1",
            "directory_name": "V1",
            "model_directory_name": "L36配置",
            "model_directory_path": "D:/root/L36配置",
            "firmware_type": "mainboard",
            "firmware_label": "主板程序",
            "flash_mode": "tool_launch",
            "files": ["main.bin"],
            "modified_time": 0,
        }
    ])
    panel._hidden_items = {"D:/root/L36配置": "model_directory"}

    panel._filter_assets()
    assert panel.assets == []

    panel.show_hidden_var.set(True)
    panel._filter_assets()
    assert len(panel.assets) == 1
    assert panel.asset_tree.populate_calls[-1]["hidden_indices"] == {0}


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

    last_asset = panel.header_bar.update_from_asset_calls[-1]
    assert last_asset.get("model") == "L36"
    assert last_asset.get("firmware_label") == "手控UI"


def test_asset_select_does_not_rebuild_full_card_list(monkeypatch):
    panel = _mk_asset_stub(monkeypatch)
    panel.assets = [
        {"model": "L36", "version": "V1.0.0", "path": "D:/a", "directory_name": "a", "firmware_type": "handcontrol_ui", "firmware_label": "手控UI", "flash_mode": "auto_usb", "files": ["ui.rom", "ui.pkg"], "modified_time": 0},
        {"model": "L50S", "version": "V2.0.0", "path": "D:/b", "directory_name": "b", "firmware_type": "music_files", "firmware_label": "音乐文件", "flash_mode": "auto_usb", "files": ["song.mp3"], "modified_time": 0},
    ]
    panel._render_asset_tree()
    original_populate_count = len(panel.asset_tree.populate_calls)

    panel._select_asset(1)

    assert len(panel.asset_tree.populate_calls) == original_populate_count
    assert panel.asset_tree.focused[-1] == 1


def test_asset_double_click_opens_selected_folder(monkeypatch):
    panel = _mk_asset_stub(monkeypatch)
    panel.assets = [
        {"model": "L36", "version": "V1.0.0", "path": "D:/a", "directory_name": "a", "firmware_type": "handcontrol_ui", "firmware_label": "手控UI", "flash_mode": "auto_usb", "files": ["ui.rom", "ui.pkg"], "modified_time": 0}
    ]
    panel._render_asset_tree()
    opened = []
    monkeypatch.setattr("fwasset.ui.firmware_list_panel.Path.exists", lambda _self: True)
    monkeypatch.setattr("fwasset.ui.firmware_list_panel.os.startfile", lambda path: opened.append(path), raising=False)

    panel.asset_tree.double_click_asset(0)

    assert opened


def test_asset_tree_context_menu_callback_keeps_hide_metadata(monkeypatch):
    panel = _mk_asset_stub(monkeypatch)
    calls = []
    panel._show_hidden_context_menu = lambda event, path, hide_type: calls.append((path, hide_type))

    panel.asset_tree.context_menu(object(), "D:/root/L36配置", "model_directory")

    assert calls == [("D:/root/L36配置", "model_directory")]


def test_panel_pollers_skip_when_deactivated(monkeypatch):
    panel = _mk_asset_stub(monkeypatch)
    panel._polling_active = False
    panel._task_queue.put(("done", "任务", {}, None))
    panel.after = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not schedule"))

    FirmwareListPanel._poll_task_queue(panel)

    assert panel._busy is False


def test_handcontrol_one_click_runs_service(monkeypatch):
    """一键刷机逻辑已迁移到 AutoUsbPanel，直接测试面板行为。"""
    from fwasset.ui.operation_panels.auto_usb_panel import AutoUsbPanel

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

    monkeypatch.setattr("fwasset.ui.operation_panels.auto_usb_panel.run_one_click", mock_one_click)
    panel._run_task = lambda _name, fn, on_done=None: fn(panel._log)

    usb_panel = AutoUsbPanel.__new__(AutoUsbPanel)
    usb_panel.asset = panel.assets[0]
    usb_panel._log = panel._log
    usb_panel._panel_host = panel

    usb_panel._one_click_handcontrol()

    assert called["one_click"] is True


def test_directory_flash_runs_music_service(monkeypatch):
    """目录刷机逻辑已迁移到 AutoUsbPanel，直接测试面板行为。"""
    from fwasset.ui.operation_panels.auto_usb_panel import AutoUsbPanel

    panel = _mk_asset_stub(monkeypatch)
    panel._selected_idx = 0
    panel.assets = [
        {"model": "L50S", "version": "V2.0.0", "path": "D:/music", "directory_name": "music", "firmware_type": "music_files", "firmware_label": "音乐文件", "flash_mode": "auto_usb", "files": ["song.mp3"], "modified_time": 0}
    ]
    panel.usb_drive.set("E:\\")
    called = {"music": False}

    def mock_music_flash(*args, **kwargs):
        called["music"] = True
        return {"ok": True, "message": "done"}

    monkeypatch.setattr("fwasset.ui.operation_panels.auto_usb_panel.run_music_flash", mock_music_flash)
    panel._run_task = lambda _name, fn, on_done=None: (on_done(fn(panel._log)) if on_done else fn(panel._log))

    usb_panel = AutoUsbPanel.__new__(AutoUsbPanel)
    usb_panel.format_first = FakeVar(True)
    usb_panel.eject_after = FakeVar(False)
    usb_panel._log = panel._log
    usb_panel._panel_host = panel

    usb_panel._run_directory_flash()

    assert called["music"] is True


def test_auto_usb_paired_handcontrol_missing_pair_never_falls_back_to_directory(monkeypatch):
    """usb_flow 分流逻辑已迁移到 AutoUsbPanel，直接测试面板 build 分支。"""
    from fwasset.ui.operation_panels.auto_usb_panel import AutoUsbPanel

    panel = _mk_asset_stub(monkeypatch)
    panel._build_usb_selector_row = lambda *_args, **_kwargs: None
    panel._refresh_usb = lambda: None
    labels = []

    def fake_label(*args, **kwargs):
        labels.append(str(kwargs.get("text", "")))
        return FakeWidget(*args, **kwargs)

    monkeypatch.setattr(ctk, "CTkLabel", fake_label)

    usb_panel = AutoUsbPanel.__new__(AutoUsbPanel)
    usb_panel.asset = {
        "firmware_type": "handcontrol_ui",
        "firmware_label": "手控UI",
        "flash_mode": "auto_usb",
        "usb_flow": "paired_files",
        "files": ["only.rom"],
    }
    usb_panel._log = panel._log
    usb_panel._panel_host = panel

    usb_panel.build()

    assert any("缺少 PKG" in text for text in labels)


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
    """工具+目录组合操作已迁移到 ToolLaunchPanel。"""
    from fwasset.ui.operation_panels.tool_launch_panel import ToolLaunchPanel

    panel = _mk_asset_stub(monkeypatch)
    panel._selected_idx = 0
    panel.assets = [
        {"model": "L36", "version": "V1.0.0", "path": "D:/fw/L36", "directory_name": "L36", "firmware_type": "mainboard", "firmware_label": "主板程序", "flash_mode": "tool_launch", "files": ["main.bin"], "modified_time": 0}
    ]
    calls = []

    tool_panel = ToolLaunchPanel.__new__(ToolLaunchPanel)
    tool_panel._current_tool_path = ""
    tool_panel._log = panel._log
    tool_panel._panel_host = panel

    tool_panel._launch_current_tool = lambda: calls.append("tool")
    panel._open_current_asset_dir = lambda: calls.append("dir")

    tool_panel._launch_tool_and_open_asset_dir()

    assert calls == ["tool", "dir"]


def test_shell_hosts_single_asset_panel(monkeypatch):
    import fwasset.ui.shell as shell_module

    monkeypatch.setattr(ctk, "CTk", FakeAppBase)
    monkeypatch.setattr(ctk, "CTkFrame", FakeWidget)

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
