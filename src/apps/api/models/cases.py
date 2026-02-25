"""主题模型（沿用历史表名 cases）。"""

from typing import TYPE_CHECKING

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .sessions import Session


class Case(Base, TimestampMixin):
    """主题表。

    说明：为兼容历史数据与迁移，当前仍沿用 `cases` 表名和部分字段名。
    """

    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True, comment="主题ID")
    title: Mapped[str] = mapped_column(String(200), comment="主题标题")
    difficulty: Mapped[str] = mapped_column(String(20), comment="难度：easy/medium/hard")
    department: Mapped[str] = mapped_column(String(50), comment="学段/方向")

    # 历史字段（语义已迁移为主题上下文）
    patient_info: Mapped[dict] = mapped_column(JSON, comment="背景信息")
    chief_complaint: Mapped[str] = mapped_column(Text, comment="核心诉求")
    present_illness: Mapped[str] = mapped_column(Text, comment="场景说明")
    past_history: Mapped[dict] = mapped_column(JSON, comment="补充背景")
    physical_exam: Mapped[dict] = mapped_column(
        JSON, comment="结构化扩展字段"
    )
    available_tests: Mapped[list] = mapped_column(JSON, comment="扩展字段（当前可为空）")

    # 历史兼容字段
    marriage_childbearing_history: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="婚育个人史"
    )
    family_history: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="家族史"
    )
    case_number: Mapped[int | None] = mapped_column(
        nullable=True, comment="历史序号字段"
    )

    # 内部参考答案（仅教师端可见）
    standard_diagnosis: Mapped[dict] = mapped_column(JSON, comment="内部参考答案")
    key_points: Mapped[list] = mapped_column(JSON, comment="关键教学点列表")
    recommended_tests: Mapped[list | None] = mapped_column(
        JSON, nullable=True, comment="扩展推荐项"
    )

    # 主题来源
    source: Mapped[str] = mapped_column(
        String(20),
        default="fixed",
        comment="主题来源：fixed（内置）/custom（用户自定义）",
    )
    generation_meta: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="生成元信息",
    )

    # 是否启用
    is_active: Mapped[bool] = mapped_column(default=True, comment="是否启用")

    # 关系
    sessions: Mapped[list["Session"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Case(id={self.id}, title={self.title}, difficulty={self.difficulty})>"
