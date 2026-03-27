# 需求文档

## 目标

将当前项目从根目录布局迁移为标准 `src/` 布局，作为 Python 工程现代化调整的一部分。
迁移后源码放入 `src/handcontrol/`，构建后端使用 `hatchling`，开发环境通过 editable install 保持原有开发体验。

本次迁移不保留旧的根目录兼容层。迁移完成后，根目录 `app.py` 与 `core/` 删除。

## 术语

- `src layout`：将源码包放在 `src/<包名>/` 下的布局方式。
- `PROJECT_ROOT`：包含 `pyproject.toml` 的项目根目录。
- `run.py`：迁移后位于根目录的启动入口。
- 覆盖率基线：迁移前测试覆盖率，迁移后不得低于该值。

---

## 需求 1：目录结构迁移

1. 迁移完成后，源码包必须位于 `src/handcontrol/`，且包含 `__init__.py`。
2. 迁移完成后，根目录不得再保留 `core/` 目录和顶层 `app.py`。
3. 执行 `uv sync` 后，必须可以通过 `import handcontrol` 导入项目包。
4. 迁移完成后执行 `python -m pytest -q`，测试必须通过，覆盖率不得低于迁移前基线。

## 需求 2：构建与打包配置

1. `pyproject.toml` 必须增加 `[build-system]`，使用 `hatchling` 作为构建后端。
2. `pyproject.toml` 必须增加 `[tool.hatch.build.targets.wheel]`，并声明 `packages = ["src/handcontrol"]`。
3. `pyproject.toml` 中原有 `[tool.uv] package = false` 必须删除。
4. `pyproject.toml` 必须增加 `[project.scripts]`，声明 `handcontrol = "handcontrol.app:main"`。
5. 本次迁移默认不修改 `[project].name`，除非另有单独决定。

## 需求 3：导入路径与启动方式

1. `src/handcontrol/` 下所有源码文件，凡是引用原 `core` 包内容，必须改为 `handcontrol.core` 前缀。
2. `tests/` 下所有测试文件，凡是引用应用或核心模块，必须改为 `handcontrol` 前缀。
3. 测试中原有 `from app import App` 必须改为 `from handcontrol.app import App`。
4. 测试中 monkeypatch 或其他字符串路径引用 `app.xxx` 的位置，必须改为 `handcontrol.app.xxx`。
5. `src/handcontrol/core/settings.py` 中 `PROJECT_ROOT` 的解析不得依赖固定层级的 `parent.parent`。
6. 根目录 `run.py` 必须调用 `handcontrol.app.main` 启动程序。

## 需求 4：测试与校验

1. `pyproject.toml` 中 pytest 的覆盖率目标必须从 `--cov=core` 改为 `--cov=src/handcontrol`。
2. `tests/` 目录下不得存在 `__init__.py`。
3. 迁移后测试必须能正常发现并运行，不得出现导入错误。
4. 若保留 property-based 测试方案，开发依赖中必须加入 `hypothesis`。
5. 必须新增 `tests/test_src_layout.py`，用于校验目录结构、导入规则、`PROJECT_ROOT` 解析和启动入口配置。

## 需求 5：文档更新

1. `README.md` 必须更新为新的启动方式，如 `python run.py` 或 `uv run handcontrol`。
2. `README.md` 必须反映迁移后的 `src/handcontrol/` 目录结构。
3. `CHANGELOG.md` 必须记录本次 `src layout` 迁移、构建后端切换，以及迁移前后覆盖率。
