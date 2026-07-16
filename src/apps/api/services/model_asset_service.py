"""固定版本模型资产登记与发布清单。"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.api.config import settings
from src.apps.api.models import ModelAsset


@dataclass(frozen=True)
class ConfiguredModelAsset:
    asset_type: str
    logical_name: str
    repository: str
    revision: str
    served_model_name: str
    metadata: dict


def configured_model_assets() -> list[ConfiguredModelAsset]:
    """返回代码与环境共同冻结的三类工程模型资产。"""
    return [
        ConfiguredModelAsset(
            asset_type="generation",
            logical_name=settings.LLM_LOGICAL_MODEL,
            repository=settings.VLLM_GENERATION_MODEL,
            revision=settings.VLLM_GENERATION_REVISION,
            served_model_name=settings.VLLM_GENERATION_SERVED_NAME,
            metadata={"purpose": "engineering_generation_candidate"},
        ),
        ConfiguredModelAsset(
            asset_type="embedding",
            logical_name="teaching-embedding",
            repository=settings.EMBEDDING_MODEL,
            revision=settings.EMBEDDING_REVISION,
            served_model_name=settings.EMBEDDING_SERVED_NAME,
            metadata={"dimensions": settings.EMBEDDING_DIMENSIONS},
        ),
        ConfiguredModelAsset(
            asset_type="reranker",
            logical_name="teaching-reranker",
            repository=settings.RERANKER_MODEL,
            revision=settings.RERANKER_REVISION,
            served_model_name=settings.RERANKER_SERVED_NAME,
            metadata={"purpose": "engineering_retrieval_candidate"},
        ),
    ]


async def sync_model_assets(db: AsyncSession) -> None:
    """幂等同步固定资产；旧资产保留用于历史追溯。"""
    for configured in configured_model_assets():
        result = await db.execute(
            select(ModelAsset).where(
                ModelAsset.asset_type == configured.asset_type,
                ModelAsset.logical_name == configured.logical_name,
                ModelAsset.revision == configured.revision,
                ModelAsset.runtime_version == settings.VLLM_RUNTIME_VERSION,
            )
        )
        asset = result.scalar_one_or_none()
        status = "candidate"
        if asset is None:
            db.add(
                ModelAsset(
                    asset_type=configured.asset_type,
                    logical_name=configured.logical_name,
                    provider="vllm",
                    repository=configured.repository,
                    revision=configured.revision,
                    served_model_name=configured.served_model_name,
                    runtime="vllm",
                    runtime_version=settings.VLLM_RUNTIME_VERSION,
                    runtime_image=settings.VLLM_RUNTIME_IMAGE,
                    status=status,
                    asset_metadata=configured.metadata,
                )
            )
        else:
            asset.repository = configured.repository
            asset.served_model_name = configured.served_model_name
            asset.runtime_image = settings.VLLM_RUNTIME_IMAGE
            asset.status = status
            asset.asset_metadata = configured.metadata
    await db.commit()


def release_manifest() -> dict:
    """绑定当前应用、模型、检索与 Skill 版本的最小发布清单。"""
    from src.apps.api.services.skill_runtime import SKILL_REGISTRY

    return {
        "application_release": settings.APP_RELEASE,
        "vllm": {
            "runtime_version": settings.VLLM_RUNTIME_VERSION,
            "runtime_image": settings.VLLM_RUNTIME_IMAGE,
        },
        "models": [
            {
                "asset_type": item.asset_type,
                "repository": item.repository,
                "revision": item.revision,
                "served_model_name": item.served_model_name,
            }
            for item in configured_model_assets()
        ],
        "retrieval": {
            "semantic_enabled": settings.SEMANTIC_RAG_ENABLED,
            "embedding_dimensions": settings.EMBEDDING_DIMENSIONS,
            "embedding_max_tokens": settings.EMBEDDING_MAX_TOKENS,
            "lexical_weight": settings.RETRIEVE_LEXICAL_WEIGHT,
            "vector_weight": settings.RETRIEVE_VECTOR_WEIGHT,
        },
        "skills": {
            skill_id: skill.skill_version for skill_id, skill in SKILL_REGISTRY.items()
        },
    }
