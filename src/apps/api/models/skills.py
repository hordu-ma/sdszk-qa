"""产品 Skill 注册表模型（开发计划 §2.5.1 SkillDefinition 契约）。"""

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class SkillDefinition(Base, TimestampMixin):
    """版本化的受控产品 Skill 定义。

    代码内注册表是阶段 1A 的事实来源；本表提供运维可见性、
    审计定位和 status 停用开关。字段对齐开发计划 §2.5.1。
    """

    __tablename__ = "skill_definitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    skill_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    skill_version: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(100))
    owner: Mapped[str] = mapped_column(String(100), default="luyun-platform")
    status: Mapped[str] = mapped_column(String(20), default="enabled", index=True)
    execution_mode: Mapped[str] = mapped_column(String(10), default="sync")
    # 阶段 1B 前未达到独立产品成熟度的 Skill 只登记契约，不对外承诺（计划 §10.3）
    maturity: Mapped[str] = mapped_column(String(30), default="baseline")
    input_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    output_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    required_roles: Mapped[list] = mapped_column(JSON, default=list)
    quota_class: Mapped[str] = mapped_column(String(30), default="standard")
    timeout_ms: Mapped[int] = mapped_column(default=30_000)
    max_retries: Mapped[int] = mapped_column(default=0)
    model_logic_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rule_set_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    knowledge_scope: Mapped[str | None] = mapped_column(String(100), nullable=True)
    degradation_policy: Mapped[str | None] = mapped_column(String(100), nullable=True)
    audit_level: Mapped[str] = mapped_column(String(20), default="full")
