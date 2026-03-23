# 需求 Backlog

> 状态标记：`[ ]` 待办 / `[~]` 进行中 / `[x]` 已完成

---

## 已完成

- [x] 递归扫描根目录，识别同时含 `.ROM` 和 `.PKG` 的可刷机目录
- [x] 从 ROM 文件名正则解析型号（`L\d+`）和版本（`V\d+.\d+`）
- [x] 路径补偿识别型号（`guess_model_from_path`）
- [x] 过滤无关目录（`CH341SER`、`主板程序`）
- [x] U 盘检测（psutil 可移动盘符）
- [x] U 盘清理垃圾文件（可配置扩展名与文件名规则）
- [x] U 盘格式化 FAT32（cmd format，需用户二次确认）
- [x] 复制 ROM/PKG 到 U 盘（先清除旧文件）
- [x] PowerShell 安全弹出 U 盘
- [x] 一键流程：清理 → 复制 → 弹出 → 写表（默认"待确认"）
- [x] Excel 台账写入/更新（openpyxl，按型号+版本匹配行）
- [x] Excel 被占用时写备用文件 `*_刷机记录_待导入.xlsx`，返回结构化结果
- [x] Excel 台账读取：全量预览、单行回填、状态批量加载
- [x] 审核页：填写 logo / 语言 / 业务员 / 备注 / 测试状态并保存
- [x] 列表项按测试状态着色（黄/绿/白）
- [x] 所有耗时操作后台线程执行，界面保持可响应
- [x] `config.toml` 集中配置（路径、Excel 参数、USB 清理规则）
- [x] 配置加载状态暴露（ok / missing / parser_missing / parse_error），不静默失败
- [x] Python 3.8-3.10 兼容（`tomli` 条件依赖）
- [x] pytest 测试框架，覆盖率门禁 >= 70%
- [x] `scripts/test.ps1` 统一测试入口
- [x] README、CHANGELOG、COMMIT_TEMPLATE 文档体系

---

## 待办 / 规划

### 高优先级

- [x] **service 层抽离**：将 `app.py` 中的流程编排逻辑（一键执行、写表判断等）提取到独立 `core/service.py`，UI 层只负责展示与事件绑定
- [x] **返回结构类型注解**：为 `write_excel_record`、`find_handcontrol_folders` 等关键函数增加 `TypedDict` 类型注解，减少调用方猜测字段名
- [x] **数量统计**：手控文件夹列表添加序号以便统计数量，表格添加数据序号自增
- [ ] **驱动修复**：检测并使用 Windows 系统自带工具修复 U 盘驱动程序问题
- [ ] **快速定位**：在手控文件夹列表双击某一项，可直接调用系统资源管理器（Explorer）打开对应的文件存放位置
- [ ] **搜索/过滤框**：增加定制化搜索栏，支持快速过滤手控文件夹列表（目前先预留 UI 与基础过滤逻辑，具体深度需求待定）
- [ ] **表格UI新增**： 在 UI 和 Excel 中新增一个记录字段“附图”（内容可选“定制”或“可通用”），位于现有的“备注”列左侧。
- [ ] **覆盖率门禁提升**：当前门禁 70%，目标提升至 80%，补充边界场景用例

### 中优先级

- [ ] **错误日志落盘**：将运行时异常写入本地日志文件（如 `logs/app.log`），便于用户反馈问题时提供诊断信息
- [ ] **备用文件合并辅助**：当 Excel 被占用、备用文件已生成时，提供"合并备用文件"按钮，自动将备用文件中的新行追加到主表
- [ ] **型号/版本识别规则可配置**：将 ROM 文件名正则规则移入 `config.toml`，支持不同命名规范的项目复用
- [ ] **多 U 盘并发支持**：当前只支持单 U 盘操作，考虑支持同时向多个 U 盘复制（批量刷机场景）
- [ ] **列表排序与筛选**：支持按型号、版本、测试状态对文件夹列表排序或筛选，方便大量型号时快速定位

### 工程规范：迁移至 src 布局

> 背景：src 布局是 2026 年 Python 社区（pypa / uv / hatch）的默认标准。将包隔离在 `src/` 下，
> 可避免根目录被意外加入 `sys.path`，确保测试环境与安装后行为一致。
> 本项目当前无打包发布需求，收益偏规范层面，分步渐进执行，每步独立可验证。

- [ ] **Step 1 — 准备与验证基线**
  - 确认当前 `python -m pytest -q` 全部通过，记录覆盖率基线
  - 确认 `uv run python app.py` 可正常启动
  - 在 git 创建独立分支 `refactor/src-layout`

- [ ] **Step 2 — 移动包目录**
  - 新建 `src/handcontrol/` 目录，添加 `src/handcontrol/__init__.py`
  - 将 `core/` 整体移动到 `src/handcontrol/core/`
  - 将 `app.py` 移动到 `src/handcontrol/app.py`
  - 根目录保留一个轻量启动入口 `run.py`：
    ```python
    from handcontrol.app import main
    if __name__ == "__main__":
        main()
    ```

- [ ] **Step 3 — 修改 pyproject.toml**
  - 启用打包模式，删除 `[tool.uv] package = false`（或改为 `package = true`）
  - 声明包路径与入口：
    ```toml
    [tool.setuptools.packages.find]
    where = ["src"]

    [project.scripts]
    handcontrol = "handcontrol.app:main"
    ```
  - 重新执行 `uv sync --extra dev` 以 editable 模式安装

- [ ] **Step 4 — 修复所有内部导入路径**
  - 全局替换 `from core.` → `from handcontrol.core.`
  - 全局替换 `import core.` → `import handcontrol.core.`
  - 检查 `core/settings.py` 中 `PROJECT_ROOT` 的计算逻辑（`__file__` 路径层级变化，需上移两级）：
    ```python
    # 修改前（core/settings.py 在 core/ 下，上移一级到项目根）
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    # 修改后（src/handcontrol/core/settings.py，需上移三级）
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
    ```

- [ ] **Step 5 — 修复测试导入路径**
  - `tests/` 目录不移动，pytest 通过 editable install 自动找到 `handcontrol` 包
  - 将 `tests/` 中所有 `from core.` 替换为 `from handcontrol.core.`
  - 确认 `pyproject.toml` 的 `testpaths = ["tests"]` 配置不变

- [ ] **Step 6 — 验证与收尾**
  - 执行 `python -m pytest -q`，确认全部通过且覆盖率不低于基线
  - 执行 `uv run python run.py`，确认 UI 正常启动
  - 删除根目录遗留的旧 `core/` 目录和 `app.py`
  - 更新 `README.md` 启动命令（`python run.py` 或 `uv run handcontrol`）
  - 合并分支，在 CHANGELOG 记录此次重构

### 低优先级 / 长期规划

- [ ] **最小化诊断信息导出**：提供"导出诊断包"功能，一键打包日志、配置（脱敏）、测试状态快照，便于远程排查
- [ ] **Excel 模板版本管理**：在台账中记录工具版本号，便于后续格式升级时做兼容处理
- [ ] **跨平台适配评估**：当前强依赖 Windows 盘符与 PowerShell，评估是否有 macOS/Linux 使用场景，若有则抽象 USB 操作接口
- [ ] **UI 国际化**：界面文案目前硬编码中文，若有多语言需求可引入简单 i18n 机制
- [ ] **自动化集成测试**：当前测试全部基于 mock，考虑增加使用真实临时文件的集成测试场景（Excel 读写端到端）

---

## 已知问题 / 技术债

- [ ] `find_handcontrol_folders` 过滤规则（`CH341SER`、`主板程序`）硬编码在函数内，应移入配置
- [ ] `copy_to_usb` 在复制大文件时无进度反馈，日志只有完成提示，用户体验较差
- [ ] `format_usb` 使用 `shell=True`，存在命令注入风险，应改为参数列表形式
- [ ] `eject_usb` 的 PowerShell 脚本依赖 WMI，在部分 Windows 精简版系统上可能失败，需增加备用弹出方案
- [x] Excel 台账序号列（A 列）已自动按有效数据行重排为连续计数

