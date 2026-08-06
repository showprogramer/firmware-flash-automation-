# Commit Message 模板（中文）

## 标准模板（Conventional Commits）

```text
<type>(<scope>): <一句话摘要>

- <改动点1（结果导向）>
- <改动点2（行为变化/兼容性）>
- <改动点3（配置/文档/测试）>

影响范围:
- <模块/文件或功能>

验证:
- <已执行的验证1>
- <已执行的验证2>
```

## 常用 type

- `feat`: 新功能/可见能力增强
- `fix`: 缺陷修复
- `refactor`: 重构（不改外部行为）
- `docs`: 文档变更
- `chore`: 工程维护（依赖、脚本、配置）
- `test`: 测试相关

## 示例（贴合本项目）

```text
feat(core,app): 优化 Excel 写入流程并接入配置化默认值

- write_excel_record 返回结构化结果，区分占用与写入失败
- UI 按失败原因分别提示，保留备用文件补录路径
- 新增 config.toml 并在 settings 中提供安全回退
- 有用户可见变化时同步 `docs/CHANGELOG.md` 的 `Unreleased` 条目；纯内部工程、测试或格式化提交不要求新增 CHANGELOG 条目

影响范围:
- app 写入与提示逻辑
- core/excel_ops 与 core/settings
- data 模板与配置文件

验证:
- 手动检查 git diff 与变更记录一致
- 校验提交文件列表与实际修改一致
```
