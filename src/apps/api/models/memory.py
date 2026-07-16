"""核心用户 Memory 最小集模型（开发计划 §2.5.2 / WP1.3c）。

Memory 是用户显式管理、可删除、可审计的教学工作记忆。
禁止：思想侧写、能力评级、绩效画像和未确认的自动注入。
"""

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class UserPreference(Base, TimestampMixin):
    """L1 账户偏好：可自动带入，界面可改（每用户一条）。"""

    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    default_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    default_course_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    textbook_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    export_template: Mapped[str | None] = mapped_column(String(100), nullable=True)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)


class ClassContextProfile(Base, TimestampMixin):
    """L2 命名班情档案：用户录入、可删，注入前必须确认。"""

    __tablename__ = "class_context_profiles"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_class_profile_user_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    # 班额、设备、已知差异等用户自述内容；系统不推断、不补全
    context: Mapped[dict] = mapped_column(JSON, default=dict)


class MemoryInjectionAudit(Base):
    """记录谁在何时把哪条记忆注入哪次 SkillRun（计划 §2.5.2 必备对象）。

    审计行保留注入时刻的内容快照；记忆本体被删除后，
    历史审计仍可追溯，但新 SkillRun 无法再解析已删引用。
    """

    __tablename__ = "memory_injection_audits"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    skill_run_id: Mapped[int] = mapped_column(
        ForeignKey("skill_runs.id", ondelete="CASCADE"), index=True
    )
    memory_type: Mapped[str] = mapped_column(String(50))
    memory_id: Mapped[int] = mapped_column()
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default="now()", index=True)


class PinnedMemoryItem(Base, TimestampMixin):
    """用户显式钉选的项目或模板；只作为可管理工作记忆。"""

    __tablename__ = "pinned_memory_items"
    __table_args__ = (
        UniqueConstraint("user_id", "item_type", "name", name="uq_pinned_item_user_type_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    item_type: Mapped[str] = mapped_column(String(30))
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("teaching_projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
