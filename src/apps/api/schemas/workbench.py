"""阶段 1A 工作台 API Schema。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    stage: str = Field(min_length=1, max_length=50)
    course_type: str = Field(min_length=1, max_length=50)


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    stage: str
    course_type: str
    status: str
    created_at: datetime
    updated_at: datetime


class ProjectVersionCreate(BaseModel):
    content: dict = Field(default_factory=dict)
    status: str = Field(default="draft", pattern="^(draft|pending_confirmation|completed)$")


class ProjectVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    version_number: int
    status: str
    content: dict
    created_by: int
    created_at: datetime


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    filename: str
    content_type: str
    checksum_sha256: str
    status: str
    review_status: str
    version_number: int
    error_message: str | None
    created_at: datetime


class DocumentReviewRequest(BaseModel):
    review_status: str = Field(pattern="^(approved|rejected|disabled)$")


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int | None
    task_type: str
    status: str
    progress: int
    attempt: int
    input_payload: dict
    output_payload: dict | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class UploadAccepted(BaseModel):
    document: DocumentResponse
    task: TaskResponse


class RetrieveBasisRequest(BaseModel):
    project_id: int
    query: str = Field(min_length=2, max_length=500)
    limit: int = Field(default=5, ge=1, le=10)


class BasisCitation(BaseModel):
    document_id: int
    filename: str
    chunk_id: int
    location_label: str
    content: str
    relevance: float


class RetrieveBasisResponse(BaseModel):
    skill_run_id: int
    skill_id: str = "skill.retrieve_basis"
    skill_version: str = "1.0.0"
    insufficient_basis: bool
    citations: list[BasisCitation]
