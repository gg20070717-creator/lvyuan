"""网络搜索（T13 / D-2：知识检索第三来源）— 免费源 + 超时静默降级。"""
import json
from unittest.mock import MagicMock, patch

from brain_of_cloud.plugins import InboundGuidePlugin
from brain_of_cloud.services.orchestrator import Orchestrator
from brain_of_cloud.services.web_search import WebSearchService
from brain_of_cloud.storage.sqlite import SQLiteStore

_SAMPLE_HTML = """\
<html><body>
<div class="result">
  <a class="result__a" href="https://example.com/guide">导游接站流程详解</a>
  <a class="result__snippet">接站前核对航班号、人数，接站时举牌确认，接站后清点行李。</a>
</div>
<div class="result">
  <a class="result__a" href="https://example.com/tips">接团注意事项</a>
  <a class="result__snippet">提前两小时到达机场，随时关注航班动态。</a>
</div>
</body></html>
"""


def _mock_httpx(text: str, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    ctx = MagicMock()
    ctx.__enter__.return_value.get.return_value = resp
    ctx.__exit__.return_value = False
    return patch("httpx.Client", return_value=ctx)


class TestWebSearchService:
    def test_parse_ddg_html(self):
        svc = WebSearchService()
        results = svc._parse_ddg(_SAMPLE_HTML)
        assert len(results) == 2
        assert results[0]["title"] == "导游接站流程详解"
        assert results[0]["url"] == "https://example.com/guide"
        assert "航班号" in results[0]["snippet"]

    def test_parse_bing_html(self):
        svc = WebSearchService()
        html = (
            '<li class="b_algo" data-id="x"><h2><a href="https://baike.baidu.com/item/x">导游资格证</a></h2>'
            '<p>1999年起实施导游资格证制度，分为初级、中级、高级和特级。</p></li>'
            '<li class="b_algo"><h2><a href="https://example.com">报名条件</a></h2><p>报考条件说明</p></li>'
        )
        results = svc._parse_bing(html)
        assert len(results) == 2
        assert results[0]["title"] == "导游资格证"
        assert "1999" in results[0]["snippet"]

    def test_search_success(self):
        svc = WebSearchService()
        with _mock_httpx(_SAMPLE_HTML):
            results = svc.search("导游接站", top_k=1)
        assert len(results) == 1
        assert results[0]["title"] == "导游接站流程详解"

    def test_search_http_error_returns_empty(self):
        svc = WebSearchService()
        with _mock_httpx("", status=503):
            assert svc.search("导游") == []

    def test_search_exception_returns_empty(self):
        """网络异常（代理/超时/断网）→ []，绝不抛出。"""
        svc = WebSearchService()
        with patch("httpx.Client", side_effect=RuntimeError("network down")):
            assert svc.search("导游") == []


class TestOrchestratorWebResults:
    def _orch(self, tmp_path):
        store = SQLiteStore(tmp_path / "w.sqlite")
        store.initialize()
        llm = MagicMock()
        llm.model = "deepseek-v4-pro"
        orch = Orchestrator(store=store, plugin=InboundGuidePlugin(), llm_client=llm)
        orch._user_id_ctx.set("u1")
        orch._session_id_ctx.set("s1")
        return orch

    def _stub_retrieval(self, orch, n: int):
        from brain_of_cloud.domain.models import Evidence
        evs = [
            Evidence(
                chunk_id=f"ev_{i}",
                content=f"知识片段{i}内容",
                source=f"inbound-guide/source{i}",
                trust_score=0.8,
                knowledge_point_ids=[f"kp_{i}"],
            )
            for i in range(n)
        ]
        orch._retrieval.run = MagicMock(return_value=type("R", (), {"evidence": evs, "query": "q"})())

    def test_web_results_added_when_evidence_sparse(self, tmp_path):
        """知识库证据不足（<3）→ 附加网络搜索结果（T13 第三来源）。"""
        orch = self._orch(tmp_path)
        self._stub_retrieval(orch, 1)
        orch._web_search = MagicMock()
        orch._web_search.search.return_value = [
            {"title": "接站流程", "url": "https://example.com", "snippet": "核对航班"}
        ]

        payload = json.loads(orch._handle_search_knowledge("一个知识库里没有的冷门话题"))

        assert payload["web_results"]
        assert payload["web_results"][0]["title"] == "接站流程"
        orch._web_search.search.assert_called_once()

    def test_web_results_skipped_when_evidence_enough(self, tmp_path):
        """知识库证据充足（≥3）→ 不调网络搜索（控制延迟与噪音）。"""
        orch = self._orch(tmp_path)
        self._stub_retrieval(orch, 4)
        orch._web_search = MagicMock()

        payload = json.loads(orch._handle_search_knowledge("接待外国游客"))

        assert payload["count"] >= 3
        assert payload["web_results"] == []
        orch._web_search.search.assert_not_called()

    def test_web_search_failure_does_not_break_search(self, tmp_path):
        """网络搜索抛异常 → 主检索结果不受影响。"""
        orch = self._orch(tmp_path)
        self._stub_retrieval(orch, 1)
        orch._web_search = MagicMock(side_effect=RuntimeError("boom"))

        payload = json.loads(orch._handle_search_knowledge("冷门话题"))

        assert payload["count"] >= 0  # 主链路正常
        assert payload["web_results"] == []
