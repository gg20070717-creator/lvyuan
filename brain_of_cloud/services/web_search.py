"""网络搜索服务（T13 / D-2：知识检索第三来源）— 免费源 + 超时降级。

多源 fallback：DuckDuckGo HTML → Bing 搜索（cn.bing.com）。
任何失败（网络不可用/反爬/超时）都返回空列表，绝不拖垮主检索链路。
"""

from __future__ import annotations

import re
from html import unescape
from typing import Any

import httpx

_DDG_URL = "https://html.duckduckgo.com/html/"
_BING_URL = "https://www.bing.com/search"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class WebSearchService:
    def __init__(self, timeout: float = 5.0, top_k: int = 3) -> None:
        self._timeout = timeout
        self._top_k = top_k

    def search(self, query: str, top_k: int | None = None) -> list[dict[str, Any]]:
        """搜索返回 [{title, url, snippet}]；任何异常返回 []（静默降级）。"""
        k = top_k or self._top_k
        for url, parser in ((_DDG_URL, self._parse_ddg), (_BING_URL, self._parse_bing)):
            try:
                with httpx.Client(
                    timeout=self._timeout,
                    trust_env=False,  # 避开环境代理 502（本机已知问题）
                    headers={"User-Agent": _UA},
                    follow_redirects=True,
                ) as client:
                    resp = client.get(url, params={"q": query})
                if resp.status_code != 200:
                    continue
                results = parser(resp.text)
                if results:
                    return results[:k]
            except Exception:
                continue
        return []

    def _parse_ddg(self, html_text: str) -> list[dict[str, Any]]:
        """解析 DuckDuckGo HTML 结果：result__a 标题链接 + result__snippet 摘要。"""
        results: list[dict[str, Any]] = []
        blocks = re.split(r'class="result\b', html_text)[1:]
        for block in blocks:
            m = re.search(r'result__a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
            if not m:
                continue
            url = m.group(1)
            title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            snippet = ""
            s = re.search(r'result__snippet[^>]*>(.*?)</a>', block, re.S)
            if s:
                snippet = re.sub(r"<[^>]+>", "", s.group(1)).strip()
            if not title:
                continue
            results.append({
                "title": unescape(title)[:120],
                "url": url[:300],
                "snippet": unescape(snippet)[:200],
            })
        return results

    def _parse_bing(self, html_text: str) -> list[dict[str, Any]]:
        """解析 Bing 结果：li.b_algo 块内 h2 a 标题 + p 摘要。"""
        results: list[dict[str, Any]] = []
        blocks = re.split(r'<li class="b_algo"', html_text)[1:]
        for block in blocks:
            t = re.search(r'<h2[^>]*><a[^>]*href="([^"]+)"[^>]*>(.*?)</a></h2>', block, re.S)
            if not t:
                continue
            url = t.group(1)
            title = re.sub(r"<[^>]+>", "", t.group(2)).strip()
            p = re.search(r"<p[^>]*>(.*?)</p>", block, re.S)
            snippet = re.sub(r"<[^>]+>", "", p.group(1)).strip() if p else ""
            if not title:
                continue
            results.append({
                "title": unescape(title)[:120],
                "url": url[:300],
                "snippet": unescape(snippet)[:200],
            })
        return results
