# 提交信息

使用中文 Conventional Commit：

```text
<type>(<scope>): <具体结果>
```

`scope` 可省略。常用 type：`feat` 新功能、`fix` 修复、`refactor` 重构、`docs` 文档、`chore` 工程维护、`test` 测试。

小改动只写标题。正文仅补充标题无法表达的原因、行为或兼容性影响；不凑改动条数，不重复文件清单或 Task 验证记录。没有 Task 时，可在正文简记必要验证。

```text
fix(usb): 复制固件时排除内部工作目录

避免将事务暂存文件写入 U 盘。
```

提交前的验证和授权要求见 [agent-workflow.md](agent-workflow.md)。不为回填 commit hash 单独追加提交。
