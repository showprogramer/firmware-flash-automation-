from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    ComboBox,
    EditableComboBox,
    FluentIcon,
    FluentWindow,
    ListWidget,
    PrimaryPushButton,
    PushButton,
    SearchLineEdit,
    StrongBodyLabel,
    SubtitleLabel,
    TogglePushButton,
    setTheme,
    Theme,
)

from fwasset.core.asset_helpers import open_path_in_explorer
from fwasset.core.logging_utils import FileLogger
from fwasset.core.services.scan_service import build_cached_scan_result, build_scan_result
from fwasset.core.settings import DEFAULT_ROOT
from fwasset.core.types import ServiceResult
from fwasset.core.usb_ops import get_usb_drives
from fwasset.ui.view_models.scan_state_model import ScanStateModel
from fwasset.ui.view_models.scheme_workbench_model import (
    ModuleCardData,
    ModuleVariant,
    SchemeWorkbenchModel,
    WorkbenchSelection,
)
from fwasset.ui.workbench_helpers import flash_mode_label, model_chip_values
from fwasset.ui_qt.data_grid import DataGrid
from fwasset.ui_qt.design_tokens import (
    SEARCH_MIN_WIDTH,
    SIDEBAR_WIDTH,
    SPACE_MD,
    SPACE_SM,
    SPACE_XS,
    SPACE_XXS,
    USB_COMBO_MIN_WIDTH,
)
from fwasset.ui_qt.log_panel import LogPanel


SEARCH_REFRESH_DEBOUNCE_MS = 180


class WorkbenchInterface(QWidget):
    """程序资产工作台（Qt 版）。布局与交互对齐 ui/workbench_panel.py。"""

    # Signal 元类型只能是运行时类型，TypedDict（ServiceResult）不可用；
    # 类型契约由槽函数 _handle_scan_result 的参数标注承担。
    scan_result_ready = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("workbenchInterface")

        self.root_dir: str = DEFAULT_ROOT
        self.workbench_model = SchemeWorkbenchModel()
        self.scan_state_model = ScanStateModel()
        self.current_selection = WorkbenchSelection()
        self._available_models: list[str] = []
        self._nav_entries: list[tuple[str, str]] = []  # (kind, key)：all / common_type / custom_scheme
        self._file_logger = FileLogger()

        self._build_layout()

        self.scan_result_ready.connect(self._handle_scan_result)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(SEARCH_REFRESH_DEBOUNCE_MS)
        self._search_timer.timeout.connect(self._on_search_debounced)
        self.search_edit.textChanged.connect(lambda _t: self._search_timer.start())

        QTimer.singleShot(100, self._refresh_usb)
        QTimer.singleShot(100, self._load_cached_assets)

    # ------------------------------------------------------------------ 布局
    def _build_layout(self) -> None:
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, SPACE_SM, SPACE_SM)
        root_layout.setSpacing(SPACE_MD)

        # --- 左侧边栏 ---
        sidebar = QFrame(self)
        sidebar.setFixedWidth(SIDEBAR_WIDTH)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(SPACE_MD, SPACE_MD, SPACE_XS, 0)
        side_layout.addWidget(SubtitleLabel("程序资产", sidebar))
        side_layout.addWidget(CaptionLabel("通用模块与定制方案", sidebar))

        self.nav = ListWidget(sidebar)
        side_layout.addWidget(self.nav, stretch=1)
        self.nav.currentRowChanged.connect(self._on_nav_changed)

        self.scan_btn = PrimaryPushButton("扫描目录", sidebar)
        self.scan_btn.clicked.connect(self._on_scan_button_click)
        side_layout.addWidget(self.scan_btn)
        side_layout.addSpacing(SPACE_SM)
        root_layout.addWidget(sidebar)

        # --- 右侧主区 ---
        main = QVBoxLayout()
        main.setSpacing(SPACE_SM)

        # 头部：标题行
        title_row = QHBoxLayout()
        self.header_title = SubtitleLabel("请选择左侧分类进行过滤", self)
        title_row.addWidget(self.header_title)
        title_row.addStretch(1)
        self.header_badge = StrongBodyLabel("", self)
        title_row.addWidget(self.header_badge)
        main.addLayout(title_row)

        # 头部：过滤行（型号 chips + 搜索 + U盘）
        filter_row = QHBoxLayout()
        filter_row.addWidget(BodyLabel("型号", self))
        self.chip_bar = QHBoxLayout()
        self.chip_bar.setSpacing(SPACE_XS)
        filter_row.addLayout(self.chip_bar)
        self.model_hint = CaptionLabel("扫描后显示可选型号", self)
        filter_row.addWidget(self.model_hint)
        filter_row.addStretch(1)

        self.search_edit = SearchLineEdit(self)
        self.search_edit.setPlaceholderText("搜索模块 / 版本 / 方案 / 平台")
        self.search_edit.setMinimumWidth(SEARCH_MIN_WIDTH)
        filter_row.addWidget(self.search_edit, stretch=2)

        filter_row.addWidget(BodyLabel("U 盘", self))
        self.usb_combo = ComboBox(self)
        self.usb_combo.setMinimumWidth(USB_COMBO_MIN_WIDTH)
        filter_row.addWidget(self.usb_combo)
        usb_refresh = PushButton("刷新", self)
        usb_refresh.clicked.connect(self._refresh_usb)
        filter_row.addWidget(usb_refresh)
        main.addLayout(filter_row)

        # 数据表格
        self.grid_panel = DataGrid(self._log, self)
        self.grid_panel.selection_changed.connect(self._on_grid_selection_changed)
        self.grid_panel.variant_right_clicked.connect(self._on_grid_right_click)
        main.addWidget(self.grid_panel, stretch=1)

        # 操作区（Phase 3 迁移操作面板，这里先给选择摘要 + 占位）
        ops = QFrame(self)
        ops_layout = QVBoxLayout(ops)
        ops_layout.setContentsMargins(SPACE_XS, SPACE_XXS, SPACE_XS, SPACE_XXS)
        self.selection_summary = CaptionLabel("未选择变体", ops)
        ops_layout.addWidget(self.selection_summary)
        self.ops_placeholder = BodyLabel("展开模块并选择具体变体以查看操作（操作面板 Phase 3 迁移中，双击行可打开目录）", ops)
        ops_layout.addWidget(self.ops_placeholder)
        main.addWidget(ops)

        # 日志
        self.log_panel = LogPanel(self)
        main.addWidget(self.log_panel)

        root_layout.addLayout(main, stretch=1)

    # ------------------------------------------------------------------ 日志
    def _log(self, message: str) -> None:
        self.log_panel.write(message or "")
        self._file_logger.log(message or "")

    # ------------------------------------------------------------------ USB
    def _refresh_usb(self) -> None:
        drives = get_usb_drives() or [""]
        current = self.usb_combo.currentText()
        self.usb_combo.clear()
        self.usb_combo.addItems(drives)
        if current in drives:
            self.usb_combo.setCurrentText(current)
        self._log(f"U盘刷新: {', '.join([d for d in drives if d]) or '未发现'}")

    def get_global_usb_drive(self) -> str:
        return self.usb_combo.currentText()

    # ------------------------------------------------------------------ 扫描
    @property
    def _scan_cancel_event(self) -> threading.Event | None:
        return self.scan_state_model.cancel_event

    def _on_scan_button_click(self) -> None:
        if self._scan_cancel_event is not None:
            self._scan_cancel_event.set()
            self._log("正在取消扫描，请稍候...")
            self.scan_btn.setText("取消中...")
            self.scan_btn.setEnabled(False)
            return
        self._start_scan()

    def _start_scan(self) -> None:
        root = (self.root_dir or "").strip()
        if not root:
            root = QFileDialog.getExistingDirectory(self, "选择固件所在的根目录", str(Path.cwd()))
            if not root:
                return
            self.root_dir = root

        cancel_event = threading.Event()
        self.scan_state_model.replace(cancel_event)
        self.scan_btn.setText("取消扫描")
        self._log(f"开始扫描目录: {root}")

        def run_scan():
            result = build_scan_result(root, log_fn=self._log, cancel_event=cancel_event)
            # Signal 跨线程 emit 自动走 queued connection，回到 UI 线程处理
            self.scan_result_ready.emit(result)

        threading.Thread(target=run_scan, daemon=True).start()

    def _load_cached_assets(self) -> None:
        result = build_cached_scan_result(log_fn=self._log)
        self._handle_scan_result(result)

    def _handle_scan_result(self, result: ServiceResult) -> None:
        self.scan_state_model.replace(None)
        self.scan_btn.setText("扫描目录")
        self.scan_btn.setEnabled(True)

        if not result["ok"]:
            self._log(f"加载失败: {result['message']}")
            return

        payload = result["payload"]
        if "asset_count" in payload:
            self._log(f"已加载上次扫描的索引，共有 {payload['asset_count']} 个项目")
        else:
            assets = payload.get("assets", [])
            errors = payload.get("errors", [])
            self._log(f"扫描完成，共找到 {len(assets)} 个项目")
            if errors:
                self._log(f"扫描过程中有 {len(errors)} 个错误")

        root = (self.root_dir or "").strip()
        if not root:
            # 本机未配置 DEFAULT_ROOT 时，从最近一次扫描的 scan_meta 恢复扫描根，
            # 避免绑定到 "." 后型号列表退化成文件名解析的噪声假型号。
            meta = payload.get("scan_meta") or []
            if meta:
                root = str(meta[0].get("root_dir", "")).strip()
                if root:
                    self.root_dir = root
                    self._log(f"使用上次扫描的根目录: {root}")
        root_dir = Path(root) if root else Path(".")
        self.workbench_model.bind(None, root_dir)

        models = self.workbench_model.load_all_models()
        self._refresh_model_selector(models)

        if models:
            if not self.current_selection.model_name or self.current_selection.model_name not in models:
                self._on_model_changed(models[0])
            else:
                self._refresh_model_selector()
                self._refresh_sidebar_tree()
                self._refresh_main_grid()

    # ------------------------------------------------------------------ 型号 chips
    def _on_model_changed(self, choice: str) -> None:
        # 只接受真实型号：可搜索下拉的中间输入态（如敲了一半的 "L5"）不得
        # 污染 model_name，否则视图会静默变空。
        if not choice or choice not in self._available_models:
            return
        self.current_selection.model_name = choice
        self.current_selection.node_type = "all"
        self._refresh_model_selector()
        self._refresh_sidebar_tree()
        self._refresh_main_grid()

    def _refresh_model_selector(self, models: list[str] | None = None) -> None:
        if models is not None:
            self._available_models = models
        while self.chip_bar.count():
            item = self.chip_bar.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

        chips, overflow = model_chip_values(self._available_models, self.current_selection.model_name)
        self.model_hint.setVisible(not chips)
        for model in chips:
            btn = TogglePushButton(model, self)
            btn.setChecked(model == self.current_selection.model_name)
            btn.clicked.connect(lambda _c=False, value=model: self._on_model_changed(value))
            self.chip_bar.addWidget(btn)

        if overflow:
            # 型号多时给可输入过滤的下拉（型号本身是作用域选择器，不进搜索框；
            # 这里让烧录员敲几个字就能定位到型号）。
            combo = EditableComboBox(self)
            combo.addItems(overflow)
            combo.setPlaceholderText("更多型号…")
            combo.setCurrentIndex(-1)
            if combo.completer() is not None:
                combo.completer().setFilterMode(Qt.MatchFlag.MatchContains)
            combo.currentTextChanged.connect(self._on_model_changed)
            self.chip_bar.addWidget(combo)

    # ------------------------------------------------------------------ 侧边树
    def _refresh_sidebar_tree(self) -> None:
        self.nav.blockSignals(True)
        self.nav.clear()
        self._nav_entries.clear()

        model_name = self.current_selection.model_name
        if not model_name:
            self.nav.blockSignals(False)
            return

        tree_data = self.workbench_model.build_sidebar_tree(model_name)
        search_kw = self.search_edit.text().lower().strip()

        def _add_entry(text: str, kind: str, key: str, selected: bool) -> None:
            item = QListWidgetItem(text)
            self.nav.addItem(item)
            self._nav_entries.append((kind, key))
            if selected:
                self.nav.setCurrentItem(item)

        def _add_section(text: str) -> None:
            item = QListWidgetItem(text)
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.nav.addItem(item)
            self._nav_entries.append(("section", ""))

        sel = self.current_selection
        _add_entry("全部程序与模块", "all", "", sel.node_type == "all")

        if tree_data["common"]:
            _add_section("── 通用模块 ──")
            for fw_label, count in tree_data["common"].items():
                if search_kw and search_kw not in fw_label.lower():
                    continue
                _add_entry(
                    f"{fw_label} ({count})",
                    "common_type",
                    fw_label,
                    sel.node_type == "common_type" and sel.common_type == fw_label,
                )

        if tree_data["custom"]:
            _add_section("── 定制方案 ──")
            for scheme in tree_data["custom"]:
                if search_kw and search_kw not in scheme.lower():
                    continue
                _add_entry(
                    f"◆ {scheme}",
                    "custom_scheme",
                    scheme,
                    sel.node_type == "custom_scheme" and sel.scheme_name == scheme,
                )

        self.nav.blockSignals(False)

    def _on_nav_changed(self, row: int) -> None:
        if not (0 <= row < len(self._nav_entries)):
            return
        kind, key = self._nav_entries[row]
        if kind == "section":
            return
        if kind == "all":
            self.current_selection.node_type = "all"
        elif kind == "common_type":
            self.current_selection.node_type = "common_type"
            self.current_selection.common_type = key
        elif kind == "custom_scheme":
            self.current_selection.node_type = "custom_scheme"
            self.current_selection.scheme_name = key
        self._refresh_main_grid()

    # ------------------------------------------------------------------ 搜索
    def _on_search_debounced(self) -> None:
        self._refresh_sidebar_tree()
        self._refresh_main_grid()

    # ------------------------------------------------------------------ 主表格
    def _refresh_main_grid(self) -> None:
        model_name = self.current_selection.model_name
        node_type = self.current_selection.node_type
        search_kw = self.search_edit.text().lower().strip()

        if not model_name or not node_type:
            self.header_title.setText("请选择左侧分类进行过滤")
            self.header_badge.setText("")
            return

        cards_data: list[ModuleCardData] = []
        if node_type == "all":
            self.header_title.setText(f"全部模块 ({model_name})")
            self.header_badge.setText("全部")
            cards_data = self.workbench_model.get_all_modules(model_name, search_kw)
        elif node_type == "common_type":
            fw_label = self.current_selection.common_type
            self.header_title.setText(f"通用模块: {fw_label}")
            self.header_badge.setText("通用模块")
            cards_data = self.workbench_model.get_common_modules(model_name, fw_label, search_kw)
        elif node_type == "custom_scheme":
            scheme_name = self.current_selection.scheme_name
            self.header_title.setText(f"定制方案: {scheme_name}")
            self.header_badge.setText("整机模块")
            rows = self.workbench_model.get_scheme_module_tree(model_name, scheme_name, search_kw)
            self.grid_panel.populate_tree(rows)
            self._on_grid_selection_changed(None)
            return

        self.grid_panel.populate(cards_data)
        self._on_grid_selection_changed(None)

    # ------------------------------------------------------------------ 选择与操作区
    def _on_grid_selection_changed(self, variant: ModuleVariant | None) -> None:
        if not variant:
            self.selection_summary.setText("未选择变体")
            self.ops_placeholder.setText(
                "展开模块并选择具体变体以查看操作（操作面板 Phase 3 迁移中，双击行可打开目录）"
            )
            return
        asset = variant.asset
        mode = str(asset.get("flash_mode", "disabled"))
        module = str(asset.get("firmware_label", "")) or str(asset.get("firmware_type", ""))
        version = variant.version or str(asset.get("version", "")) or "-"
        self.selection_summary.setText(
            f"已选：{module} / {variant.name or str(asset.get('directory_name', ''))}"
            f" · {version} · {variant.source_label} · {flash_mode_label(mode)}"
        )
        self.ops_placeholder.setText(f"操作模式 {flash_mode_label(mode)} 的面板将在 Phase 3 提供；双击行可打开目录")

    # ------------------------------------------------------------------ 右键菜单（设为平台默认）
    def _on_grid_right_click(self, variant: ModuleVariant, global_pos) -> None:
        menu = QMenu(self)

        asset = variant.asset
        is_common = variant.source_kind == "common" and str(asset.get("category", "")) == "common"
        if is_common:
            platforms = self.workbench_model.platform_names(self.current_selection.model_name)
            current_defaults = set(self.workbench_model.default_platforms_for(asset))
            if not platforms:
                action = QAction("设为平台默认（未找到平台配置）", menu)
                action.setEnabled(False)
                menu.addAction(action)
            elif len(platforms) == 1:
                p = platforms[0]
                if p in current_defaults:
                    action = QAction(f"✓ 已是「{p}」默认程序", menu)
                    action.setEnabled(False)
                    menu.addAction(action)
                else:
                    action = QAction(f"设为「{p}」默认程序", menu)
                    action.triggered.connect(lambda _c=False, name=p: self._set_default_variant(name, variant))
                    menu.addAction(action)
            else:
                submenu = menu.addMenu("设为平台默认")
                for p in platforms:
                    if p in current_defaults:
                        action = QAction(f"✓ {p}（当前默认）", submenu)
                        action.setEnabled(False)
                    else:
                        action = QAction(p, submenu)
                        action.triggered.connect(
                            lambda _c=False, name=p: self._set_default_variant(name, variant)
                        )
                    submenu.addAction(action)
            menu.addSeparator()

        open_action = QAction("打开目录", menu)
        open_action.triggered.connect(lambda: self._open_asset_dir(variant))
        menu.addAction(open_action)
        copy_action = QAction("复制目录路径", menu)
        copy_action.triggered.connect(lambda: self._copy_to_clipboard(str(variant.asset.get("path", ""))))
        menu.addAction(copy_action)

        menu.exec(global_pos)

    def _set_default_variant(self, platform_name: str, variant: ModuleVariant) -> None:
        asset = variant.asset
        module = str(asset.get("firmware_label", "")) or str(asset.get("firmware_type", ""))
        shown = variant.name or str(asset.get("directory_name", ""))
        answer = QMessageBox.question(
            self,
            "设为平台默认",
            f"将「{module} / {shown}」设为平台「{platform_name}」的默认程序？\n\n"
            "定制方案缺少该模块时，将使用此程序补齐。",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        result = self.workbench_model.set_default_variant(
            self.current_selection.model_name, platform_name, asset, log_fn=self._log
        )
        if not result["ok"]:
            self._log(result["message"])
            QMessageBox.critical(self, "设置失败", result["message"])
            return
        self._refresh_main_grid()

    # ------------------------------------------------------------------ 工具
    def _open_asset_dir(self, variant: ModuleVariant) -> None:
        open_path_in_explorer(str(variant.asset.get("path", "")), self._log)

    def _copy_to_clipboard(self, text: str) -> None:
        if not text:
            return
        QApplication.clipboard().setText(text)
        self._log(f"已复制: {text}")


class QtWorkbenchWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("按摩椅程序资产管理系统 | Massage Chair Firmware Asset Manager")
        self.resize(1400, 850)
        self.workbench = WorkbenchInterface(self)
        self.addSubInterface(self.workbench, FluentIcon.HOME, "程序资产工作台")


def main() -> int:
    app = QApplication(sys.argv)
    setTheme(Theme.AUTO)
    window = QtWorkbenchWindow()
    window.show()

    # 自动化验证钩子（截图 / 定时退出），供开发与 Phase 4 回归用
    shot = os.environ.get("FWASSET_QT_SCREENSHOT", "")
    if shot:
        QTimer.singleShot(1500, lambda: (window.grab().save(shot), print(f"SCREENSHOT={shot}", flush=True)))
    quit_ms = int(os.environ.get("FWASSET_QT_QUIT_MS", "0") or "0")
    if quit_ms > 0:
        QTimer.singleShot(quit_ms, app.quit)

    return app.exec()


if __name__ == "__main__":
    # 开发直跑入口（等价 FWASSET_UI=qt uv run fwasset）；正式入口在 app.main。
    raise SystemExit(main())
