from __future__ import annotations

import os
import subprocess
from tkinter import ttk

import customtkinter as ctk

from fwasset.core.asset_helpers import asset_primary_file_name
from fwasset.ui.design_tokens import (
    BG_CARD,
    BG_HOVER,
    BORDER_COLOR,
    RADIUS_LG,
    SEPARATOR,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from fwasset.ui.view_models.scheme_workbench_model import (
    ModuleCardData,
    ModuleRow,
    ModuleVariant,
)


def _token_value(token: str | tuple[str, str]) -> str:
    if isinstance(token, tuple):
        return token[1] if ctk.get_appearance_mode() == "Dark" else token[0]
    return token


class DataGridPanel(ctk.CTkFrame):
    """整机模块固定层级的可展开树。

    顶层 = 模块类型行（ModuleRow），多变体（如手控UI 3 份）收在该行的子节点下，
    绝不在顶层铺平。程序归属列只显示「定制专属 / 通用默认」，绝不出现"回源"。
    选中变体子节点才回传 ModuleVariant；选中多变体父行不选具体变体（等用户展开）。
    大部分机型包含 7 个标准模块，但非完整，缺失的模块不显示。
    """

    # iid 前缀：区分模块父行与变体子行
    _MOD_PREFIX = "mod::"

    def __init__(self, master, on_selection_changed, on_log, on_right_click=None, **kwargs):
        super().__init__(
            master,
            fg_color=BG_CARD,
            corner_radius=RADIUS_LG,
            border_width=1,
            border_color=BORDER_COLOR,
            **kwargs,
        )

        self._on_selection_changed = on_selection_changed
        self._on_log = on_log
        self._on_right_click = on_right_click
        # iid -> ModuleVariant（仅变体子节点登记；父行不登记）
        self._variant_map: dict[str, ModuleVariant] = {}

        columns = ("variant", "version", "source", "program")
        self.tree = ttk.Treeview(self, columns=columns, show="tree headings", selectmode="browse")

        # #0 列承载程序类型（父）/ 程序名（子）+ 展开箭头
        self.tree.heading("#0", text="程序类型", anchor="w")
        self.tree.heading("variant", text="程序名称", anchor="w")
        self.tree.heading("version", text="版本", anchor="center")
        self.tree.heading("source", text="程序归属", anchor="w")
        self.tree.heading("program", text="程序文件", anchor="w")

        # 归属列加宽以显示「定制专属 · 方案名」（Issue 20-A）
        self.tree.column("#0", width=170, minwidth=130)
        self.tree.column("variant", width=210, minwidth=150)
        self.tree.column("version", width=80, minwidth=64, anchor="center")
        self.tree.column("source", width=200, minwidth=160, anchor="w")
        self.tree.column("program", width=260, minwidth=140)

        self._configure_tags()

        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True, padx=1, pady=1)
        self.scrollbar.pack(side="right", fill="y", pady=1)

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<Button-3>", self._on_tree_right_click)

    # --- 渲染 ---
    def _configure_tags(self) -> None:
        """Configure semantic row tags for ownership and alternating backgrounds."""
        bg = _token_value(BG_CARD)
        alt_bg = _token_value(BG_HOVER)
        normal_fg = _token_value(TEXT_PRIMARY)
        muted_fg = _token_value(TEXT_SECONDARY)
        for source, fg in (("custom", normal_fg), ("common", normal_fg), ("neutral", muted_fg)):
            for parity, row_bg in (("even", bg), ("odd", alt_bg)):
                self.tree.tag_configure(f"{source}_{parity}", foreground=fg, background=row_bg)
        self.tree.tag_configure("parent_even", foreground=normal_fg, background=_token_value(SEPARATOR))
        self.tree.tag_configure("parent_odd", foreground=normal_fg, background=_token_value(SEPARATOR))

    def _row_tags(self, source_kind: str, row_index: int) -> tuple[str]:
        source = source_kind if source_kind in {"custom", "common"} else "neutral"
        parity = "odd" if row_index % 2 else "even"
        return (f"{source}_{parity}",)

    def _source_text(self, label: str) -> str:
        if label == "定制专属":
            return "定制专属"
        if label == "通用默认":
            return "通用默认"
        return label

    def populate_tree(self, rows: list[ModuleRow]) -> None:
        """渲染整机模块固定层级。"""
        self.tree.delete(*self.tree.get_children())
        self._variant_map.clear()

        for row_index, row in enumerate(rows):
            mod_iid = f"{self._MOD_PREFIX}{row.label}"

            # 单变体模块：折叠成一行叶子。版本/归属/程序文件直接落在模块行上。
            # Issue 20-A：程序名称始终用变体目录名（directory_name），不再压成「默认」；
            # 同类型多条靠目录名 + 归属列（定制专属 · 方案）区分。
            if len(row.variants) == 1:
                variant = row.variants[0]
                asset = variant.asset
                variant_text = variant.name or "默认"
                if variant.default_badge:
                    variant_text = f"{variant_text}  {variant.default_badge}"
                self.tree.insert(
                    "",
                    "end",
                    iid=mod_iid,
                    text=row.label,
                    values=(
                        variant_text,
                        variant.version or "-",
                        self._source_text(variant.source_label),
                        asset_primary_file_name(asset),
                    ),
                    tags=self._row_tags(variant.source_kind, row_index),
                )
                self._variant_map[mod_iid] = variant
                continue

            # 多变体模块：父行（不可直接选中变体）+ 子节点变体（可选、可展开）。
            self.tree.insert(
                "",
                "end",
                iid=mod_iid,
                text=row.label,
                values=("", "", self._source_text(row.source_label), ""),
                tags=self._row_tags(row.source_kind, row_index),
                open=True,
            )
            for child_index, variant in enumerate(row.variants, start=1):
                asset = variant.asset
                child_iid = str(asset.get("path", "")) or f"{mod_iid}::{variant.name}"
                self._variant_map[child_iid] = variant
                child_text = variant.name
                if variant.default_badge:
                    child_text = f"{child_text}  {variant.default_badge}"
                self.tree.insert(
                    mod_iid,
                    "end",
                    iid=child_iid,
                    text="",
                    values=(
                        child_text,
                        variant.version or "-",
                        self._source_text(variant.source_label),
                        asset_primary_file_name(asset),
                    ),
                    tags=self._row_tags(variant.source_kind, row_index + child_index),
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
            # Prefer the explicit source_kind set by the model layer.
            # Fall back to is_fallback only for legacy callers that omit it.
            kind = data.source_kind if data.source_kind else ("common" if data.is_fallback else "custom")
            # Issue 20-A：保留 model 给出的归属文案（如「定制专属 · 马来西亚」）
            raw = (data.source_label or "").strip()
            if raw and "回源" not in raw:
                source_label = raw
            else:
                source_label = "通用默认" if kind == "common" else "定制专属"
            variant = ModuleVariant(
                asset=asset,
                name=str(asset.get("directory_name", "")),
                version=str(asset.get("version", "")),
                source_kind=kind,
                source_label=source_label,
                default_badge=data.default_badge,
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

    def _on_tree_right_click(self, event):
        """右键：先选中命中的行，再把变体与屏幕坐标交给上层弹菜单。"""
        if self._on_right_click is None:
            return
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        self.tree.selection_set(iid)
        self.tree.focus(iid)
        variant = self._variant_map.get(iid)
        if variant is not None:
            self._on_right_click(variant, event.x_root, event.y_root)

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
