# REVIEW-20260905-managed-paths-and-layout：受管路径判定与工作区布局识别

状态：代码审查通过，人工验证通过；已归档

对应任务：`TASK-20260905-managed-paths-and-layout`（父规格 D4.3、D4.5、D8.2、D9.0；任务文件未入库）。

触发条件：新增 core 公共 API（`managed_paths`）、改动扫描行为与 USB 复制边界。

## 审查范围

- `core/types.py`：新增 `ManagedPathReason`、`WorkspaceLayout` 两个共享 Literal。
- `core/managed_paths.py`（新增）：受管路径判定、内部路径生成与写授权守卫、工作区布局识别。
- `core/file_scan.py`：`_is_excluded_dir` 接入受管判定；新增 `_visible_asset_files` 过滤 `FirmwareAsset.files`。
- `core/usb_ops.py`：`copy_directory_to_usb` 增加 `ignore` 回调。
- `core/reference_lookup.py`：`enumerate_model_roots` 传入工作区根；`_has_model_marker` 配置判定收紧为 `.is_file()`。

## 关注点与结论

**1. 受管身份不能靠目录名判定。** 内部区域只在给出 `workspace_root`、且路径位于该工作区受管根之下时才命中。工作区外的同名 `.fwasset/`、用户在业务目录下自建的 `staging/` 均不视为应用所有。缺少 `workspace_root` 时不做猜测，直接返回 `None`。

**1a. 路径形状也不证明所有权。** 受管根必须带应用写入的 `.fwasset-owned` 标记才获得写授权（`is_managed_root_owned`）。用户预建的同名目录没有标记，因而拿不到写授权；判定全程只读，不删除、不覆盖用户内容。标记的**写入**属受管根初始化，归子任务 1b。`quarantine` 在工作区外、不受工作区守卫保护，标记是它唯一的所有权保障。

**2. 排除判定不等于写授权。** `should_exclude_managed_path` 只回答遍历是否跳过；受管目录写入必须另外通过 `assert_managed_write`（三层：路径形式 → 受管根归属 → 所有权标记）。`旧版本/` 被扫描排除但不是受管写入区，测试显式固化了这一点。

**2a. 归属判定看词法与解析后身份，任一命中即受管。** 只看解析结果会在受管根被换成 junction 时整片漏排；只看词法会把 `staging/../../X` 误判为受管（故词法比较前先 `os.path.normpath` 折叠 `..`）。**但不反向追踪受管根的解析目标**——早期修复曾这么做，结果一条指向真实资产目录的 staging junction 会让该目录被判为受管，扫描静默丢掉资产。重定向的受管根按不可信现场处理，由 1b 的初始化在写盘前经 `assert_managed_root_not_redirected` 拒绝。`resolve()` 的失败一律捕获（含 `RuntimeError`），不让链接循环把扫描整体打断。

**2b. 受管根的创建不在 1a。** 检查与创建之间目标可被替换或抢占；原子创建、并发保护与失败恢复由 1b 完成。1a 只保留只读的 `assert_managed_root_not_redirected` 与 `is_managed_root_owned`，不提供创建入口；`assert_managed_write` 不提供跳过所有权校验的开关。

**3. 路径归一顺序。** `_segments` 沿用 `path_guard` 的既定顺序（先 `normcase` 再转正斜杠）。顺序颠倒会使 Windows 分隔符归一失效——这是 2026-08-03 已发生过的回归，注释中标注了原因。

**4. 型号标志规则重复。** `managed_paths._has_model_marker` 与 `reference_lookup._has_model_marker` 是同一规则的两处实现。当前保持复制而非抽取，理由是 `reference_lookup` 体量大且 R8 已定稿，本轮不做结构性改动。

本轮把**两处**的配置判定同步从 `.exists()` 收紧为 `.is_file()`：名为 `型号配置.toml` 的**目录**不是有效型号标志（后续配置读取用不了它）。`test_model_marker_rule_matches_reference_lookup` 对普通目录、配置为目录、真实型号三种现场断言两处结果一致，防止再次漂移。**剩余风险：仍需在子任务 3a 合并为单一真源。**

**5. `invalid` 不得被当作空工作区。** 存在无法归类的一级内容（无标志的普通目录、散落文件）、根标志与型号子目录混合、或根不可读时返回 `invalid`，避免在用户既有资料上直接建结构、或让子任务 3a 的迁移用错误归属搬运目录。`empty` 只看目录与配置，不查资产索引——空白型号（仅有配置、无程序）仍算型号。扫描排除关键词只对目录生效，根下散落文件一律计入未知内容。

**6. USB `ignore` 回调不传 `workspace_root`。** 复制来源可能已脱离工作区，此处只需目录段与文件名两类规则生效；内部受管区域本就不应出现在被复制的程序目录内。

**7. 扫描入口必须传工作区根。** `_is_excluded_dir` / `_visible_asset_files` 增加 `workspace_root` 参数，`_scan_assets` 与 `enumerate_model_roots` 传入。不传则内部受管区域规则完全失效，staging / 候选区 / 状态目录内的固件会被扫描成正式资产——这是首轮审查发现的 P1。

**8. legacy `"旧"` 泛化关键词保留。** 本轮仅补测试固化现状（`旧款L36` 这类真实型号目录会被静默整棵排除）。**剩余风险：该隐患仍在，退役归子任务 7（父规格 D4.3③）。**

## 剩余风险

- 型号标志规则两处实现，待子任务 3a 合并。
- legacy `"旧"` 关键词仍会误排真实型号目录，待子任务 7 退役。
- 受管目录的生命周期、TTL、清理与事务恢复未实现（子任务 1b）；本轮只冻结位置、身份与写授权入口。
- 人工及音乐 USB 过滤验证结论见对应任务；本轮不将自动化结果记为 USB 实机通过。
