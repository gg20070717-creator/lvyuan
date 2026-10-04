"""Tests for the user memory service."""

import pytest

from brain_of_cloud.services.memory import UserMemoryService
from brain_of_cloud.storage.sqlite import SQLiteStore


@pytest.fixture
def store(tmp_path):
    s = SQLiteStore(tmp_path / "memory.sqlite")
    s.initialize()
    return s


@pytest.fixture
def memory(store):
    return UserMemoryService(store)


def test_add_and_list(memory, store):
    memory.add_memory("u1", "goal", "目标：通过导游资格考试", importance=0.9)
    memory.add_memory("u1", "preference", "偏好：情景演练", importance=0.6)
    mems = memory.list_memories("u1")
    assert len(mems) == 2
    # 按重要性降序
    assert mems[0]["memory_type"] == "goal"
    assert mems[0]["content"] == "目标：通过导游资格考试"


def test_extract_name(memory, store):
    extracted = memory.extract_from_message("u2", "s1", "你好，我叫王小明，我是一名旅游管理专业的学生")
    contents = [e["content"] for e in extracted]
    assert any("王小明" in c for c in contents)
    assert any("旅游管理专业" in c for c in contents)


def test_extract_goal(memory, store):
    extracted = memory.extract_from_message("u3", "s1", "我的目标是拿到导游证，正在备考导游资格考试")
    contents = [e["content"] for e in extracted]
    assert any("导游证" in c for c in contents)
    assert any("备考" in c for c in contents)


def test_extract_dedup(memory, store):
    memory.extract_from_message("u4", "s1", "我叫张三")
    extracted2 = memory.extract_from_message("u4", "s2", "我是张三，又见面了")
    # 张三 已被记住，不应重复
    assert not any("张三" in e["content"] for e in extracted2)


def test_build_user_context(memory, store):
    memory.add_memory("u5", "goal", "目标：一次通过考试", importance=0.9)
    memory.add_memory("u5", "preference", "偏好：错题复盘", importance=0.6)
    ctx = memory.build_user_context("u5", weak_point_titles=["导游服务", "政策法规"])
    assert "目标：一次通过考试" in ctx
    assert "错题复盘" in ctx
    assert "导游服务" in ctx
    assert "学员档案" in ctx


def test_build_user_context_with_profile(memory, store):
    from brain_of_cloud.domain.models import LearnerProfile

    profile = LearnerProfile(
        user_id="u6", background="在职转行考导游",
        target_role="导游资格证", current_level="intro",
        style_preferences={"mode": "实操优先"},
    )
    ctx = memory.build_user_context("u6", profile=profile)
    assert "在职转行考导游" in ctx
    assert "导游资格证" in ctx
    assert "实操优先" in ctx


def test_memories_isolated_per_user(memory, store):
    memory.add_memory("u7", "fact", "我叫A")
    assert memory.list_memories("u8") == []


def test_persist_across_service_instances(store, tmp_path):
    m1 = UserMemoryService(store)
    m1.add_memory("u9", "goal", "目标：通过考试", importance=0.8)
    # 重新实例化（模拟重启）仍能读到
    m2 = UserMemoryService(store)
    assert len(m2.list_memories("u9")) == 1
