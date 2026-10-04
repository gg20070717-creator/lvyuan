from __future__ import annotations

import json
from dataclasses import dataclass

from brain_of_cloud.domain.models import AgentConfig, AgentId, Evidence
from brain_of_cloud.llm.client import LLMClient
from brain_of_cloud.plugins import InboundGuidePlugin
from brain_of_cloud.services.agents.base import BaseAgent


@dataclass(frozen=True)
class RetrievalResult:
    query: str
    evidence: list[Evidence]


RETRIEVAL_SYSTEM_PROMPT = """\
你是入境游地陪导游训练系统的知识检索与证据排序专家。

任务：根据用户查询，对提供的证据片段进行相关性排序。过滤掉明显无关的证据。
对保留的每个证据片段，给出简要的相关性说明。

输出严格JSON格式：
{"ranked_evidence": [{"chunk_id": "...", "relevance_reason": "...", "relevance_score": 0.0-1.0}]}

只保留有相关性的证据（score > 0）。按relevance_score降序排列。不要修改证据内容。"""


class RetrievalAgent(BaseAgent):
    agent_id = AgentId.RETRIEVAL

    def __init__(
        self,
        plugin: InboundGuidePlugin,
        llm_client: LLMClient,
        config: AgentConfig | None = None,
    ) -> None:
        super().__init__(llm_client, config)
        self._plugin = plugin

    def run(
        self,
        query: str,
        knowledge_point_ids: list[str] | None = None,
        top_k: int = 5,
    ) -> RetrievalResult:
        raw_evidence = self._plugin.search(
            query=query,
            knowledge_point_ids=knowledge_point_ids or [],
            top_k=max(top_k, 3),
        )

        if not raw_evidence:
            return RetrievalResult(query=query, evidence=[])

        evidence_list = [
            {
                "chunk_id": item.chunk_id,
                "content": item.content,
                "source": item.source,
                "trust_score": item.trust_score,
                "knowledge_point_ids": item.knowledge_point_ids,
            }
            for item in raw_evidence
        ]

        user_prompt = (
            f"用户查询: {query}\n\n"
            f"待排序证据片段:\n{json.dumps(evidence_list, ensure_ascii=False, indent=2)}"
        )

        try:
            result = self._call_llm_json(
                RETRIEVAL_SYSTEM_PROMPT + "\n\n只输出合法JSON，不要其他内容。",
                user_prompt,
            )
            ranked = result.get("ranked_evidence", [])
        except Exception:
            # LLM rerank 失败（不可用/解析异常）→ 静默降级为原始检索结果，不让检索整体失败
            return RetrievalResult(query=query, evidence=raw_evidence[:top_k])

        ranked_ids = {item["chunk_id"] for item in ranked}
        evidence_by_id = {item.chunk_id: item for item in raw_evidence}
        ranked_evidence = [
            evidence_by_id[chunk_id]
            for chunk_id in ranked_ids
            if chunk_id in evidence_by_id
        ]
        remaining = [
            item for item in raw_evidence if item.chunk_id not in ranked_ids
        ]
        result = (ranked_evidence + remaining)[:top_k]
        return RetrievalResult(query=query, evidence=result)
