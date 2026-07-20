"""WP2.4 抽检队列模型：SkillRun/诊断产物的双评与仲裁留痕。

抽检结论只回答「诊断输出是否成立」（confirmed / needs_adjustment），
不承载任何教师或学生评分；自助开发模式（§0.5）下复核人为内部代理，
全部记录 signal_level=L4 且 authorized_for_training=false。
"""

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class SpotCheckItem(Base, TimestampMixin):
    """单个被抽入复核队列的 SkillRun 及其证据快照。"""

    __tablename__ = "spot_check_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    skill_run_id: Mapped[int] = mapped_column(
        ForeignKey("skill_runs.id", ondelete="CASCADE"), unique=True, index=True
    )
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("teaching_projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    sampled_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    sample_source: Mapped[str] = mapped_column(String(30), default="random_recent")
    skill_id: Mapped[str] = mapped_column(String(100), index=True)
    skill_version: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    # 抽检时刻的发布清单与 L4 信号声明快照，供复核人对照模型/规则版本
    context_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    resolved_verdict: Mapped[str | None] = mapped_column(String(30), nullable=True)
    resolved_issue_tags: Mapped[list] = mapped_column(JSON, default=list)


class SpotCheckReview(Base):
    """复核人对单个抽检项的独立复核或仲裁记录，独立留痕不互相覆盖。"""

    __tablename__ = "spot_check_reviews"
    __table_args__ = (
        UniqueConstraint(
            "item_id",
            "reviewer_id",
            "review_kind",
            name="uq_spot_check_reviewer_kind",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("spot_check_items.id", ondelete="CASCADE"), index=True
    )
    reviewer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    review_kind: Mapped[str] = mapped_column(String(30), index=True)
    verdict: Mapped[str] = mapped_column(String(30))
    issue_tags: Mapped[list] = mapped_column(JSON, default=list)
    # 分歧仲裁时对规则字典/量规修订的反馈，供后续规则版本迭代引用
    rubric_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default="now()")
