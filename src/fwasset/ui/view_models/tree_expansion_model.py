from __future__ import annotations

from fwasset.core.types import FirmwareAsset
from fwasset.ui.view_models.asset_filter_model import AssetFilterModel


class TreeExpansionModel:
    """Manages which tree nodes are expanded/collapsed in the asset tree.

    Extracts tree expansion state from FirmwareListPanel so it can be
    tested independently of the UI layer.
    """

    def __init__(self) -> None:
        self._expanded: set[str] = set()

    @property
    def expanded(self) -> set[str]:
        return self._expanded

    def clear(self) -> None:
        self._expanded.clear()

    def is_open(self, key: str) -> bool:
        return key in self._expanded

    def toggle(self, key: str) -> bool:
        """Toggle a node and return the new state (True = open)."""
        if key in self._expanded:
            self._expanded.remove(key)
            return False
        self._expanded.add(key)
        return True

    def mark_open(self, key: str) -> None:
        self._expanded.add(key)

    def mark_closed(self, key: str) -> None:
        self._expanded.discard(key)

    def expand_all_default(
        self,
        assets: list[FirmwareAsset],
        filter_model: AssetFilterModel,
        hidden_items: dict[str, str],
        is_hidden,
    ) -> None:
        """Expand series, model, and type nodes for the given assets.

        Only expands when the expanded set is currently empty and assets exist.
        """
        if self._expanded or not assets:
            return
        groups = filter_model.build_tree_groups(assets, hidden_items=hidden_items, is_hidden=is_hidden)
        for series_node in groups:
            self._expanded.add(filter_model.tree_key("series", series_node["series"]))
            for model_node in series_node["models"]:
                self._expanded.add(
                    filter_model.tree_key("model", series_node["series"], model_node["path"])
                )
                for type_node in model_node["types"]:
                    self._expanded.add(
                        filter_model.tree_key("type", model_node["path"], type_node["firmware_type"])
                    )