"""主题相关的 Pydantic schemas。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CaseListItem(BaseModel):
    """主题列表项（不含敏感信息）。"""

    id: int = Field(..., description="主题ID")
    title: str = Field(..., description="主题标题")
    difficulty: str = Field(..., description="难度：easy/medium/hard")
    department: str = Field(..., description="学段/方向")
    is_active: bool = Field(..., description="是否启用")
    created_at: datetime = Field(..., description="创建时间")

    class Config:
        """Pydantic 配置。"""

        from_attributes = True


class CaseDetail(BaseModel):
    """主题详情（基础视图，不含内部参考答案）。"""

    id: int = Field(..., description="主题ID")
    title: str = Field(..., description="主题标题")
    difficulty: str = Field(..., description="难度")
    department: str = Field(..., description="学段/方向")
    patient_info: dict[str, Any] = Field(..., description="背景信息")
    chief_complaint: str = Field(..., description="核心诉求")
    present_illness: str = Field(..., description="应用场景说明")
    past_history: dict[str, Any] = Field(..., description="补充背景")
    physical_exam: dict[str, Any] = Field(..., description="结构化扩展字段")
    available_tests: list[dict[str, Any]] = Field(..., description="扩展字段（当前可为空）")

    class Config:
        """Pydantic 配置。"""

        from_attributes = True


class CaseDetailFull(CaseDetail):
    """主题完整详情（教师端，含内部参考答案）。"""

    standard_diagnosis: dict[str, Any] = Field(..., description="内部参考答案")
    key_points: list[str] = Field(..., description="关键教学点")
    recommended_tests: list[str] | None = Field(None, description="扩展推荐项")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
