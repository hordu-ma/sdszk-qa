import math

import pytest

from src.apps.api.services.model_asset_service import (
    configured_model_assets,
    release_manifest,
)
from src.apps.api.services.retrieval_gateway import (
    SemanticRetrievalError,
    parse_embedding_response,
    parse_rerank_response,
)


def test_fixed_model_assets_are_reproducible() -> None:
    assets = configured_model_assets()
    assert {item.asset_type for item in assets} == {
        "generation",
        "embedding",
        "reranker",
    }
    assert all(len(item.revision) == 40 for item in assets)
    manifest = release_manifest()
    assert manifest["vllm"]["runtime_version"] == "0.18.0"
    assert manifest["retrieval"]["embedding_dimensions"] == 512
    assert manifest["retrieval"]["embedding_max_tokens"] == 512


def test_embedding_contract_orders_and_normalizes_vectors() -> None:
    first = [1.0] + [0.0] * 511
    second = [0.0, 2.0] + [0.0] * 510
    vectors = parse_embedding_response(
        {
            "data": [
                {"index": 1, "embedding": second},
                {"index": 0, "embedding": first},
            ]
        },
        expected_count=2,
    )
    assert vectors[0] == first
    assert vectors[1][1] == 1.0
    assert math.isclose(sum(value * value for value in vectors[1]), 1.0)


@pytest.mark.parametrize(
    ("body", "expected_message"),
    [
        ({"data": [{"index": 0, "embedding": [1.0]}]}, "维度不匹配"),
        ({"data": []}, "数量不匹配"),
        (
            {
                "data": [
                    {"index": 0, "embedding": [1.0] + [0.0] * 511},
                    {"index": 0, "embedding": [0.0, 1.0] + [0.0] * 510},
                ]
            },
            "索引不完整",
        ),
    ],
)
def test_embedding_contract_rejects_invalid_payloads(
    body: dict, expected_message: str
) -> None:
    with pytest.raises(SemanticRetrievalError, match=expected_message):
        parse_embedding_response(body, expected_count=len(body["data"]) or 1)


def test_rerank_contract_supports_results_and_orders_scores() -> None:
    result = parse_rerank_response(
        {
            "results": [
                {"index": 0, "relevance_score": 0.2},
                {"index": 1, "relevance_score": 0.9},
            ]
        },
        document_count=2,
    )
    assert [item.index for item in result] == [1, 0]


def test_rerank_contract_rejects_incomplete_indexes() -> None:
    with pytest.raises(SemanticRetrievalError, match="索引不完整"):
        parse_rerank_response(
            {"data": [{"index": 0, "score": 0.8}]}, document_count=2
        )
