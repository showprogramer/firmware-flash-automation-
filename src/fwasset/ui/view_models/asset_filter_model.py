from __future__ import annotations

import os
from collections.abc import Callable, Iterable

from fwasset.core.asset_index import query_assets
from fwasset.core.sort_config import SortKey, apply_sort
from fwasset.core.types import FirmwareAsset


class AssetFilterModel:
    def selected_sort_key(self, label: str) -> SortKey:
        if label == "按型号":
            return SortKey.MODEL
        if label == "按版本":
            return SortKey.VERSION
        return SortKey.PATH

    def sort_assets(
        self,
        assets: list[FirmwareAsset],
        *,
        sort_label: str,
        ascending: bool = True,
    ) -> list[FirmwareAsset]:
        return apply_sort(assets, sort_key=self.selected_sort_key(sort_label), ascending=ascending)

    def query_filtered_assets(
        self,
        *,
        keyword: str,
        selected_types: Iterable[str],
        sort_label: str,
        ascending: bool,
        show_hidden: bool,
        is_hidden: Callable[[FirmwareAsset], bool],
    ) -> list[FirmwareAsset]:
        selected = {str(item) for item in selected_types if str(item).strip()}
        if not selected:
            return []
        queried = query_assets(
            keyword=keyword,
            firmware_types=selected,
            sort_key=self.selected_sort_key(sort_label),
            ascending=ascending,
        )
        if show_hidden:
            return queried
        return [asset for asset in queried if not is_hidden(asset)]

    def tree_key(self, kind: str, *parts: object) -> str:
        return "|".join([kind, *[str(part) for part in parts]])

    def build_tree_groups(
        self,
        assets: list[FirmwareAsset],
        *,
        hidden_items: dict[str, str],
        is_hidden: Callable[[FirmwareAsset], bool],
    ) -> list[dict]:
        series_map: dict[str, dict] = {}
        for idx, asset in enumerate(assets):
            series = str(asset.get("series", "") or "未知系列")
            model_path = str(asset.get("model_directory_path", "") or asset.get("path", ""))
            model_name = str(asset.get("model_directory_name", "") or asset.get("model", "") or model_path)
            firmware_type = str(asset.get("firmware_type", "") or "unknown")
            firmware_label = str(asset.get("firmware_label", "") or firmware_type)
            hidden = is_hidden(asset)
            series_node = series_map.setdefault(series, {"series": series, "models": {}})
            model_node = series_node["models"].setdefault(
                model_path,
                {"name": model_name, "path": model_path, "types": {}, "hidden": False},
            )
            model_node["hidden"] = bool(model_node["hidden"] or hidden_items.get(model_path) == "model_directory")
            type_node = model_node["types"].setdefault(
                firmware_type,
                {"firmware_type": firmware_type, "label": firmware_label, "asset_indices": [], "hidden": False},
            )
            type_node["hidden"] = bool(type_node["hidden"] or hidden)
            type_node["asset_indices"].append(idx)

        out: list[dict] = []
        for series_name in sorted(series_map.keys(), key=str.casefold):
            series_node = series_map[series_name]
            series_key = self.tree_key("series", series_name)
            models = []
            for model_path, model_node in sorted(series_node["models"].items(), key=lambda item: item[1]["name"].casefold()):
                model_key = self.tree_key("model", series_name, model_path)
                types = []
                for _firmware_type, type_node in sorted(model_node["types"].items(), key=lambda item: item[1]["label"].casefold()):
                    type_node["key"] = self.tree_key("type", model_path, type_node["firmware_type"])
                    type_node["version_count"] = len(
                        {str(assets[idx].get("version", "") or "-") for idx in type_node["asset_indices"]}
                    )
                    type_node["hide_path"] = self.common_asset_path(assets, type_node["asset_indices"])
                    types.append(type_node)
                models.append(
                    {
                        "key": model_key,
                        "name": model_node["name"],
                        "path": model_path,
                        "types": types,
                        "type_count": len(types),
                        "hidden": bool(model_node.get("hidden")),
                    }
                )
            out.append({"key": series_key, "series": series_name, "models": models, "model_count": len(models)})
        return out

    def visible_tree_asset_indices(self, groups: list[dict], expanded_keys: set[str]) -> list[int]:
        visible: list[int] = []
        for series_node in groups:
            if str(series_node["key"]) not in expanded_keys:
                continue
            for model_node in series_node["models"]:
                if str(model_node["key"]) not in expanded_keys:
                    continue
                for type_node in model_node["types"]:
                    if str(type_node["key"]) in expanded_keys:
                        visible.extend(type_node["asset_indices"])
        return visible

    def common_asset_path(self, assets: list[FirmwareAsset], indices: list[int]) -> str:
        paths = [str(assets[idx].get("path", "") or "") for idx in indices if idx < len(assets)]
        paths = [path for path in paths if path]
        if not paths:
            return ""
        if len(paths) == 1:
            return paths[0]
        try:
            return os.path.commonpath(paths)
        except ValueError:
            return paths[0]
