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


class MemoryRef(BaseModel):
    """显式 Memory 注入引用；仅用户确认传入的引用可被解析（计划 §2.5.2）。"""

    memory_type: str = Field(pattern="^(user_preference|class_context_profile)$")
    memory_id: int


class RetrieveBasisRequest(BaseModel):
    project_id: int
    query: str = Field(min_length=2, max_length=500)
    limit: int = Field(default=5, ge=1, le=10)
    memory_refs: list[MemoryRef] = Field(default_factory=list, max_length=10)


class BasisCitation(BaseModel):
    document_id: int
    filename: str
    chunk_id: int
    location_label: str
    content: str
    relevance: float


class RetrieveBasisInput(BaseModel):
    """`skill.retrieve_basis` 的输入 Schema（Skill 契约，不含运行时字段）。"""

    project_id: int
    query: str = Field(min_length=2, max_length=500)
    limit: int = Field(default=5, ge=1, le=10)


class RetrieveBasisOutput(BaseModel):
    """`skill.retrieve_basis` 的输出 Schema（Skill 契约）。"""

    insufficient_basis: bool
    retrieval_mode: str
    citations: list[BasisCitation]


class RetrieveBasisResponse(BaseModel):
    skill_run_id: int
    skill_id: str = "skill.retrieve_basis"
    skill_version: str
    insufficient_basis: bool
    retrieval_mode: str
    citations: list[BasisCitation]


class SkillInfo(BaseModel):
    """注册 Skill 的对外描述（运维与工作台可见性）。"""

    skill_id: str
    skill_version: str
    name: str
    status: str
    execution_mode: str
    maturity: str
    required_roles: list[str]
    quota_class: str
    timeout_ms: int
    degradation_policy: str | None


class UserPreferenceUpdate(BaseModel):
    default_stage: str | None = Field(default=None, max_length=50)
    default_course_type: str | None = Field(default=None, max_length=50)
    textbook_version: str | None = Field(default=None, max_length=100)
    export_template: str | None = Field(default=None, max_length=100)
    extra: dict = Field(default_factory=dict)


class UserPreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    default_stage: str | None
    default_course_type: str | None
    textbook_version: str | None
    export_template: str | None
    extra: dict
    updated_at: datetime


class ClassProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    context: dict = Field(default_factory=dict)


class ClassProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    context: dict
    created_at: datetime
    updated_at: datetime


class PinnedItemCreate(BaseModel):
    item_type: str = Field(pattern="^(project|template)$")
    project_id: int | None = None
    name: str = Field(min_length=1, max_length=120)
    payload: dict = Field(default_factory=dict)


class PinnedItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_type: str
    project_id: int | None
    name: str
    payload: dict
    created_at: datetime
    updated_at: datetime


class MemoryExportResponse(BaseModel):
    """个人记忆清单导出（计划 WP1.3c：可导出、可清除）。"""

    preference: UserPreferenceResponse | None
    class_profiles: list[ClassProfileResponse]
    pinned_items: list[PinnedItemResponse] = Field(default_factory=list)


class MemoryClearResponse(BaseModel):
    cleared_preference: bool
    cleared_class_profiles: int
    cleared_pinned_items: int


class AlignmentCardInput(BaseModel):
    project_id: int
    topic: str = Field(min_length=2, max_length=200)
    core_question: str = Field(min_length=2, max_length=500)
    basis_query: str = Field(min_length=2, max_length=500)


class AlignmentCardOutput(BaseModel):
    topic: str
    core_question: str
    objectives: list[str]
    basis_summary: list[str]
    citations: list[BasisCitation]
    warnings: list[str]
    version_number: int


class AlignmentCardRequest(AlignmentCardInput):
    memory_refs: list[MemoryRef] = Field(default_factory=list, max_length=10)


class AlignmentCardResponse(AlignmentCardOutput):
    skill_run_id: int
    skill_id: str = "skill.alignment_card"
    skill_version: str


class DesignBlueprintInput(BaseModel):
    project_id: int
    lesson_minutes: int = Field(default=45, ge=20, le=180)


class DesignBlueprintOutput(BaseModel):
    core_question: str
    objectives: list[str]
    evidence: list[str]
    learning_tasks: list[dict]
    lesson_minutes: int
    version_number: int


class DesignBlueprintRequest(DesignBlueprintInput):
    memory_refs: list[MemoryRef] = Field(default_factory=list, max_length=10)


class DesignBlueprintResponse(DesignBlueprintOutput):
    skill_run_id: int
    skill_id: str = "skill.design_blueprint"
    skill_version: str


class GenerateSectionInput(BaseModel):
    project_id: int
    section_name: str = Field(default="课时设计", min_length=2, max_length=100)
    guidance: str = Field(default="", max_length=1000)


class GenerateSectionOutput(BaseModel):
    section_name: str
    opening: str
    activities: list[dict]
    assessment_evidence: list[str]
    teacher_notes: list[str]
    version_number: int


class GenerateSectionRequest(GenerateSectionInput):
    memory_refs: list[MemoryRef] = Field(default_factory=list, max_length=10)


class GenerateSectionResponse(GenerateSectionOutput):
    skill_run_id: int
    skill_id: str = "skill.generate_section"
    skill_version: str


class DiagnoseArtifactInput(BaseModel):
    project_id: int


class DiagnosisItem(BaseModel):
    dimension: str
    status: str = Field(pattern="^(aligned|needs_attention)$")
    evidence: str
    suggestion: str


class DiagnoseArtifactOutput(BaseModel):
    conclusion: str
    items: list[DiagnosisItem]
    blocking_issues: list[str]
    version_number: int


class DiagnoseArtifactRequest(DiagnoseArtifactInput):
    memory_refs: list[MemoryRef] = Field(default_factory=list, max_length=10)


class DiagnoseArtifactResponse(DiagnoseArtifactOutput):
    skill_run_id: int
    skill_id: str = "skill.diagnose_artifact"
    skill_version: str


class ExportArtifactInput(BaseModel):
    project_id: int
    template_name: str = Field(default="standard-v1", min_length=2, max_length=100)


class ExportArtifactOutput(BaseModel):
    export_id: int
    filename: str
    download_url: str
    template_version: str
    version_number: int


class ExportArtifactRequest(ExportArtifactInput):
    memory_refs: list[MemoryRef] = Field(default_factory=list, max_length=10)


class ExportArtifactResponse(ExportArtifactOutput):
    skill_run_id: int
    skill_id: str = "skill.export_artifact"
    skill_version: str


class VersionDiffSection(BaseModel):
    section: str
    before: object | None
    after: object | None


class VersionDiffResponse(BaseModel):
    project_id: int
    from_version: int
    to_version: int
    changed_sections: list[VersionDiffSection]
