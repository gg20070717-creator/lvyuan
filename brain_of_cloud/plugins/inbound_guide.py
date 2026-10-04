from __future__ import annotations

from collections import Counter

from brain_of_cloud.domain.models import Evidence, KnowledgePoint, Question


class InboundGuidePlugin:
    manifest = {
        "plugin_id": "inbound_tour_local_guide",
        "name": "入境游地陪导游训练",
        "version": "0.1.0",
        "training_provider": "Brain of Cloud built-in",
        "supported_assets": ["lecture", "practice_guide", "graded_quiz", "text"],
    }

    def __init__(self) -> None:
        self._knowledge_points = [
            KnowledgePoint(
                id="kp_pickup",
                name="接站流程",
                level="intro",
                target_skill="完成入境游客抵达后的身份确认、行李协助和上车交接。",
            ),
            KnowledgePoint(
                id="kp_welcome",
                name="欢迎词与行程说明",
                level="intro",
                prerequisites=["kp_pickup"],
                target_skill="用清晰友好的语言完成欢迎词、团队提醒和当日行程说明。",
            ),
            KnowledgePoint(
                id="kp_scenic",
                name="景点讲解",
                level="basic",
                prerequisites=["kp_welcome"],
                target_skill="面向外国游客讲解景点历史、文化背景和参观动线。",
            ),
            KnowledgePoint(
                id="kp_cross_culture",
                name="跨文化沟通",
                level="basic",
                target_skill="识别文化差异并用尊重、准确、简洁的方式回应游客需求。",
            ),
            KnowledgePoint(
                id="kp_emergency",
                name="突发情况应对",
                level="advanced",
                target_skill="处理证件遗失、身体不适、交通延误等入境游常见突发情况。",
            ),
        ]
        self._evidence = [
            Evidence(
                chunk_id="ev_pickup_flow",
                content="接站流程包括核对团队名单、确认航班到达、举牌迎接、协助行李、清点人数并引导游客上车。",
                source="built-in:inbound-guide/pickup",
                trust_score=0.82,
                knowledge_point_ids=["kp_pickup"],
            ),
            Evidence(
                chunk_id="ev_welcome_script",
                content="欢迎词应先欢迎外国游客来到中国，介绍本人和司机，再说明当天行程、用餐安排、集合时间和安全提醒。",
                source="built-in:inbound-guide/welcome",
                trust_score=0.9,
                knowledge_point_ids=["kp_welcome"],
            ),
            Evidence(
                chunk_id="ev_scenic_intro",
                content="景点讲解要把历史背景、文化含义和参观路线结合起来，避免只堆砌年代和数字。",
                source="built-in:inbound-guide/scenic",
                trust_score=0.78,
                knowledge_point_ids=["kp_scenic"],
            ),
            Evidence(
                chunk_id="ev_cross_culture",
                content="跨文化沟通需要使用礼貌表达，确认游客真实需求，避免使用容易造成误解的本地习惯说法。",
                source="built-in:inbound-guide/cross-culture",
                trust_score=0.86,
                knowledge_point_ids=["kp_cross_culture"],
            ),
            Evidence(
                chunk_id="ev_emergency",
                content="突发情况应对要先安抚游客情绪，再联系领队、旅行社或相关机构，并记录时间、地点和处理结果。",
                source="built-in:inbound-guide/emergency",
                trust_score=0.84,
                knowledge_point_ids=["kp_emergency"],
            ),
        ]
        self._questions = [
            Question(
                question_id="q_welcome_1",
                knowledge_point_id="kp_welcome",
                difficulty="intro",
                prompt="请为刚抵达上海机场的外国游客团队写一段地陪导游欢迎词，并说明当天行程。",
                answer_key="应包含问候、自我介绍、司机介绍、行程说明、集合或安全提醒，并保持亲切清晰。",
                rubric="信息完整、表达得体、行程说明准确、适合外国游客理解。",
                misconception_tags=["missing_itinerary", "unclear_welcome"],
            ),
            Question(
                question_id="q_cross_1",
                knowledge_point_id="kp_cross_culture",
                difficulty="basic",
                prompt="外国游客对餐桌礼仪产生疑问时，地陪导游应如何解释并保持跨文化尊重？",
                answer_key="应先肯定游客提问，再用中性语言解释本地习惯，避免评价对错，并主动确认游客是否需要替代安排。",
                rubric="尊重文化差异、解释准确、回应具体、能继续确认需求。",
                misconception_tags=["stereotype", "dismissive_response"],
            ),
            Question(
                question_id="q_emergency_1",
                knowledge_point_id="kp_emergency",
                difficulty="advanced",
                prompt="一名外国游客发现护照遗失，地陪导游应按什么顺序处理？",
                answer_key="先安抚并确认遗失信息，再通知领队和旅行社，协助报警或联系使领馆，保留记录并调整行程。",
                rubric="顺序合理、协同对象明确、记录完整、兼顾游客情绪和行程安排。",
                misconception_tags=["skip_record", "no_coordination"],
            ),
        ]

    def list_knowledge_points(self) -> list[KnowledgePoint]:
        return list(self._knowledge_points)

    def search(
        self,
        query: str,
        knowledge_point_ids: list[str] | None = None,
        top_k: int = 5,
    ) -> list[Evidence]:
        allowed_ids = set(knowledge_point_ids or [])
        candidates = [
            item
            for item in self._evidence
            if not allowed_ids or allowed_ids.intersection(item.knowledge_point_ids)
        ]
        ranked = [(self._score(query, item), item) for item in candidates]
        matches = [(score, item) for score, item in ranked if score > 0]
        matches.sort(key=lambda pair: (-pair[0], -pair[1].trust_score, pair[1].chunk_id))
        return [item for _, item in matches[: max(top_k, 0)]]

    def questions(self, knowledge_point_ids: list[str] | None = None) -> list[Question]:
        allowed_ids = set(knowledge_point_ids or [])
        return [
            item
            for item in self._questions
            if not allowed_ids or item.knowledge_point_id in allowed_ids
        ]

    def _score(self, query: str, evidence: Evidence) -> int:
        text = evidence.content + " " + " ".join(evidence.knowledge_point_ids)
        tokens = [token for token in query.split() if token]
        token_score = sum(text.count(token) * (len(token) + 1) for token in tokens)
        character_counts = Counter(char for char in query if not char.isspace())
        character_score = sum(text.count(char) * count for char, count in character_counts.items())
        return token_score + character_score
