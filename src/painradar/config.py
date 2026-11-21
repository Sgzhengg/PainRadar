"""Project paths and category configuration.

Market assumptions are deliberately *illustrative*: every number carries a
source grade (A/B/C/D per plan §4.6) and is rendered on the card together with
its grade. Replacing them with A/B-grade evidence is an M1 task; until then the
report must not be used as a priced deliverable.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
SAMPLE_DIR = DATA_DIR / "samples"
VAR_DIR = PROJECT_ROOT / "var"
REPORT_DIR = PROJECT_ROOT / "reports"
DOCS_DIR = PROJECT_ROOT / "docs"

DB_PATH = Path(os.environ.get("PAINRADAR_DB", VAR_DIR / "painradar.db"))

MODEL_VERSION = "extract-rule-v0.1"
PROMPT_VERSION = "p01"
TAXONOMY_VERSION = "tax-2026.11"

#: Source grades used by the market estimator (plan §4.6).
GRADE_LABEL = {
    "A": "A 一手数据/官方统计",
    "B": "B 第三方报告",
    "C": "C 评论推断",
    "D": "D 类比猜测",
}


@dataclass(frozen=True)
class Triple:
    """A low / mid / high assumption."""

    low: float
    mid: float
    high: float


@dataclass(frozen=True)
class MarketSpec:
    """Bottom-up SOM inputs, one triple per assumption."""

    population: Triple
    penetration: Triple
    reachability: Triple
    conversion: Triple
    arpu: Triple
    currency: str = "USD"
    notes: str = ""


@dataclass(frozen=True)
class CategorySpec:
    key: str
    name: str
    name_en: str
    market: MarketSpec
    scenes: dict[str, tuple[str, ...]] = field(default_factory=dict)
    personas: dict[str, tuple[str, ...]] = field(default_factory=dict)
    domain_path: tuple[str, ...] = ()
    job_template: str = "solve the problem described in the quote"
    #: Category-specific nouns used to decide whether a prediction is concrete
    #: enough for the B set. Generic words (app, subscription, device) must not
    #: appear here — the first backtest showed they match every app on earth.
    domain_terms: tuple[str, ...] = ()
    #: App ids that appeared in a search but do not belong to the category
    #: (e.g. a pet-insurance app showing up under "pet water fountain").
    excluded_apps: tuple[str, ...] = ()
    #: Human-readable app names for evidence attribution.
    app_names: dict[str, str] = field(default_factory=dict)


CATEGORIES: dict[str, CategorySpec] = {
    "pet_water_fountain": CategorySpec(
        key="pet_water_fountain",
        name="宠物智能设备",
        name_en="Pet tech device",
        domain_path=("宠物", "猫用品", "饮水器"),
        market=MarketSpec(
            population=Triple(18_000_000, 25_000_000, 32_000_000),
            penetration=Triple(0.08, 0.15, 0.22),
            reachability=Triple(0.20, 0.35, 0.50),
            conversion=Triple(0.015, 0.030, 0.050),
            arpu=Triple(32, 45, 60),
            notes="US cat-owning households; illustrative only.",
        ),
        scenes={
            "App 与连接": ("app", "wifi", "wi-fi", "connect", "connection", "connected", "connecting", "disconnect", "network", "server", "servers", "offline", "outage", "pairing", "bluetooth", "云端", "连接", "断网", "服务器"),
            "固件与更新": ("update", "updated", "updates", "firmware", "upgrade", "version", "更新", "升级", "固件"),
            "订阅与付费": ("subscription", "subscriptions", "subscribe", "plan", "paywall", "trial", "cancel", "refund", "订阅", "会员", "付费", "退款"),
            "客服与售后": ("customer support", "customer service", "support", "agent", "warranty", "replacement", "客服", "售后", "保修"),
            "夜间噪音": ("at night", "night", "loud", "noise", "noisy", "hum", "rattl", "夜间", "晚上", "噪音", "吵"),
            "清洗换水": ("clean", "wash", "rinse", "refill", "mold", "slimy", "scrub", "清洗", "换水", "发霉", "刷"),
            "多猫共饮": ("two cats", "three cats", "multi-cat", "多猫", "两只猫", "三只猫"),
            "水泵故障": ("pump died", "motor", "impeller", "seized", "pump failed", "水泵", "电机", "烧了"),
            "电源线": ("cord", "cable", "outlet", "adapter", "电源线", "插座", "线太短"),
            "水流外溅": ("splash", "spill", "水流", "溅"),
            "配件耗材": ("filter", "replacement", "proprietary", "耗材", "滤芯"),
            "感应与报警": ("sensor", "alarm", "low water", "感应", "报警"),
            "外出托管": ("travel", "weekend away", "出差", "出门"),
        },
        personas={
            "多猫家庭": ("two cats", "three cats", "multi-cat", "多猫", "两只猫", "三只猫"),
            "公寓住户": ("apartment", "flat", "studio", "公寓", "出租屋"),
            "上班族": ("work", "office", "上班", "加班"),
        },
        domain_terms=(
            "fountain", "feeder", "litter", "pump", "filter", "nozzle", "bowl",
            "collar", "camera", "sensor", "wifi", "refill", "mold", "noise",
            "battery", "cord", "spout", "motor", "clog", "leak",
        ),
        excluded_apps=("1278520013",),  # Pet Cloud: pet insurance, not a device
        app_names={
            "1586120661": "Petlibro",
            "994053492": "PETKIT",
            "999707163": "Furbo",
            "921588809": "Tractive",
            "720151500": "Petcube",
        },
    ),
    "home_storage": CategorySpec(
        key="home_storage",
        name="家居收纳",
        name_en="Home storage",
        domain_path=("家居", "收纳", "小户型"),
        market=MarketSpec(
            population=Triple(9_000_000, 14_000_000, 20_000_000),
            penetration=Triple(0.10, 0.18, 0.26),
            reachability=Triple(0.18, 0.30, 0.45),
            conversion=Triple(0.012, 0.025, 0.045),
            arpu=Triple(45, 70, 110),
            notes="Urban renters in tier-1/2 cities; illustrative only.",
        ),
        scenes={
            "换季收纳": ("换季", "过季", "被子", "羽绒服", "season"),
            "厨房台面": ("厨房", "台面", "调料", "砧板", "沥水", "kitchen"),
            "衣柜整理": ("衣柜", "衣架", "挂衣", "closet", "wardrobe"),
            "床底缝隙": ("床底", "床下", "沙发底", "缝隙"),
            "租房改造": ("租房", "出租屋", "打孔", "免钉", "顶天立地"),
            "小户型": ("小户型", "两居", "60平", "50平", "平米"),
        },
        personas={
            "租房青年": ("租房", "出租屋", "renter"),
            "小户型家庭": ("小户型", "两居", "60平", "50平"),
            "宝妈": ("孩子", "宝宝", "宝妈", "娃"),
        },
        domain_terms=(
            "storage", "closet", "shelf", "bin", "drawer", "wardrobe", "rack",
            "box", "organizer", "cabinet", "hanger", "container",
        ),
    ),
    "camping_gear": CategorySpec(
        key="camping_gear",
        name="户外露营装备",
        name_en="Camping gear",
        domain_path=("户外", "露营", "装备"),
        market=MarketSpec(
            population=Triple(6_000_000, 9_000_000, 13_000_000),
            penetration=Triple(0.10, 0.17, 0.25),
            reachability=Triple(0.20, 0.32, 0.45),
            conversion=Triple(0.015, 0.028, 0.045),
            arpu=Triple(80, 130, 200),
            notes="Weekend car-camping households; illustrative only.",
        ),
        scenes={
            "搭建收纳": ("setup", "pitch", "pack", "pole", "tent bag", "搭建", "收纳", "帐篷"),
            "雨雪天气": ("rain", "wind", "storm", "wet", "下雨", "大风"),
            "车载出行": ("trunk", "roof bag", "car", "后备箱", "自驾", "装车"),
            "炊事烹饪": ("stove", "cook", "fuel", "flame", "炉", "做饭"),
            "睡眠休息": ("sleeping pad", "pad", "sleep", "deflat", "睡垫", "睡眠"),
        },
        personas={
            "周末露营": ("weekend", "family trip", "周末", "亲子"),
            "新手": ("first time", "beginner", "新手", "第一次"),
            "自驾党": ("car", "trunk", "自驾", "后备箱"),
        },
        domain_terms=(
            "tent", "pole", "cooler", "stove", "sleeping pad", "backpack",
            "lantern", "campsite", "tarp", "peg", "trunk", "camp",
        ),
    ),
    "sleep_tech": CategorySpec(
        key="sleep_tech",
        name="睡眠应用",
        name_en="Sleep tracking app",
        domain_path=("健康", "睡眠", "应用"),
        market=MarketSpec(
            population=Triple(8_000_000, 14_000_000, 22_000_000),
            penetration=Triple(0.08, 0.15, 0.24),
            reachability=Triple(0.20, 0.32, 0.45),
            conversion=Triple(0.012, 0.025, 0.045),
            arpu=Triple(30, 50, 80),
            notes="Illustrative only; predictions do not depend on it.",
        ),
        scenes={
            "入睡与助眠": ("fall asleep", "insomnia", "relax", "sleep sound", "入睡", "失眠", "助眠"),
            "闹钟与唤醒": ("alarm", "wake up", "snooze", "smart wake", "闹钟", "唤醒"),
            "数据与准确性": ("tracking", "accuracy", "sleep score", "data is", "数据", "准确", "评分"),
            "订阅与付费": ("subscription", "premium", "trial", "paywall", "订阅", "会员", "付费"),
            "设备与同步": ("watch", "sync", "apple health", "wearable", "同步", "手表", "设备"),
            "客服与退款": ("support", "refund", "cancel", "客服", "退款"),
        },
        personas={"新手": ("new to", "first time", "新手"), "长期用户": ("years", "long time", "长期")},
        domain_terms=(
            "sleep", "insomnia", "snore", "alarm", "dream", "nap", "wake",
            "bedtime", "wearable", "watch",
        ),
    ),
    "budgeting": CategorySpec(
        key="budgeting",
        name="记账理财应用",
        name_en="Budgeting app",
        domain_path=("金融", "个人理财", "应用"),
        market=MarketSpec(
            population=Triple(12_000_000, 20_000_000, 30_000_000),
            penetration=Triple(0.06, 0.12, 0.20),
            reachability=Triple(0.18, 0.30, 0.42),
            conversion=Triple(0.015, 0.030, 0.050),
            arpu=Triple(40, 70, 110),
            notes="Illustrative only; predictions do not depend on it.",
        ),
        scenes={
            "记账与分类": ("categorize", "category", "transaction", "记账", "分类", "流水"),
            "银行同步": ("bank", "sync", "connect", "plaid", "银行", "同步", "连接"),
            "预算与超支": ("budget", "overspend", "limit", "预算", "超支"),
            "报表与洞察": ("report", "chart", "insight", "报表", "图表"),
            "订阅与付费": ("subscription", "premium", "paywall", "订阅", "付费"),
            "导出与迁移": ("export", "csv", "migrate", "导入", "导出", "迁移"),
        },
        personas={"预算新手": ("first budget", "new to budgeting", "新手"), "家庭": ("family", "家庭")},
        domain_terms=(
            "budget", "expense", "receipt", "bank", "transaction", "bill",
            "cash", "income", "debt", "category",
        ),
    ),
    "plant_care": CategorySpec(
        key="plant_care",
        name="植物养护应用",
        name_en="Plant care app",
        domain_path=("生活方式", "园艺", "应用"),
        market=MarketSpec(
            population=Triple(10_000_000, 18_000_000, 28_000_000),
            penetration=Triple(0.07, 0.14, 0.22),
            reachability=Triple(0.18, 0.30, 0.45),
            conversion=Triple(0.010, 0.022, 0.040),
            arpu=Triple(25, 45, 70),
            notes="Illustrative only; predictions do not depend on it.",
        ),
        scenes={
            "浇水与提醒": ("water", "reminder", "schedule", "浇水", "提醒"),
            "识别准确性": ("identify", "identification", "wrong plant", "识别", "不准"),
            "病虫害诊断": ("disease", "pest", "diagnose", "病害", "虫害"),
            "订阅与付费": ("subscription", "premium", "paywall", "订阅", "付费"),
            "光照与位置": ("light", "window", "placement", "光照", "位置"),
        },
        personas={"新手": ("beginner", "first plant", "新手"), "多肉玩家": ("succulent", "多肉")},
        domain_terms=(
            "plant", "leaf", "soil", "pest", "watering", "sunlight",
            "fertilizer", "pot", "root", "identify",
        ),
    ),
}


def category(key: str) -> CategorySpec:
    try:
        return CATEGORIES[key]
    except KeyError as exc:  # pragma: no cover - defensive
        raise SystemExit(
            f"unknown category {key!r}; known: {', '.join(sorted(CATEGORIES))}"
        ) from exc


# --- custom categories ---------------------------------------------------
#
# A category needs more than a name: a scene vocabulary (how clusters are
# labelled), domain terms (what makes a B-set prediction specific) and market
# assumptions. Users only supply a name and a search term, so we start from a
# generic six-scene template and let the data decide the rest.

CUSTOM_PATH = PROJECT_ROOT / "var" / "custom_categories.json"

DEFAULT_SCENES: dict[str, tuple[str, ...]] = {
    "功能与故障": ("broken", "stopped", "doesn't work", "not working", "fail", "error",
                "故障", "坏了", "失灵", "不能用"),
    "连接与同步": ("connect", "sync", "bluetooth", "wifi", "pair", "app", "连接", "同步", "断连", "配对"),
    "清洁与保养": ("clean", "wash", "mold", "filter", "descale", "清洗", "清洁", "发霉", "滤芯", "除垢"),
    "价格与订阅": ("subscription", "price", "expensive", "paywall", "refund", "订阅", "价格", "贵", "退款"),
    "客服与售后": ("support", "warranty", "customer service", "replacement", "客服", "售后", "保修", "换货"),
    "其他场景": (),
}


def _default_market(name: str) -> MarketSpec:
    return MarketSpec(
        population=Triple(1_000_000, 3_000_000, 8_000_000),
        penetration=Triple(0.03, 0.08, 0.15),
        reachability=Triple(0.15, 0.28, 0.40),
        conversion=Triple(0.010, 0.020, 0.035),
        arpu=Triple(20, 40, 70),
        notes=f"Custom category {name}: placeholder assumptions (grade D).",
    )


def load_custom_categories(path: Path | None = None) -> int:
    """Merge var/custom_categories.json into CATEGORIES. Returns how many loaded."""
    path = path or CUSTOM_PATH
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    n = 0
    for key, raw in data.items():
        if not isinstance(raw, dict):
            continue
        if key in CATEGORIES and not key.startswith("custom_"):
            continue
        name = str(raw.get("name") or key)
        scenes = raw.get("scenes") or DEFAULT_SCENES
        CATEGORIES[key] = CategorySpec(
            key=key,
            name=name,
            name_en=str(raw.get("name_en") or name),
            market=_default_market(name),
            scenes={k: tuple(v) for k, v in scenes.items()},
            personas={},
            domain_terms=tuple(raw.get("domain_terms") or ()),
            excluded_apps=tuple(raw.get("excluded_apps") or ()),
            app_names=dict(raw.get("app_names") or {}),
        )
        n += 1
    return n


def register_custom_category(
    name: str,
    term: str,
    app_names: dict[str, str] | None = None,
    path: Path | None = None,
) -> str:
    """Create (or reuse) a custom category and persist it. Returns the key."""
    path = path or CUSTOM_PATH
    slug = re.sub(r"[^a-z0-9]+", "_", term.lower()).strip("_")[:24] or "custom"
    key = f"custom_{slug}"
    data: dict = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
    if key not in data:
        tokens = [t for t in re.split(r"[^a-z0-9]+", term.lower()) if len(t) >= 3]
        data[key] = {
            "name": name,
            "name_en": term,
            "domain_terms": tokens,
            "scenes": {k: list(v) for k, v in DEFAULT_SCENES.items()},
            "app_names": app_names or {},
        }
    else:
        data[key]["name"] = name or data[key].get("name", key)
        data[key]["name_en"] = term or data[key].get("name_en", "")
        if app_names:
            data[key].setdefault("app_names", {}).update(app_names)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    load_custom_categories(path)
    return key


load_custom_categories()
