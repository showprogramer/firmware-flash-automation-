from fwasset.ui.view_models.asset_filter_model import AssetFilterModel
from fwasset.ui.view_models.tree_expansion_model import TreeExpansionModel


def test_tree_expansion_model_starts_empty():
    model = TreeExpansionModel()
    assert model.expanded == set()
    assert model.is_open("series|L36") is False


def test_tree_expansion_model_mark_open_closed():
    model = TreeExpansionModel()
    model.mark_open("series|L36")
    assert model.is_open("series|L36") is True
    model.mark_closed("series|L36")
    assert model.is_open("series|L36") is False


def test_tree_expansion_model_toggle():
    model = TreeExpansionModel()
    assert model.toggle("type|D:/root/L36|mainboard") is True
    assert model.is_open("type|D:/root/L36|mainboard") is True
    assert model.toggle("type|D:/root/L36|mainboard") is False
    assert model.is_open("type|D:/root/L36|mainboard") is False


def test_tree_expansion_model_clear():
    model = TreeExpansionModel()
    model.mark_open("a")
    model.mark_open("b")
    model.clear()
    assert model.expanded == set()


def test_tree_expansion_model_mark_closed_idempotent():
    model = TreeExpansionModel()
    model.mark_closed("nonexistent")
    assert model.expanded == set()


def test_expand_all_default_only_expands_visible_series_nodes():
    model = TreeExpansionModel()
    filter_model = AssetFilterModel()
    assets = [
        {
            "series": "L36",
            "model": "L36",
            "version": "V1.0.0",
            "path": "D:/root/L36-config/mainboard/V1",
            "directory_name": "V1",
            "model_directory_name": "L36-config",
            "model_directory_path": "D:/root/L36-config",
            "firmware_type": "mainboard",
            "firmware_label": "Mainboard",
        }
    ]

    model.expand_all_default(assets, filter_model, {}, lambda _asset: False)

    assert model.expanded == {"series|L36"}
