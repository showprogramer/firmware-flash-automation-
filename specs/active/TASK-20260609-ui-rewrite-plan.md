# TASK-20260609 · 工作台 UI 改写计划（主区树 + 精简操作区 + Fluent 风格）

> 分支：`feature/ui-workbench-redesign`
> 前置：P0 崩溃已修、数据层 `get_scheme_module_tree()` 已完成并验证（崩溃没了、数据对了）。
> 本计划只覆盖 **UI 渲染层**，数据层不再改。
> 交付顺序（用户已锁定）：**先改主区逻辑 + 操作区让用户试，功能对了再调 Fluent 风格。**

---

## 0. 设计基线（已锁定，勿改）

- **整机七程序固定层级**：一台机子固定 7 模块行：主板 / 手控UI / 蓝牙 / 语音 / 快捷键 / 3D机芯 /（2D机芯）/ 腿部。
- **多变体收在模块行下可展开**，绝不在顶层铺平。
- **来源标签**：🔵「定制专属」/ ⚫「通用默认」。**界面绝不出现「回源」**。
- **左侧导航**：保留「通用 / 定制」两区一目了然；型号（Model）仅用于搜索过滤，不污染分区。
  - 点 定制 → 某方案 = 右侧整机 7 模块可展开树。
  - 点 通用 → 某类型 = 该类型所有变体（可保持平铺，因为本就是按类看）。
- **操作区精简**：
  - 双击行 = 开目录（已实现于 DataGridPanel，移植到树）；**删除「打开目录」按钮**。
  - 手控UI（auto_usb）只要一个「一键烧录」；删 U盘选择器、删 1/2/3/4 分步按钮、删复制路径。
  - tool_launch 只要「打开烧录工具」；删 handoff 的复制路径 / U盘那一排。
  - 多变体不预设烧哪个：用户展开选中具体变体行后操作区才出现按钮。
  - 预留「增删改查」位置（占位按钮区，禁用态，future）。
- **风格目标**：对齐 `specs/images/treeview_workbench_mockup.png`（Win11 Fluent）。
  - 参考图要点：单棵可展开树（Module Type 带 ▾ 展开箭头），列 = Module Type / Variant Name / Version / Source / Mode；
    交替行底色；底部一条紧凑动作条（Open Folder / Flash / Validate / Upload）。

---

## 1. 改动文件清单

| 文件 | 动作 | 说明 |
|---|---|---|
| `ui/panels/data_grid_panel.py` | **重写** | 平表 → 父子可展开 `ttk.Treeview`，渲染 `list[ModuleRow]`。 |
| `ui/workbench_panel.py` | **改** | 主区接 `get_scheme_module_tree`；操作区精简；删顶部 `目录路径:` 标签。 |
| `ui/operation_panels/auto_usb_panel.py` | **改** | 手控 paired_files 只留「一键烧录」；删 U盘选择器与分步按钮。 |
| `ui/operation_panels/tool_launch_panel.py` | **改** | 只留「打开烧录工具」；去掉 `build_handoff_actions` 的复制/U盘排。 |
| `ui/operation_panels/shared_actions.py` | **看情况改** | 若 handoff 仅剩开目录，可瘦身或绕过。 |
| `tests/test_operation_panels.py` | **改** | 跟随面板精简调整断言（按钮文本/数量）。 |
| `tests/test_data_grid_panel.py` | **新增** | 树渲染：7 行、多变体收子节点、来源标签、双击开目录回调。 |

数据层 `scheme_workbench_model.py` **不动**（`ModuleRow` / `ModuleVariant` / `get_scheme_module_tree` 已就绪）。

---

## 2. 分步实施（TDD：红 → 绿）

### Step A — 重写 DataGridPanel 为可展开树（主区核心）
1. **测试先行** `test_data_grid_panel.py`：
   - 给定一个 `list[ModuleRow]`（含一个 3 变体的手控UI、一个单变体主板），`populate_tree()` 后：
     - 顶层 item 数 == 模块行数（7 或测试用的子集）。
     - 手控UI 顶层节点的 children == 3。
     - 单变体模块：顶层节点直接承载该变体（或 1 child，与实现一致）。
     - 选中某变体 child → `get_selected_data()` 返回对应 `ModuleVariant`（带 asset）。
     - 选中模块行（多变体父节点）→ 不触发操作面板（返回 None 或父态），等用户展开选变体。
2. **实现**：
   - 列：`("variant", "version", "source", "mode")`，`show="tree headings"`（开启 `#0` 列做模块类型 + 展开箭头）。
   - `#0` 列放 Module Type（顶层）/ 变体名（子层）。
   - 顶层 item：`iid=f"mod::{label}"`，存 `ModuleRow`；子 item：`iid=asset_path`，存 `ModuleVariant`。
   - 单变体模块：仍建父节点但默认展开，或父节点直接可选（实现时二选一，测试对齐）。
   - 来源列文本：`定制专属` / `通用默认`；用 ttk tag 上蓝/灰前景色。
   - `<Double-1>` 在变体行上 = 开目录（移植现有逻辑）。
   - 新增 `populate_tree(rows: list[ModuleRow])`，保留旧 `populate` 暂时兼容或一并替换（通用类型视图改走 rows 包装）。
3. **门禁**：`uv run pytest -m "not ui" -q --no-cov` 绿。

### Step B — workbench_panel 接树 + 删顶部路径标签
1. `_select_custom_scheme` / `_refresh_main_grid` 的 `custom_scheme` 分支：改调
   `self.workbench_model.get_scheme_module_tree(model, scheme, kw)` → `grid_panel.populate_tree(rows)`。
2. `common_type` / `all` 分支：把 `ModuleCardData` 列表包成单变体 `ModuleRow`（每类型一组变体），同走 `populate_tree`，保证主区只有一种渲染路径。
3. `_on_grid_selection_changed`：
   - 入参改为 `ModuleVariant | None`（或保留 dict 取 `.asset`）。
   - **删除顶部 `目录路径: {path}` 标签那段**（用户嫌信息杂；路径仍可在操作区内小字或 tooltip，先删）。
   - 选中父模块行（多变体）→ 显示占位「展开并选择具体变体」。
4. 操作区高度从 200 收缩；预留一行禁用态「➕ 新增 / ✏️ 编辑 / 🗑️ 删除」占位（future CRUD）。
5. 手动验证：`uv run fwasset` → 点定制方案见 7 行树、手控UI 收 3 变体、来源标签对、双击开目录。

### Step C — 精简操作面板
1. `auto_usb_panel.py`：
   - paired_files 分支只保留「一键烧录」按钮（沿用 `_one_click_handcontrol`）。
   - **删** `self._panel_host._build_usb_selector_row(self)` / `_refresh_usb` 调用与 1/2/3/4 分步按钮。
   - U盘盘符来源：改用 `panel_host.get_global_usb_drive()`；若为空，点按钮时弹「请先在工具中心/设置选择 U 盘」或退化为自动探测（实现时确认；先用 get_global_usb_drive，空则提示）。
   - directory_copy（音乐）分支：保留精简版「执行目录刷机」，删 U盘选择器。
2. `tool_launch_panel.py`：只留「打开烧录工具」；删 `build_handoff_actions(..., include_tool_combo=True)` 的复制/U盘排（保留开目录走双击）。
3. 跟随改 `test_operation_panels.py` 断言。
4. 门禁绿 + `uv run fwasset` 手验操作区是否「不再大的离谱」。

### Step D —（功能确认后）调 Fluent 风格
> 仅在 A–C 用户试用通过后进行。
> 布局采方案 B（顶部检索条 + 左侧方案/类型树 + 右区七程序表 + 选中详情/操作条 + 日志）。

**已锁定的 Step D 决策（2026-06-12 补充）：**
- **核心目标**：灵活迅速查找 + 烧录员/新人一眼看懂。
- **型号入口（2026-06-12 修正，推翻"只塞搜索框"）**：搜索框与型号区**并存**，服务两种不同用户。
  - **关键洞察**：搜索框是"我知道找啥→快速定位"（老手）；型号展示是"我不知道有哪些机子→给我看清单"（新人/烧录员）。后者是搜索框**永远替代不了**的——新人无从敲一个他不知道存在的型号。**先服务看不懂的人。**
  - **型号区 = 平铺按钮 + 更多收纳**：`型号: [全部] [L36] [L30] [X8] [L28] [更多▾]`。常用型号直接平铺成可点按钮，新人扫一眼看全有哪些；超出一行的收进 `更多▾`（带搜索）。型号变多也不撑爆 UI。点亮=当前筛选。
  - **搜索框独立**：管"已知要找什么"的快速检索（空格分词那套），型号也仍是可搜字段之一，但**不取代**型号区。
- **搜索语义**：空格分词 = AND 多维模糊（每个词 OR 跨字段，词间 AND）。在 `query_assets` 改：
  单 keyword → split 后每词一组 OR-跨10字段，组间 AND。`字段:值` 精确语法暂不做（待定）。
- **单变体折叠**：单变体模块直接一行（带版本），点一下即出操作，**不再 `主板程序/主板程序` 重复**；
  多变体才父子可展开。变体名若 == 模块类型名则显示「默认」或版本号。
- **「打开烧录工具」**：待增删改查（CRUD）完整后再推进精确"打开对应工具"，当前先占位。

**实施清单：**
1. 顶部检索条：独立搜索框（分词）+ 型号平铺按钮条（常用平铺 + `更多▾` 收纳带搜索）；移除旧 `model_combo` 穷举下拉。
2. 搜索分词：`query_assets` 改空格分词 AND（含型号字段）。
3. 单变体折叠 + 变体名去冗余（`populate_tree` / `data_grid_panel`）。
4. ttk 主题：行高 ~32、交替行底色、悬停高亮、Win11 展开箭头 ▾（`apply_ttk_theme` 扩展）。
5. 来源用色块：🔵定制专属 / ⚫通用默认。
6. 底部「已选 XXX」详情条 + 横向紧凑动作条（图标+文案）。
7. 可加「操作模式」列（USB刷机/工具烧录）让烧录员一眼知道怎么烧。

---

## 3. 验证门禁

- 单测门禁：`uv run pytest -m "not ui" -q --no-cov`（全量 `pytest -q` 含 UI 窗口测试本机会卡住）。
- 手动门禁（每个 Step 后）：`uv run fwasset`，按下方清单逐项点。
- 已知无关失败：`test_src_layout::test_run_py_uses_fwasset_main`（缺 run.py），不在本任务范围。

### 手动验收清单
- [ ] 点定制 → 某方案：右侧出现整机 7 模块行。
- [ ] 手控UI 有多变体时收成 1 行可展开，展开见各变体，**不在顶层铺平**。
- [ ] 缺失模块行标 ⚫通用默认，方案自带的标 🔵定制专属；**全程无「回源」字样**。
- [ ] 双击变体行 = 打开该目录；**无「打开目录」按钮**。
- [ ] 选手控UI 变体 → 操作区只有一个「一键烧录」，无 U盘选择器、无分步按钮、无复制路径。
- [ ] 选 tool_launch 变体 → 只有「打开烧录工具」。
- [ ] 操作区高度收敛，不再「大的离谱」。
- [ ] 点定制方案/通用类型/搜索切换均不崩溃。

---

## 4. 收尾（全部验收通过后，遵 AGENTS.md）

1. 写 `docs/code-review/REVIEW-20260609-workbench-ui.md`（更新现有那份）：列改动、验证记录、commit hash 占位。
2. 更新 `docs/CHANGELOG.md`。
3. 人工验证确认后，按 Conventional Commit 提交（UI/core/view-model 改动需人工先验）。

---

## 5. 风险与决策点（实施中若卡，回到这里）

- **单变体模块的父/叶呈现**：建父节点默认展开，还是父节点直接可选？→ 默认建父+自动展开，保证视觉一致「7 行」；测试对齐此实现。
- **通用类型视图复用树**：把 `ModuleCardData` 包成 `ModuleRow` 是否引入数据层耦合？→ 在 workbench_panel 内做轻量包装函数，不动 model。
- **手控 U盘盘符**：删了选择器后盘符从哪来？→ `get_global_usb_drive()`；为空则按钮内提示。若用户希望保留某种极简选择，Step C 时再问。
- **Category 顶部下拉**（参考图 All/Common/Custom）：当前用左侧两区实现「通用/定制」。是否要并入顶部下拉？→ 默认保持左侧两区（用户明确要侧边栏两区一目了然），Fluent 阶段再议。

---

# Step E/F · 增删改查（CRUD）—— 免重扫双写架构（2026-06-12 规划）

> 这是从"只读查看器"升级成"管理平台"的关键。**先做 Step D（查），再做 E/F（增删改）。**

## E0. 用户已锁定的 CRUD 决策

- **真改磁盘**：增=建目录+复制文件、删=移回收站、改=重命名/换文件。不是只改索引。
- **最高频 = 变体/程序级**（给某方案的某模块加/换一份新版程序）。方案级 CRUD 低频。
- **核心诉求：一次扫描，后续所有操作都在软件内完成，不需要反复重扫。**

## E1. 架构基石：双写（dual-write），而非重扫

现状是单向 `磁盘 ──全量扫描──> 索引(DB) ──> UI`，所以软件外动磁盘只能重扫。
改为：**每个 CRUD 操作同一动作里既改磁盘、又改那一条索引**，软件自己是磁盘变化的来源，无需重扫。

| 操作 | 磁盘动作 | 索引动作（单条，O(1) 毫秒级） |
|---|---|---|
| 增变体 | 建目录 + 复制文件进去 | `INSERT` 一条 asset |
| 改变体 | （可能重命名目录） | `UPDATE` 那条 |
| 删变体 | 移到 `.回收站\` | `DELETE` 那条 + 写回收站表 |
| 恢复 | 移回原位 | 重新 `INSERT` |

对比全量重扫（扫几百目录）：双写是毫秒级、无感。重扫降级为"软件外被改过"时的**核武器**（保留手动「重新扫描」按钮兜底）。

## E2. 新增 core 层：`core/asset_repository.py`（纯逻辑，可单测）

`asset_index.py` 现仅有整批 `save_assets` + 只读 `query_assets`。新增单条双写函数：

```
create_variant(scheme_path, module_label, name, version, src_files) -> ServiceResult
    建目录 → 复制文件 → 推导 FirmwareAsset → INSERT 索引 → 返回新 asset
update_variant(path, *, new_name=None, new_version=None, new_files=None) -> ServiceResult
    （重命名目录 / 换文件）→ UPDATE 索引（注意 path 是主键，改名要 UPDATE 主键）
delete_variant(path, *, soft=True) -> ServiceResult
    soft: 移到 <root>/.回收站/<时间戳>/ → DELETE 索引 → 写 recycle 表
    hard: 真删 → DELETE 索引
restore_variant(recycle_id) -> ServiceResult
    移回原位 → 重新 INSERT
```

配套 `asset_index.py` 加单条原语：`insert_asset(asset)`、`update_asset(path, changes)`、`delete_asset(path)`；
新增 `recycle_bin` 表（id, original_path, recycled_path, asset_json, deleted_at）。

## E3. 三个一致性裂缝 + 兜底（必须做，否则"免重扫"不可靠）

1. **软件外改动**：操作时校验磁盘与索引是否一致；不一致 → 提示"资源已变动，是否刷新该行/重扫"。保留手动重扫按钮。
2. **双写中途失败**：顺序"先磁盘后索引，索引失败回滚磁盘动作"；失败有明确日志 + ServiceResult code。
3. **文件复制慢/错**：走后台线程（复用现有 `_run_task`）+ 进度，不卡 UI；权限/占用错误友好提示。

## E4. UI 设计（CRUD 从"查"长出来，不另开管理后台）

- **变体级（高频）**：行内悬停显 `＋ / ✏️ / 🗑️`（平时隐藏，鼠标移上才淡入，保持只读时干净）。
  - 模块行 `＋` = 给该模块加变体；变体行 `✏️` 编辑、`🗑️` 删除。
  - **回源行（⚫通用默认）不显 CRUD 图标**（借自通用区，在方案内改它会污染全局）。
- **方案级（低频）**：左栏定制区顶部 `＋新建方案 / 📋复制方案`。复制现有方案再改对新人更友好。
- **增/改表单**（轻量对话框）：变体名、版本号、文件选择器、**实时预览目标磁盘路径（只读，让人安心）**。
- **删除确认**（防误删三层）：① 默认软删除到回收站 / 永久删除二选一；② 高危需手输变体名确认；③ 操作写日志。
- **回收站入口**：工具中心或左栏底部，可查看/恢复/清空。
- 每次操作只刷新**那一行**（双写已知改了啥），全程不触发扫描。

## E5. 分阶段落地

```
Step E：asset_repository 双写地基 + recycle 表 + 「增变体」闭环   ← 先用最高频打通免重扫
        （TDD：临时目录+临时DB，断言"建完磁盘有目录 且 DB 有记录 且 不重扫即可见"）
Step F：改 / 软删除回收站 / 恢复 / 一致性兜底 + UI 行内 CRUD
```

## E6. CRUD 验收清单（Step E/F 各自验）

- [ ] 在软件内「增变体」后，**不点重新扫描**，该模块行立刻出现新变体。
- [ ] 磁盘上对应目录与文件确实被创建。
- [ ] 「删变体」默认进 `.回收站\`，原列表消失但可从回收站恢复。
- [ ] 「改版本/改名」后磁盘目录同步重命名，索引同步更新，无需重扫。
- [ ] 回源行（通用默认）不显示增删改图标。
- [ ] 双写失败（如文件占用）有明确报错且不留下半成品（磁盘/索引不一致）。
- [ ] 手动「重新扫描」仍可用作核武器，重建后数据与双写结果一致。
