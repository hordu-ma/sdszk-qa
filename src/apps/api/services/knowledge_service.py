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
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from xml.etree import ElementTree

from minio import Minio
from pypdf import PdfReader
from sqlalchemy import case, delete, func, or_, select, update
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

# WP2.5：可执行文件魔数；无论声明何种类型/后缀一律拒绝
_EXECUTABLE_MAGIC = (
    b"MZ",  # Windows PE
    b"\x7fELF",  # Linux ELF
    b"\xfe\xed\xfa\xce",  # Mach-O 32
    b"\xfe\xed\xfa\xcf",  # Mach-O 64
    b"\xcf\xfa\xed\xfe",  # Mach-O 64 (LE)
    b"\xca\xfe\xba\xbe",  # Mach-O fat / Java class
)


class UploadContentError(ValueError):
    """上传内容与声明类型不符或包含被禁止的载荷。"""


def validate_upload_content(filename: str, data: bytes) -> None:
    """按真实内容（魔数/结构）校验上传文件，不信任客户端声明的 MIME。

    - 任何后缀：拒绝可执行文件魔数。
    - .pdf：必须以 %PDF- 开头。
    - .docx：必须是含 [Content_Types].xml 与 word/ 的 ZIP；拒绝宏载荷
      （vbaProject.bin），防止宏文档改名混入。
    - .txt/.md：必须可按 UTF-8 解码且不含 NUL 字节，拒绝伪装文本的二进制。
    """
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    head = data[:8]
    if any(head.startswith(magic) for magic in _EXECUTABLE_MAGIC):
        raise UploadContentError("检测到可执行文件特征，禁止上传")
    if suffix == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise UploadContentError("PDF 内容与后缀不符")
    elif suffix == ".docx":
        if not data.startswith(b"PK"):
            raise UploadContentError("DOCX 内容与后缀不符")
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = set(archive.namelist())
        except zipfile.BadZipFile as exc:
            raise UploadContentError("DOCX 内容与后缀不符") from exc
        if "[Content_Types].xml" not in names or not any(
            name.startswith("word/") for name in names
        ):
            raise UploadContentError("DOCX 缺少必要的文档结构")
        if any(name.lower().endswith("vbaproject.bin") for name in names):
            raise UploadContentError("禁止包含宏代码的文档")
    elif suffix in {".txt", ".md"}:
        if b"\x00" in data:
            raise UploadContentError("文本资料不能包含二进制内容")
        try:
            data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise UploadContentError("文本资料必须是 UTF-8 编码") from exc


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


@dataclass(frozen=True)
class ChunkPiece:
    """带页码/段落定位的分块；页码仅对 PDF 提取结果有值。"""

    content: str
    page_number: int | None
    paragraph_start: int
    paragraph_end: int

    @property
    def location_label(self) -> str:
        paragraphs = (
            f"段 {self.paragraph_start}"
            if self.paragraph_start == self.paragraph_end
            else f"段 {self.paragraph_start}-{self.paragraph_end}"
        )
        if self.page_number is not None:
            return f"第 {self.page_number} 页 · {paragraphs}"
        return paragraphs


_PAGE_MARKER = re.compile(r"^\[第 (\d+) 页\]\s*")


def chunk_document(text: str) -> list[ChunkPiece]:
    """按段落打包分块，同时跟踪 PDF 页码与全文段落序号。"""
    size = settings.KNOWLEDGE_CHUNK_SIZE
    overlap = min(settings.KNOWLEDGE_CHUNK_OVERLAP, size // 2)
    paragraphs: list[tuple[str, int | None, int]] = []
    current_page: int | None = None
    paragraph_no = 0
    for raw in re.split(r"\n{2,}", text):
        item = raw.strip()
        if not item:
            continue
        marker = _PAGE_MARKER.match(item)
        if marker:
            current_page = int(marker.group(1))
            item = item[marker.end() :].strip()
            if not item:
                continue
        paragraph_no += 1
        paragraphs.append((item, current_page, paragraph_no))

    pieces: list[ChunkPiece] = []
    buffer: list[tuple[str, int | None, int]] = []

    def flush() -> None:
        if not buffer:
            return
        pieces.append(
            ChunkPiece(
                content="\n".join(entry[0] for entry in buffer),
                page_number=buffer[0][1],
                paragraph_start=buffer[0][2],
                paragraph_end=buffer[-1][2],
            )
        )
        buffer.clear()

    for content, page, number in paragraphs:
        buffered = sum(len(entry[0]) for entry in buffer) + len(buffer)
        if buffer and (buffered + len(content) + 1 > size or buffer[0][1] != page):
            # 尺寸超限或跨页都切块，保证页码定位不失真
            flush()
        if len(content) <= size:
            buffer.append((content, page, number))
            continue
        flush()
        start = 0
        step = max(1, size - overlap)
        while start < len(content):
            pieces.append(
                ChunkPiece(
                    content=content[start : start + size],
                    page_number=page,
                    paragraph_start=number,
                    paragraph_end=number,
                )
            )
            start += step
    flush()
    return pieces


def chunk_text(text: str) -> list[str]:
    return [piece.content for piece in chunk_document(text)]


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
            pieces = chunk_document(text)
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
                    content=piece.content,
                    location_label=piece.location_label,
                    page_number=piece.page_number,
                    paragraph_start=piece.paragraph_start,
                    paragraph_end=piece.paragraph_end,
                )
                for index, piece in enumerate(pieces)
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
                "chunk_count": len(pieces),
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


def _validity_conditions(now: datetime) -> tuple[Any, Any]:
    """过期或未生效的资料不进入检索（资料有效期策略）。"""
    return (
        or_(KnowledgeDocument.valid_from.is_(None), KnowledgeDocument.valid_from <= now),
        or_(KnowledgeDocument.valid_until.is_(None), KnowledgeDocument.valid_until >= now),
    )


def _citation_row(chunk: KnowledgeChunk, document: KnowledgeDocument, relevance: float) -> dict:
    return {
        "document_id": document.id,
        "filename": document.filename,
        "chunk_id": chunk.id,
        "location_label": chunk.location_label,
        "page_number": chunk.page_number,
        "paragraph_start": chunk.paragraph_start,
        "paragraph_end": chunk.paragraph_end,
        "content": chunk.content,
        "relevance": round(relevance, 4),
    }


def assess_insufficiency(citations: list[dict]) -> tuple[bool, str | None]:
    """资料不足策略：没有候选，或最高相关度低于阈值，都视为资料不足。

    低于阈值时仍返回候选内容，由界面明示为低置信参考，不冒充可靠依据。
    """
    if not citations:
        return True, "no_candidates"
    if float(citations[0]["relevance"]) < settings.RETRIEVE_INSUFFICIENT_TOP_RELEVANCE:
        return True, "low_relevance"
    return False, None


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
    now = _utcnow()
    result = await db.execute(
        select(KnowledgeChunk, KnowledgeDocument, score.label("relevance"))
        .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
        .where(
            KnowledgeDocument.project_id == project_id,
            KnowledgeDocument.owner_id == user_id,
            KnowledgeDocument.status == "ready",
            KnowledgeDocument.review_status == "approved",
            *_validity_conditions(now),
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
        ranked.append(_citation_row(chunk, document, relevance))
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
            *_validity_conditions(_utcnow()),
            KnowledgeChunk.embedding.is_not(None),
            KnowledgeChunk.embedding_model == settings.EMBEDDING_MODEL,
            KnowledgeChunk.embedding_revision == settings.EMBEDDING_REVISION,
        )
        .order_by(distance, KnowledgeChunk.id)
        .limit(settings.RETRIEVE_CANDIDATE_LIMIT)
    )
    semantic_rows = semantic_result.tuples().all()
    if lexical_rows and not semantic_rows:
        # 项目内没有任何符合当前模型/revision 的语义向量：pgvector 零贡献，
        # 不得以语义模式返回结果，必须显式走降级链。
        raise SemanticRetrievalError(
            "项目缺少当前模型版本的语义索引（semantic_index_missing），请重建知识索引"
        )
    candidates: dict[int, dict] = {}
    for chunk, document, lexical_relevance in lexical_rows:
        candidates[chunk.id] = {
            "chunk": chunk,
            "document": document,
            "lexical": float(lexical_relevance),
            "semantic": 0.0,
        }
    for chunk, document, vector_distance in semantic_rows:
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
        relevance = 0.5 * (
            settings.RETRIEVE_LEXICAL_WEIGHT * float(item["lexical"])
            + settings.RETRIEVE_VECTOR_WEIGHT * float(item["semantic"])
        ) + 0.5 * reranked_item.relevance
        if relevance < settings.RETRIEVE_MIN_RELEVANCE:
            continue
        rows.append(_citation_row(item["chunk"], item["document"], relevance))
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
    insufficient, reason = assess_insufficiency(search_result.citations)
    return RetrieveBasisOutput(
        insufficient_basis=insufficient,
        insufficiency_reason=reason,
        retrieval_mode=search_result.mode,
        citations=[BasisCitation(**citation) for citation in search_result.citations],
    )
