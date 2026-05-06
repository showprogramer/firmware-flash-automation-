from pathlib import Path

from fwasset.core.tool_usage import (
    MAX_RECENT_TOOLS,
    load_tool_usage,
    record_recent_tool,
    save_tool_usage,
    toggle_favorite_tool,
)


def test_tool_usage_loads_defaults_for_missing_file(tmp_path: Path):
    assert load_tool_usage(tmp_path / "missing.json") == {"favorites": [], "recent": []}


def test_tool_usage_round_trips_json(tmp_path: Path):
    path = tmp_path / "state" / "tool_usage.json"
    usage = {"favorites": ["mainboard"], "recent": ["voice", "mainboard"]}

    assert save_tool_usage(usage, path) is True

    assert load_tool_usage(path) == usage


def test_toggle_favorite_tool_adds_and_removes():
    usage = toggle_favorite_tool("voice", {"favorites": [], "recent": []})
    assert usage["favorites"] == ["voice"]

    usage = toggle_favorite_tool("voice", usage)
    assert usage["favorites"] == []


def test_record_recent_tool_moves_latest_to_front_and_limits():
    usage = {"favorites": [], "recent": [f"type_{idx}" for idx in range(MAX_RECENT_TOOLS)]}

    usage = record_recent_tool("type_3", usage)
    assert usage["recent"][0] == "type_3"
    assert len(usage["recent"]) == MAX_RECENT_TOOLS

    usage = record_recent_tool("new_type", usage)
    assert usage["recent"][0] == "new_type"
    assert len(usage["recent"]) == MAX_RECENT_TOOLS
