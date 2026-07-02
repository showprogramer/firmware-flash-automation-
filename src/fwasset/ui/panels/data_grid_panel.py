from __future__ import annotations

import os
import subprocess
from tkinter import ttk

import customtkinter as ctk

from fwasset.core.asset_helpers import asset_primary_file_name
from fwasset.ui.design_tokens import BG_CARD
from fwasset.ui.view_models.scheme_workbench_model import (
    ModuleCardData,
    ModuleRow,
    ModuleVariant,
)


class DataGridPanel(ctk.CTkFrame):
    """整机模块固定层级的可展开树。

    顶层 = 模块类型行（ModuleRow），多变体（如手控UI 3 份）收在该行的子节点下，
    绝不在顶层铺平。来源列只显示「定制专属 / 通用默认」，绝不出现"回源"。
    选中变体子节点才回传 ModuleVariant；选中多变体父行不选具体变体（等用户展开）。
    大部分机型包含 7 个标准模块，但非完整，缺失的模块不显示。
    """

    # iid 前缀：区分模块父行与变体子行
    _MOD_PREFIX = "mod::"

    def __init__(self, master, on_selection_changed, on_log, **kwargs):
        super().__init__(master, fg_color=BG_CARD, corner_radius=0, **kwargs)

        self._on_selection_changed = on_selection_changed
        self._on_log = on_log
        # iid -> ModuleVariant（仅变体子节点登记；父行不登记）
        self._variant_map: dict[str, ModuleVariant] = {}

        columns = ("variant", "version", "source", "program")
        self.tree = ttk.Treeview(self, columns=columns, show="tree headings", selectmode="browse")

        # #0 列承载模块类型（父）/ 变体名（子）+ 展开箭头
        self.tree.heading("#0", text="模块类型")
        self.tree.heading("variant", text="变体名称")
        self.tree.heading("version", text="版本")
        self.tree.heading("source", text="来源")
        self.tree.heading("program", text="程序名称")

        self.tree.column("#0", width=200, minwidth=160)
        self.tree.column("variant", width=200, minwidth=140)
        self.tree.column("version", width=80, minwidth=60)
        self.tree.column("source", width=110, minwidth=90)
        self.tree.column("program", width=220, minwidth=140)

        # 来源标签着色：蓝(定制) / 灰(通用)
        self.tree.tag_configure("custom", foreground="#0a66c2")
        self.tree.tag_configure("common", foreground="#6b6b6b")

        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", self._on_tree_double_click)

    # --- 渲染 ---
    def populate_tree(self, rows: list[ModuleRow]) -> None:
        """渲染整机模块固定层级。"""
        self.tree.delete(*self.tree.get_children())
        self._variant_map.clear()

        for row in rows:
            mod_iid = f"{self._MOD_PREFIX}{row.label}"

            # 单变体模块：折叠成一行叶子。版本/来源/模式直接落在模块行上；
            # 变体名仅在 == 模块类型名时留空（消除 `主板程序/主板程序` 真重复），
            # 若变体名有区分信息（如 `主板程序-减少灯光`）则照常显示，否则看不出是哪一份。
            if len(row.variants) == 1:
                variant = row.variants[0]
                asset = variant.asset
                variant_text = "" if variant.name == row.label else variant.name
                self.tree.insert(
                    "",
                    "end",
                    iid=mod_iid,
                    text=row.label,
                    values=(
                        variant_text,
                        variant.version or "-",
                        variant.source_label,
                        asset_primary_file_name(asset),
                    ),
                    tags=(variant.source_kind,),
                )
                self._variant_map[mod_iid] = variant
                continue

            # 多变体模块：父行（不可直接选中变体）+ 子节点变体（可选、可展开）。
            self.tree.insert(
                "",
                "end",
                iid=mod_iid,
                text=row.label,
                values=("", "", row.source_label, ""),
                tags=(row.source_kind,),
                open=True,
            )
            for variant in row.variants:
                asset = variant.asset
                child_iid = str(asset.get("path", "")) or f"{mod_iid}::{variant.name}"
                self._variant_map[child_iid] = variant
                self.tree.insert(
                    mod_iid,
                    "end",
                    iid=child_iid,
                    text="",
                    values=(
                        variant.name,
                        variant.version or "-",
                        variant.source_label,
                        asset_primary_file_name(asset),
                    ),
                    tags=(variant.source_kind,),
                )

    def populate(self, data_list: list[ModuleCardData]) -> None:
        """兼容旧调用（通用/全部视图）：按模块类型归组成可展开行，再走 populate_tree。

        同一类型的多张卡片（如多份手控UI变体）必须收在同一模块行下，否则会产生
        重复的 mod:: iid。归组逻辑与 get_scheme_module_tree 一致。
        """
        grouped: dict[str, list[ModuleVariant]] = {}
        for data in data_list:
            asset = data.asset
            label = str(asset.get("firmware_label", "")) or str(asset.get("firmware_type", ""))
            kind = "common" if data.is_fallback else "custom"
            source_label = "通用默认" if kind == "common" else "定制专属"
            variant = ModuleVariant(
                asset=asset,
                name=str(asset.get("directory_name", "")),
                version=str(asset.get("version", "")),
                source_kind=kind,
                source_label=source_label,
            )
            grouped.setdefault(label, []).append(variant)

        rows: list[ModuleRow] = []
        for label, variants in grouped.items():
            row_kind = "custom" if any(v.source_kind == "custom" for v in variants) else "common"
            rows.append(
                ModuleRow(
                    label=label,
                    source_kind=row_kind,
                    source_label="定制专属" if row_kind == "custom" else "通用默认",
                    variants=variants,
                )
            )
        self.populate_tree(rows)

    # --- 选择 ---
    def get_selected_variant(self) -> ModuleVariant | None:
        selection = self.tree.selection()
        if not selection:
            return None
        return self._variant_map.get(selection[0])

    # 旧名兼容（workbench_panel 仍调 get_selected_data().asset）
    def get_selected_data(self) -> ModuleVariant | None:
        return self.get_selected_variant()

    def _on_tree_select(self, _event):
        self._on_selection_changed(self.get_selected_variant())

    def _on_tree_double_click(self, _event):
        variant = self.get_selected_variant()
        if not variant:
            return
        path = str(variant.asset.get("path", ""))
        if not path or not os.path.exists(path):
            self._on_log(f"无法打开目录：路径不存在 ({path})")
            return
        try:
            if os.name == "nt":
                os.startfile(path)
            elif os.name == "posix":
                subprocess.run(["xdg-open", path], check=False)
        except Exception as e:  # noqa: BLE001
            self._on_log(f"打开目录失败: {e}")
