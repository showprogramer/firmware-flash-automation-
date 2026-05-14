from fwasset.core.sort_config import SortKey
from fwasset.ui.view_models.asset_filter_model import AssetFilterModel


def _asset(
    path: str,
    *,
    series: str = "L36",
    model: str = "L36",
    version: str = "V1.0.0",
    firmware_type: str = "mainboard",
    firmware_label: str = "主板程序",
) -> dict:
    model_dir = path.rsplit("/", 2)[0]
    return {
        "series": series,
        "model": model,
        "version": version,
        "path": path,
        "directory_name": path.rsplit("/", 1)[-1],
        "model_directory_name": model_dir.rsplit("/", 1)[-1],
        "model_directory_path": model_dir,
        "firmware_type": firmware_type,
        "firmware_label": firmware_label,
        "flash_mode": "tool_launch",
        "files": ["main.bin"],
        "modified_time": 0,
    }


def test_selected_sort_key_maps_ui_labels():
    model = AssetFilterModel()

    assert model.selected_sort_key("按型号") == SortKey.MODEL
    assert model.selected_sort_key("按版本") == SortKey.VERSION
    assert model.selected_sort_key("默认(名称)") == SortKey.PATH


def test_query_filtered_assets_delegates_query_and_applies_hidden_filter(monkeypatch):
    model = AssetFilterModel()
    visible = _asset("D:/root/L36配置/主板/V1")
    hidden = _asset("D:/root/L39配置/主板/V1", series="L39", model="L39")
    calls = []

    def fake_query_assets(**kwargs):
        calls.append(kwargs)
        return [visible, hidden]

    monkeypatch.setattr("fwasset.ui.view_models.asset_filter_model.query_assets", fake_query_assets)

    result = model.query_filtered_assets(
        keyword="L",
        selected_types={"mainboard"},
        sort_label="按型号",
        ascending=False,
        show_hidden=False,
        is_hidden=lambda asset: asset["model"] == "L39",
    )

    assert result == [visible]
    assert calls[0]["keyword"] == "L"
    assert calls[0]["firmware_types"] == {"mainboard"}
    assert calls[0]["sort_key"] == SortKey.MODEL
    assert calls[0]["ascending"] is False


def test_build_tree_groups_and_visible_indices():
    model = AssetFilterModel()
    assets = [
        _asset("D:/root/L36配置/主板/V1", version="V1.0.0"),
        _asset("D:/root/L36配置/主板/V2", version="V2.0.0"),
    ]

    groups = model.build_tree_groups(
        assets,
        hidden_items={"D:/root/L36配置": "model_directory"},
        is_hidden=lambda _asset: False,
    )

    assert groups[0]["key"] == "series|L36"
    assert groups[0]["models"][0]["key"] == "model|L36|D:/root/L36配置"
    assert groups[0]["models"][0]["hidden"] is True
    assert groups[0]["models"][0]["types"][0]["key"] == "type|D:/root/L36配置|mainboard"
    assert groups[0]["models"][0]["types"][0]["version_count"] == 2

    expanded = {
        "series|L36",
    }
    assert model.visible_tree_asset_indices(groups, expanded) == [0, 1]
