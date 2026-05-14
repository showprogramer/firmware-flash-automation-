import pytest

from fwasset.ui.asset_tree import AssetTreeView

pytestmark = pytest.mark.ui


class FakeTree:
    def __init__(self):
        self.rows = []
        self._known = set()

    def exists(self, iid):
        return iid in self._known

    def delete(self, iid):
        self._known.discard(iid)

    def insert(self, parent, _index, **kwargs):
        iid = kwargs.get("iid", f"row-{len(self.rows)}")
        self._known.add(iid)
        self.rows.append(
            {
                "parent": parent,
                "iid": iid,
                "text": kwargs.get("text", ""),
                "values": kwargs.get("values", ()),
                "tags": kwargs.get("tags", ()),
            }
        )

    def selection_set(self, _iid):
        pass

    def focus(self, _iid):
        pass

    def see(self, _iid):
        pass

    def get_children(self, _parent):
        return ()


def test_populate_keeps_leaf_columns_compact_without_redundant_model_or_type():
    view = AssetTreeView.__new__(AssetTreeView)
    view.tree = FakeTree()
    view._asset_by_iid = {}
    view._context_by_iid = {}
    view._node_key_by_iid = {}
    view._iid_by_asset_idx = {}
    view.focus_asset = lambda _idx: None

    groups = [
        {
            "key": "series|L36",
            "series": "L36",
            "model_count": 1,
            "models": [
                {
                    "key": "model|L36|D:/root/L36配置",
                    "name": "L36配置",
                    "path": "D:/root/L36配置",
                    "types": [
                        {
                            "key": "type|D:/root/L36配置|mainboard",
                            "label": "主板程序",
                            "version_count": 1,
                            "hide_path": "D:/root/L36配置/主板/V1",
                            "asset_indices": [0],
                        }
                    ],
                }
            ],
        }
    ]
    assets = [
        {
            "model": "L36",
            "directory_name": "V1",
            "model_directory_name": "L36配置",
            "firmware_label": "主板程序",
            "version": "V1.0.0",
            "path": "D:/root/L36配置/主板/V1",
        }
    ]

    view.populate(
        groups,
        assets,
        {"series|L36", "model|L36|D:/root/L36配置", "type|D:/root/L36配置|mainboard"},
        -1,
    )

    assert all(row["text"] != assets[0]["model_directory_name"] for row in view.tree.rows)
    asset_row = next(row for row in view.tree.rows if row["text"] == "L36")
    series_row = next(row for row in view.tree.rows if row["text"].startswith("L36  ("))

    assert len(view.tree.rows) == 2
    assert asset_row["parent"] == series_row["iid"]
    assert asset_row["values"] == ("V1", "V1.0.0")
