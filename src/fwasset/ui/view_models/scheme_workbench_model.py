from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from fwasset.core.asset_index import query_assets
from fwasset.core.platform_config import load_platform_config, default_variant_for, PlatformDefaults
from fwasset.core.services.platform_default_service import (
    set_default_variant as _set_default_variant_service,
)
from fwasset.core.types import FirmwareAsset


def _strip_model_suffix(name: str) -> str:
    """目录名 → 型号名（'L36程序' → 'L36'）。"""
    for suffix in ("程序", "目录"):
        if name.endswith(suffix):
            return name[: -len(suffix)].strip()
    return name.strip()


def _module_matches(asset: FirmwareAsset, module_key: str) -> bool:
    """判断资产是否属于平台配置里的某个模块键。

    平台配置.toml 的 defaults 键是"模块目录名"（来自固件目录，如 主板程序 /
    3D机芯版程序），而 asset 的 firmware_label 来自 catalog，可能有用字差异
    （版/板）。因此除标签相等外，再检查 module_key 是否命中资产路径任一段。
    """
    key = str(module_key or "").strip()
    if not key:
        return False
    if str(asset.get("firmware_label", "")) == key:
        return True
    return key in Path(str(asset.get("path", ""))).parts


@dataclass
class WorkbenchSelection:
    """表示当前工作台选中的节点状态"""
    model_name: str = ""           # 选中的型号名（顶级切换，如 "L36"）
    node_type: str = ""            # 选中的节点类型 ("common_type" 或 "custom_scheme")
    common_type: str = ""          # 如果是 common_type，这是选中的 firmware_label (如 "主板程序")
    scheme_name: str = ""          # 如果是 custom_scheme，这是选中的方案名 (如 "以色列-Royal-Z9")


@dataclass
class ModuleCardData:
    """右侧单张卡片的数据"""
    asset: FirmwareAsset
    source_type: str               # "common_default" | "custom_exclusive" | "common_fallback" | "common_variant"
    source_label: str              # 用于显示的来源标签文本
    is_fallback: bool              # 是否是回源模块
    source_kind: str = ""          # "common" | "custom" — coarse bucket for the row-level 定制专属/通用 标签
    default_badge: str = ""        # 平台默认徽章文案（如 "★默认"），非默认为空串


# 整机标准模块的固定展示顺序（按烧录习惯，大部分机型包含这些模块）
STANDARD_MODULE_ORDER = [
    "主板程序",
    "手控UI",
    "蓝牙程序",
    "语音程序",
    "快捷键程序",
    "3D机芯板程序",
    "2D机芯板程序",
    "腿部程序",
]


@dataclass
class ModuleVariant:
    """模块下的单个具体变体（可直接烧录的资产）。"""
    asset: FirmwareAsset
    name: str                      # 变体显示名（目录名）
    version: str
    source_kind: str               # "custom"（定制专属）/ "common"（通用）
    source_label: str              # 用户可读来源文案，绝不含"回源"
    default_badge: str = ""        # 平台默认徽章文案（如 "★默认"），非默认为空串


@dataclass
class ModuleRow:
    """整机模块固定层级中的一行（一个模块类型）。"""
    label: str                     # 模块中文名，如 "手控UI"
    source_kind: str               # 该模块整体来源：custom / common
    source_label: str              # 行级来源文案
    variants: list[ModuleVariant]  # 该模块下的所有变体（单变体则长度为 1）


class SchemeWorkbenchModel:
    def __init__(self):
        self.db_path: Path | None = None
        self.root_dir: Path | None = None
        self._platforms: list[PlatformDefaults] = []
        self._model_root_paths: dict[str, str] = {}  # model_name → model_directory_path
        # 布局模式：True = 扫描根本身是一个型号目录（含 通用/定制）；
        # False = 扫描根是父文件夹，一级子目录各是一个型号（多型号根）。
        self._single_model_root: bool = True
        self._multi_model_dirs: dict[str, str] = {}  # model_name → 一级子目录名
        self._platforms_by_model: dict[str, list[PlatformDefaults]] = {}
        # Single-shot in-memory asset cache. Populated by bind() so the hot
        # path (sidebar rebuild on every search keystroke) does not re-query
        # SQLite. Methods that previously called query_assets() now read from
        # this list and filter in Python. The cache is invalidated by bind();
        # see test_cache_invalidates_on_rebind.
        self._all_assets: list[FirmwareAsset] = []

    def _cache_loaded(self) -> bool:
        """True once bind() has populated the asset cache."""
        return bool(self._all_assets)

    def bind(self, db_path: Path | None, root_dir: Path):
        self.db_path = db_path
        self.root_dir = root_dir
        # Load once. Any view method on the hot path reads from this list.
        self._all_assets = list(query_assets(path=self.db_path))
        self._single_model_root = self._detect_single_model_root()
        self._load_multi_model_dirs()
        self._load_model_root_paths()
        self._load_platforms_for_all_models()

    def _detect_single_model_root(self) -> bool:
        """扫描根直接含 通用/定制 → 单型号根；否则视为多型号父文件夹。

        根目录不存在（如仅有索引的测试场景）时保持单型号语义，向后兼容。
        """
        if self.root_dir is None or not self.root_dir.is_dir():
            return True
        return (self.root_dir / "通用").is_dir() or (self.root_dir / "定制").is_dir()

    def _load_multi_model_dirs(self):
        """多型号根：从资产路径的一级子目录枚举型号（'L36程序' → 'L36'）。

        以"该子目录下扫到过资产"为准，未整理的型号目录（还没有 通用/定制）
        也会出现在型号列表里。
        """
        self._multi_model_dirs.clear()
        if self.root_dir is None or self._single_model_root:
            return
        for a in self._all_assets:
            try:
                rel = Path(str(a.get("path", ""))).relative_to(self.root_dir)
            except ValueError:
                continue
            if not rel.parts:
                continue
            top = rel.parts[0]
            model = _strip_model_suffix(top)
            if model and model not in self._multi_model_dirs:
                self._multi_model_dirs[model] = top

    def _load_model_root_paths(self):
        """从数据库中提取每个型号的根目录路径 (model_directory_path)。"""
        self._model_root_paths.clear()
        # Use the cache when available (avoid re-hitting SQLite for a derived
        # lookup that runs at every bind). Falls back to a one-shot query if
        # bind() was bypassed somehow.
        assets = self._all_assets if self._cache_loaded() else query_assets(path=self.db_path)
        for a in assets:
            model = str(a.get("model", ""))
            mdp = str(a.get("model_directory_path", ""))
            if model and mdp and model not in self._model_root_paths:
                self._model_root_paths[model] = mdp

    # 与 query_assets / _filter_assets 共用的跨字段分词搜索字段
    _KEYWORD_FIELDS = (
        "series",
        "model",
        "version",
        "firmware_label",
        "directory_name",
        "model_directory_name",
        "path",
        "flash_mode",
        "scheme_name",
        "platform",
    )

    def _asset_matches_keyword(self, asset: FirmwareAsset, keyword: str) -> bool:
        """空格分词 AND：每个 token 在 _KEYWORD_FIELDS 任一字段命中（OR）。"""
        tokens = keyword.split() if keyword else []
        if not tokens:
            return True
        for token in tokens:
            needle = token.lower()
            hit = any(
                needle in str(asset.get(field, "")).lower()
                for field in self._KEYWORD_FIELDS
            )
            if not hit:
                return False
        return True

    def _filter_assets(
        self,
        *,
        keyword: str = "",
        category: str = "",
        scheme_name: str = "",
    ) -> list[FirmwareAsset]:
        """Read assets from the cache, applying the same filters query_assets would.

        Falls back to a one-shot query_assets call if bind() has not populated
        the cache yet — keeps the model correct for callers that skip bind
        (and lets the existing 6 fixture tests keep passing).
        """
        if not self._cache_loaded():
            return query_assets(
                keyword=keyword,
                path=self.db_path,
                category=category,
                scheme_name=scheme_name,
            )
        out: list[FirmwareAsset] = []
        # scheme_name uses a substring LIKE in query_assets; mirror that.
        scheme_needle = scheme_name.strip().lower() if scheme_name else ""
        for a in self._all_assets:
            if category and str(a.get("category", "")) != category:
                continue
            if scheme_needle:
                sn = str(a.get("scheme_name", "")).lower()
                if scheme_needle not in sn:
                    continue
            if not self._asset_matches_keyword(a, keyword):
                continue
            out.append(a)
        return out

    def _load_platforms_for_all_models(self):
        """加载平台配置（平台配置.toml），并按型号隔离。

        - 多型号根：每个型号只读自己目录下的 `平台配置.toml`（型号间绝不混用，
          否则同名平台/同名模块的默认会跨型号串扰）。
        - 单型号根：配置位于扫描根（如 L36程序/），优先从 root_dir 读取；再尝试
          每个 model_directory_path 及其上层目录，结果去重合并。
        `self._platforms` 保留为全量合并列表，供无型号上下文的旧调用使用。
        """
        self._platforms.clear()
        self._platforms_by_model.clear()

        def _merge(platforms: list[PlatformDefaults]) -> None:
            for plat in platforms:
                if plat.platform_name not in {p.platform_name for p in self._platforms}:
                    self._platforms.append(plat)

        if not self._single_model_root and self.root_dir is not None:
            for model, dir_name in self._multi_model_dirs.items():
                platforms = load_platform_config(self.root_dir / dir_name)
                self._platforms_by_model[model] = platforms
                _merge(platforms)
            return

        seen_dirs: set[str] = set()
        candidate_dirs: list[Path] = []
        if self.root_dir is not None:
            candidate_dirs.append(self.root_dir)
        # 兼容：型号目录可能各自带平台配置，从 model_directory_path 向上回溯
        for model_path in self._model_root_paths.values():
            p = Path(model_path)
            candidate_dirs.append(p)
            candidate_dirs.append(p.parent)

        for model_dir in candidate_dirs:
            key = str(model_dir)
            if key in seen_dirs:
                continue
            seen_dirs.add(key)
            _merge(load_platform_config(model_dir))

        structural = self._structural_model()
        if structural:
            self._platforms_by_model[structural] = list(self._platforms)

    def _platforms_for(self, model_name: str) -> list[PlatformDefaults]:
        """该型号可用的平台列表；无型号上下文时退化为全量合并列表。"""
        return self._platforms_by_model.get(model_name, self._platforms)

    def _model_of_asset(self, asset: FirmwareAsset) -> str:
        """资产所属型号：多型号根按一级子目录推导，单型号根即结构化型号。"""
        if self._single_model_root or self.root_dir is None:
            return self._structural_model()
        try:
            rel = Path(str(asset.get("path", ""))).relative_to(self.root_dir)
        except ValueError:
            return ""
        return _strip_model_suffix(rel.parts[0]) if rel.parts else ""

    # --- 平台默认（设默认功能） ---
    def platform_names(self, model_name: str = "") -> list[str]:
        """可选平台名列表：优先取该型号的平台配置，缺失时退化为资产上出现过的平台。"""
        platforms = self._platforms_for(model_name) if model_name else self._platforms
        names = [p.platform_name for p in platforms]
        if names:
            return names
        seen: list[str] = []
        for a in self._all_assets:
            if model_name and not self._belongs_to_model(a, model_name):
                continue
            pn = str(a.get("platform", ""))
            if pn and pn not in seen:
                seen.append(pn)
        return seen

    def _common_module_parts(self, asset: FirmwareAsset) -> tuple[str, str]:
        """解析通用区资产的 (模块目录名, 变体目录名)。

        路径形如 …/通用/主板程序/量产_默认：模块 = 通用后的第一段（跳过双机芯
        等平台子目录），变体 = 资产目录名。资产目录直接位于模块层（该模块唯一
        一份）时变体返回空串——与 平台配置.toml 中空值的语义一致。
        非通用区或无法解析时返回 ("", "")。
        """
        parts = Path(str(asset.get("path", ""))).parts
        if "通用" not in parts:
            return "", ""
        rest = list(parts[parts.index("通用") + 1:])
        platform = str(asset.get("platform", ""))
        if rest and platform and rest[0] == platform:
            rest = rest[1:]
        if not rest:
            return "", ""
        if len(rest) == 1:
            return rest[0], ""
        return rest[0], rest[-1]

    def _common_assets_matching_module(
        self, model_name: str, module_key: str
    ) -> list[FirmwareAsset]:
        """当前型号下、匹配平台配置模块键的全部通用资产。"""
        assets = self._all_assets if self._cache_loaded() else query_assets(path=self.db_path)
        out: list[FirmwareAsset] = []
        for a in assets:
            if str(a.get("category", "")) != "common":
                continue
            if not self._belongs_to_model(a, model_name):
                continue
            if _module_matches(a, module_key):
                out.append(a)
        return out

    def default_platforms_for(self, asset: FirmwareAsset) -> list[str]:
        """返回把该通用变体配置为默认程序的平台名列表（只看资产所属型号的配置）。

        平台配置约定：
        - ``defaults[模块] = "量产_默认"``：变体目录名精确匹配；
        - ``defaults[模块] = ""``：该模块**唯一**通用变体即默认（可嵌套在
          ``通用/语音程序/中文唯一版/``，不要求文件直接落在模块目录下）。
          若匹配该模块的通用资产不止一份，视为配置异常，不标默认。
        """
        if str(asset.get("category", "")) != "common":
            return []
        dir_name = str(asset.get("directory_name", ""))
        if not dir_name:
            return []
        model_name = self._model_of_asset(asset)
        asset_path = str(asset.get("path", ""))
        names: list[str] = []
        for p in self._platforms_for(model_name):
            for module_key, variant_name in p.defaults.items():
                if not _module_matches(asset, module_key):
                    continue
                configured = str(variant_name or "").strip()
                if configured == "":
                    peers = self._common_assets_matching_module(model_name, module_key)
                    if len(peers) == 1 and str(peers[0].get("path", "")) == asset_path:
                        names.append(p.platform_name)
                        break
                elif configured == dir_name:
                    names.append(p.platform_name)
                    break
        return names

    def default_badge(self, asset: FirmwareAsset) -> str:
        """默认徽章文案：该型号单平台只标 ★默认，多平台附上平台名。"""
        names = self.default_platforms_for(asset)
        if not names:
            return ""
        if len(self._platforms_for(self._model_of_asset(asset))) <= 1:
            return "★默认"
        return "★默认·" + "/".join(names)

    def _platform_config_root(self, model_name: str) -> str:
        """平台配置.toml 的落盘目录。

        不能直接用 _get_model_root：扫描器的 model_directory_path 可能指向
        通用/ 子目录，把配置写到那里后加载器会先读到扫描根下的旧文件（按平台
        名去重，旧值获胜）。因此按加载器同样的候选顺序找现存配置文件所在目录；
        都不存在时落在扫描根（配置的规范位置）。
        """
        # 多型号根：配置的规范位置就是各型号自己的目录
        if not self._single_model_root:
            return self._get_model_root(model_name)

        candidates: list[Path] = []
        if self.root_dir is not None:
            candidates.append(self.root_dir)
        model_path = self._model_root_paths.get(model_name, "")
        if model_path:
            p = Path(model_path)
            candidates.extend([p, p.parent])
        for d in candidates:
            if (d / "平台配置.toml").exists():
                return str(d)
        return str(candidates[0]) if candidates else ""

    def set_default_variant(
        self, model_name: str, platform_name: str, asset: FirmwareAsset, log_fn=print
    ) -> dict:
        """把选中的通用变体设为指定平台的默认程序（写入 平台配置.toml）。

        成功后就地重载平台配置，回源与徽章立即生效——不需要重新扫描。
        """
        module_dir, variant_name = self._common_module_parts(asset)
        if not module_dir:
            return {
                "ok": False,
                "code": "invalid_args",
                "message": "设置默认失败：该程序不在通用区，无法作为平台默认",
                "payload": {},
            }
        # 平台配置里可能已存在用字略有差异的模块键（如 版/板），沿用旧键，
        # 避免同一模块出现两个 defaults 条目。
        for p in self._platforms_for(model_name):
            if p.platform_name != platform_name:
                continue
            for key in p.defaults:
                if _module_matches(asset, key):
                    module_dir = key
                    break
            break
        result = _set_default_variant_service(
            self._platform_config_root(model_name), platform_name, module_dir, variant_name, log_fn=log_fn
        )
        if result["ok"]:
            self._load_platforms_for_all_models()
        return result

    def _structural_model(self) -> str:
        """从扫描根目录名推导结构化型号（如 'L36程序' → 'L36'）。

        固件目录是单型号根（整个 root_dir 即一个型号），因此型号应以目录结构为准，
        而不是来自单个文件名的解析（文件名里出现 'L50S' 等会污染型号列表）。
        """
        if self.root_dir is None:
            return ""
        return _strip_model_suffix(self.root_dir.name)

    def _belongs_to_model(self, asset: FirmwareAsset, model_name: str) -> bool:
        """资产是否属于该型号。

        多型号根：以"路径的一级子目录 == 该型号目录"为准，不看解析 model
        （文件名里的 L50S 等噪声会跨型号误判）。
        单型号根：资产的解析 model 可能因文件名噪声而异（L50/L50S...），
        但它们物理上都在 root_dir 内，因此以"路径在 root_dir 下"为准。
        兼容旧多型号结构：解析 model 精确相等也算。
        """
        if not self._single_model_root:
            dir_name = self._multi_model_dirs.get(model_name, "")
            if not dir_name or self.root_dir is None:
                return False
            try:
                rel = Path(str(asset.get("path", ""))).relative_to(self.root_dir)
            except ValueError:
                return False
            return bool(rel.parts) and rel.parts[0] == dir_name

        if str(asset.get("model", "")) == model_name:
            return True
        if self.root_dir is None or model_name != self._structural_model():
            return False
        try:
            Path(str(asset.get("path", ""))).relative_to(self.root_dir)
            return True
        except ValueError:
            return False

    def _get_model_root(self, model_name: str) -> str:
        """获取给定型号的根目录路径。"""
        if not self._single_model_root:
            dir_name = self._multi_model_dirs.get(model_name, "")
            if dir_name and self.root_dir is not None:
                return str(self.root_dir / dir_name)
            return ""
        root = self._model_root_paths.get(model_name, "")
        if root:
            return root
        # 结构化型号（单型号根）→ 直接用扫描根目录
        if self.root_dir is not None and model_name == self._structural_model():
            return str(self.root_dir)
        return ""

    def load_all_models(self) -> list[str]:
        """获取型号列表，用于下拉框。

        多型号根：枚举一级子目录推导的型号；单型号根：以扫描根目录名为准。
        两者都不从文件名解析型号，避免 L50/L50S 等噪声产生假型号。
        """
        if not self._single_model_root and self._multi_model_dirs:
            return sorted(self._multi_model_dirs)
        structural = self._structural_model()
        if structural:
            return [structural]
        # 退化：无 root_dir 时回退到解析 model（兼容旧调用）
        assets = self._all_assets if self._cache_loaded() else query_assets(path=self.db_path)
        models = {str(a.get("model", "")) for a in assets if str(a.get("model", ""))}
        return sorted(models)

    def build_sidebar_tree(self, model_name: str) -> dict:
        """
        构建左侧树的数据结构。
        格式:
        {
            "common": {"主板程序": 6, "手控UI": 17, ...},
            "custom": ["以色列-Royal-Z9", "葡萄牙-凡强", ...]
        }
        """
        if not model_name:
            return {"common": {}, "custom": []}

        assets = self._all_assets if self._cache_loaded() else query_assets(path=self.db_path)
        # 过滤出该型号的资产
        model_assets = [a for a in assets if self._belongs_to_model(a, model_name)]

        common_counts: dict[str, int] = {}
        custom_schemes: set[str] = set()

        for a in model_assets:
            cat = str(a.get("category", ""))
            if cat == "common":
                label = str(a.get("firmware_label", a.get("firmware_type", "")))
                common_counts[label] = common_counts.get(label, 0) + 1
            elif cat == "custom":
                scheme = str(a.get("scheme_name", ""))
                if scheme:
                    custom_schemes.add(scheme)

        return {
            "common": common_counts,
            "custom": sorted(list(custom_schemes))
        }

    def get_common_modules(self, model_name: str, firmware_label: str, keyword: str = "") -> list[ModuleCardData]:
        """点击通用模块时，返回该类型下的所有变体"""
        assets = self._filter_assets(keyword=keyword, category="common")
        results: list[ModuleCardData] = []

        for a in assets:
            if not self._belongs_to_model(a, model_name):
                continue
            if str(a.get("category", "")) != "common":
                continue
            if str(a.get("firmware_label", "")) != firmware_label and str(a.get("firmware_type", "")) != firmware_label:
                continue

            # 判断是否是默认变体
            dir_name = str(a.get("directory_name", ""))
            is_default = "_默认" in dir_name

            source_type = "common_default" if is_default else "common_variant"
            # 用户可见归属：仅「通用」（禁内部路径/回源字样）
            source_label = "通用"

            results.append(ModuleCardData(
                asset=a,
                source_type=source_type,
                source_label=source_label,
                is_fallback=False,
                source_kind="common",
                default_badge=self.default_badge(a),
            ))

        return results

    def get_scheme_modules(self, model_name: str, scheme_name: str, keyword: str = "") -> list[ModuleCardData]:
        """点击定制方案时，返回完整模块清单（含回源）。

        keyword 过滤与 ``_filter_assets`` / ``query_assets`` 一致（空格分词 + 多字段）。
        UI 层进入方案时应清空搜索框，使默认展示满树（Issue 19-A）。
        """
        # 1. 本方案定制模块（keyword 走统一分词，不再只扫 label/directory_name）
        custom_assets = self._filter_assets(
            category="custom",
            scheme_name=scheme_name,
            keyword=keyword,
        )
        # 回源覆盖判定必须基于「未按 keyword 缩小」的完整方案定制集，
        # 否则搜「手控」时会把未命中的主板当成「未覆盖」而错误回源一份通用主板。
        all_scheme_custom = self._filter_assets(category="custom", scheme_name=scheme_name)

        # 获取方案所属的平台名（用完整定制集，避免 keyword 漏掉带 platform 的资产）
        platform_name = ""
        model_root = self._get_model_root(model_name)
        for a in all_scheme_custom:
            if a.get("platform"):
                platform_name = str(a.get("platform", ""))
                break

        results: list[ModuleCardData] = []
        # 平台配置 defaults 的键是"模块目录名"（如 主板程序 / 3D机芯版程序），
        # 它来自固件目录本身；而 firmware_label 来自 catalog，二者可能有用字差异
        # （例如目录"3D机芯版程序"vs catalog"3D机芯板程序"，版/板不同）。
        # 因此覆盖判定用 _module_matches：标签相等或键命中资产路径任一段即视为覆盖。
        covered_assets = list(all_scheme_custom)

        for a in custom_assets:
            results.append(ModuleCardData(
                asset=a,
                source_type="custom_exclusive",
                source_label="定制专属",
                is_fallback=False,
                source_kind="custom",
            ))

        # 2. 从 platform_config 中寻找缺失的通用模块（回源）
        # 平台按型号隔离；如果不知道 platform，则从该型号所有平台找（退化处理）
        model_platforms = self._platforms_for(model_name)
        relevant_platforms = model_platforms
        if platform_name:
            relevant_platforms = [p for p in model_platforms if p.platform_name == platform_name]

        if relevant_platforms and model_root:
            common_assets = self._filter_assets(category="common")
            # 过滤出同型号的通用资产
            model_common = [a for a in common_assets if self._belongs_to_model(a, model_name)]

            for p in relevant_platforms:
                for module_key, default_dir in p.defaults.items():
                    # 该模块已被定制方案提供（或已回源），无需重复
                    if any(_module_matches(a, module_key) for a in covered_assets):
                        continue

                    # 找到对应的通用资产：
                    # - default_dir 非空 → 在该模块下按变体目录名精确匹配（如 量产_默认）
                    # - default_dir 为空 → 该模块在通用区唯一一份，按模块匹配
                    fallback_asset = None
                    for ca in model_common:
                        if not _module_matches(ca, module_key):
                            continue
                        if default_dir:
                            if str(ca.get("directory_name", "")) == default_dir:
                                fallback_asset = ca
                                break
                        else:
                            fallback_asset = ca
                            break

                    if fallback_asset:
                        if not self._asset_matches_keyword(fallback_asset, keyword):
                            continue

                        # 加入覆盖集，避免同一模块（含别名平台）重复回源
                        covered_assets.append(fallback_asset)
                        results.append(ModuleCardData(
                            asset=fallback_asset,
                            source_type="common_fallback",
                            # 用户可见：仅「通用」，禁止「回源」字样（Issue 6）
                            source_label="通用",
                            is_fallback=True,
                            source_kind="common",
                            default_badge=self.default_badge(fallback_asset),
                        ))

        return results

    def get_scheme_module_tree(
        self, model_name: str, scheme_name: str, keyword: str = ""
    ) -> list[ModuleRow]:
        """返回整机"模块固定层级"。

        把 get_scheme_modules 的扁平卡片按模块类型（firmware_label）归组：
        - 每个模块一行（ModuleRow），多变体（如手控UI 3 份）收在该行的 variants 下，
          不在顶层铺平。
        - 行级来源：只要该模块有任一"定制专属"变体即视为 custom，否则 common。
        - 用户文案只用「定制专属」/「通用」，绝不出现"回源"。
        - 行顺序按 STANDARD_MODULE_ORDER；不在标准列表里的模块（如接线图）排在最后。
        - 大部分机型包含 7 个标准模块，但非完整，缺失的模块不显示。
        """
        cards = self.get_scheme_modules(model_name, scheme_name, keyword)

        grouped: dict[str, list[ModuleVariant]] = {}
        for c in cards:
            label = str(c.asset.get("firmware_label", "")) or str(c.asset.get("firmware_type", ""))
            # source_kind is set by the producer (get_scheme_modules etc.). Fall
            # back to the legacy is_fallback inference for safety.
            kind = c.source_kind or ("common" if c.is_fallback else "custom")
            # 卡片层 source_label 已是用户文案；树行仍统一 定制专属/通用
            display = c.source_label if c.source_label and "回源" not in c.source_label else (
                "通用" if kind == "common" else "定制专属"
            )
            variant = ModuleVariant(
                asset=c.asset,
                name=str(c.asset.get("directory_name", "")),
                version=str(c.asset.get("version", "")),
                source_kind=kind,
                source_label=display,
                default_badge=c.default_badge,
            )
            grouped.setdefault(label, []).append(variant)

        def _order_index(label: str) -> int:
            return STANDARD_MODULE_ORDER.index(label) if label in STANDARD_MODULE_ORDER else len(STANDARD_MODULE_ORDER)

        rows: list[ModuleRow] = []
        for label in sorted(grouped, key=lambda l: (_order_index(l), l)):
            variants = grouped[label]
            row_kind = "custom" if any(v.source_kind == "custom" for v in variants) else "common"
            rows.append(
                ModuleRow(
                    label=label,
                    source_kind=row_kind,
                    source_label="定制专属" if row_kind == "custom" else "通用",
                    variants=variants,
                )
            )
        return rows

    def get_all_modules(self, model_name: str, keyword: str = "") -> list[ModuleCardData]:
        """获取指定型号下的所有模块（不回源，仅展示物理存在的模块）。

        归属文案：``通用`` 或 ``定制专属 · {scheme_name}``。
        程序名称由 UI 使用 ``directory_name`` 展示，本方法不折叠。
        """
        assets = self._filter_assets(keyword=keyword)
        results: list[ModuleCardData] = []
        for a in assets:
            if not self._belongs_to_model(a, model_name):
                continue
            cat = str(a.get("category", ""))
            dir_name = str(a.get("directory_name", ""))

            if cat == "common":
                is_default = "_默认" in dir_name
                source_type = "common_default" if is_default else "common_variant"
                source_label = "通用"
            elif cat == "custom":
                scheme = str(a.get("scheme_name", "")).strip()
                source_type = "custom_exclusive"
                source_label = f"定制专属 · {scheme}" if scheme else "定制专属"
            else:
                source_type = "unknown"
                source_label = "未知来源"

            results.append(ModuleCardData(
                asset=a,
                source_type=source_type,
                source_label=source_label,
                is_fallback=False,
                source_kind="common" if cat == "common" else "custom",
                default_badge=self.default_badge(a) if cat == "common" else "",
            ))
        return results