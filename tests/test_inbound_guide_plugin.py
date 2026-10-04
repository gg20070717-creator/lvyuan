from brain_of_cloud.domain.models import Evidence, KnowledgePoint, Question
from brain_of_cloud.plugins import InboundGuidePlugin


def test_manifest_and_knowledge_points_cover_inbound_guide_training():
    plugin = InboundGuidePlugin()

    assert plugin.manifest["plugin_id"] == "inbound_tour_local_guide"
    assert plugin.manifest["name"]
    assert plugin.manifest["version"]
    assert plugin.manifest["training_provider"]
    assert plugin.manifest["supported_assets"]

    knowledge_points = plugin.list_knowledge_points()
    assert all(isinstance(point, KnowledgePoint) for point in knowledge_points)
    by_id = {point.id: point for point in knowledge_points}
    assert set(by_id) == {
        "kp_pickup",
        "kp_welcome",
        "kp_scenic",
        "kp_cross_culture",
        "kp_emergency",
    }
    assert {point.name for point in knowledge_points} == {
        "接站流程",
        "欢迎词与行程说明",
        "景点讲解",
        "跨文化沟通",
        "突发情况应对",
    }


def test_search_ranks_welcome_script_evidence_for_chinese_query():
    plugin = InboundGuidePlugin()

    results = plugin.search("欢迎词 行程", top_k=2)

    assert 0 < len(results) <= 2
    assert all(isinstance(item, Evidence) for item in results)
    assert all(item.trust_score > 0 for item in results)
    assert results[0].chunk_id == "ev_welcome_script"
    assert results[0].knowledge_point_ids == ["kp_welcome"]
    assert "欢迎词" in results[0].content


def test_search_filters_by_knowledge_point_ids():
    plugin = InboundGuidePlugin()

    results = plugin.search(
        "游客 沟通 应对",
        knowledge_point_ids=["kp_cross_culture"],
        top_k=5,
    )

    assert results
    assert all("kp_cross_culture" in item.knowledge_point_ids for item in results)
    assert all("kp_emergency" not in item.knowledge_point_ids for item in results)


def test_questions_include_required_items_and_filter_by_knowledge_point():
    plugin = InboundGuidePlugin()

    questions = plugin.questions()
    assert all(isinstance(item, Question) for item in questions)
    question_ids = {item.question_id for item in questions}
    assert {"q_welcome_1", "q_cross_1"}.issubset(question_ids)

    welcome = plugin.questions(["kp_welcome"])
    assert [item.question_id for item in welcome] == ["q_welcome_1"]
    assert welcome[0].difficulty == "intro"

    cross_culture = plugin.questions(["kp_cross_culture"])
    assert [item.question_id for item in cross_culture] == ["q_cross_1"]
    assert cross_culture[0].difficulty == "basic"
