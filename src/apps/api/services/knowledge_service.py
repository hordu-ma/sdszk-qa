"""资料存储、解析、分块和可信检索服务。"""

import asyncio
import hashlib
import io
import re
import zipfile
from datetime import UTC, datetime
from xml.etree import ElementTree

from minio import Minio
from pypdf import PdfReader
from sqlalchemy import case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.api.config import settings
from src.apps.api.dependencies import AsyncSessionLocal
from src.apps.api.logging_config import logger
from src.apps.api.models import KnowledgeChunk, KnowledgeDocument, SkillRun, TaskRun, User
from src.apps.api.schemas.workbench import (
    BasisCitation,
    RetrieveBasisInput,
    RetrieveBasisOutput,
)
from src.apps.api.services.project_service import get_owned_project

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
            db.add_all(
                [
                    KnowledgeChunk(
                        document_id=document.id,
                        chunk_index=index,
                        content=content,
                        location_label=f"分块 {index + 1}",
                    )
                    for index, content in enumerate(chunks)
                ]
            )
            document.status = "ready"
            document.error_message = None
            task.status = "completed"
            task.progress = 100
            task.output_payload = {"document_id": document.id, "chunk_count": len(chunks)}
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


RETRIEVAL_MODE = "lexical_trgm"
_ILIKE_ESCAPE = "\\"


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
) -> list[dict]:
    """库内词法检索：pg_trgm 相似度排序 + 子串兜底。

    排序与阈值过滤在 PostgreSQL 内完成；
    2–3 字短查询走 ILIKE 子串兜底；
    向量混合检索待 D0 选型后接入。
    """
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
            score >= settings.RETRIEVE_MIN_RELEVANCE,
        )
        .order_by(score.desc(), KnowledgeChunk.id)
        .limit(limit)
    )
    return [
        {
            "document_id": document.id,
            "filename": document.filename,
            "chunk_id": chunk.id,
            "location_label": chunk.location_label,
            "content": chunk.content,
            "relevance": round(float(relevance), 4),
        }
        for chunk, document, relevance in result.tuples().all()
    ]


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
    citations = await search_chunks(
        db,
        project_id=payload.project_id,
        user_id=user.id,
        query=payload.query,
        limit=payload.limit,
    )
    return RetrieveBasisOutput(
        insufficient_basis=not citations,
        retrieval_mode=RETRIEVAL_MODE,
        citations=[BasisCitation(**citation) for citation in citations],
    )
