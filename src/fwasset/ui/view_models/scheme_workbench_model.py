from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fwasset.core.asset_index import query_assets
from fwasset.core.platform_config import load_platform_config, default_variant_for, PlatformDefaults
from fwasset.core.types import FirmwareAsset


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
    source_kind: str               # "custom"（定制专属）/ "common"（通用默认）
    source_label: str              # 用户可读来源文案，绝不含"回源"


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

    def bind(self, db_path: Path | None, root_dir: Path):
        self.db_path = db_path
        self.root_dir = root_dir
        self._load_model_root_paths()
        self._load_platforms_for_all_models()

    def _load_model_root_paths(self):
        """从数据库中提取每个型号的根目录路径 (model_directory_path)。"""
        self._model_root_paths.clear()
        assets = query_assets(path=self.db_path)
        for a in assets:
            model = str(a.get("model", ""))
            mdp = str(a.get("model_directory_path", ""))
            if model and mdp and model not in self._model_root_paths:
                self._model_root_paths[model] = mdp

    def _load_platforms_for_all_models(self):
        """加载平台配置（平台配置.toml）。

        `平台配置.toml` 位于扫描根目录（如 L36程序/），因此优先从 root_dir 读取。
        为兼容"根目录下含多个型号子目录"的结构，再尝试每个 model_directory_path
        的上层目录。所有结果去重合并。
        """
        self._platforms.clear()
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
            platforms = load_platform_config(model_dir)
            for plat in platforms:
                if plat.platform_name not in {p.platform_name for p in self._platforms}:
                    self._platforms.append(plat)

    def _structural_model(self) -> str:
        """从扫描根目录名推导结构化型号（如 'L36程序' → 'L36'）。

        固件目录是单型号根（整个 root_dir 即一个型号），因此型号应以目录结构为准，
        而不是来自单个文件名的解析（文件名里出现 'L50S' 等会污染型号列表）。
        """
        if self.root_dir is None:
            return ""
        name = self.root_dir.name
        for suffix in ("程序", "目录"):
            if name.endswith(suffix):
                name = name[: -len(suffix)]
                break
        return name.strip()

    def _belongs_to_model(self, asset: FirmwareAsset, model_name: str) -> bool:
        """资产是否属于该型号。

        单型号根下，资产的解析 model 可能因文件名噪声而异（L50/L50S...），
        但它们物理上都在 root_dir 内，因此以"路径在 root_dir 下"为准。
        兼容旧多型号结构：解析 model 精确相等也算。
        """
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
        root = self._model_root_paths.get(model_name, "")
        if root:
            return root
        # 结构化型号（单型号根）→ 直接用扫描根目录
        if self.root_dir is not None and model_name == self._structural_model():
            return str(self.root_dir)
        return ""

    def load_all_models(self) -> list[str]:
        """获取型号列表，用于下拉框。

        以扫描根目录结构为准（单型号根），避免文件名解析噪声产生 L50/L50S 等假型号。
        """
        structural = self._structural_model()
        if structural:
            return [structural]
        # 退化：无 root_dir 时回退到解析 model（兼容旧调用）
        assets = query_assets(path=self.db_path)
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

        assets = query_assets(path=self.db_path)
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
        assets = query_assets(keyword=keyword, path=self.db_path)
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
            source_label = f"通用/{dir_name}" + (" (默认)" if is_default else "")

            results.append(ModuleCardData(
                asset=a,
                source_type=source_type,
                source_label=source_label,
                is_fallback=False
            ))

        return results

    def get_scheme_modules(self, model_name: str, scheme_name: str, keyword: str = "") -> list[ModuleCardData]:
        """点击定制方案时，返回完整模块清单（含回源）"""
        # 1. 查找属于这个方案的定制模块
        custom_assets = query_assets(path=self.db_path, category="custom", scheme_name=scheme_name)
        # 如果方案被关键字过滤掉了，说明用户正在搜索，我们需要让全局过滤生效
        if keyword:
            custom_assets = [a for a in custom_assets if keyword.lower() in str(a.get("label", "")).lower() or keyword.lower() in str(a.get("directory_name", "")).lower()]

        # 获取方案所属的平台名
        platform_name = ""
        model_root = self._get_model_root(model_name)
        for a in custom_assets:
            if a.get("platform"):
                platform_name = str(a.get("platform", ""))
                break

        results: list[ModuleCardData] = []
        # 平台配置 defaults 的键是"模块目录名"（如 主板程序 / 3D机芯版程序），
        # 它来自固件目录本身；而 firmware_label 来自 catalog，二者可能有用字差异
        # （例如目录"3D机芯版程序"vs catalog"3D机芯板程序"，版/板不同）。
        # 因此覆盖判定用 _module_matches：标签相等或键命中资产路径任一段即视为覆盖。
        covered_assets = list(custom_assets)

        for a in custom_assets:
            results.append(ModuleCardData(
                asset=a,
                source_type="custom_exclusive",
                source_label=f"定制/{scheme_name} (专属)",
                is_fallback=False
            ))

        # 2. 从 platform_config 中寻找缺失的通用模块（回源）
        # 如果不知道 platform，则从所有平台找（退化处理）
        relevant_platforms = self._platforms
        if platform_name:
            relevant_platforms = [p for p in self._platforms if p.platform_name == platform_name]

        if relevant_platforms and model_root:
            common_assets = query_assets(path=self.db_path, category="common")
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
                        # 应用关键字过滤
                        if keyword and keyword.lower() not in str(fallback_asset.get("label", "")).lower() and keyword.lower() not in str(fallback_asset.get("directory_name", "")).lower():
                            continue

                        # 加入覆盖集，避免同一模块（含别名平台）重复回源
                        covered_assets.append(fallback_asset)
                        src_dir = default_dir or str(fallback_asset.get("directory_name", ""))
                        results.append(ModuleCardData(
                            asset=fallback_asset,
                            source_type="common_fallback",
                            source_label=f"通用/{src_dir} (回源)",
                            is_fallback=True
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
        - 用户文案只用「定制专属」/「通用默认」，绝不出现"回源"。
        - 行顺序按 STANDARD_MODULE_ORDER；不在标准列表里的模块（如接线图）排在最后。
        - 大部分机型包含 7 个标准模块，但非完整，缺失的模块不显示。
        """
        cards = self.get_scheme_modules(model_name, scheme_name, keyword)

        grouped: dict[str, list[ModuleVariant]] = {}
        for c in cards:
            label = str(c.asset.get("firmware_label", "")) or str(c.asset.get("firmware_type", ""))
            kind = "common" if c.is_fallback else "custom"
            variant = ModuleVariant(
                asset=c.asset,
                name=str(c.asset.get("directory_name", "")),
                version=str(c.asset.get("version", "")),
                source_kind=kind,
                source_label="通用默认" if kind == "common" else "定制专属",
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
                    source_label="定制专属" if row_kind == "custom" else "通用默认",
                    variants=variants,
                )
            )
        return rows

    def get_all_modules(self, model_name: str, keyword: str = "") -> list[ModuleCardData]:
        """获取指定型号下的所有模块（不回源，仅展示物理存在的模块）"""
        assets = query_assets(keyword=keyword, path=self.db_path)
        results: list[ModuleCardData] = []
        for a in assets:
            if not self._belongs_to_model(a, model_name):
                continue
            cat = str(a.get("category", ""))
            dir_name = str(a.get("directory_name", ""))
            
            if cat == "common":
                is_default = "_默认" in dir_name
                source_type = "common_default" if is_default else "common_variant"
                source_label = f"通用/{dir_name}" + (" (默认)" if is_default else "")
            elif cat == "custom":
                scheme = str(a.get("scheme_name", ""))
                source_type = "custom_exclusive"
                source_label = f"定制/{scheme}" if scheme else "定制专属"
            else:
                source_type = "unknown"
                source_label = "未知来源"
                
            results.append(ModuleCardData(
                asset=a,
                source_type=source_type,
                source_label=source_label,
                is_fallback=False
            ))
        return results