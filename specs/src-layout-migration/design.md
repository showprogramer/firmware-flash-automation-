# 设计文档

## 设计概述

本次改造的核心是把当前根目录源码迁移到 `src/handcontrol/`，让项目按标准 `src layout` 组织。
迁移后：

- 根目录只保留轻量启动入口 `run.py`
- 业务源码集中到 `src/handcontrol/`
- 构建后端改为 `hatchling`
- 测试和运行都以安装后的包路径为准

本次迁移不保留旧的根目录兼容导入。

---

## 迁移前后结构

### 迁移前

```text
Firmware Flash Automation/
├── app.py
├── core/
├── tests/
└── pyproject.toml
```

### 迁移后

```text
Firmware Flash Automation/
├── run.py
├── src/
│   └── handcontrol/
│       ├── __init__.py
│       ├── app.py
│       └── core/
├── tests/
├── specs/
└── pyproject.toml
```

---

## 关键设计

### 1. 目录调整

- `app.py` 移动到 `src/handcontrol/app.py`
- `core/` 整体移动到 `src/handcontrol/core/`
- 根目录新增 `run.py`
- 迁移完成后删除根目录 `app.py` 和 `core/`

### 2. 启动入口

根目录保留一个非常薄的启动文件：

```python
from handcontrol.app import main

if __name__ == "__main__":
    main()
```

这样可以继续从项目根目录启动，同时避免业务代码继续留在根目录。

### 3. pyproject.toml 调整

需要完成以下配置调整：

- 增加 `[build-system]`，使用 `hatchling`
- 增加 `[tool.hatch.build.targets.wheel]`，声明 `packages = ["src/handcontrol"]`
- 删除 `[tool.uv] package = false`
- 增加 `[project.scripts]`，声明 `handcontrol = "handcontrol.app:main"`
- pytest 覆盖率目标改为 `--cov=src/handcontrol`
- dev 依赖中加入 `hypothesis`
- 本次迁移默认不修改 `[project].name`

### 4. 导入路径调整

源码中的旧导入：

- `from core.xxx import ...`
- `import core.xxx`

迁移后统一改为：

- `from handcontrol.core.xxx import ...`
- `import handcontrol.core.xxx`

测试中的旧导入：

- `from app import App`
- `from core.xxx import ...`
- `import core.xxx`
- `monkeypatch.setattr("app.xxx", ...)`

迁移后统一改为：

- `from handcontrol.app import App`
- `from handcontrol.core.xxx import ...`
- `import handcontrol.core.xxx`
- `monkeypatch.setattr("handcontrol.app.xxx", ...)`

### 5. PROJECT_ROOT 解析

当前 `settings.py` 里 `PROJECT_ROOT` 依赖固定目录层级，这在迁移后不够稳妥。

迁移后改为向上查找包含 `pyproject.toml` 的目录，例如：

```python
def _find_project_root(start: Path) -> Path:
    for parent in [start, *start.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return start
```

这样目录层级变化后仍能正确定位项目根目录。

---

## 风险与处理

### 风险 1：遗漏导入替换

如果有文件仍保留 `core` 或 `app` 的旧导入，迁移后会直接出现导入错误。

处理方式：

- 全量搜索 `from core.`
- 全量搜索 `import core.`
- 全量搜索 `from app import App`
- 全量搜索字符串路径中的 `app.`

### 风险 2：PROJECT_ROOT 解析错误

如果根目录计算错误，会影响 `config.toml`、数据文件等路径解析。

处理方式：

- 改为动态向上查找 `pyproject.toml`
- 增加针对 `_find_project_root` 的测试

### 风险 3：结构测试无法运行

如果决定保留 property-based testing，但没有加入 `hypothesis`，测试会直接失败。

处理方式：

- 在 dev 依赖中显式加入 `hypothesis`

---

## 测试设计

本次迁移的测试分两类。

### 1. 回归测试

现有业务测试全部继续运行，目标是证明迁移没有破坏原有功能。

### 2. 结构测试

新增 `tests/test_src_layout.py`，至少覆盖以下内容：

- `src/handcontrol/__init__.py` 存在
- 根目录 `core/` 和 `app.py` 已删除
- `import handcontrol` 成功
- pytest 覆盖率目标已改为 `src/handcontrol`
- `run.py` 正确调用 `handcontrol.app.main`
- `tests/` 下无 `__init__.py`
- 所有源码和测试文件中不再出现裸 `core` 导入
- `_find_project_root` 能正确返回包含 `pyproject.toml` 的目录

如果保留 Hypothesis，则用于 `_find_project_root` 这类路径性质测试。

---

## 验收关注点

迁移完成后，重点检查以下几项：

1. `uv sync` 后可以正常 `import handcontrol`
2. `python run.py` 可以启动
3. `uv run handcontrol` 可以启动
4. `python -m pytest -q` 全量通过
5. 覆盖率不低于迁移前基线
