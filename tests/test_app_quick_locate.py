from pathlib import Path

from fwasset.ui.firmware_list_panel import FirmwareListPanel as App


class FakeVar:
    def __init__(self, value=None):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


class FakeListbox:
    def __init__(self, selection=None, nearest_idx=0):
        self._selection = list(selection or [])
        self._nearest_idx = nearest_idx
        self.set_calls = []

    def curselection(self):
        return tuple(self._selection)

    def selection_clear(self, _start, _end):
        self._selection = []

    def selection_set(self, idx):
        self._selection = [idx]
        self.set_calls.append(idx)

    def nearest(self, _y):
        return self._nearest_idx


def _build_app_stub(folders, selection=None, nearest_idx=0):
    app = App.__new__(App)
    app.folders = folders
    app.listbox = FakeListbox(selection=selection, nearest_idx=nearest_idx)
    app.current_idx = FakeVar(-1)
    app.logs = []
    app.log = app.logs.append
    call_count = {"on_select": 0}

    def _on_select(_event=None):
        call_count["on_select"] += 1

    app._on_select = _on_select
    return app, call_count


def test_open_folder_from_listbox_opens_explorer(monkeypatch, tmp_path: Path):
    app, call_count = _build_app_stub(
        [{"path": str(tmp_path), "model": "L36", "version": "V1.0.0"}],
        selection=[0],
    )
    opened = []
    monkeypatch.setattr("fwasset.ui.firmware_list_panel.os.startfile", lambda path: opened.append(path), raising=False)

    App._open_folder_from_listbox(app)

    assert opened == [str(tmp_path)]
    assert app.current_idx.get() == 0
    assert call_count["on_select"] == 1
    assert any("快速定位已打开" in msg for msg in app.logs)


def test_open_folder_from_listbox_warns_when_path_missing(monkeypatch, tmp_path: Path):
    missing = tmp_path / "not-exists"
    app, _ = _build_app_stub(
        [{"path": str(missing), "model": "L36", "version": "V1.0.0"}],
        selection=[0],
    )
    opened = []
    warnings = []
    monkeypatch.setattr("fwasset.ui.firmware_list_panel.os.startfile", lambda path: opened.append(path), raising=False)
    monkeypatch.setattr("fwasset.ui.firmware_list_panel.messagebox.showwarning", lambda title, message: warnings.append((title, message)))

    App._open_folder_from_listbox(app)

    assert opened == []
    assert warnings
    assert "目录不存在" in warnings[0][1]


def test_open_folder_from_listbox_uses_double_click_position(monkeypatch, tmp_path: Path):
    d1 = tmp_path / "a"
    d2 = tmp_path / "b"
    d1.mkdir()
    d2.mkdir()
    app, _ = _build_app_stub(
        [
            {"path": str(d1), "model": "L36", "version": "V1.0.0"},
            {"path": str(d2), "model": "L50S", "version": "V2.0.0"},
        ],
        selection=[],
        nearest_idx=1,
    )
    opened = []
    monkeypatch.setattr("fwasset.ui.firmware_list_panel.os.startfile", lambda path: opened.append(path), raising=False)
    event = type("Evt", (), {"y": 42})()

    App._open_folder_from_listbox(app, event)

    assert opened == [str(d2)]
    assert app.current_idx.get() == 1
    assert app.listbox.set_calls[-1] == 1


def test_open_in_explorer_shows_error_when_startfile_fails(monkeypatch, tmp_path: Path):
    app, _ = _build_app_stub([], selection=[])
    errors = []

    def _raise(_path):
        raise OSError("boom")

    monkeypatch.setattr("fwasset.ui.firmware_list_panel.os.startfile", _raise, raising=False)
    monkeypatch.setattr("fwasset.ui.firmware_list_panel.messagebox.showerror", lambda title, message: errors.append((title, message)))

    App._open_in_explorer(app, str(tmp_path), "L36", "V1.0.0")

    assert errors
    assert "boom" in errors[0][1]
