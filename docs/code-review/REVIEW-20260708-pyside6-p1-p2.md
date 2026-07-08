# 代码审查:PySide6 迁移 Phase 1+2(壳 + 数据面)

- 日期:2026-07-08
- 类型:UI 框架迁移(增量 + 双轨)
- 模块:
  - `src/fwasset/app.py`(入口加 `FWASSET_UI=qt` 开关,默认仍走 CTk)
  - `src/fwasset/ui_qt/__init__.py`(包文档)
  - `src/fwasset/ui_qt/workbench_window.py`(新增 579 行,Qt 版工作台)
  - `src/fwasset/ui_qt/data_grid.py`(新增 165 行,Qt 版可展开树)
  - `src/fwasset/ui_qt/log_panel.py`(新增 45 行,可折叠日志)
  - `scripts/spike_pyside6.py`(Phase 0 spike 脚本,194 行,留档)
  - `pyproject.toml`(`[qt]` optional extra + `coverage.omit` 加 `ui_qt/*`)
- 来源:`specs/active/TASK-20260708-pyside6-migration.md` Phase 1+2 段 + AGENTS.md「双轨 + scope 纪律」

## 0. 整体评价

**优点**:scope 纪律执行到位,`ui_qt/` 目录与 `ui/` 严格分离,`app.py` 懒加载避免污染默认路径,数据层(`SchemeWorkbenchModel` / `core/**`)零改动,search debounce 与 scan 跨线程用 Qt 原生 `QTimer(singleShot=True)` + `Signal/Slot` 替换了 Tk 的 `after()` + 三次 `winfo_exists()` 防御 —— 长期更稳。

**问题**:有 1 项阻断级 + 3 项重要发现（另有 1 项原判为重要的 3.5 经代码对照确认为误判）+ 4 项遗漏需要先处理再提交;整体不需重写,但 P1 计划里的「QSS 设计令牌落位」**未落地**(`workbench_window.py` 有 9 处硬编码 `setSpacing(8/12/6/10)` / `setContentsMargins(12,12,4,0)` / `SIDEBAR_WIDTH=300` 等,与 `ui/design_tokens.py` 没有对应关系)。

---

## 1. 与计划对照(Phase 1+2 交付清单)

| 计划项 | 状态 | 证据 |
|---|---|---|
| 新建 `ui_qt/` 并行目录 | OK | `src/fwasset/ui_qt/{__init__,data_grid,log_panel,workbench_window}.py` |
| 不动现有 `ui/` | OK | `git diff ui/` 改动为空 |
| shell + 布局骨架(侧边/顶栏/表格/操作/日志) | OK | `_build_layout` 五段齐全(line 122-202) |
| QSS 设计令牌落位 | **缺失** | 无 QSS 文件;9 处硬编码 spacing;`SIDEBAR_WIDTH` 重复定义未与 `ui/design_tokens.SIDEBAR_WIDTH` 同步 |
| `app.py` 加 `FWASSET_UI=qt` 开关 | OK | `app.py:9-13`,懒加载,默认仍走 CTk |
| 侧边树(通用 + 定制) | OK | `_refresh_sidebar_tree` (line 337-390) + `_on_nav_changed` 路由三类节点 |
| 型号 chips + 溢出 ComboBox | OK | `model_chip_values` + `_refresh_model_selector`(line 313-334) |
| 搜索框 + 防抖 | OK | `_search_timer = QTimer(singleShot=True)` + 180ms(line 112-116) |
| DataGrid:模块行/变体子行 | OK | `populate_tree` 单变体平铺 / 多变体收子节点(line 56-90) |
| ★默认 徽章 | OK | `_variant_text` 拼接 `default_badge`,多平台格式由 view_model 决定 |
| 右键菜单:设为默认/打开目录/复制路径 | OK | `_on_grid_right_click` 三段齐全(line 467-508) |
| 双击开目录 | OK | `data_grid._on_double_click` + `workbench_window._open_asset_dir` |
| 操作区占位 + PanelHost 留 Phase 3 | OK | `ops_placeholder` 显式标注「Phase 3 迁移中」(line 194) |
| 默认入口切到 Qt | 跳过(按计划) | 默认仍 CTk,正确 |
| `coverage.omit` 加 `ui_qt/*` | OK | `pyproject.toml:47` |

**Phase 1+2 计划完成度:11/12 关键项 OK,1 项缺失(QSS 令牌未落位)**。

---

## 2. 自动化门禁(我跑的)

- `python -m pytest -m "not ui" -q --no-cov` → **216 passed, 34 deselected in 6.71s**(与 commit message 一致)
- `ast.parse` 三文件 → AST_OK
- `python -c "import pyside6"` → **ModuleNotFoundError**(`pyside6` 不在当前 `.venv` 中,需要 `uv sync --extra dev --extra qt` 才能在 review 端跑 Qt 代码)

---

## 3. 发现(按严重度分级)

### 阻断级(必须本轮处理)

#### 3.1 P1 计划承诺的「QSS 设计令牌落位」未落地

`specs/active/TASK-20260708-pyside6-migration.md` Phase 1 明文写「**QSS 设计令牌落位**」,但当前 `ui_qt/` 里没有任何 QSS 文件或令牌模块。`workbench_window.py` / `data_grid.py` / `log_panel.py` 共 9 处硬编码:

```
workbench_window.py:124: root_layout.setContentsMargins(0, 0, 8, 8)
workbench_window.py:125: root_layout.setSpacing(12)
workbench_window.py:131: side_layout.setContentsMargins(12, 12, 4, 0)
workbench_window.py:147: main.setSpacing(10)
workbench_window.py:162: chip_bar.setSpacing(6)
workbench_window.py:191: ops_layout.setContentsMargins(4, 2, 4, 2)
workbench_window.py:  SIDEBAR_WIDTH = 300          (line 57,与 ui/design_tokens.SIDEBAR_WIDTH=400 偏离)
data_grid.py:37:        layout.setContentsMargins(0, 0, 0, 0)
log_panel.py:16:        layout.setContentsMargins(0, 0, 0, 0)
```

**违反 AGENTS.md 规则**:「All colors and fonts from `ui/design_tokens.py`」「Never hard-code hex values or font sizes」。

**处理方案**(二选一):

- **方案 A(推荐)**:新建 `src/fwasset/ui_qt/design_tokens.py`,把 CTk 的 light/dark 元组映射到 QSS 字符串;在 `main()` 里 `app.setStyleSheet(...)` 一次性注入;`workbench_window.py` 用常量名引用(`SIDE_PAD`, `V_GAP`, `H_GAP` 等),删除硬编码。
- **方案 B**:在 `ui_qt/` 下加一个 `layout.py`,把 9 处常量集中,至少留一个 token 表 + 注释指明「对应 ui/design_tokens.SPACE_*」,后续 Phase 3 集中迁。

#### 3.2 Qt 工作台零测试覆盖

`src/fwasset/tests/` 下没有任何 `test_*qt*.py` / `test_ui_qt*`。Phase 0 spike 也没有自动化测试,纯靠截图肉眼比对。

commit message 说「216 passed」**这是 CTk 测试数,与 Qt 无关**。意味着:
- Qt 工作台目前**任何一行新代码都没有 CI 门禁**;
- Phase 4「pytest-qt 重写关键契约」的工作量还没开始堆;
- 如果有人在 PR 里改坏 `populate_tree` 的渲染逻辑,CI 不会报警。

**处理方案**(至少先做 smoke 级):

- 新增 `tests/test_qt_smoke.py`(`@pytest.mark.ui`,需要 display):仅做 `from fwasset.ui_qt.workbench_window import QtWorkbenchWindow` + `QApplication` 起一个 + 调用 `populate_tree([])` 不抛异常。
- 把 dev extra 加上 `pytest-qt` + `qt` extra 加进 dev 的 `uv sync` 默认建议(改 `scripts/test.ps1`)。
- 当前合并前**至少先确认**:`uv sync --extra dev --extra qt && uv run python -m pytest tests/test_qt_smoke.py -q --no-cov` 通过。

---

### 重要(建议本轮修)

#### 3.3 `model_chip_values` 与 `flash_mode_label` 在两处 verbatim 重复

`workbench_window.py:62-78` 与 `workbench_panel.py` 中的同名函数逐字相同;同样 `flash_mode_label` 也重复。注释说「CTk 退役时合并到共享模块」,但**目前已经在重复**。

**建议**:Phase 1 阶段就提前抽到 `src/fwasset/ui/_shared/model_chips.py`,让 CTk 与 Qt 都 import 这个。两份函数现在就开始漂移(虽然内容一样),Phase 3 之后大概率 bug。

#### 3.4 双击/右键开目录逻辑在两处实现

- `data_grid.py:124-138` `_on_double_click` 内嵌 5 行 `os.startfile`/xdg-open 逻辑
- `workbench_window.py:532-543` `_open_asset_dir` 又写一遍

**建议**:抽 `src/fwasset/core/asset_helpers.py` 或新建 `src/fwasset/ui/_shared/open_dir.py`,签名 `open_path_in_os(path: str, log_fn)`,两边都用,避免下次加 macOS `open` 支持时漏改一处。

#### 3.5 `search_edit.textChanged` lambda 必要（审查误判，无需修改）

`workbench_window.py:116`:
```python
self.search_edit.textChanged.connect(lambda _t: self._search_timer.start())
```

审查初判 `_t` 被忽略、Qt signal slot 允许直连。**但实际不可行**：
`textChanged` 信号发射 `str` 参数，`QTimer.start` 有 `start()` 和 `start(int)` 两个重载，直连会把字符串传给 `start(int)` 导致 `TypeError`。Lambda 正确地销毁了多余参数，是必要代码。

**处理**：保留当前写法，无需修改。

#### 3.6 Signal 类型太宽

`workbench_window.py:94`:
```python
scan_result_ready = Signal(dict)
```

`dict` 太松,应该用 `ServiceResult` TypedDict 给 mypy / IDE 留类型钩子。当前纯运行时不会有问题,但 Phase 3 接操作面板后这条 signal 会传更复杂 payload。

**建议**:改成 `Signal(ServiceResult)`(`from fwasset.core.types import ServiceResult`)。

---

### 一般(可延后到 Phase 3 或合并前 polish)

#### 3.7 `scripts/spike_pyside6.py` 默认 `--root "D:\按摩器程序"`

`scripts/spike_pyside6.py:30` 的 argparse 默认值指向具体机器路径。在其他机器或 CI 上 `--root` 不传会直接报路径不存在。

**建议**:默认改为 `""`,在 `build_model` 里 `if not args.root: parser.error(...)`。

#### 3.8 多变体父行右键无菜单

`data_grid.py:139-145` 仅当 child 有 `_VARIANT_ROLE` 时才 emit `variant_right_clicked`。父行(模块类型行)右键不会出菜单。

**这是 by design**(只对变体操作),但 UI 上用户看到多变体父行的右键「无反应」会困惑。**建议**:在多变体父行右键时弹一个简化菜单(如「展开/收起」+ 「查看模块信息」),或在 `setFlags` 时给父行加视觉提示。

#### 3.9 `__main__` 块存在但无 docstring 说明

`workbench_window.py:578-579`:
```python
if __name__ == "__main__":
    raise SystemExit(main())
```

`app.py` 已经接管入口,这里的 `__main__` 是给直接 `python workbench_window.py` 用的,但没有 docstring 说明。**建议**加一行注释指向 spike 脚本。

#### 3.10 `_handle_scan_result` 中 `db_path = None` 的遗留

虽然 Phase 1 不动数据层,但 `workbench_model.bind(None, root_dir)` 这里 `None` 仍然走 `ASSET_INDEX_PATH` 默认值。**plan 里 Phase 3 才修,认可**。

#### 3.11 （遗漏）`QTreeWidget` 未启用斑马纹

`data_grid.py:39-47` 未调用 `setAlternatingRowColors(True)`。AGENTS.md 承诺的「斑马纹原生支持」未落地。

**建议**：加一行 `self.tree.setAlternatingRowColors(True)`。

#### 3.12 （遗漏）单变体/多变体 name 渲染逻辑不一致

`data_grid.py:56-61` `_variant_text` 静态方法在单变体时将 `variant.name == label` 替换为「默认」；但多变体子行(line 83-84)直接拼接原名，未用 `_variant_text`。

**建议**：统一走 `_variant_text`，或加注释说明有意为之。

#### 3.13 （遗漏）DataGrid 列未设 stretch

`data_grid.py:42-46` 所有列固定宽度，未设置 `header.setStretchLastSection(True)`，窗口横向缩放时最后一列不填充。

#### 3.14 （遗漏）`scripts/test.ps1` 不含 `--extra qt`

`scripts/test.ps1:3` 仅 `uv sync --extra dev`，不装 PySide6，即使 Phase 4 加了 Qt 测试也无法被 CI 覆盖。

**建议**：改 `scripts/test.ps1:3` 为 `uv sync --extra dev --extra qt`。

---

### 已对齐 / 表扬

- **数据层零改动**:`scheme_workbench_model.py` / `core/**` 未被 ui_qt 触碰;
- **懒加载**: `app.py:11` 在 `FWASSET_UI=qt` 之前不 import `fwasset.ui_qt`,默认 `.\scripts\test.ps1` 不被 PySide6 污染;
- **coverage omit 更新**:`pyproject.toml:47` 加 `src/fwasset/ui_qt/*`,不让 Qt UI 把覆盖率拉低;
- **跨线程**: `run_scan` 在子线程里 emit `scan_result_ready`,Qt 自动 queued connection,免去 Tk 的 `winfo_exists()` 三次防御;
- **搜索防抖语义**:`QTimer(singleShot=True)` 的 `start()` 自动取消前一次,等价于 Tk 的「cancel + reschedule」,但代码更短;
- **`get_global_usb_drive()` 实现** (`workbench_window.py:219-220`),满足 PanelHost 契约,Phase 3 可直接接入;
- **`_on_nav_changed` 处理 `kind == "section"`** early-return(line 396),避免点「── 通用模块 ──」分隔符引发空刷新;
- **★默认徽章文本格式由 view_model 提供**(`default_badge: "★默认"` / `"★默认·平台A/平台B"`),UI 不再硬编码格式;
- **ui_qt 包文档**(`__init__.py`)明确指向迁移 plan。

---

## 4. 人验回归清单(按 AGENTS.md 「UI 改动先人工验证」)

提交前请人工跑一遍,贴结果:

- [ ] **FWASSET_UI=qt 启动**:`uv run fwasset`(环境变量前置)能弹出 FluentWindow,标题栏中文不糊
- [ ] **真实数据截图**:`.runtime/qt_phase1b.png` 与新截图肉眼一致(7 通用模块 + 6 方案、双型号 chips、★默认徽章)
- [ ] **缓存加载**:无 scan_meta 时启动显示「请扫描」;有 scan_meta 时显示「使用上次扫描的根目录: …」
- [ ] **扫描**:点「扫描目录」选根,扫描期间按钮变「取消中…」,完成后自动 populate_tree
- [ ] **取消扫描**:扫描中点按钮,线程退出,按钮回到「扫描目录」
- [ ] **U 盘选择器**:启动后 100ms 内列表非空(自动 `after(100, _refresh_usb)`),插拔 U 盘后点「刷新」实时更新
- [ ] **搜索**:连打「主板 防夹」空格分词,侧栏/主表只刷新一次(180ms 内连续输入不闪)
- [ ] **★默认徽章**:右键通用模块变体 → 「设为平台默认」 → 确认 → 徽章位置立即迁移到新变体
- [ ] **右键菜单**:右键变体 → 「打开目录」「复制目录路径」「设为平台默认」三项齐全
- [ ] **多变体父行**:展开 / 折叠,选 child 才触发操作区
- [ ] **关闭主窗口**:无 `TclError`(Qt 不存在此问题,但需确认不阻塞)

---

## 5. 风险与建议

### 风险

- **GPLv3 锁死**:QFluentWidgets 是 GPLv3,本机 OK,但若日后要分发 exe 必须决策(plan 风险段已提)。Phase 4 之前必须明确「分发对象」并把这一项从「待决」变「已决」。
- **Python 3.13+ PySide6 wheel**:Phase 0 spike 没验过 ≥ 3.13,`tomllib` 内置后 `tomli` 兜底已不需要,但 Qt 6.6+ 是否对 3.13 出 wheels 需要复核。
- **Phase 3 PanelHost 协议改造**:本次没动 `host_types.py`,但 `get_global_usb_drive()` 已经在 Qt 端实现。Phase 3 第一步必须先把 `usb_drive: tk.StringVar` 字段从 Protocol 拿掉(用结构子类型),否则注册表走两套。

### 建议(提交前可立即做)

1. **3.1 QSS 令牌**:抽 `ui_qt/design_tokens.py`,9 处硬编码改成命名常量。**优先级最高**。
2. **3.2 Qt smoke 测试**:加 `tests/test_qt_smoke.py`(至少 import + 空 populate_tree 不抛异常),并在 dev extra 或 README 写清 `uv sync --extra dev --extra qt`。
3. **3.11 斑马纹**:加一行 `setAlternatingRowColors(True)`。
4. **3.13 列 stretch**:加 `header.setStretchLastSection(True)`。
5. **3.14 test.ps1**:改 `uv sync --extra dev` 为 `uv sync --extra dev --extra qt`。
6. **3.3 + 3.4**:抽 `_shared/` 公共代码,避免 Phase 3 时三处改同一逻辑。

### 不建议延后

- 3.1(QSS 令牌)是 AGENTS.md 规则硬约束,延后等于技术债。
- 3.2(零测试)让 Phase 4 验收清单没有任何自动化兜底。
- 3.11/3.13(斑马纹/列stretch)各一行代码,随手修。

---

## 6. 状态（2026-07-08 修复轮已完成）

- [x] 阻断级 3.1 令牌落位 → `ui_qt/design_tokens.py`（布局度量令牌，9 处硬编码全部替换；颜色/字体由 QFluentWidgets 主题供给并在模块 docstring 声明，SIDEBAR_WIDTH=300 与 CTk 400 的偏离已注明原因：Qt 壳另有导航栏）
- [x] 阻断级 3.2 Qt smoke 测试 → `tests/test_qt_smoke.py`（6 例，`QT_QPA_PLATFORM=offscreen` 无显示器可跑，`pytest.importorskip` 保证未装 qt extra 时优雅跳过）
- [x] 重要 3.3 helper 去重 → 抽 `ui/workbench_helpers.py`（纯函数，双壳共用），CTk 侧 re-export 保持旧导入路径，`test_workbench_panel_helpers` 不受影响
- [x] 重要 3.4 开目录去重 → `core/asset_helpers.py::open_path_in_explorer`（含 3 个新测试），ui_qt 两处调用点收敛
- [x] 重要 3.5 误判确认 → 保留 lambda（textChanged(str) 直连 QTimer.start(int) 会 TypeError）
- [x] 重要 3.6 调整后处理 → **审查建议本身不可行**：`ServiceResult` 是 TypedDict，不能作 `Signal()` 元类型；改为槽函数参数标注 `result: ServiceResult` + Signal 处注释说明
- [x] 一般 3.7 spike 默认路径 → `--root` 改必填（parser.error）
- [x] 一般 3.8 父行右键 → 加「展开/收起」轻量菜单
- [x] 一般 3.9 `__main__` 注释 → 已加
- [x] 一般 3.10 db_path=None → 按计划留 Phase 3，不动
- [x] 一般 3.11 斑马纹 → `setAlternatingRowColors(True)`
- [x] 一般 3.12 渲染差异 → 有意为之（多变体子行必须显示原名，否则同名多份无法区分；与 CTk 一致），已加注释
- [x] 一般 3.13 列 stretch → `header().setStretchLastSection(True)`
- [x] 一般 3.14 test.ps1 → `uv sync --extra dev --extra qt`
- [x] 自动化门禁重跑：**219 passed, 40 deselected, coverage 85.06%**；Qt smoke 6 passed
- [x] 用户反馈补充：型号溢出下拉改 `EditableComboBox`（可输入过滤，MatchContains），`_on_model_changed` 加"仅接受真实型号"防呆（中间输入态不污染视图）
- [ ] 人验回归 11 项(见第 4 节) ← 待用户执行
- [x] Commit：`9dddc41`（Phase 1+2 本体，用户已拍板合 1 个）+ 本修复轮 commit（见第 7 节）

## 7. 关联 Commit

- 待填(用户拍板 commit hash):
  - `9dddc41 feat(qt): Qt 工作台壳与数据面(Phase 1+2,双轨)` ← 本次审查对象
  - `f12b0ed chore(qt): PySide6 迁移 Phase 0 spike 通过` ← 已 commit,本次未审(留档)

对应规划:`specs/active/TASK-20260708-pyside6-migration.md` Phase 1/2 完成,Phase 3 启动前补本 review 列出的 3.1 / 3.2 阻断项。