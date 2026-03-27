# 实施任务

- [x] 1. 记录迁移前基线
  - 运行 `python -m pytest -q --cov=core`
  - 记录当前覆盖率，用于迁移后对比

- [x] 2. 创建新的源码目录
  - 新建 `src/handcontrol/`
  - 新建 `src/handcontrol/__init__.py`
  - 将根目录 `app.py` 移到 `src/handcontrol/app.py`
  - 将根目录 `core/` 移到 `src/handcontrol/core/`
  - 在根目录新增 `run.py`

- [x] 3. 更新打包与测试配置
  - 在 `pyproject.toml` 中增加 `hatchling` 构建配置
  - 增加 wheel 包路径声明 `packages = ["src/handcontrol"]`
  - 删除 `[tool.uv] package = false`
  - 增加 `[project.scripts]`
  - 将 pytest 覆盖率目标改为 `--cov=src/handcontrol`
  - 在 dev 依赖中加入 `hypothesis`
  - 保持 `[project].name` 不变

- [x] 4. 修复源码导入
  - 将 `src/handcontrol/` 下所有 `core` 旧导入改为 `handcontrol.core`
  - 搜索并清理残留的裸 `core` 导入

- [x] 5. 修复 `PROJECT_ROOT` 解析
  - 在 `src/handcontrol/core/settings.py` 中增加 `_find_project_root`
  - 用动态查找替换原来的固定层级写法

- [x] 6. 修复测试导入
  - 将测试中的 `from core...` 改为 `from handcontrol.core...`
  - 将测试中的 `import core...` 改为 `import handcontrol.core...`
  - 将测试中的 `from app import App` 改为 `from handcontrol.app import App`
  - 将测试中字符串形式的 `app.xxx` 改为 `handcontrol.app.xxx`
  - 确认 `tests/` 下没有 `__init__.py`

- [x] 7. 增加结构测试
  - 新建 `tests/test_src_layout.py`
  - 校验 `src/handcontrol/__init__.py` 存在
  - 校验根目录 `core/` 和 `app.py` 已删除
  - 校验 `import handcontrol` 成功
  - 校验 `run.py` 调用 `handcontrol.app.main`
  - 校验 pytest 覆盖率目标已改为 `src/handcontrol`
  - 校验 dev 依赖已包含 `hypothesis`
  - 校验测试目录中没有 `__init__.py`

- [x] 8. 增加规则校验测试
  - 增加“无裸 `core` 导入”检查
  - 增加 `_find_project_root` 正确性测试
  - 若使用 Hypothesis，则用于路径性质测试

- [x] 9. 删除旧目录遗留
  - 删除根目录旧 `app.py`
  - 删除根目录旧 `core/`

- [x] 10. 完整验证
  - 运行 `uv sync`
  - 验证 `import handcontrol`
  - 验证 `python run.py`
  - 验证 `uv run handcontrol`
  - 运行 `python -m pytest -q`
  - 确认覆盖率不低于基线

- [x] 11. 更新文档
  - 更新 `README.md`
  - 更新 `CHANGELOG.md`
