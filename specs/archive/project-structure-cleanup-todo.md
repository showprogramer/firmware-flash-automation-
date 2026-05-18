# 项目结构现代化清理 TODO

> 状态：`[ ]` 待办 / `[~]` 进行中 / `[x]` 已完成 / `[-]` 已取消
>
> 目标：清理根目录产物，规范配置样例，移除入口 monkey patch，并把运行时数据从源码目录分离。

## 根目录清理

- [x] 删除根目录异常生成的 `tool-resultsdirs_4deep.txt` 类临时文件
- [x] `.gitignore` 保持 `.coverage`、`.pytest_cache/`、`.hypothesis/`、`__pycache__/`、`logs/`、`fwasset.db` 不进入版本管理
- [x] `.gitignore` 补齐 `.runtime/`、`dist/`、`build/`、临时 spec 规则，并保留已跟踪的 `fwasset.spec`

## 配置样例

- [x] 新增 `config.example.toml`，保留配置结构并移除本机路径
- [x] `config.toml` 改为本地配置，加入 `.gitignore`
- [x] 保留 `firmware_catalog.toml` 作为项目级固件类型注册表
- [x] 更新 `README.md`，说明首次运行复制 `config.example.toml` 并配置 `root_dir`、`tool_root`

## 入口清理

- [x] 将 `_open_in_explorer`、`_open_folder_from_listbox` 迁回 `FirmwareListPanel`
- [x] `src/fwasset/app.py` 只保留 `main()`、`App` 兼容导出和 shell 入口导出
- [x] 删除 `app.py` 中未使用的 service imports 和运行时挂载语句
- [x] 更新快速定位测试，直接验证 `FirmwareListPanel` 正式类方法

## 运行时数据隔离

- [x] `settings.py` 增加统一运行时目录解析
- [x] 开发模式默认使用项目根目录 `.runtime/`
- [x] 打包模式默认使用 exe 同级 `runtime/`
- [x] 支持 `FWASSET_RUNTIME_DIR` 环境变量覆盖
- [x] `fwasset.db` 默认写入运行时目录
- [x] 日志默认写入运行时目录下的 `logs/app.log`
- [x] `config.toml`、`firmware_catalog.toml` 继续从应用根目录读取
- [x] 启动时自动创建运行时目录，创建失败时抛出中文错误

## 验收测试

- [x] `uv run python -m pytest tests/test_src_layout.py tests/test_app_quick_locate.py tests/test_settings.py -q --no-cov`
- [x] `uv run python -m pytest tests/test_asset_index.py tests/test_logging_utils.py tests/test_app_service_smoke.py -q --no-cov`
- [x] `.\scripts\test.ps1`
