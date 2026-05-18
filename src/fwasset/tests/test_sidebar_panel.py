import customtkinter as ctk

from fwasset.ui.panels.sidebar_panel import SidebarPanel


class FakeVar:
    def __init__(self, value=""):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


class FakeWidget:
    def __init__(self, master=None, **kwargs):
        self.master = master
        self.children = []
        self.command = kwargs.get("command")
        self.values = kwargs.get("values", [])
        self.text = kwargs.get("text", "")
        self.pack_count = 0
        self.grid_count = 0
        if hasattr(master, "children"):
            master.children.append(self)
        for key, value in kwargs.items():
            setattr(self, key, value)

    def pack(self, **_kwargs):
        self.pack_count += 1

    def grid(self, **_kwargs):
        self.grid_count += 1

    def grid_propagate(self, *_args, **_kwargs):
        pass

    def winfo_children(self):
        return list(self.children)


class FakeAssetTree:
    def __init__(
        self,
        master,
        *,
        on_select_asset,
        on_open_asset,
        on_context_menu,
        on_node_open,
        on_node_close,
    ):
        self.master = master
        self.on_select_asset = on_select_asset
        self.on_open_asset = on_open_asset
        self.on_context_menu = on_context_menu
        self.on_node_open = on_node_open
        self.on_node_close = on_node_close
        self.pack_count = 0

    def pack(self, **_kwargs):
        self.pack_count += 1


def _patch_widgets(monkeypatch):
    base_frame = SidebarPanel.__mro__[1]
    monkeypatch.setattr(base_frame, "__init__", lambda self, master=None, **kwargs: FakeWidget.__init__(self, master, **kwargs))
    monkeypatch.setattr(base_frame, "grid_propagate", lambda self, *args, **kwargs: None)
    monkeypatch.setattr(ctk, "CTkFrame", FakeWidget)
    monkeypatch.setattr(ctk, "CTkLabel", FakeWidget)
    monkeypatch.setattr(ctk, "CTkButton", FakeWidget)
    monkeypatch.setattr(ctk, "CTkEntry", FakeWidget)
    monkeypatch.setattr(ctk, "CTkOptionMenu", FakeWidget)
    monkeypatch.setattr(ctk, "CTkCheckBox", FakeWidget)
    monkeypatch.setattr("fwasset.ui.panels.sidebar_panel.AssetTreeView", FakeAssetTree)


def test_sidebar_panel_exposes_scan_button_and_asset_tree_callbacks(monkeypatch):
    _patch_widgets(monkeypatch)
    calls = []

    panel = SidebarPanel(
        FakeWidget(),
        search_var=FakeVar(""),
        sort_key_var=FakeVar("default"),
        show_hidden_var=FakeVar(False),
        type_quick_var=FakeVar("choose"),
        type_label_to_key={"Hand": "handcontrol_ui"},
        on_open_tool_center=lambda: calls.append("tools"),
        on_select_single_type_filter=lambda value: calls.append(("type", value)),
        on_filter_assets=lambda: calls.append("filter"),
        on_clear_type_filters=lambda: calls.append("clear"),
        on_scan_button_click=lambda: calls.append("scan"),
        on_select_asset=lambda idx: calls.append(("select", idx)),
        on_open_asset=lambda idx: calls.append(("open", idx)),
        on_context_menu=lambda event, path, hide_type: calls.append(("menu", path, hide_type)),
        on_node_open=lambda key: calls.append(("node_open", key)),
        on_node_close=lambda key: calls.append(("node_close", key)),
    )

    assert panel.scan_btn.command is not None
    panel.scan_btn.command()
    panel.asset_tree.on_select_asset(3)
    panel.asset_tree.on_node_open("series:A")

    assert "scan" in calls
    assert ("select", 3) in calls
    assert ("node_open", "series:A") in calls
    assert panel.asset_tree.pack_count == 1
