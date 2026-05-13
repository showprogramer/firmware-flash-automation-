from __future__ import annotations

from fwasset.core.types import FirmwareAsset


class AssetSelectionModel:
    def __init__(self) -> None:
        self.selected_idx = -1
        self.hidden_items: dict[str, str] = {}

    def clear_selection(self) -> None:
        self.selected_idx = -1

    def set_selected_idx(self, idx: int) -> None:
        self.selected_idx = int(idx)

    def clamped_selected_idx(self, asset_count: int) -> int:
        if asset_count <= 0:
            return -1
        return min(max(self.selected_idx, 0), asset_count - 1)

    def selected_asset(self, assets: list[FirmwareAsset]) -> FirmwareAsset | None:
        if self.selected_idx < 0 or self.selected_idx >= len(assets):
            return None
        return assets[self.selected_idx]

    def selected_flash_mode(self, assets: list[FirmwareAsset]) -> str:
        asset = self.selected_asset(assets)
        if asset is None:
            return ""
        return str(asset.get("flash_mode", "") or "")

    def replace_hidden_items(self, hidden_items: dict[str, str]) -> None:
        self.hidden_items = {
            str(path): str(hide_type)
            for path, hide_type in hidden_items.items()
            if str(path)
        }

    def is_item_hidden(self, item_path: str) -> bool:
        return str(item_path or "") in self.hidden_items

    def is_asset_hidden(self, asset: FirmwareAsset) -> bool:
        asset_path = str(asset.get("path", "") or "")
        model_path = str(asset.get("model_directory_path", "") or "")
        if asset_path in self.hidden_items or model_path in self.hidden_items:
            return True
        return any(
            hide_type == "firmware_type" and bool(hidden_path) and asset_path.startswith(hidden_path)
            for hidden_path, hide_type in self.hidden_items.items()
        )

    def asset_hidden_type(self, asset: FirmwareAsset) -> str:
        asset_path = str(asset.get("path", "") or "")
        model_path = str(asset.get("model_directory_path", "") or "")
        if asset_path in self.hidden_items:
            return "asset"
        if model_path in self.hidden_items:
            return "model_directory"
        for hidden_path, hide_type in self.hidden_items.items():
            if hide_type == "firmware_type" and bool(hidden_path) and asset_path.startswith(hidden_path):
                return "firmware_type"
        return ""
