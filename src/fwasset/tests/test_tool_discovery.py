from pathlib import Path

from fwasset.core import tool_discovery


def _exe(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("tool", encoding="utf-8")
    return path


def test_discover_tool_path_prefers_explicit_path(tmp_path: Path, monkeypatch):
    explicit = _exe(tmp_path / "explicit" / "writer.exe")
    root = tmp_path / "root"
    root.mkdir()
    monkeypatch.setattr(tool_discovery, "TOOL_ROOT", str(root))
    tool_discovery.clear_tool_discovery_cache()

    found = tool_discovery.discover_tool_path("mainboard", "主板烧录工具", tool_path=str(explicit))

    assert found == str(explicit)


def test_discover_tool_path_uses_tool_root_and_tool_dir(tmp_path: Path, monkeypatch):
    root = tmp_path / "tools-root"
    expected = _exe(root / "刷主板程序工具" / "writer_cn.exe")
    monkeypatch.setattr(tool_discovery, "TOOL_ROOT", str(root))
    tool_discovery.clear_tool_discovery_cache()

    found = tool_discovery.discover_tool_path("mainboard", "主板烧录工具", tool_dir="刷主板程序工具")

    assert found == str(expected)


def test_discover_tool_path_fuzzy_searches_tool_root(tmp_path: Path, monkeypatch):
    root = tmp_path / "tools-root"
    expected = _exe(root / "语音烧录工具包" / "voice.exe")
    monkeypatch.setattr(tool_discovery, "TOOL_ROOT", str(root))
    tool_discovery.clear_tool_discovery_cache()

    found = tool_discovery.discover_tool_path("voice", "语音烧录工具", dir_keywords=["语音"])

    assert found == str(expected)


def test_discover_tool_path_falls_back_to_app_tools(tmp_path: Path, monkeypatch):
    app_root = tmp_path / "app"
    expected = _exe(app_root / "tools" / "快捷键程序" / "shortcut.exe")
    monkeypatch.setattr(tool_discovery, "TOOL_ROOT", "")
    monkeypatch.setattr(tool_discovery, "APP_ROOT", app_root)
    tool_discovery.clear_tool_discovery_cache()

    found = tool_discovery.discover_tool_path("shortcut_key", "快捷键烧录工具", tool_dir="快捷键程序")

    assert found == str(expected)


def test_discover_tool_path_caches_result(tmp_path: Path, monkeypatch):
    root = tmp_path / "tools-root"
    expected = _exe(root / "主板程序" / "writer.exe")
    monkeypatch.setattr(tool_discovery, "TOOL_ROOT", str(root))
    tool_discovery.clear_tool_discovery_cache()

    first = tool_discovery.discover_tool_path("mainboard", "主板烧录工具", tool_dir="主板程序")
    expected.unlink()
    second = tool_discovery.discover_tool_path("mainboard", "主板烧录工具", tool_dir="主板程序")

    assert first == second
