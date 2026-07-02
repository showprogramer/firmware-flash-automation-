import pytest
import customtkinter as ctk

pytestmark = pytest.mark.ui


class FakeWidget:
    def __init__(self, master=None, **kwargs):
        self.master = master
        self.grid_count = 0
        self.pack_count = 0

    def grid(self, **kwargs):
        self.grid_count += 1

    def pack(self, **kwargs):
        self.pack_count += 1

    def configure(self, **kwargs):
        pass

    def grid_rowconfigure(self, *args, **kwargs):
        pass

    def grid_columnconfigure(self, *args, **kwargs):
        pass


class FakeAppBase(FakeWidget):
    def title(self, _value):
        pass

    def geometry(self, _value):
        pass

    def minsize(self, *_args):
        pass


def test_shell_hosts_workbench_panel(monkeypatch):
    import fwasset.ui.shell as shell_module

    monkeypatch.setattr(ctk, "CTk", FakeAppBase)
    monkeypatch.setattr(ctk, "CTkFrame", FakeWidget)

    class FakeAssetPanel(FakeWidget):
        def __init__(self, master):
            super().__init__(master)
            self.activate_count = 0

        def activate(self):
            self.activate_count += 1

    monkeypatch.setattr(shell_module, "WorkbenchPanel", FakeAssetPanel)

    app = shell_module.UnifiedFlashPlatform()

    assert app.asset_panel.grid_count == 1
    assert app.asset_panel.activate_count == 1
