"""资料存储、解析、分块和可信检索服务。"""

import asyncio
import hashlib
import io
import json
import math
import re
import zipfile
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from xml.etree import ElementTree

from minio import Minio
from pypdf import PdfReader
from sqlalchemy import case, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.api.config import settings
from src.apps.api.dependencies import AsyncSessionLocal
from src.apps.api.logging_config import logger
from src.apps.api.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeIndexVersion,
    SkillRun,
    TaskRun,
    User,
)
from src.apps.api.schemas.workbench import (
    BasisCitation,
    RetrieveBasisInput,
    RetrieveBasisOutput,
)
from src.apps.api.services.project_service import get_owned_project
from src.apps.api.services.retrieval_gateway import (
    SemanticRetrievalError,
    embed_texts,
    rerank,
)

SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf", ".docx"}


def _utcnow() -> datetime:
    """返回与当前 PostgreSQL timestamp 列兼容的 UTC 无时区时间。"""
    return datetime.now(UTC).replace(tzinfo=None)


def checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _minio_client() -> Minio:
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )


def _ensure_bucket(client: Minio) -> None:
    if not client.bucket_exists(settings.MINIO_BUCKET):
        client.make_bucket(settings.MINIO_BUCKET)


async def put_object(object_key: str, data: bytes, content_type: str) -> None:
    def _put() -> None:
        client = _minio_client()
        _ensure_bucket(client)
        client.put_object(
            settings.MINIO_BUCKET,
            object_key,
            io.BytesIO(data),
            len(data),
            content_type=content_type,
        )

    await asyncio.to_thread(_put)


async def get_object(object_key: str) -> bytes:
    def _get() -> bytes:
        response = _minio_client().get_object(settings.MINIO_BUCKET, object_key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    return await asyncio.to_thread(_get)


def _extract_docx(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    paragraphs: list[str] = []
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    for paragraph in root.iter(f"{namespace}p"):
        text = "".join(node.text or "" for node in paragraph.iter(f"{namespace}t"))
        if text.strip():
            paragraphs.append(text.strip())
    return "\n".join(paragraphs)


def _extract_pdf(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(f"[第 {index} 页]\n{text}" for index, text in enumerate(pages, 1))


def extract_text(filename: str, data: bytes) -> str:
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError("仅支持 DOCX、文本型 PDF、Markdown 和 TXT")
    if suffix == ".docx":
        text = _extract_docx(data)
    elif suffix == ".pdf":
        text = _extract_pdf(data)
    else:
        text = data.decode("utf-8-sig")
    normalized = re.sub(r"\r\n?", "\n", text).strip()
    if not normalized:
        raise ValueError("资料中没有可提取的文本；扫描 PDF 暂不支持")
    return normalized


def chunk_text(text: str) -> list[str]:
    size = settings.KNOWLEDGE_CHUNK_SIZE
    overlap = min(settings.KNOWLEDGE_CHUNK_OVERLAP, size // 2)
    paragraphs = [item.strip() for item in re.split(r"\n{2,}", text) if item.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 1 <= size:
            current = f"{current}\n{paragraph}".strip()
            continue
        if current:
            chunks.append(current)
        if len(paragraph) <= size:
            current = paragraph
            continue
        start = 0
        step = max(1, size - overlap)
        while start < len(paragraph):
            chunks.append(paragraph[start : start + size])
            start += step
        current = ""
    if current:
        chunks.append(current)
    return chunks


async def process_document_task(task_id: int, document_id: int) -> None:
    """处理一个资料任务；任务状态存库，应用重启后可恢复。"""
    async with AsyncSessionLocal() as db:
        task = await db.get(TaskRun, task_id)
        document = await db.get(KnowledgeDocument, document_id)
        if task is None or document is None or task.status == "cancelled":
            return
        task.status = "running"
        task.progress = 10
        task.started_at = _utcnow()
        await db.commit()
        try:
            data = await get_object(document.object_key)
            text = await asyncio.to_thread(extract_text, document.filename, data)
            chunks = chunk_text(text)
            await db.refresh(task)
            if task.status == "cancelled":
                return
            await db.execute(
                delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id)
            )
            chunk_rows = [
                KnowledgeChunk(
                    document_id=document.id,
                    chunk_index=index,
                    content=content,
                    location_label=f"分块 {index + 1}",
                )
                for index, content in enumerate(chunks)
            ]
            db.add_all(chunk_rows)
            await db.flush()
            semantic_status = "disabled"
            semantic_error: str | None = None
            if settings.SEMANTIC_RAG_ENABLED:
                index_version: KnowledgeIndexVersion | None = None
                try:
                    index_version = await _create_index_version(db, document.project_id)
                    vectors = await embed_texts([item.content for item in chunk_rows])
                    for chunk_row, vector in zip(chunk_rows, vectors, strict=True):
                        _apply_embedding(chunk_row, vector, index_version.id)
                    index_version.chunk_count = len(chunk_rows)
                    await _activate_index_version(db, index_version)
                    semantic_status = "indexed"
                except SemanticRetrievalError as exc:
                    semantic_status = "degraded"
                    semantic_error = str(exc)[:1000]
                    if index_version is not None:
                        index_version.status = "failed"
                        index_version.error_message = semantic_error
                    logger.warning(
                        "语义索引失败，资料保留词法降级能力",
                        document_id=document.id,
                        error=semantic_error,
                    )
            document.status = "ready"
            document.error_message = None
            task.status = "completed"
            task.progress = 100
            task.output_payload = {
                "document_id": document.id,
                "chunk_count": len(chunks),
                "semantic_status": semantic_status,
                "semantic_error": semantic_error,
            }
            task.finished_at = _utcnow()
            await db.commit()
        except Exception as exc:
            await db.rollback()
            task = await db.get(TaskRun, task_id)
            document = await db.get(KnowledgeDocument, document_id)
            if task is not None:
                task.status = "failed"
                task.error_message = str(exc)[:1000]
                task.finished_at = _utcnow()
            if document is not None:
                document.status = "failed"
                document.error_message = str(exc)[:1000]
            await db.commit()
            logger.exception("资料处理失败", task_id=task_id, document_id=document_id)


async def recover_document_tasks() -> None:
    """启动时恢复未完成的资料任务。"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TaskRun).where(
                TaskRun.task_type == "document_parse",
                TaskRun.status.in_(["queued", "running"]),
            )
        )
        tasks = list(result.scalars())
        for task in tasks:
            document_id = int(task.input_payload["document_id"])
            asyncio.create_task(process_document_task(task.id, document_id))


DEGRADED_RETRIEVAL_MODE = "hybrid_trgm_char_vector"
SEMANTIC_RETRIEVAL_MODE = "hybrid_trgm_pgvector_reranker"
_ILIKE_ESCAPE = "\\"


def _index_config() -> dict:
    return {
        "embedding_model": settings.EMBEDDING_MODEL,
        "embedding_revision": settings.EMBEDDING_REVISION,
        "reranker_model": settings.RERANKER_MODEL,
        "reranker_revision": settings.RERANKER_REVISION,
        "dimensions": settings.EMBEDDING_DIMENSIONS,
    }


async def _create_index_version(
    db: AsyncSession, project_id: int
) -> KnowledgeIndexVersion:
    config = _index_config()
    canonical = json.dumps(config, sort_keys=True, ensure_ascii=False)
    config_hash = hashlib.sha256(canonical.encode()).hexdigest()
    latest_result = await db.execute(
        select(func.max(KnowledgeIndexVersion.version_number)).where(
            KnowledgeIndexVersion.project_id == project_id
        )
    )
    version_number = int(latest_result.scalar() or 0) + 1
    version = KnowledgeIndexVersion(
        project_id=project_id,
        version_number=version_number,
        status="building",
        embedding_model=settings.EMBEDDING_MODEL,
        embedding_revision=settings.EMBEDDING_REVISION,
        reranker_model=settings.RERANKER_MODEL,
        reranker_revision=settings.RERANKER_REVISION,
        dimensions=settings.EMBEDDING_DIMENSIONS,
        config_hash=config_hash,
        chunk_count=0,
    )
    db.add(version)
    await db.flush()
    return version


async def _activate_index_version(
    db: AsyncSession, version: KnowledgeIndexVersion
) -> None:
    """仅在向量已完整写入后原子切换当前有效索引。"""
    await db.execute(
        update(KnowledgeIndexVersion)
        .where(
            KnowledgeIndexVersion.project_id == version.project_id,
            KnowledgeIndexVersion.status == "active",
            KnowledgeIndexVersion.id != version.id,
        )
        .values(status="superseded")
    )
    version.status = "active"
    version.error_message = None
    version.activated_at = _utcnow()


def _apply_embedding(chunk: KnowledgeChunk, vector: list[float], index_version_id: int) -> None:
    chunk.embedding = vector
    chunk.embedding_model = settings.EMBEDDING_MODEL
    chunk.embedding_revision = settings.EMBEDDING_REVISION
    chunk.index_version_id = index_version_id
    chunk.semantic_indexed_at = _utcnow()


async def rebuild_project_index(
    db: AsyncSession, *, project_id: int, user_id: int
) -> KnowledgeIndexVersion:
    """对当前用户项目的已审核资料重建一个新的不可变索引版本。"""
    await get_owned_project(db, project_id, user_id)
    result = await db.execute(
        select(KnowledgeChunk)
        .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
        .where(
            KnowledgeDocument.project_id == project_id,
            KnowledgeDocument.owner_id == user_id,
            KnowledgeDocument.status == "ready",
            KnowledgeDocument.review_status == "approved",
        )
        .order_by(KnowledgeChunk.id)
    )
    chunks = list(result.scalars())
    if not chunks:
        raise ValueError("项目没有可建立语义索引的已审核资料")
    version = await _create_index_version(db, project_id)
    try:
        vectors = await embed_texts([chunk.content for chunk in chunks])
        for chunk, vector in zip(chunks, vectors, strict=True):
            _apply_embedding(chunk, vector, version.id)
        version.chunk_count = len(chunks)
        await _activate_index_version(db, version)
        await db.commit()
        await db.refresh(version)
        return version
    except Exception as exc:
        version.status = "failed"
        version.error_message = str(exc)[:1000]
        await db.commit()
        raise


class SearchResult:
    def __init__(
        self, citations: list[dict], mode: str, degraded_reason: str | None = None
    ) -> None:
        self.citations = citations
        self.mode = mode
        self.degraded_reason = degraded_reason


def _ilike_pattern(query: str) -> str:
    escaped = (
        query.replace(_ILIKE_ESCAPE, _ILIKE_ESCAPE * 2).replace("%", r"\%").replace("_", r"\_")
    )
    return f"%{escaped}%"


async def search_chunks(
    db: AsyncSession,
    *,
    project_id: int,
    user_id: int,
    query: str,
    limit: int,
) -> SearchResult:
    """全文 + pgvector + Reranker；Provider 失败时显式回退字符向量。"""
    score = func.greatest(
        func.word_similarity(query, KnowledgeChunk.content),
        case(
            (
                KnowledgeChunk.content.ilike(_ilike_pattern(query), escape=_ILIKE_ESCAPE),
                0.9,
            ),
            else_=0.0,
        ),
    )
    result = await db.execute(
        select(KnowledgeChunk, KnowledgeDocument, score.label("relevance"))
        .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
        .where(
            KnowledgeDocument.project_id == project_id,
            KnowledgeDocument.owner_id == user_id,
            KnowledgeDocument.status == "ready",
            KnowledgeDocument.review_status == "approved",
        )
        .order_by(score.desc(), KnowledgeChunk.id)
        .limit(settings.RETRIEVE_CANDIDATE_LIMIT)
    )
    lexical_rows = result.tuples().all()
    if settings.SEMANTIC_RAG_ENABLED:
        try:
            semantic = await _semantic_search(
                db,
                project_id=project_id,
                user_id=user_id,
                query=query,
                lexical_rows=lexical_rows,
                limit=limit,
            )
            return SearchResult(semantic, SEMANTIC_RETRIEVAL_MODE)
        except SemanticRetrievalError as exc:
            logger.warning("语义检索降级", project_id=project_id, error=str(exc))
            degraded_reason = str(exc)
    else:
        degraded_reason = "semantic_rag_disabled"

    ranked: list[dict] = []
    for chunk, document, lexical_relevance in lexical_rows:
        vector_relevance = _char_vector_similarity(query, chunk.content)
        relevance = (
            settings.RETRIEVE_LEXICAL_WEIGHT * float(lexical_relevance)
            + settings.RETRIEVE_VECTOR_WEIGHT * vector_relevance
        )
        if relevance < settings.RETRIEVE_MIN_RELEVANCE:
            continue
        ranked.append(
            {
                "document_id": document.id,
                "filename": document.filename,
                "chunk_id": chunk.id,
                "location_label": chunk.location_label,
                "content": chunk.content,
                "relevance": round(relevance, 4),
            }
        )
    ranked.sort(key=lambda item: (-float(item["relevance"]), int(item["chunk_id"])))
    return SearchResult(ranked[:limit], DEGRADED_RETRIEVAL_MODE, degraded_reason)


async def _semantic_search(
    db: AsyncSession,
    *,
    project_id: int,
    user_id: int,
    query: str,
    lexical_rows: Sequence[tuple[KnowledgeChunk, KnowledgeDocument, Any]],
    limit: int,
) -> list[dict]:
    query_vector = (await embed_texts([query]))[0]
    distance = KnowledgeChunk.embedding.cosine_distance(query_vector).label("distance")
    semantic_result = await db.execute(
        select(KnowledgeChunk, KnowledgeDocument, distance)
        .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
        .where(
            KnowledgeDocument.project_id == project_id,
            KnowledgeDocument.owner_id == user_id,
            KnowledgeDocument.status == "ready",
            KnowledgeDocument.review_status == "approved",
            KnowledgeChunk.embedding.is_not(None),
            KnowledgeChunk.embedding_model == settings.EMBEDDING_MODEL,
            KnowledgeChunk.embedding_revision == settings.EMBEDDING_REVISION,
        )
        .order_by(distance, KnowledgeChunk.id)
        .limit(settings.RETRIEVE_CANDIDATE_LIMIT)
    )
    candidates: dict[int, dict] = {}
    for chunk, document, lexical_relevance in lexical_rows:
        candidates[chunk.id] = {
            "chunk": chunk,
            "document": document,
            "lexical": float(lexical_relevance),
            "semantic": 0.0,
        }
    for chunk, document, vector_distance in semantic_result.tuples().all():
        item = candidates.setdefault(
            chunk.id,
            {"chunk": chunk, "document": document, "lexical": 0.0, "semantic": 0.0},
        )
        item["semantic"] = max(0.0, 1.0 - float(vector_distance))
    if not candidates:
        return []
    combined = sorted(
        candidates.values(),
        key=lambda item: (
            -(
                settings.RETRIEVE_LEXICAL_WEIGHT * float(item["lexical"])
                + settings.RETRIEVE_VECTOR_WEIGHT * float(item["semantic"])
            ),
            item["chunk"].id,
        ),
    )[: settings.RERANKER_CANDIDATE_LIMIT]
    reranked = await rerank(query, [item["chunk"].content for item in combined])
    rows: list[dict] = []
    for reranked_item in reranked:
        item = combined[reranked_item.index]
        chunk = item["chunk"]
        document = item["document"]
        relevance = 0.5 * (
            settings.RETRIEVE_LEXICAL_WEIGHT * float(item["lexical"])
            + settings.RETRIEVE_VECTOR_WEIGHT * float(item["semantic"])
        ) + 0.5 * reranked_item.relevance
        if relevance < settings.RETRIEVE_MIN_RELEVANCE:
            continue
        rows.append(
            {
                "document_id": document.id,
                "filename": document.filename,
                "chunk_id": chunk.id,
                "location_label": chunk.location_label,
                "content": chunk.content,
                "relevance": round(relevance, 4),
            }
        )
    return rows[:limit]


def _char_vector(text: str) -> Counter[str]:
    normalized = re.sub(r"\s+", "", text.lower())
    if len(normalized) < 2:
        return Counter(normalized)
    return Counter(normalized[index : index + 2] for index in range(len(normalized) - 1))


def _char_vector_similarity(left: str, right: str) -> float:
    left_vector = _char_vector(left)
    right_vector = _char_vector(right)
    if not left_vector or not right_vector:
        return 0.0
    dot = sum(value * right_vector.get(key, 0) for key, value in left_vector.items())
    left_norm = math.sqrt(sum(value * value for value in left_vector.values()))
    right_norm = math.sqrt(sum(value * value for value in right_vector.values()))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


async def retrieve_basis_handler(
    db: AsyncSession,
    user: User,
    payload: RetrieveBasisInput,
    run: SkillRun,
) -> RetrieveBasisOutput:
    """`skill.retrieve_basis` 执行体：项目权限校验 + 库内可信检索。

    SkillRun 生命周期、输入校验与 Memory 注入审计由 skill_runtime 统一承担。
    """
    await get_owned_project(db, payload.project_id, user.id)
    run.project_id = payload.project_id
    search_result = await search_chunks(
        db,
        project_id=payload.project_id,
        user_id=user.id,
        query=payload.query,
        limit=payload.limit,
    )
    return RetrieveBasisOutput(
        insufficient_basis=not search_result.citations,
        retrieval_mode=search_result.mode,
        citations=[BasisCitation(**citation) for citation in search_result.citations],
    )
