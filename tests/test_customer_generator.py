"""游客动态生成器测试 — mock LLM，覆盖年龄段均匀抽取、12 键人设、年龄落位、失败兜底、prompt 注入。"""
import json
import random
from types import SimpleNamespace
from unittest.mock import MagicMock

from brain_of_cloud.domain.models import AgentId
from brain_of_cloud.llm.client import LLMClient, LLMResponse
from brain_of_cloud.services.customer_generator import (
    AGE_BANDS,
    CustomerGenerator,
    inject_profile_into_customer_prompt,
)

EXPECTED_KEYS = {
    "name", "nationality", "age", "personality", "preferences", "quirks", "hidden",
    "gender", "occupation", "health", "consumption", "speech_style",
}

VALID_PROFILE = {
    "name": "小林",
    "nationality": "中国",
    "age": "32",
    "personality": "务实高效，注重体验",
    "preferences": "喜欢小众景点与美食探店",
    "quirks": "说话直接，爱列清单",
    "hidden": "工作压力大，想借旅行放松，担心行程太赶",
    "gender": "女",
    "occupation": "互联网公司产品经理",
    "health": "良好，久坐腰略酸",
    "consumption": "愿意为品质付费，也看性价比",
    "speech_style": "语速快，条理清楚",
}


def _mock_llm(content: str) -> LLMClient:
    llm = MagicMock(spec=LLMClient)
    llm.chat.return_value = LLMResponse(content=content, usage_tokens={"total_tokens": 10})
    llm.model = "deepseek-chat"
    return llm


def _make_template(customer: SimpleNamespace | None = None) -> SimpleNamespace:
    base = customer or SimpleNamespace(
        name="汉斯",
        nationality="德国",
        age="45",
        personality="严谨固执，讲原则但好面子",
        preferences="喜欢历史，尤其古建筑工艺",
        quirks="习惯直说，不高兴会当场质问",
        hidden="其实很尊重古建筑，只是因为不懂规则被当众指出而觉得丢面子，需要台阶下",
    )
    return SimpleNamespace(
        title="江南古镇 · 游客违规",
        location="游客服务中心",
        task="制止游客违反景区规定，同时维护游客情绪与服务态度",
        opening="烟雨蒙蒙的清晨，你带团的江南古镇迎来了外国游客。",
        situation="你刚跨进护栏踩踏古建筑基座，还点起了一根烟。",
        customer_pool=[base],
    )


def _make_agent(llm: LLMClient) -> CustomerGenerator:
    return CustomerGenerator(llm_client=llm)


def _band_range(band: str) -> tuple[int, int]:
    if band == "70+":
        return (70, 85)
    lo, hi = band.split("-")
    return (int(lo), int(hi))


# ─────────────────────────── AgentId / 枚举 ───────────────────────────

class TestAgentId:
    def test_customer_generator_member_exists(self):
        assert AgentId.CUSTOMER_GENERATOR == "customer_generator"
        assert AgentId.CUSTOMER_GENERATOR in AgentId

    def test_agent_class_uses_enum(self):
        assert CustomerGenerator.agent_id == AgentId.CUSTOMER_GENERATOR

    def test_scene_director_still_present(self):
        # 并行任务 t2 的成员不应被覆盖
        assert AgentId.SCENE_DIRECTOR == "scene_director"


# ─────────────────────────── pick_age_band ───────────────────────────

class TestPickAgeBand:
    def test_returns_one_of_five_bands(self):
        agent = _make_agent(_mock_llm(""))
        rng = random.Random(7)
        labels = {label for label, _ in AGE_BANDS}
        for _ in range(50):
            assert agent.pick_age_band(rng) in labels

    def test_uniform_distribution_covers_all_bands(self):
        agent = _make_agent(_mock_llm(""))
        rng = random.Random(42)
        counts: dict[str, int] = {label: 0 for label, _ in AGE_BANDS}
        n = 1000
        for _ in range(n):
            counts[agent.pick_age_band(rng)] += 1
        # 5 档全部出现（均匀性：每档期望 200，宽松区间 [50, 350]）
        assert len([c for c in counts.values() if c > 0]) == 5
        for label, count in counts.items():
            assert 50 <= count <= 350, f"band {label} 计数异常: {count}"


# ─────────────────────────── generate ───────────────────────────

class TestGenerate:
    def test_generate_returns_dict_with_all_12_keys(self):
        llm = _mock_llm(json.dumps(VALID_PROFILE, ensure_ascii=False))
        profile = _make_agent(llm).generate(
            template=_make_template(), rng=random.Random(1), band="26-40"
        )

        assert set(profile.keys()) == EXPECTED_KEYS
        assert all(str(profile[k]).strip() for k in EXPECTED_KEYS)  # 全部非空
        # 新维度取自 LLM 输出
        assert profile["gender"] == "女"
        assert profile["occupation"] == "互联网公司产品经理"
        assert profile["health"] == "良好，久坐腰略酸"
        assert profile["consumption"] == "愿意为品质付费，也看性价比"
        assert profile["speech_style"] == "语速快，条理清楚"
        # 年龄强制落位 band 内
        lo, hi = _band_range("26-40")
        assert lo <= int(profile["age"]) <= hi
        # LLM 调用 1 次即成功（无重试）
        assert llm.chat.call_count == 1

    def test_age_in_band_for_all_five_bands(self):
        llm = _mock_llm(json.dumps(VALID_PROFILE, ensure_ascii=False))
        agent = _make_agent(llm)
        rng = random.Random(3)
        for label, _ in AGE_BANDS:
            profile = agent.generate(template=_make_template(), rng=rng, band=label)
            lo, hi = _band_range(label)
            age = int(profile["age"])
            assert lo <= age <= hi, f"band={label} age={age} 未落在 [{lo}, {hi}]"
            assert set(profile.keys()) == EXPECTED_KEYS

    def test_generate_without_band_picks_uniformly(self):
        llm = _mock_llm(json.dumps(VALID_PROFILE, ensure_ascii=False))
        profile = _make_agent(llm).generate(template=_make_template(), rng=random.Random(5))
        assert set(profile.keys()) == EXPECTED_KEYS
        lo, hi = _band_range("70+") if int(profile["age"]) >= 70 else (18, 70)
        assert lo <= int(profile["age"]) <= hi

    def test_fallback_on_invalid_json_does_not_raise(self):
        llm = _mock_llm("这不是合法 JSON {{{")
        profile = _make_agent(llm).generate(
            template=_make_template(), rng=random.Random(2), band="56-70"
        )

        # 不抛异常、12 键齐全、含新维度默认值
        assert set(profile.keys()) == EXPECTED_KEYS
        assert all(str(profile[k]).strip() for k in EXPECTED_KEYS)
        assert profile["health"]
        assert profile["consumption"]
        assert profile["speech_style"]
        assert profile["gender"] in ("男", "女")
        # 兜底基于模板 customer_pool[0]（7 键兼容）
        assert profile["name"] == "汉斯"
        assert profile["nationality"] == "德国"
        assert profile["personality"] == "严谨固执，讲原则但好面子"
        # 年龄仍在 band 内
        lo, hi = _band_range("56-70")
        assert lo <= int(profile["age"]) <= hi
        # 首次失败 + 重试 1 次 = 2 次调用
        assert llm.chat.call_count == 2

    def test_retry_then_success(self):
        llm = _mock_llm("bad {{{")
        llm.chat.side_effect = [
            LLMResponse(content="bad {{{", usage_tokens={"total_tokens": 1}),
            LLMResponse(content=json.dumps(VALID_PROFILE, ensure_ascii=False), usage_tokens={"total_tokens": 1}),
        ]
        profile = _make_agent(llm).generate(
            template=_make_template(), rng=random.Random(4), band="18-25"
        )

        assert set(profile.keys()) == EXPECTED_KEYS
        assert profile["occupation"] == "互联网公司产品经理"  # 重试后取自 LLM
        assert llm.chat.call_count == 2

    def test_fallback_missing_fields_in_valid_json(self):
        # 合法 JSON 但缺字段 → 视为解析失败，走重试+兜底
        partial = dict(VALID_PROFILE)
        del partial["hidden"]
        llm = _mock_llm(json.dumps(partial, ensure_ascii=False))
        profile = _make_agent(llm).generate(
            template=_make_template(), rng=random.Random(6), band="41-55"
        )

        assert set(profile.keys()) == EXPECTED_KEYS
        lo, hi = _band_range("41-55")
        assert lo <= int(profile["age"]) <= hi
        # 兜底补上了 hidden 与默认新维度
        assert profile["hidden"]
        assert profile["consumption"]
        assert llm.chat.call_count == 2


# ─────────────────────────── inject_profile_into_customer_prompt ───────────────────────────

class TestInjectProfile:
    def test_injects_four_new_dimensions(self):
        line = inject_profile_into_customer_prompt(
            {
                "occupation": "退休教师",
                "health": "有轻度高血压，不能走太急",
                "consumption": "愿意为品质付费",
                "speech_style": "语速慢，客气敬语多",
            }
        )
        assert line.startswith("- ")
        assert "职业：退休教师" in line
        assert "健康状况：有轻度高血压，不能走太急" in line
        assert "消费习惯：愿意为品质付费" in line
        assert "说话风格：语速慢，客气敬语多" in line

    def test_skips_missing_fields(self):
        line = inject_profile_into_customer_prompt(
            {"occupation": "程序员", "health": "良好"}
        )
        assert "职业：程序员" in line
        assert "健康状况：良好" in line
        assert "消费习惯" not in line
        assert "说话风格" not in line

    def test_empty_dict_returns_empty_string(self):
        assert inject_profile_into_customer_prompt({}) == ""
        assert inject_profile_into_customer_prompt({"name": "汉斯"}) == ""
