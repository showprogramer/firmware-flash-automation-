# REVIEW-20260728：配置简化 + USB 烧录流程对齐（T1/T2/T3）

| 项 | 内容 |
| --- | --- |
| 类型 | 配置 schema 精简、首次配置向导、USB 格式化 + 复制流程的实现审查 |
| 复审基线 | 2026-07-28，当前工作区（含尚未提交的 Issue 7 ASCII 盘符修复） |
| 状态 | 🟡 Issue 1–6、8–9 已关闭；Issue 7 已修复、待 USB 人工验证后提交 |
| 相关 TASK | `specs/active/TASK-20260728-config-usb-simplification.md` |
| 相关 Commit | `e8558d2`（T1）、`ebcc197`（T2）、`d6a846f`（向导完成后自动扫描）、`3286975`（T3）、`1adf724`（QDialog 修复）、`47529e0`（Format-Volume）、`1e42607`（Issue 2/3）、`4999f13`（Issue 4/6/7）、`b9e9c13`（Issue 5） |

> 本文档只把当前仍需采取行动的项目保留为活跃议题。UI、USB 与 core 流程改动仍须按 `AGENTS.md` 人工验证通过后才能提交。

## 已关闭议题

### Issue 1（P1·已关闭）：首次配置向导返回后缺少 `QDialog` 导入  `complexity: low`

**复杂度理由：** 单个 Qt import 修复，无 schema、service 或测试改动。

**处理结果：** `1adf724` 已补齐 `QDialog` import，消除了首次向导返回后的 `NameError`。

**状态：** ✅ 已提交。

### Issue 2（P2·已关闭）：README 配置说明与真实配置路径不一致  `complexity: low`

**复杂度理由：** 纯文档同步，无代码或测试改动。

**处理结果：** `1e42607` 已将 README 分为冻结 exe 与开发模式：冻结 exe 使用 `%APPDATA%\fwasset\config.toml`，开发模式保留项目根目录配置；字段表仅保留 `paths.root_dir` 与 `paths.tool_root`，并说明跳过后的重提示行为。

**状态：** ✅ 已提交。

### Issue 3（P2·已关闭）：`flash_service` 的 `format_failed` 未写入服务错误码契约  `complexity: low`

**复杂度理由：** 既有代码与测试语义不变，仅同步项目契约文档。

**处理结果：** `1e42607` 已在 `AGENTS.md` 的 `flash_service` 错误码表登记 `format_failed`；`test_flash_service.py` 已覆盖该返回码。

**状态：** ✅ 已提交。

### Issue 4（P2·已关闭）：格式化 + 复制流程之外的垃圾文件清理遗留  `complexity: medium`

**复杂度理由：** 需同步删除 core helper、settings 常量和对应测试；不动 schema、UI 或服务返回结构。

**处理结果：** `4999f13` 已删除 `clean_usb()`、`JUNK_EXTENSIONS`、`JUNK_FILENAMES` 及其测试；复审确认当前生产代码无相关引用。

**状态：** ✅ 已提交。

### Issue 5（P3·已关闭）：未接入的 `usb_repair_service` 现场诊断冷路径  `complexity: medium`

**复杂度理由：** 删除涉及 service 模块、导出、底层诊断/修复 helpers 与测试。

**处理结果：** 已决策删除。`b9e9c13` 已移除 `usb_repair_service.py`、`services.__all__` 导出、底层诊断/修复代码与对应测试；复审确认生产代码无残留引用。

**状态：** ✅ 已提交。

### Issue 6（P2·已关闭）：格式化后固定等待 2 秒，慢设备复制时可能未就绪  `complexity: medium`

**复杂度理由：** 单个 core 函数的等待策略调整，需补立即就绪、延迟就绪和超时测试。

**处理结果：** `4999f13` 已改为最长 10 秒、每 0.5 秒轮询 `Path(drive).is_dir()`；驱动器延迟就绪与超时路径均有单测覆盖。

**状态：** ✅ 已提交；真实 U 盘格式化/重新挂载的人验仍应随下次 USB 流程验收进行。

## 已修复，待人工验证后提交

### Issue 7（P3·破坏性操作防御）：盘符校验必须限制为 ASCII 英文字母  `complexity: low`

**复杂度理由：** 单个输入守卫加一条回归测试；无 UI、schema 或服务结构变更。

**复审发现：** `4999f13` 已加 `len(letter) == 1 and letter.isalpha()`，但 Python 的 `isalpha()` 会接受非 ASCII 字母，例如 `"中"`；这仍不符合 Windows 盘符只能为 A–Z 的约束。

**本次修复：**

```python
if not (len(letter) == 1 and letter.isascii() and letter.isalpha()):
```

同时将 `"中:\\"` 加入 `test_format_usb_invalid_drive_letter`。测试先在旧校验上按预期失败（会进入 `subprocess.run`），再在修复后通过。

**自动化验证：**

```text
uv run python -m pytest src/fwasset/tests/test_usb_ops.py::test_format_usb_invalid_drive_letter -q --no-cov  -> 1 passed
uv run python -m pytest src/fwasset/tests/test_usb_ops.py src/fwasset/tests/test_flash_service.py -q --no-cov -> 15 passed
uv run python -m pytest -m "not ui" -q --no-cov -> 357 passed, 18 deselected
```

**状态：** 🟡 已完成，请人工验证后提交。建议人工确认真实盘符 `E:\` 等仍可正常进入格式化确认与烧录流程；无效输入不会触发格式化。

## 活跃议题

### Issue 8（P2·已转入 TASK）：首次配置“跳过”后的配置入口与日常工作流定位  `complexity: medium`

**复杂度理由：** 涉及 Qt UI 导航、向导调用、settings reload 与人工 UI 验证；并须保持未来 CRUD 与低频外部目录读取的职责边界。

**处理：** 已转入 `specs/active/TASK-20260728-program-folder-settings-entry.md`。实现新增「设置 → 程序文件夹」、向导路径校验/预填、跳过后的「前往设置」提示，并将用户可见的低频读取动作命名为「重新读取程序文件夹」。

**验证：** 新增 Qt smoke 6 项通过；冻结 exe 人工验证于 2026-07-28 通过；`.\scripts\test.ps1` → 381 passed，coverage 94.33%。

**状态：** ✅ 已关闭。

### Issue 9（P3·已关闭）：`_start_scan` 与 `_auto_scan` 的读取执行部分重复  `complexity: low`

**复杂度理由：** 单个 UI 文件内提取私有方法，不改变 scan service 或结果处理逻辑。

**处理：** 本 TASK 已抽取 `_read_program_folder(directory)` 作为共同后台读取路径；“重新读取程序文件夹”只使用已配置根目录，配置为空时跳转设置，不再以临时选择目录的方式切换工作区。

**状态：** ✅ 已关闭；随 Issue 8 的冻结 exe 验证通过。
