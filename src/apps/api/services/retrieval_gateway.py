"""Embedding 与 Reranker 的可替换 HTTP Provider Adapter。"""

import math
from dataclasses import dataclass

import httpx

from src.apps.api.config import settings


class SemanticRetrievalError(Exception):
    """语义检索 Provider 不可用或返回无效契约。"""


@dataclass(frozen=True)
class RerankedItem:
    index: int
    relevance: float


def _normalize(vector: list[float]) -> list[float]:
    if len(vector) != settings.EMBEDDING_DIMENSIONS:
        raise SemanticRetrievalError(
            f"Embedding 维度不匹配: expected={settings.EMBEDDING_DIMENSIONS}, got={len(vector)}"
        )
    norm = math.sqrt(sum(value * value for value in vector))
    if not norm:
        raise SemanticRetrievalError("Embedding 返回零向量")
    return [value / norm for value in vector]


def parse_embedding_response(body: dict, expected_count: int) -> list[list[float]]:
    """校验并标准化 OpenAI-compatible Embeddings 响应。"""
    data = body.get("data", [])
    if len(data) != expected_count:
        raise SemanticRetrievalError("Embedding Provider 返回数量不匹配")
    try:
        indexes = [int(item["index"]) for item in data]
        if set(indexes) != set(range(expected_count)) or len(indexes) != expected_count:
            raise SemanticRetrievalError("Embedding Provider 返回索引不完整")
        ordered = sorted(data, key=lambda item: int(item["index"]))
        vectors = [
            _normalize([float(value) for value in item["embedding"]]) for item in ordered
        ]
    except SemanticRetrievalError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise SemanticRetrievalError("Embedding Provider 返回格式无效") from exc
    return vectors


def parse_rerank_response(body: dict, document_count: int) -> list[RerankedItem]:
    """兼容并校验 vLLM rerank 的 results/data 两种响应字段。"""
    items = body.get("results") or body.get("data") or []
    try:
        reranked = [
            RerankedItem(
                index=int(item["index"]),
                relevance=float(item.get("relevance_score", item.get("score", 0.0))),
            )
            for item in items
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise SemanticRetrievalError("Reranker Provider 返回格式无效") from exc
    if {item.index for item in reranked} != set(range(document_count)):
        raise SemanticRetrievalError("Reranker Provider 返回索引不完整")
    return sorted(reranked, key=lambda item: (-item.relevance, item.index))


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """调用 vLLM OpenAI-compatible Embeddings API。"""
    if not texts:
        return []
    payload = {
        "model": settings.EMBEDDING_SERVED_NAME,
        "input": texts,
        "truncate_prompt_tokens": settings.EMBEDDING_MAX_TOKENS,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.EMBEDDING_TIMEOUT) as client:
            response = await client.post(
                f"{settings.EMBEDDING_BASE_URL.rstrip('/')}/v1/embeddings", json=payload
            )
            response.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        raise SemanticRetrievalError(f"Embedding Provider 调用失败: {exc}") from exc
    return parse_embedding_response(response.json(), len(texts))


async def rerank(query: str, documents: list[str]) -> list[RerankedItem]:
    """调用 vLLM Jina-compatible rerank API。"""
    if not documents:
        return []
    payload = {
        "model": settings.RERANKER_SERVED_NAME,
        "query": query,
        "documents": documents,
        "top_n": len(documents),
    }
    try:
        async with httpx.AsyncClient(timeout=settings.RERANKER_TIMEOUT) as client:
            response = await client.post(
                f"{settings.RERANKER_BASE_URL.rstrip('/')}/v1/rerank", json=payload
            )
            response.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        raise SemanticRetrievalError(f"Reranker Provider 调用失败: {exc}") from exc
    return parse_rerank_response(response.json(), len(documents))
