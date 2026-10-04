"""审查判定标准修正（T8，评审反馈 #6）：
- 审查只判定「无虚假、无矛盾」，不得以「与原文一致」为通过条件；
- 合理演绎（举例/类比/讲解转化）必须放行；
- 生成侧必须「讲解转化」而非照搬原文。
这里断言各智能体提示词包含新判定标准（输出判定本身依赖 LLM，单测验证契约）。"""

from brain_of_cloud.services.agents.black_hat import BLACK_HAT_SYSTEM_PROMPT
from brain_of_cloud.services.agents.blue_hat import BLUE_HAT_SYSTEM_PROMPT
from brain_of_cloud.services.agents.concierge import CONCIERGE_SYSTEM_PROMPT
from brain_of_cloud.services.agents.green_hat import GREEN_HAT_SYSTEM_PROMPT
from brain_of_cloud.services.agents.red_hat import RED_HAT_SYSTEM_PROMPT
from brain_of_cloud.services.agents.text_generator import TEXT_GENERATOR_SYSTEM_PROMPT
from brain_of_cloud.services.agents.white_hat import WHITE_HAT_SYSTEM_PROMPT
from brain_of_cloud.services.agents.yellow_hat import YELLOW_HAT_SYSTEM_PROMPT


class TestWhiteHatStandard:
    """白帽：无虚假/无矛盾即通过，演绎放行。"""

    def test_definition_includes_deduction_category(self):
        assert "演绎" in WHITE_HAT_SYSTEM_PROMPT

    def test_deduction_is_not_failure(self):
        assert "演绎不是问题" in WHITE_HAT_SYSTEM_PROMPT
        assert "就不能作为「不通过」的理由" in WHITE_HAT_SYSTEM_PROMPT

    def test_only_contradiction_or_false_fails(self):
        assert "只有出现「矛盾」或「明显虚假」时才判「不通过」" in WHITE_HAT_SYSTEM_PROMPT

    def test_not_requiring_verbatim(self):
        assert "不是要求照搬原文" in WHITE_HAT_SYSTEM_PROMPT

    def test_unverified_is_watchlist_not_failure(self):
        assert "待核验" in WHITE_HAT_SYSTEM_PROMPT
        assert "不单独判不通过" in WHITE_HAT_SYSTEM_PROMPT


class TestBlackHatStandard:
    """黑帽：判定依据是逻辑与规范，不是原文一致。"""

    def test_judgement_basis_is_logic(self):
        assert "判定依据是逻辑与规范" in BLACK_HAT_SYSTEM_PROMPT
        assert "不是「与参考原文一致」" in BLACK_HAT_SYSTEM_PROMPT

    def test_deduction_allowed(self):
        assert "允许合理的教学演绎" in BLACK_HAT_SYSTEM_PROMPT
        assert "不能作为「不通过」的理由" in BLACK_HAT_SYSTEM_PROMPT

    def test_differs_from_original_is_not_error(self):
        assert "内容与原文不一致 ≠ 错误" in BLACK_HAT_SYSTEM_PROMPT


class TestBlueHatStandard:
    """蓝帽：事实准确 = 无矛盾无虚构，不等于原文一致。"""

    def test_fact_dimension_definition(self):
        assert "无矛盾、无虚构" in BLUE_HAT_SYSTEM_PROMPT

    def test_verbatim_never_penalized(self):
        assert "「与参考原文不一致」永远不是扣分理由" in BLUE_HAT_SYSTEM_PROMPT

    def test_teaching_rewording_is_value(self):
        assert "讲解转化、举例、个性化的表达是教学价值所在" in BLUE_HAT_SYSTEM_PROMPT


class TestTextGeneratorStandard:
    """文本生成：证据是依据不是模板，必须讲解转化。"""

    def test_evidence_is_basis_not_template(self):
        assert "参考证据是「事实依据」不是「抄写模板」" in TEXT_GENERATOR_SYSTEM_PROMPT
        assert "禁止大段照搬或复述检索原文" in TEXT_GENERATOR_SYSTEM_PROMPT

    def test_extension_encouraged(self):
        assert "允许并鼓励在证据基础上扩展演绎" in TEXT_GENERATOR_SYSTEM_PROMPT

    def test_not_a_photocopy(self):
        assert "不是「书本复印件」" in TEXT_GENERATOR_SYSTEM_PROMPT


class TestConciergeStandard:
    """管家：讲解转化铁律，禁止照搬原文。"""

    def test_teaching_conversion_rule_present(self):
        assert "讲解转化铁律" in CONCIERGE_SYSTEM_PROMPT

    def test_no_verbatim_copy(self):
        assert "禁止照搬或大段复述原文" in CONCIERGE_SYSTEM_PROMPT

    def test_evidence_is_basis(self):
        assert "检索结果只是「事实依据」，不是「朗读材料」" in CONCIERGE_SYSTEM_PROMPT


class TestHatsFollowConciergeRequirements:
    """六帽内容与管家新要求对齐（讲解转化/教学 persona/主题上下文）。"""

    def test_green_hat_checks_teaching_conversion(self):
        assert "讲解转化" in GREEN_HAT_SYSTEM_PROMPT
        assert "照本宣科 = 不合格" in GREEN_HAT_SYSTEM_PROMPT
        assert "只有原文没有讲解" in GREEN_HAT_SYSTEM_PROMPT

    def test_green_hat_checks_teacher_trace(self):
        assert "老师在讲" in GREEN_HAT_SYSTEM_PROMPT

    def test_yellow_hat_checks_teacher_persona(self):
        assert "备考老师" in YELLOW_HAT_SYSTEM_PROMPT
        assert "温暖友好同时保持专业" in YELLOW_HAT_SYSTEM_PROMPT

    def test_red_hat_checks_teaching_context(self):
        assert "当前教学上下文" in RED_HAT_SYSTEM_PROMPT
        assert "教学主题" in RED_HAT_SYSTEM_PROMPT
        assert "答非所问" in RED_HAT_SYSTEM_PROMPT

    def test_red_hat_checks_plain_talk_for_low_level(self):
        assert "降维解释" in RED_HAT_SYSTEM_PROMPT

    def test_metaphor_example_allowed(self):
        assert "可以打比方、举例子、串学员的经历" in CONCIERGE_SYSTEM_PROMPT

    def test_no_fabrication(self):
        assert "不歪曲事实、不编造数字" in CONCIERGE_SYSTEM_PROMPT
