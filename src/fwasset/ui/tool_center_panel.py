"""工具中心面板 - 统一管理所有烧录工具.

提供功能:
1. 查看所有工具的配置状态
2. 自动发现未配置的工具
3. 手动指定工具路径
4. 一键启动常用工具
"""

from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from fwasset.core.firmware_catalog import enabled_firmware_types
from fwasset.core.tool_discovery import (
    discover_tool_path,
    launch_tool,
    save_tool_paths_to_catalog,
)
from fwasset.core.settings import APP_ROOT
from fwasset.core.tool_usage import (
    load_tool_usage,
    record_recent_tool,
    save_tool_usage,
    toggle_favorite_tool,
)
from fwasset.ui.design_tokens import (
    BG_CARD,
    BG_HOVER,
    BG_INPUT,
    BORDER_COLOR,
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    FONT_FAMILY,
    FONT_SIZE_LG,
    FONT_SIZE_MD,
    FONT_SIZE_SM,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class ToolCenterPanel(ctk.CTkToplevel):
    """工具中心窗口."""
    
    def __init__(self, parent, log_fn=None):
        super().__init__(parent)
        self.log_fn = log_fn or print
        self.search_var = tk.StringVar(value="")
        self.tool_usage = load_tool_usage()
        self.tool_configs: list[dict] = []
        self.tool_widgets: list[dict] = []
        
        self.title("工具中心 | Tool Center")
        self.geometry("800x600")
        self.minsize(700, 500)
        
        self._build_ui()
        self._load_tools()
        self.search_var.trace_add("write", lambda *_: self._render_tools())
        self.transient(parent)
        self.grab_set()
        
    def _build_ui(self):
        """构建界面."""
        # 顶部标题栏
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 12))
        
        ctk.CTkLabel(
            header,
            text="烧录工具中心",
            font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
            text_color=TEXT_PRIMARY,
        ).pack(side="left")
        
        # 自动发现按钮
        ctk.CTkButton(
            header,
            text="自动发现工具",
            width=120,
            height=32,
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            command=self._auto_discover,
        ).pack(side="right", padx=(8, 0))
        
        # 打开tools文件夹按钮
        ctk.CTkButton(
            header,
            text="打开tools文件夹",
            width=130,
            height=32,
            fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            hover_color=BG_HOVER,
            command=self._open_tools_folder,
        ).pack(side="right")
        
        # 说明文字
        self.hint_label = ctk.CTkLabel(
            self,
            text='提示: 工具中心支持先打开工具再找程序。搜索工具名/类型，找到后直接点"启动"。',
            font=(FONT_FAMILY, FONT_SIZE_SM),
            text_color=TEXT_SECONDARY,
        )
        self.hint_label.pack(anchor="w", padx=20, pady=(0, 12))

        self.search_entry = ctk.CTkEntry(
            self,
            height=36,
            corner_radius=8,
            placeholder_text="搜索工具名 / 固件类型 / 目录关键词",
            textvariable=self.search_var,
            fg_color=BG_CARD,
            border_width=1,
            border_color=BORDER_COLOR,
            font=(FONT_FAMILY, FONT_SIZE_MD),
        )
        self.search_entry.pack(fill="x", padx=20, pady=(0, 12))

        self.quick_frame = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=10, border_width=1, border_color=BORDER_COLOR)
        self.quick_frame.pack(fill="x", padx=20, pady=(0, 12))
        
        # 工具列表区域
        self.tools_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
        )
        self.tools_frame.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        
        # 底部按钮栏
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 16))
        
        ctk.CTkButton(
            footer,
            text="关闭",
            width=100,
            height=36,
            command=self.destroy,
        ).pack(side="right")
        
        self.status_label = ctk.CTkLabel(
            footer,
            text="",
            font=(FONT_FAMILY, FONT_SIZE_SM),
            text_color=TEXT_SECONDARY,
        )
        self.status_label.pack(side="left")
    
    def _load_tools(self):
        """加载工具配置列表."""
        # 只加载 tool_launch 模式的固件类型
        fw_types = enabled_firmware_types()
        self.tool_configs = []
        for item in fw_types:
            if item.get("flash_mode") != "tool_launch" or not item.get("enabled", True):
                continue
            config = {
                "key": item["key"],
                "label": item["label"],
                "tool_name": item["tool_name"],
                "tool_path": item["tool_path"],
                "tool_dir": item.get("tool_dir", ""),
                "dir_keywords": item.get("dir_keywords", []),
            }
            config["resolved_path"] = discover_tool_path(
                config["key"],
                config["tool_name"] or config["label"],
                tool_path=config.get("tool_path", ""),
                tool_dir=config.get("tool_dir", ""),
                dir_keywords=config.get("dir_keywords", []),
            )
            self.tool_configs.append(config)
        self._render_tools()

    def _render_tools(self):
        """Render quick launch area and filtered tool rows."""
        for widget in self.tools_frame.winfo_children():
            widget.destroy()
        for widget in self.quick_frame.winfo_children():
            widget.destroy()
        self.tool_widgets = []
        
        if not self.tool_configs:
            ctk.CTkLabel(
                self.tools_frame,
                text="没有需要配置工具路径的固件类型",
                font=(FONT_FAMILY, FONT_SIZE_MD),
                text_color=TEXT_SECONDARY,
            ).pack(pady=40)
            return

        keyword = self.search_var.get().strip().lower()
        filtered_configs = [
            config
            for config in self.tool_configs
            if self._matches_search(config, keyword)
        ]

        ctk.CTkLabel(
            self.quick_frame,
            text="常用 / 最近启动",
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
            text_color=TEXT_PRIMARY,
        ).pack(anchor="w", padx=14, pady=(12, 6))

        favorite_configs = self._ordered_usage_configs("favorites", filtered_configs)
        recent_configs = self._ordered_usage_configs("recent", filtered_configs)
        self._render_quick_section("常用工具", favorite_configs, empty_text="点击工具行右侧星标加入常用。")
        self._render_quick_section("最近使用", recent_configs, empty_text="启动工具后会自动出现在这里。")
        
        # 创建每个工具的配置行
        for idx, config in enumerate(filtered_configs):
            self._create_tool_row(idx, config)

        if not filtered_configs:
            ctk.CTkLabel(
                self.tools_frame,
                text="没有匹配的工具。",
                font=(FONT_FAMILY, FONT_SIZE_MD),
                text_color=TEXT_SECONDARY,
            ).pack(pady=40)
        
        self._update_status()

    def _ordered_usage_configs(self, usage_key: str, configs: list[dict]) -> list[dict]:
        by_key = {config["key"]: config for config in configs if config.get("resolved_path")}
        return [
            by_key[key]
            for key in self.tool_usage.get(usage_key, [])
            if key in by_key
        ][:8]

    def _render_quick_section(self, title: str, configs: list[dict], *, empty_text: str):
        section = ctk.CTkFrame(self.quick_frame, fg_color="transparent")
        section.pack(fill="x", padx=10, pady=(0, 8))
        ctk.CTkLabel(
            section,
            text=title,
            width=72,
            anchor="w",
            font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
            text_color=TEXT_SECONDARY,
        ).pack(side="left", padx=(4, 8))
        button_area = ctk.CTkFrame(section, fg_color="transparent")
        button_area.pack(side="left", fill="x", expand=True)
        if not configs:
            ctk.CTkLabel(
                button_area,
                text=empty_text,
                font=(FONT_FAMILY, FONT_SIZE_SM),
                text_color=TEXT_SECONDARY,
            ).pack(anchor="w", padx=4, pady=4)
            return
        for idx, config in enumerate(configs):
            ctk.CTkButton(
                button_area,
                text=config["label"],
                width=126,
                height=32,
                fg_color=COLOR_PRIMARY,
                hover_color=COLOR_PRIMARY_HOVER,
                command=lambda c=config: self._launch_tool(c),
            ).grid(row=idx // 4, column=idx % 4, sticky="ew", padx=4, pady=4)

    def _matches_search(self, config: dict, keyword: str) -> bool:
        if not keyword:
            return True
        haystack = " ".join(
            [
                str(config.get("key", "")),
                str(config.get("label", "")),
                str(config.get("tool_name", "")),
                str(config.get("tool_dir", "")),
                str(config.get("tool_path", "")),
                str(config.get("resolved_path", "")),
                " ".join(config.get("dir_keywords", []) or []),
            ]
        ).lower()
        return keyword in haystack
    
    def _create_tool_row(self, idx: int, config: dict):
        """创建单个工具的配置行."""
        launch_path = config.get("resolved_path") or config.get("tool_path", "")
        has_path = bool(launch_path)
        
        # 卡片容器
        card = ctk.CTkFrame(
            self.tools_frame,
            fg_color=BG_CARD,
            corner_radius=10,
            border_width=1,
            border_color=BORDER_COLOR if has_path else "#E74C3C",
        )
        card.pack(fill="x", pady=6, padx=4)
        
        # 左侧信息区
        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=16, pady=12)
        
        # 工具名称
        name_row = ctk.CTkFrame(info, fg_color="transparent")
        name_row.pack(fill="x")
        
        ctk.CTkLabel(
            name_row,
            text=config["label"],
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
            text_color=TEXT_PRIMARY,
        ).pack(side="left")
        
        # 状态标签
        status_text = "可启动" if has_path else "未找到"
        status_color = "#27AE60" if has_path else "#E74C3C"
        ctk.CTkLabel(
            name_row,
            text=status_text,
            font=(FONT_FAMILY, FONT_SIZE_SM),
            text_color=status_color,
        ).pack(side="left", padx=(12, 0))
        
        # 工具路径
        path_text = launch_path or "点击右侧按钮配置工具路径"
        path_color = TEXT_SECONDARY if has_path else "#E74C3C"
        path_label = ctk.CTkLabel(
            info,
            text=path_text,
            font=(FONT_FAMILY, FONT_SIZE_SM),
            text_color=path_color,
            wraplength=400,
        )
        path_label.pack(anchor="w", pady=(4, 0))
        
        # 右侧按钮区
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(side="right", padx=16, pady=12)

        favorite_btn = ctk.CTkButton(
            btn_frame,
            text="★" if self._is_favorite(config["key"]) else "☆",
            width=70,
            height=28,
            fg_color=COLOR_PRIMARY if self._is_favorite(config["key"]) else BG_INPUT,
            text_color="white" if self._is_favorite(config["key"]) else TEXT_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER if self._is_favorite(config["key"]) else BG_HOVER,
            command=lambda c=config: self._toggle_favorite(c),
        )
        favorite_btn.pack(pady=(0, 6))
        
        # 浏览按钮
        browse_btn = ctk.CTkButton(
            btn_frame,
            text="浏览...",
            width=70,
            height=32,
            fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            hover_color=BG_HOVER,
            command=lambda c=config, l=path_label, ca=card: self._browse_tool(c, l, ca),
        )
        browse_btn.pack(pady=(0, 6))
        
        # 启动按钮
        launch_btn = ctk.CTkButton(
            btn_frame,
            text="启动",
            width=70,
            height=32,
            fg_color=COLOR_PRIMARY if has_path else BG_INPUT,
            hover_color=COLOR_PRIMARY_HOVER if has_path else BG_HOVER,
            state="normal" if has_path else "disabled",
            command=lambda c=config: self._launch_tool(c),
        )
        launch_btn.pack()
        
        self.tool_widgets.append({
            "card": card,
            "path_label": path_label,
            "launch_btn": launch_btn,
            "config": config,
        })
    
    def _browse_tool(self, config: dict, path_label: ctk.CTkLabel, card: ctk.CTkFrame):
        """浏览选择工具路径."""
        file_path = filedialog.askopenfilename(
            title=f"选择 {config['label']} 的可执行文件",
            filetypes=[
                ("可执行文件", "*.exe"),
                ("批处理文件", "*.bat;*.cmd"),
                ("所有文件", "*.*"),
            ],
        )
        if not file_path:
            return
        
        # 更新配置
        config["tool_path"] = file_path
        config["resolved_path"] = file_path
        
        # 更新UI
        path_label.configure(text=file_path, text_color=TEXT_SECONDARY)
        card.configure(border_color=BORDER_COLOR)
        
        # 更新对应行的按钮状态
        for widget in self.tool_widgets:
            if widget["config"]["key"] == config["key"]:
                widget["launch_btn"].configure(
                    state="normal",
                    fg_color=COLOR_PRIMARY,
                    hover_color=COLOR_PRIMARY_HOVER,
                )
                break
        
        # 保存到配置
        self._save_tool_path(config["key"], file_path)
        self._update_status()
        self._render_tools()
    
    def _launch_tool(self, config: dict):
        """启动指定工具."""
        result = launch_tool(config.get("resolved_path") or config.get("tool_path", ""))
        if result.get("ok"):
            self.tool_usage = record_recent_tool(config.get("key", ""), self.tool_usage)
            save_tool_usage(self.tool_usage)
            self.log_fn(f"[工具中心] {result.get('message')}")
            self._render_tools()
        else:
            messagebox.showerror("启动失败", result.get("message", ""))
            self.log_fn(f"[工具中心] {result.get('message')}")

    def _is_favorite(self, fw_type: str) -> bool:
        return fw_type in self.tool_usage.get("favorites", [])

    def _toggle_favorite(self, config: dict):
        self.tool_usage = toggle_favorite_tool(config.get("key", ""), self.tool_usage)
        save_tool_usage(self.tool_usage)
        self._render_tools()
    
    def _auto_discover(self):
        """自动发现所有未配置的工具."""
        self.status_label.configure(text="正在自动发现工具...")
        self.update()
        
        discovered: dict[str, str] = {}
        
        for config in self.tool_configs:
            if not config.get("tool_path"):
                fw_type = config["key"]
                tool_name = config["tool_name"] or config["label"]
                
                self.status_label.configure(text=f"正在查找: {tool_name}...")
                self.update()
                
                found_path = discover_tool_path(
                    fw_type,
                    tool_name,
                    tool_path=config.get("tool_path", ""),
                    tool_dir=config.get("tool_dir", ""),
                    dir_keywords=config.get("dir_keywords", []),
                )
                if found_path:
                    discovered[fw_type] = found_path
                    config["tool_path"] = found_path
                    config["resolved_path"] = found_path
        
        # 保存发现的配置
        if discovered:
            save_tool_paths_to_catalog(discovered)
            self.status_label.configure(text=f"发现并保存了 {len(discovered)} 个工具配置")
            self.log_fn(f"[工具中心] 自动发现完成，共 {len(discovered)} 个")
        else:
            self.status_label.configure(text="未发现新的工具，请将工具放在程序同目录的tools文件夹中")
        
        self._update_status()
        self._render_tools()
    
    def _save_tool_path(self, fw_type: str, tool_path: str):
        """保存单个工具路径到配置."""
        save_tool_paths_to_catalog({fw_type: tool_path})
    
    def _update_status(self):
        """更新状态显示."""
        total = len(self.tool_configs)
        configured = sum(1 for c in self.tool_configs if c.get("resolved_path") or c.get("tool_path"))
        self.status_label.configure(text=f"可启动: {configured}/{total}")
    
    def _open_tools_folder(self):
        """打开tools文件夹."""
        tools_dir = APP_ROOT / "tools"
        tools_dir.mkdir(exist_ok=True)
        try:
            os.startfile(str(tools_dir))
        except OSError as exc:
            messagebox.showerror("错误", f"打开文件夹失败: {exc}")
