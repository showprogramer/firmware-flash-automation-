from fwasset.ui.view_models.asset_selection_model import AssetSelectionModel


def _asset(path: str, model_dir: str, flash_mode: str = "tool_launch") -> dict:
    return {
        "path": path,
        "model_directory_path": model_dir,
        "flash_mode": flash_mode,
    }


def test_selection_model_clamps_and_reads_selected_asset():
    model = AssetSelectionModel()
    assets = [
        _asset("D:/root/L36/type/V1", "D:/root/L36", flash_mode="auto_usb"),
        _asset("D:/root/L50/type/V1", "D:/root/L50", flash_mode="tool_launch"),
    ]

    assert model.clamped_selected_idx(len(assets)) == 0

    model.set_selected_idx(5)
    assert model.clamped_selected_idx(len(assets)) == 1

    model.set_selected_idx(1)
    assert model.selected_asset(assets) == assets[1]
    assert model.selected_flash_mode(assets) == "tool_launch"

    model.clear_selection()
    assert model.selected_asset(assets) is None
    assert model.selected_flash_mode(assets) == ""


def test_selection_model_detects_hidden_assets_and_hidden_type():
    model = AssetSelectionModel()
    model.replace_hidden_items(
        {
            "D:/root/L36": "model_directory",
            "D:/root/L50/type": "firmware_type",
            "D:/root/L60/type/V1": "asset",
        }
    )

    model_hidden = _asset("D:/root/L36/type/V1", "D:/root/L36")
    type_hidden = _asset("D:/root/L50/type/V3", "D:/root/L50")
    asset_hidden = _asset("D:/root/L60/type/V1", "D:/root/L60")
    visible = _asset("D:/root/L70/type/V1", "D:/root/L70")

    assert model.is_item_hidden("D:/root/L36") is True
    assert model.is_asset_hidden(model_hidden) is True
    assert model.asset_hidden_type(model_hidden) == "model_directory"
    assert model.is_asset_hidden(type_hidden) is True
    assert model.asset_hidden_type(type_hidden) == "firmware_type"
    assert model.is_asset_hidden(asset_hidden) is True
    assert model.asset_hidden_type(asset_hidden) == "asset"
    assert model.is_asset_hidden(visible) is False
    assert model.asset_hidden_type(visible) == ""
