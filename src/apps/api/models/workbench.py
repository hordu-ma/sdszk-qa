"""阶段 1A 教学工作台领域模型。"""

from datetime import datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .users import User


class TeachingProject(Base, TimestampMixin):
    """教师拥有的教学成果项目。"""

    __tablename__ = "teaching_projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    stage: Mapped[str] = mapped_column(String(50))
    course_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)

    owner: Mapped["User"] = relationship(back_populates="teaching_projects")
    versions: Mapped[list["ProjectVersion"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    documents: Mapped[list["KnowledgeDocument"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ProjectVersion(Base, TimestampMixin):
    """项目结构化内容的不可变版本快照。"""

    __tablename__ = "project_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "version_number", name="uq_project_version_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("teaching_projects.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int]
    status: Mapped[str] = mapped_column(String(30), default="draft")
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))

    project: Mapped["TeachingProject"] = relationship(back_populates="versions")


class KnowledgeDocument(Base, TimestampMixin):
    """项目内可审核、可追溯的知识资料。"""

    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("teaching_projects.id", ondelete="CASCADE"), index=True
    )
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120))
    object_key: Mapped[str] = mapped_column(String(500), unique=True)
    checksum_sha256: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(30), default="processing", index=True)
    review_status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    version_number: Mapped[int] = mapped_column(default=1)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped["TeachingProject"] = relationship(back_populates="documents")
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class KnowledgeChunk(Base):
    """可定位引用的知识分块。"""

    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk_index"),
        Index(
            "ix_knowledge_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int]
    content: Mapped[str] = mapped_column(Text)
    location_label: Mapped[str] = mapped_column(String(100))
    index_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_index_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(512), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    embedding_revision: Mapped[str | None] = mapped_column(String(64), nullable=True)
    semantic_indexed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default="now()")

    document: Mapped["KnowledgeDocument"] = relationship(back_populates="chunks")


class KnowledgeIndexVersion(Base, TimestampMixin):
    """项目级可追溯知识索引配置版本。"""

    __tablename__ = "knowledge_index_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "version_number", name="uq_knowledge_index_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("teaching_projects.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int]
    status: Mapped[str] = mapped_column(String(30), default="building", index=True)
    embedding_model: Mapped[str] = mapped_column(String(255))
    embedding_revision: Mapped[str] = mapped_column(String(64))
    reranker_model: Mapped[str] = mapped_column(String(255))
    reranker_revision: Mapped[str] = mapped_column(String(64))
    dimensions: Mapped[int]
    config_hash: Mapped[str] = mapped_column(String(64), index=True)
    chunk_count: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(nullable=True)


class TaskRun(Base, TimestampMixin):
    """数据库持久化的异步任务运行记录。"""

    __tablename__ = "task_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("teaching_projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    task_type: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    progress: Mapped[int] = mapped_column(default=0)
    attempt: Mapped[int] = mapped_column(default=1)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    input_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    output_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)


class SkillRun(Base, TimestampMixin):
    """受控产品 Skill 的输入、输出和版本审计（计划 §2.5.1 SkillRun 契约）。"""

    __tablename__ = "skill_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("teaching_projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    skill_id: Mapped[str] = mapped_column(String(100), index=True)
    skill_version: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), index=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    memory_refs: Mapped[list] = mapped_column(JSON, default=list)
    input_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    output_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)


class ModelCallAudit(Base):
    """逻辑模型调用的 Provider 与性能追溯。"""

    __tablename__ = "model_call_audits"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    logical_model: Mapped[str] = mapped_column(String(100), index=True)
    provider: Mapped[str] = mapped_column(String(30))
    provider_model_id: Mapped[str] = mapped_column(String(255))
    operation: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30))
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default="now()", index=True)


class ArtifactExport(Base):
    """由 export_artifact Skill 生成、可鉴权下载的不可变导出件。"""

    __tablename__ = "artifact_exports"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("teaching_projects.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    skill_run_id: Mapped[int] = mapped_column(
        ForeignKey("skill_runs.id", ondelete="RESTRICT"), unique=True, index=True
    )
    version_id: Mapped[int] = mapped_column(
        ForeignKey("project_versions.id", ondelete="RESTRICT"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    object_key: Mapped[str] = mapped_column(String(500), unique=True)
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    template_version: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(server_default="now()", index=True)
