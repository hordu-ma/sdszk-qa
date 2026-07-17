"""固定模型资产与可版本化工程评测模型。"""

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class ModelAsset(Base, TimestampMixin):
    """可复现的模型与运行时资产登记。"""

    __tablename__ = "model_assets"
    __table_args__ = (
        UniqueConstraint(
            "asset_type",
            "logical_name",
            "revision",
            "runtime_version",
            name="uq_model_asset_identity",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_type: Mapped[str] = mapped_column(String(30), index=True)
    logical_name: Mapped[str] = mapped_column(String(100), index=True)
    provider: Mapped[str] = mapped_column(String(30))
    repository: Mapped[str] = mapped_column(String(255))
    revision: Mapped[str] = mapped_column(String(64))
    served_model_name: Mapped[str] = mapped_column(String(120))
    runtime: Mapped[str] = mapped_column(String(30))
    runtime_version: Mapped[str] = mapped_column(String(30))
    runtime_image: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), default="configured", index=True)
    asset_metadata: Mapped[dict] = mapped_column(JSON, default=dict)


class EvaluationDataset(Base, TimestampMixin):
    """按 key + version 冻结的工程评测数据集。"""

    __tablename__ = "evaluation_datasets"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "dataset_key", "version_number", name="uq_eval_dataset_version"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("teaching_projects.id", ondelete="CASCADE"), index=True
    )
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    dataset_key: Mapped[str] = mapped_column(String(100), index=True)
    version_number: Mapped[int]
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_origin: Mapped[str] = mapped_column(String(30), default="synthetic", index=True)
    review_status: Mapped[str] = mapped_column(
        String(30), default="not_applicable", index=True
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    case_count: Mapped[int] = mapped_column(default=0)
    frozen_at: Mapped[datetime | None] = mapped_column(nullable=True)


class EvaluationCase(Base, TimestampMixin):
    """检索工程评测案例；正式专业金标可后续导入新版本。"""

    __tablename__ = "evaluation_cases"
    __table_args__ = (
        UniqueConstraint("dataset_id", "case_key", name="uq_eval_case_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), index=True
    )
    case_key: Mapped[str] = mapped_column(String(100))
    query: Mapped[str] = mapped_column(Text)
    expected_document_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    expected_insufficient_basis: Mapped[bool] = mapped_column(default=False)
    case_metadata: Mapped[dict] = mapped_column(JSON, default=dict)


class EvaluationRun(Base, TimestampMixin):
    """冻结数据集在特定发布清单下的一次可复现运行。"""

    __tablename__ = "evaluation_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="running", index=True)
    dataset_hash: Mapped[str] = mapped_column(String(64))
    release_manifest: Mapped[dict] = mapped_column(JSON)
    total_cases: Mapped[int] = mapped_column(default=0)
    matched_cases: Mapped[int] = mapped_column(default=0)
    failed_cases: Mapped[int] = mapped_column(default=0)
    error_cases: Mapped[int] = mapped_column(default=0)
    started_at: Mapped[datetime] = mapped_column(server_default="now()")
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)


class EvaluationCaseResult(Base):
    """单案例技术结果，不承载教师或学生评分。"""

    __tablename__ = "evaluation_case_results"
    __table_args__ = (
        UniqueConstraint("run_id", "case_id", name="uq_eval_run_case"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"), index=True
    )
    case_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_cases.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(30), index=True)
    returned_document_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    insufficient_basis: Mapped[bool]
    checks: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default="now()")
