from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QItemSelectionModel, Qt, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QCompleter,
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
from fwasset.ui.workbench_helpers import (
    flash_mode_label,
    model_chip_values,
    module_label_from_asset,
    set_default_action_label,
    set_default_confirm_message,
)
from fwasset.ui_qt.data_grid import DataGrid
from fwasset.ui_qt.operation_panels import get_panel
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
    # 后台任务结果回投（对应 CTk BaseFlashPanel 的 queue + after 轮询）
    # 传 (task_id, name, result)；on_done 按 id 在 UI 线程查找执行（不 marshal callable）
    _task_done = Signal(int, str, object)      # task_id, name, result
    _task_failed = Signal(int, str, str)       # task_id, name, error
    # 日志跨线程回投：worker 线程里调用 _log 时不能直写 QPlainTextEdit
    log_message = Signal(str)

    busy_message = "已有任务执行中，请稍后"
    scanning_message = "正在扫描中，请稍后再执行任务"

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
        self._busy = False
        self.active_operation_panel = None
        self._task_seq = 0
        self._pending_task_callbacks: dict[int, object] = {}

        self._build_layout()

        self.scan_result_ready.connect(self._handle_scan_result)
        self._task_done.connect(self._on_task_done)
        self._task_failed.connect(self._on_task_failed)
        self.log_message.connect(self._append_log)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(SEARCH_REFRESH_DEBOUNCE_MS)
        self._search_timer.timeout.connect(self._on_search_debounced)
        self.search_edit.textChanged.connect(lambda _t: self._search_timer.start())

        # 型号下拉的切换防抖：EditableComboBox 在输入文字恰好等于某项时会立即
        # 发 currentIndexChanged（"L36" 是 "L36双机芯-…" 的前缀，输到一半就会
        # 命中），所以切型号必须经短暂防抖确认，键入中间态被后续输入取消。
        self._pending_model = ""
        self._model_switch_timer = QTimer(self)
        self._model_switch_timer.setSingleShot(True)
        self._model_switch_timer.setInterval(250)
        self._model_switch_timer.timeout.connect(self._apply_pending_model)

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

        # 操作区：选择摘要 + 按 flash_mode 挂载的操作面板
        ops = QFrame(self)
        self.ops_layout = QVBoxLayout(ops)
        self.ops_layout.setContentsMargins(SPACE_XS, SPACE_XXS, SPACE_XS, SPACE_XXS)
        self.selection_summary = CaptionLabel("未选择变体", ops)
        self.ops_layout.addWidget(self.selection_summary)
        self.ops_placeholder = BodyLabel("展开模块并选择具体变体以查看操作", ops)
        self.ops_layout.addWidget(self.ops_placeholder)
        main.addWidget(ops)

        # 日志
        self.log_panel = LogPanel(self)
        main.addWidget(self.log_panel)

        root_layout.addLayout(main, stretch=1)

    # ------------------------------------------------------------------ 日志
    def _log(self, message: str) -> None:
        # 可能被 worker 线程调用（扫描/烧录任务的 log_fn），经 Signal 回投 UI 线程
        self.log_message.emit(message or "")

    def _append_log(self, message: str) -> None:
        self.log_panel.write(message)
        self._file_logger.log(message)

    # ------------------------------------------------------------------ 后台任务（PanelHost）
    def _run_task(self, name: str, fn, on_done=None) -> None:
        if self._busy:
            self._log(self.busy_message)
            return
        if self.scan_state_model.is_scanning:
            self._log(self.scanning_message)
            return
        self._busy = True
        task_id = self._task_seq
        self._task_seq += 1
        # 回调只存 UI 侧 map，Signal 不传 callable（与 CTk「UI 线程 on_done」一致）
        if callable(on_done):
            self._pending_task_callbacks[task_id] = on_done

        def worker():
            try:
                result = fn(self._log)
                self._task_done.emit(task_id, name, result)
            except Exception as exc:  # noqa: BLE001
                self._task_failed.emit(task_id, name, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_task_done(self, task_id: int, name: str, result) -> None:
        self._busy = False
        on_done = self._pending_task_callbacks.pop(task_id, None)
        if callable(on_done):
            try:
                on_done(result)
            except Exception as exc:  # noqa: BLE001
                self._log(f"{name} 回调异常: {exc}")
        # ServiceResult：按 ok 区分完成/失败，避免 copy_failed 仍显示「完成」
        if isinstance(result, dict) and "ok" in result:
            if result.get("ok"):
                self._log(f"{name}完成")
            else:
                msg = str(result.get("message") or "未知错误")
                self._log(f"{name}失败: {msg}")
                QMessageBox.warning(self, f"{name}失败", msg)
        else:
            self._log(f"{name}完成")

    def _on_task_failed(self, task_id: int, name: str, error: str) -> None:
        self._busy = False
        self._pending_task_callbacks.pop(task_id, None)
        self._log(f"{name}失败: {error}")
        QMessageBox.critical(self, f"{name}失败", error)

    # ------------------------------------------------------------------ PanelHost 选中资产与交接动作
    def _selected_asset(self) -> dict | None:
        data = self.grid_panel.get_selected_data()
        return data.asset if data else None

    def _open_current_asset_dir(self) -> None:
        data = self.grid_panel.get_selected_data()
        if data:
            open_path_in_explorer(str(data.asset.get("path", "")), self._log)

    def _copy_asset_dir_path(self) -> None:
        data = self.grid_panel.get_selected_data()
        if data:
            self._copy_to_clipboard(str(data.asset.get("path", "")))

    def _copy_primary_file_path(self) -> None:
        data = self.grid_panel.get_selected_data()
        if not data:
            return
        asset = data.asset
        files = list(asset.get("files", []))
        path = str(asset.get("path", ""))
        if files:
            self._copy_to_clipboard(str(Path(path) / files[0]))
        else:
            self._copy_to_clipboard(path)

    def _launch_tool_and_open_asset_dir(self) -> None:
        panel = self.active_operation_panel
        if panel is not None and hasattr(panel, "_launch_current_tool"):
            panel._launch_current_tool()
        self._open_current_asset_dir()

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
        # 与烧录任务互锁：任务进行中禁止扫描（避免 save_assets 与面板拆除竞态）
        if self._busy:
            self._log(self.busy_message)
            return
        # 单工作区：每次扫描都让用户确认/切换根目录。已绑定的 root（含启动时
        # 从 scan_meta 恢复的）只作为对话框初始路径，不再静默重扫、无法换根。
        initial = (self.root_dir or "").strip() or str(Path.cwd())
        root = QFileDialog.getExistingDirectory(self, "选择固件所在的根目录", initial)
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

        # 取消：库未写、payload 为空，勿当「扫描完成 0 项」并错误 rebind
        if result.get("code") == "cancelled":
            self._log(str(result.get("message") or "扫描已被用户取消"))
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

        chips, _overflow = model_chip_values(self._available_models, self.current_selection.model_name)
        self.model_hint.setVisible(not chips)
        for model in chips:
            btn = TogglePushButton(model, self)
            btn.setChecked(model == self.current_selection.model_name)
            btn.clicked.connect(lambda _c=False, value=model: self._on_model_changed(value))
            self.chip_bar.addWidget(btn)

        # 常驻可搜索型号下拉（含全部型号）：型号是作用域选择器，不走搜索框；
        # 型号少时也保留（用户要求，便于验证与键盘定位），多时是唯一入口。
        if self._available_models:
            combo = EditableComboBox(self)
            combo.addItems(self._available_models)
            combo.setPlaceholderText("搜索型号…")
            combo.setCurrentIndex(-1)
            combo.setMinimumWidth(150)
            completer = QCompleter(self._available_models, combo)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            combo.setCompleter(completer)
            # 不接 currentTextChanged（每键都发）；currentIndexChanged 只在文本
            # 精确命中某项/从补全菜单选中时发，再经防抖确认，见 _schedule_model_switch。
            combo.currentIndexChanged.connect(
                lambda i, c=combo: self._schedule_model_switch(c.itemText(i))
            )
            self.chip_bar.addWidget(combo)
            self.model_combo = combo

    def _schedule_model_switch(self, model_name: str) -> None:
        if not model_name or model_name not in self._available_models:
            return
        self._pending_model = model_name
        self._model_switch_timer.start()

    def _apply_pending_model(self) -> None:
        name = self._pending_model
        self._pending_model = ""
        if name and name != self.current_selection.model_name:
            self._on_model_changed(name)

    # ------------------------------------------------------------------ 侧边树
    def _nav_entry_matches_selection(self, kind: str, key: str) -> bool:
        sel = self.current_selection
        if kind == "all":
            return sel.node_type == "all"
        if kind == "common_type":
            return sel.node_type == "common_type" and sel.common_type == key
        if kind == "custom_scheme":
            return sel.node_type == "custom_scheme" and sel.scheme_name == key
        return False

    def _clear_nav_pointer_highlight(self) -> None:
        """清除 qfluentwidgets delegate 缓存的鼠标瞬态行。"""
        self.nav._setPressedRow(-1)
        self.nav._setHoverRow(-1)

    def _apply_nav_selection_highlight(self) -> None:
        """按 current_selection 定位高亮（重建列表后索引会变，不能依赖旧 currentRow）。"""
        target = -1
        for i, (kind, key) in enumerate(self._nav_entries):
            if kind == "section":
                continue
            if self._nav_entry_matches_selection(kind, key):
                target = i
                break
        # qfluentwidgets 的 delegate 会独立缓存鼠标按压/悬停行。搜索态点击后
        # 立即重建完整列表时，旧行号会映射到另一个项目并留下伪高亮。
        self._clear_nav_pointer_highlight()
        self.nav.blockSignals(True)
        try:
            if target >= 0:
                self.nav.setCurrentRow(
                    target,
                    QItemSelectionModel.SelectionFlag.ClearAndSelect,
                )
                item = self.nav.item(target)
                if item is not None:
                    self.nav.scrollToItem(item)
            else:
                self.nav.setCurrentRow(-1)
        finally:
            self.nav.blockSignals(False)
        # currentRowChanged 在 mousePressEvent 内同步触发；上述代码返回后，
        # 外层点击仍会把旧行重新写入 selection model。下一轮事件循环必须
        # 重新执行完整选择，而不只是清 delegate 的鼠标状态。
        QTimer.singleShot(0, self._finalize_nav_selection_highlight)

    def _finalize_nav_selection_highlight(self) -> None:
        """鼠标点击调用栈结束后，按逻辑选择强制同步 Qt 与 QFluent 状态。"""
        target = next(
            (
                i
                for i, (kind, key) in enumerate(self._nav_entries)
                if kind != "section" and self._nav_entry_matches_selection(kind, key)
            ),
            -1,
        )
        self._clear_nav_pointer_highlight()
        self.nav.blockSignals(True)
        try:
            if target >= 0:
                self.nav.setCurrentRow(
                    target,
                    QItemSelectionModel.SelectionFlag.ClearAndSelect,
                )
            else:
                self.nav.clearSelection()
                self.nav.setCurrentRow(-1)
        finally:
            self.nav.blockSignals(False)

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

        def _add_entry(text: str, kind: str, key: str) -> None:
            item = QListWidgetItem(text)
            self.nav.addItem(item)
            self._nav_entries.append((kind, key))

        def _add_section(text: str) -> None:
            item = QListWidgetItem(text)
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.nav.addItem(item)
            self._nav_entries.append(("section", ""))

        _add_entry("全部程序与模块", "all", "")

        if tree_data["common"]:
            _add_section("── 通用模块 ──")
            for fw_label, count in tree_data["common"].items():
                if search_kw and search_kw not in fw_label.lower():
                    continue
                _add_entry(f"{fw_label} ({count})", "common_type", fw_label)

        if tree_data["custom"]:
            _add_section("── 定制方案 ──")
            for scheme in tree_data["custom"]:
                if search_kw and search_kw not in scheme.lower():
                    continue
                _add_entry(f"◆ {scheme}", "custom_scheme", scheme)

        self.nav.blockSignals(False)
        # 重建后按逻辑选中项高亮（勿保留点击时的旧行号）
        self._apply_nav_selection_highlight()

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
            # Issue 19-A：进入方案默认满树，清掉全局搜索残留（避免「以色列」滤成只剩手控）。
            # 必须同步重建侧栏：blockSignals 清搜索不会触发 debounce，否则侧栏
            # 仍按旧关键词过滤，其它定制方案会「消失」。重建后按 scheme 重定位高亮。
            if self.search_edit.text().strip():
                self.search_edit.blockSignals(True)
                self.search_edit.clear()
                self.search_edit.blockSignals(False)
                self._refresh_sidebar_tree()
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
        # 先拆掉上一个操作面板，避免选行叠加旧面板
        if self.active_operation_panel is not None:
            self.ops_layout.removeWidget(self.active_operation_panel)
            self.active_operation_panel.deleteLater()
            self.active_operation_panel = None

        if not variant:
            self.selection_summary.setText("未选择变体")
            self.ops_placeholder.setText("展开模块并选择具体变体以查看操作")
            self.ops_placeholder.show()
            return

        asset = variant.asset
        mode = str(asset.get("flash_mode", "disabled")) or "disabled"
        module = str(asset.get("firmware_label", "")) or str(asset.get("firmware_type", ""))
        version = variant.version or str(asset.get("version", "")) or "-"
        self.selection_summary.setText(
            f"已选：{module} / {variant.name or str(asset.get('directory_name', ''))}"
            f" · {version} · {variant.source_label} · {flash_mode_label(mode)}"
        )

        PanelClass = get_panel(mode)
        if PanelClass is None:
            self.ops_placeholder.setText(f"暂不支持的操作模式: {mode}")
            self.ops_placeholder.show()
            return

        self.ops_placeholder.hide()
        panel = PanelClass(asset=asset, log_fn=self._log, panel_host=self)
        panel.build()
        self.ops_layout.addWidget(panel)
        self.active_operation_panel = panel

    # ------------------------------------------------------------------ 右键菜单（设为「型号」模块默认版本）
    def _on_grid_right_click(self, variant: ModuleVariant, global_pos) -> None:
        menu = QMenu(self)

        asset = variant.asset
        model_name = self.current_selection.model_name
        module = module_label_from_asset(asset)
        is_common = variant.source_kind == "common" and str(asset.get("category", "")) == "common"
        if is_common:
            # 无 toml 也可设默认（软件自动创建配置）；已是默认则灰掉
            if self.workbench_model.is_model_module_default(asset):
                action = QAction(
                    set_default_action_label(model_name, module, is_current=True),
                    menu,
                )
                action.setEnabled(False)
                menu.addAction(action)
            else:
                action = QAction(set_default_action_label(model_name, module), menu)
                action.triggered.connect(lambda _c=False: self._set_default_variant(variant))
                menu.addAction(action)
            menu.addSeparator()

        open_action = QAction("打开目录", menu)
        open_action.triggered.connect(lambda: self._open_asset_dir(variant))
        menu.addAction(open_action)
        copy_action = QAction("复制目录路径", menu)
        copy_action.triggered.connect(lambda: self._copy_to_clipboard(str(variant.asset.get("path", ""))))
        menu.addAction(copy_action)

        menu.exec(global_pos)

    def _set_default_variant(self, variant: ModuleVariant) -> None:
        asset = variant.asset
        model_name = self.current_selection.model_name
        module = module_label_from_asset(asset)
        shown = variant.name or str(asset.get("directory_name", ""))
        answer = QMessageBox.question(
            self,
            "设为默认版本",
            set_default_confirm_message(model_name, module, shown),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        result = self.workbench_model.set_default_variant(
            model_name, asset, log_fn=self._log
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

    # 自动化验证钩子（截图 / 自动选行 / 定时退出），供开发与 Phase 4 回归用
    if os.environ.get("FWASSET_QT_AUTOSELECT", ""):
        QTimer.singleShot(1000, lambda: window.workbench.grid_panel.select_first_variant())
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
