"""基于 HTTP API 的 Rerank 实现。

请求体形如 {"model", "query", "documents", "top_n"}，
返回 {"results": [{"index", "relevance_score"}]}，
兼容 SiliconFlow / Jina / Cohere 等 rerank 服务。
"""
import httpx

from app.providers.rerank.base import RerankProvider


class ApiReranker(RerankProvider):
    """调用 rerank HTTP API 的 RerankProvider 实现。

    Attributes:
        url: rerank 服务地址（如 https://api.siliconflow.cn/v1/rerank）。
        api_key: Bearer 鉴权用 API key。
        model: rerank 模型名（如 BAAI/bge-reranker-v2-m3）。
        timeout: 请求超时秒数。
    """

    def __init__(self, url: str, api_key: str, model: str, timeout: int = 30):
        self.url = url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def rerank(self, query: str, documents: list[str], top_n: int) -> list[tuple[int, float]]:
        """调用 rerank API，按 relevance_score 降序返回 (原索引, 分数)，截断到 top_n。"""
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            resp = await c.post(self.url, headers={"Authorization": f"Bearer {self.api_key}"}, json={
                "model": self.model,
                "query": query,
                "documents": documents,
                "top_n": top_n,
            })
            resp.raise_for_status()
            data = resp.json()
        results = data.get("results", [])
        ranked = sorted(
            [(r["index"], float(r["relevance_score"])) for r in results],
            key=lambda x: x[1], reverse=True,
        )
        return ranked[:top_n]
