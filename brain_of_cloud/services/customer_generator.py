"""游客动态生成器 — 按场景模板 + 均匀随机年龄段用 LLM 生成多维游客人设。

修正「沙盒里游客都是中老年人」的问题：5 个年龄段（含 18-25 青年）均匀抽取，
LLM 生成的人设包含性别/职业/健康状况/消费习惯/说话风格等新维度，
并在提示中强化「属性与年龄/职业/健康逻辑自洽」（70+ 不会熬夜打游戏，青年不会腿脚不便）。

与 sandbox._customer_dict 的 7 键（name/nationality/age/personality/preferences/quirks/hidden）
保持兼容，另加 5 个新维度键，共 12 键。
"""

from __future__ import annotations

import random
from typing import Any

from brain_of_cloud.domain.models import AgentConfig, AgentId
from brain_of_cloud.llm.client import LLMClient
from brain_of_cloud.services.agents.base import BaseAgent

# 5 档均匀随机年龄段（含青年/中年，修正游客年龄偏大问题）
AGE_BANDS: list[tuple[str, str]] = [
    ("18-25", "青年学生/职场新人，预算有限，爱拍照打卡"),
    ("26-40", "青年职场人，注重效率与体验，可能带娃或带父母"),
    ("41-55", "中年，事业有成，注重品质与文化深度"),
    ("56-70", "中老年，时间充裕，注重舒适与安全，可能腿脚不便"),
    ("70+", "老年，需要特殊关照，行动较慢，听力/体力下降"),
]

# 人设 12 键：7 个与 sandbox._customer_dict 兼容的核心键 + 5 个新维度键
CORE_KEYS = ("name", "nationality", "age", "personality", "preferences", "quirks", "hidden")
NEW_KEYS = ("gender", "occupation", "health", "consumption", "speech_style")
PROFILE_KEYS = CORE_KEYS + NEW_KEYS

# 各年龄段的新维度默认值（LLM 兜底与属性自洽提示共用）
_BAND_DEFAULTS: dict[str, dict[str, str]] = {
    "18-25": {
        "gender": "女",
        "occupation": "在校大学生/职场新人",
        "health": "良好，体力好，能走能爬",
        "consumption": "预算有限，看重性价比，爱砍价",
        "speech_style": "语速偏快，爱用网络词，活泼",
    },
    "26-40": {
        "gender": "女",
        "occupation": "企业职员/自由职业者",
        "health": "良好，精力充沛",
        "consumption": "愿意为体验与便利付费",
        "speech_style": "语速适中，直接干脆",
    },
    "41-55": {
        "gender": "男",
        "occupation": "企业中层/个体经营者",
        "health": "良好，偶有腰腿疲劳，不宜久站",
        "consumption": "注重品质与舒适，不太计较小钱",
        "speech_style": "沉稳客气，讲究分寸",
    },
    "56-70": {
        "gender": "男",
        "occupation": "退休/临近退休",
        "health": "尚可，腿脚略慢，不宜急行，可能有基础病",
        "consumption": "精打细算，但肯为舒适与安全花钱",
        "speech_style": "语速较慢，客气周到",
    },
    "70+": {
        "gender": "男",
        "occupation": "退休",
        "health": "有慢性病需关照，行动较慢，听力/体力下降",
        "consumption": "节俭，偏好慢节奏，怕折腾",
        "speech_style": "语速慢，亲切唠叨，爱叮嘱",
    },
}

# 未知年龄段时的新维度通用兜底
_NEW_KEY_FALLBACKS: dict[str, str] = {
    "gender": "女",
    "occupation": "普通游客",
    "health": "良好，体力正常",
    "consumption": "理性消费，按需购买",
    "speech_style": "语速适中，礼貌客气",
}

# 模板无 customer_pool 时的内置兜底基准人设（7 键）
_FALLBACK_BASE: dict[str, str] = {
    "name": "游客",
    "nationality": "中国",
    "age": "30",
    "personality": "随和友善",
    "preferences": "喜欢自然风光与历史文化",
    "quirks": "说话礼貌，偶有好奇提问",
    "hidden": "希望旅程顺利，得到周到照顾",
}

CUSTOMER_GENERATOR_SYSTEM_PROMPT = """\
你是导游资格证培训系统的「游客人设设计师」。请根据场景模板与指定年龄段，
生成一位有血有肉、属性自洽的多维游客人设，供沙盒模拟中扮演游客使用。

【场景信息】
模板：{title}
地点：{location}
带团任务：{task}
情境开场：{opening}
游客当前处境：{situation}

【基础人设参考】（模板默认游客，人物方向可参考，但年龄/职业按指定年龄段重设）
姓名：{base_name}，国籍：{base_nationality}，性格：{base_personality}，
偏好：{base_preferences}，说话习惯：{base_quirks}，隐藏诉求：{base_hidden}

【指定年龄段】{band}（本段人群特征：{band_desc}）
该游客的具体年龄为 {age} 岁，请严格按这个年龄设计人设。

【属性自洽铁律】
- 职业与年龄相符（18-25 岁可以是学生/职场新人，70+ 岁应为退休老人）；
- 健康状况与年龄相符（70+ 游客绝不可能「熬夜打游戏」或体力充沛；青年游客不会「腿脚不便」）；
- 性别、职业、健康、消费习惯、说话风格、性格、偏好、说话习惯相互联动、逻辑自洽；
- 隐藏诉求是游客对学员不可见的真实诉求（评估用），用中文描述。

只输出一个合法的 JSON 对象，不要任何其他内容，格式：
{{"name": "姓名", "nationality": "国籍", "age": "{age}", "personality": "性格",
"preferences": "偏好", "quirks": "说话习惯与特点", "hidden": "隐藏诉求",
"gender": "男或女", "occupation": "职业", "health": "健康状况",
"consumption": "消费习惯", "speech_style": "说话风格"}}
"""


def _band_range(band: str) -> tuple[int, int]:
    """返回年龄段标签对应的年龄闭区间；"70+" 取 70-85（保持可信的老年上限）。"""
    if band == "70+":
        return (70, 85)
    lo, hi = band.split("-")
    return (int(lo), int(hi))


def _pick_age(band: str, rng: random.Random) -> int:
    lo, hi = _band_range(band)
    return rng.randint(lo, hi)


def _tpl_str(template: Any, key: str, default: str = "") -> str:
    """兼容 dataclass / dict 两种模板形态地读取字符串字段。"""
    if isinstance(template, dict):
        value = template.get(key, default)
    else:
        value = getattr(template, key, default)
    return str(value) if value is not None else default


def _base_profile(template: Any) -> dict[str, str]:
    """取模板 customer_pool[0] 的 7 键基准人设；无 pool 时用内置兜底。"""
    if isinstance(template, dict):
        pool = template.get("customer_pool") or []
    else:
        pool = getattr(template, "customer_pool", None) or []
    if not pool:
        return dict(_FALLBACK_BASE)
    first = pool[0]
    if isinstance(first, dict):
        return {key: str(first.get(key, "") or "") for key in CORE_KEYS}
    return {key: str(getattr(first, key, "") or "") for key in CORE_KEYS}


def _base_profile_for_country(template: Any, country: str) -> dict[str, str] | None:
    """模板游客池中取国籍匹配的基准人设（无匹配返回 None）。"""
    pool = getattr(template, "customer_pool", None) or []
    for c in pool:
        nat = str(c.get("nationality", "") or "") if isinstance(c, dict) else str(getattr(c, "nationality", "") or "")
        if nat == country:
            return {key: (str(c.get(key, "") or "") if isinstance(c, dict) else str(getattr(c, key, "") or "")) for key in CORE_KEYS}
    return None


def _is_valid_profile(data: Any) -> bool:
    """LLM 输出须为 dict 且 12 键全部非空才算解析成功。"""
    if not isinstance(data, dict):
        return False
    return all(str(data.get(key, "") or "").strip() for key in PROFILE_KEYS)


def _assemble_profile(
    data: dict[str, Any],
    base: dict[str, str],
    band: str,
    age: int,
) -> dict[str, str]:
    """合并 LLM 输出与基准/默认值，保证 12 键齐全且 age 落在 band 内。"""
    result: dict[str, str] = {}
    for key in CORE_KEYS:
        value = str(data.get(key, "") or "").strip()
        result[key] = value or base.get(key, "") or ""
    # 年龄强制取 band 内抽取值，保证「age 落在 band 范围内」恒成立
    result["age"] = str(age)
    defaults = _BAND_DEFAULTS.get(band, _NEW_KEY_FALLBACKS)
    for key in NEW_KEYS:
        value = str(data.get(key, "") or "").strip()
        result[key] = value or defaults.get(key, _NEW_KEY_FALLBACKS[key])
    return result


class CustomerGenerator(BaseAgent):
    """游客动态生成器 — 按场景模板 + 均匀随机年龄段 LLM 生成多维游客人设。"""

    agent_id = AgentId.CUSTOMER_GENERATOR

    def __init__(
        self,
        llm_client: LLMClient,
        config: AgentConfig | None = None,
    ) -> None:
        super().__init__(llm_client, config)

    def run(self, **kwargs: Any) -> dict[str, str]:
        """满足 BaseAgent 抽象方法；kwargs 转发到 generate。"""
        return self.generate(
            template=kwargs.get("template"),
            rng=kwargs.get("rng") or random.Random(),
            band=kwargs.get("band"),
            lang=kwargs.get("lang"),
        )

    def pick_age_band(self, rng: random.Random) -> str:
        """均匀随机返回一个年龄段标签（"18-25"/"26-40"/"41-55"/"56-70"/"70+"）。"""
        return rng.choice([label for label, _ in AGE_BANDS])

    def generate(
        self,
        template: Any,
        rng: random.Random,
        band: str | None = None,
        lang: str | None = None,
    ) -> dict[str, str]:
        """按模板 + 年龄段 LLM 生成游客人设（12 键 dict，与 _customer_dict 兼容）。

        - band 缺省时用 pick_age_band 均匀抽取；age 从 band 内取具体年龄数字字符串
        - LLM 输出解析/校验失败：重试 1 次，仍失败返回基于模板 customer_pool[0] 的
          兜底 dict（补默认新维度键），不抛异常
        """
        band = band or self.pick_age_band(rng)
        labels = [label for label, _ in AGE_BANDS]
        if band not in labels:
            band = self.pick_age_band(rng)
        age = _pick_age(band, rng)
        base = _base_profile(template)

        # ── 语音/外语训练：指定语言 -> 锁定母语国家（替换原随机国籍） ──
        country = None
        lang_note = ""
        if lang:
            from brain_of_cloud.services.language_profiles import LANG_COUNTRIES, LANG_NAMES_EN

            lang = lang if lang in LANG_COUNTRIES else "en"
            country = rng.choice(LANG_COUNTRIES[lang])
            cand = _base_profile_for_country(template, country)
            if cand:
                base = cand
            lang_note = (
                "\n\n【指定语言与国籍】本单是" + LANG_NAMES_EN.get(lang, lang)
                + "语音训练场景：游客必须来自" + country + "，母语为" + LANG_NAMES_EN.get(lang, lang)
                + "（" + lang + "）。请把国籍写成「" + country + "」，姓名、口音与说话习惯与该国籍相符。\n"
            )

        def _finalize(prof: dict[str, str]) -> dict[str, str]:
            if country:
                prof["nationality"] = country
            return prof

        band_desc = dict(AGE_BANDS).get(band, "")
        user_prompt = CUSTOMER_GENERATOR_SYSTEM_PROMPT.format(
            title=_tpl_str(template, "title", "（未提供标题）"),
            location=_tpl_str(template, "location", "（未提供地点）"),
            task=_tpl_str(template, "task", "（未提供任务）"),
            opening=_tpl_str(template, "opening", "（未提供开场）"),
            situation=_tpl_str(template, "situation", "（你只是普通游客，正在正常游玩）"),
            base_name=base["name"] or "游客",
            base_nationality=base["nationality"] or "中国",
            base_personality=base["personality"] or "随和",
            base_preferences=base["preferences"] or "",
            base_quirks=base["quirks"] or "",
            base_hidden=base["hidden"] or "",
            band=band,
            band_desc=band_desc,
            age=age,
        )
        if lang_note:
            user_prompt = lang_note + user_prompt

        for _ in range(2):  # 首次尝试 + 重试 1 次
            try:
                data = self._call_llm_json(
                    CUSTOMER_GENERATOR_SYSTEM_PROMPT,
                    user_prompt,
                    max_tokens=1024,
                )
                if _is_valid_profile(data):
                    return _finalize(_assemble_profile(data, base, band, age))
            except Exception:
                pass
            user_prompt += "\n\n上次输出不是合法 JSON 或缺少字段，请只输出一个包含全部 12 个字段的合法 JSON 对象，不要任何其他内容。"

        return _finalize(_assemble_profile({}, base, band, age))


def inject_profile_into_customer_prompt(customer_dict: dict) -> str:
    """返回新维度提示行（供主智能体拼进 CUSTOMER_SYSTEM_PROMPT）：

    '- 职业：{occupation}；健康状况：{health}；消费习惯：{consumption}；说话风格：{speech_style}'
    （缺失字段跳过；全部缺失返回空串）
    """
    parts: list[str] = []
    for key, label in (
        ("occupation", "职业"),
        ("health", "健康状况"),
        ("consumption", "消费习惯"),
        ("speech_style", "说话风格"),
    ):
        value = str(customer_dict.get(key, "") or "").strip()
        if value:
            parts.append(f"{label}：{value}")
    if not parts:
        return ""
    return "- " + "；".join(parts)
