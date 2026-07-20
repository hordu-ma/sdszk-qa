"""阶段 1A 工作台 API Schema。"""

from datetime import datetime
from typing import Literal

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
    source_version: int = Field(ge=1)


class ProjectVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    version_number: int
    status: str
    content: dict
    created_by: int
    created_at: datetime


class ProjectVersionLockUpdate(BaseModel):
    source_version: int = Field(ge=1)
    locked_paths: list[str] = Field(default_factory=list, max_length=50)


class ProjectVersionRestore(BaseModel):
    source_version: int = Field(ge=1)
    restore_version: int = Field(ge=1)


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
    valid_from: datetime | None = None
    valid_until: datetime | None = None
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


class ProfessionalInputConflict(BaseModel):
    conflict_id: str
    severity: Literal["blocking", "needs_confirmation"]
    field: str
    message: str
    resolution: str


class ProfessionalInputInput(BaseModel):
    project_id: int
    topic: str = Field(min_length=2, max_length=200)
    core_question: str = Field(min_length=2, max_length=500)
    basis_query: str = Field(default="", max_length=500)
    course_basis: str = Field(default="", max_length=2000)
    learning_objectives: str = Field(default="", max_length=2000)
    class_context: str = Field(default="", max_length=2000)
    course_type: str = Field(min_length=1, max_length=50)
    activity_format: Literal["讲授", "讨论", "实践", "混合"] = "混合"
    intended_use: Literal["日常教学", "公开课", "教研展示"] = "日常教学"
    lesson_minutes: int = Field(default=45, ge=20, le=180)
    available_minutes: int = Field(default=45, ge=20, le=180)
    teacher_intent: str = Field(min_length=2, max_length=1000)
    available_resources: str = Field(default="", max_length=1000)
    assumptions_confirmed: bool = False


class ProfessionalInputOutput(BaseModel):
    rule_set_version: str
    confirmed_input: dict
    conflicts: list[ProfessionalInputConflict]
    assumptions: list[str]
    assumptions_confirmed: bool
    ready_for_alignment: bool
    invalidated_sections: list[str]
    version_number: int


class ProfessionalInputRequest(ProfessionalInputInput):
    memory_refs: list[MemoryRef] = Field(default_factory=list, max_length=10)


class ProfessionalInputResponse(ProfessionalInputOutput):
    skill_run_id: int
    skill_id: str = "skill.confirm_professional_input"
    skill_version: str


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
    page_number: int | None = None
    paragraph_start: int | None = None
    paragraph_end: int | None = None
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
    insufficiency_reason: str | None = None
    retrieval_mode: str
    citations: list[BasisCitation]


class RetrieveBasisResponse(BaseModel):
    skill_run_id: int
    skill_id: str = "skill.retrieve_basis"
    skill_version: str
    insufficient_basis: bool
    insufficiency_reason: str | None = None
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


class ModelAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_type: str
    logical_name: str
    provider: str
    repository: str
    revision: str
    served_model_name: str
    runtime: str
    runtime_version: str
    runtime_image: str
    status: str
    asset_metadata: dict


class KnowledgeIndexVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    version_number: int
    status: str
    embedding_model: str
    embedding_revision: str
    reranker_model: str
    reranker_revision: str
    dimensions: int
    config_hash: str
    chunk_count: int
    error_message: str | None
    activated_at: datetime | None
    created_at: datetime


class EvaluationDatasetCreate(BaseModel):
    project_id: int
    dataset_key: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    data_origin: Literal[
        "synthetic", "internal_authored", "customer_provided", "expert_authored"
    ] = "synthetic"


class EvaluationDatasetReviewRequest(BaseModel):
    review_status: Literal["approved", "rejected"]
    review_note: str = Field(min_length=2, max_length=2000)


class EvaluationDatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    owner_id: int
    dataset_key: str
    version_number: int
    name: str
    description: str | None
    data_origin: str
    review_status: str
    review_note: str | None
    reviewed_by: int | None
    reviewed_at: datetime | None
    status: str
    content_hash: str | None
    case_count: int
    frozen_at: datetime | None
    created_at: datetime


class EvaluationCaseCreate(BaseModel):
    case_key: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]+$")
    query: str = Field(min_length=2, max_length=500)
    expected_document_ids: list[int] = Field(default_factory=list, max_length=20)
    expected_insufficient_basis: bool = False
    case_metadata: dict = Field(default_factory=dict)


class EvaluationCaseBulkImport(BaseModel):
    cases: list[EvaluationCaseCreate] = Field(min_length=1, max_length=200)


class EvaluationCaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dataset_id: int
    case_key: str
    query: str
    expected_document_ids: list[int]
    expected_insufficient_basis: bool
    case_metadata: dict
    gold_status: str
    created_at: datetime


class EvaluationCaseReviewCreate(BaseModel):
    review_kind: Literal["independent", "arbitration"] = "independent"
    expected_document_ids: list[int] = Field(default_factory=list, max_length=20)
    expected_insufficient_basis: bool = False
    critical_error_tags: list[str] = Field(default_factory=list, max_length=20)
    rationale: str = Field(min_length=2, max_length=4000)


class EvaluationCaseReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_id: int
    reviewer_id: int
    review_kind: str
    expected_document_ids: list[int]
    expected_insufficient_basis: bool
    critical_error_tags: list[str]
    rationale: str
    created_at: datetime


class EvaluationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dataset_id: int
    status: str
    dataset_hash: str
    release_manifest: dict
    total_cases: int
    matched_cases: int
    failed_cases: int
    error_cases: int
    started_at: datetime
    finished_at: datetime | None


class EvaluationCaseResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    case_id: int
    status: str
    returned_document_ids: list[int]
    insufficient_basis: bool
    checks: dict
    error_message: str | None
    latency_ms: int | None
    created_at: datetime


class EvaluationLatestRunSummary(BaseModel):
    id: int
    status: str
    total_cases: int
    matched_cases: int
    failed_cases: int
    error_cases: int
    dataset_hash: str


class EvaluationDatasetReportResponse(BaseModel):
    dataset_id: int
    data_origin: str
    review_status: str
    dataset_status: str
    total_cases: int
    placeholder_cases: int
    gold_status_counts: dict[str, int]
    ready_for_freeze: bool
    latest_run: EvaluationLatestRunSummary | None


class EvaluationGateCheck(BaseModel):
    check: str
    threshold: str
    observed: float | int | None
    passed: bool


class EvaluationManifestChange(BaseModel):
    path: str
    baseline: str | float | int | bool | None
    current: str | float | int | bool | None


class EvaluationGateMetrics(BaseModel):
    total_cases: int
    matched_cases: int
    error_cases: int
    match_rate: float
    top1_total: int
    top1_hits: int
    top1_hit_rate: float | None
    insufficient_basis_misses: int


class EvaluationGateBaseline(BaseModel):
    baseline_run_id: int
    manifest_changes: list[EvaluationManifestChange]
    regressed_case_keys: list[str]
    improved_case_keys: list[str]
    still_failed_case_keys: list[str]


class EvaluationGateReportResponse(BaseModel):
    dataset_id: int
    dataset_key: str
    data_origin: str
    disclaimer: str
    verdict: str
    can_promote: bool
    latest_run_id: int | None
    metrics: EvaluationGateMetrics | None
    checks: list[EvaluationGateCheck]
    pending_manifest_changes: list[EvaluationManifestChange]
    baseline: EvaluationGateBaseline | None


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
    artifact_kind: Literal[
        "lesson_design",
        "task_sheet",
        "rubric",
        "board_plan",
        "slide_outline",
        "practice_task",
    ] = "lesson_design"
    target_path: str | None = Field(default=None, min_length=2, max_length=200)
    source_version: int | None = Field(default=None, ge=1)


class GenerateSectionOutput(BaseModel):
    artifact_kind: str = "lesson_design"
    section_name: str
    opening: str = ""
    activities: list[dict] = Field(default_factory=list)
    assessment_evidence: list[str] = Field(default_factory=list)
    teacher_notes: list[str] = Field(default_factory=list)
    content: dict = Field(default_factory=dict)
    changed_paths: list[str] = Field(default_factory=list)
    preserved_locked_paths: list[str] = Field(default_factory=list)
    version_number: int


class GenerateSectionRequest(GenerateSectionInput):
    memory_refs: list[MemoryRef] = Field(default_factory=list, max_length=10)


class GenerateSectionResponse(GenerateSectionOutput):
    skill_run_id: int
    skill_id: str = "skill.generate_section"
    skill_version: str


class DiagnoseArtifactInput(BaseModel):
    project_id: int
    source_version: int | None = Field(default=None, ge=1)


class DiagnosisItem(BaseModel):
    item_id: str
    dimension: str
    status: str = Field(pattern="^(aligned|needs_attention)$")
    source_path: str
    rule_basis: str
    evidence: str
    impact: str
    suggestion: str
    example_revision: str
    revision_target_path: str


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


class DiagnosisStructureNode(BaseModel):
    path: str = Field(min_length=2, max_length=200)
    section_type: str = Field(min_length=2, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    excerpt: str = Field(default="", max_length=1000)


class DiagnosisStructureConfirm(BaseModel):
    source_version: int = Field(ge=1)
    nodes: list[DiagnosisStructureNode] = Field(min_length=1, max_length=100)


class DiagnosisDecisionRequest(BaseModel):
    source_version: int = Field(ge=1)
    action: Literal["accept", "ignore", "edit", "request_expert"]
    edited_suggestion: str | None = Field(default=None, max_length=2000)


class ApplyRevisionInput(BaseModel):
    project_id: int
    source_version: int | None = Field(default=None, ge=1)


class ApplyRevisionOutput(BaseModel):
    applied_item_ids: list[str]
    skipped_item_ids: list[str]
    changed_paths: list[str]
    version_number: int


class ApplyRevisionRequest(ApplyRevisionInput):
    memory_refs: list[MemoryRef] = Field(default_factory=list, max_length=10)


class ApplyRevisionResponse(ApplyRevisionOutput):
    skill_run_id: int
    skill_id: str = "skill.apply_revision"
    skill_version: str


class ExportArtifactInput(BaseModel):
    project_id: int
    template_name: str = Field(default="standard-v2", min_length=2, max_length=100)


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


class VersionFieldChange(BaseModel):
    path: str
    change_type: Literal["added", "removed", "changed"]
    before: object | None
    after: object | None


class VersionDiffResponse(BaseModel):
    project_id: int
    from_version: int
    to_version: int
    changed_sections: list[VersionDiffSection]
    field_changes: list[VersionFieldChange]


class SpotCheckSampleRequest(BaseModel):
    skill_id: str = Field(default="skill.diagnose_artifact", min_length=2, max_length=100)
    sample_size: int = Field(default=5, ge=1, le=20)


class SpotCheckItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    skill_run_id: int
    project_id: int | None
    sampled_by: int
    sample_source: str
    skill_id: str
    skill_version: str
    status: str
    context_snapshot: dict
    resolved_verdict: str | None
    resolved_issue_tags: list[str]
    created_at: datetime


class SpotCheckQueueResponse(BaseModel):
    items: list[SpotCheckItemResponse]
    status_counts: dict[str, int]
    disclaimer: str


class SpotCheckReviewCreate(BaseModel):
    review_kind: Literal["independent", "arbitration"] = "independent"
    verdict: Literal["confirmed", "needs_adjustment"]
    issue_tags: list[str] = Field(default_factory=list, max_length=20)
    rubric_feedback: str | None = Field(default=None, max_length=4000)
    rationale: str = Field(min_length=2, max_length=4000)


class SpotCheckReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    reviewer_id: int
    review_kind: str
    verdict: str
    issue_tags: list[str]
    rubric_feedback: str | None
    rationale: str
    created_at: datetime


class SpotCheckSkillRunEvidence(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    project_id: int | None
    skill_id: str
    skill_version: str
    status: str
    input_payload: dict
    output_payload: dict | None
    created_at: datetime


class SpotCheckDetailResponse(BaseModel):
    item: SpotCheckItemResponse
    skill_run: SpotCheckSkillRunEvidence | None
    reviews: list[SpotCheckReviewResponse]
    disclaimer: str


class L4RuleSignalSummary(BaseModel):
    rule_id: str
    total_signals: int
    actions: dict[str, int]


class L4DimensionSignalSummary(BaseModel):
    dimension: str
    total_signals: int
    actions: dict[str, int]
    rules: list[L4RuleSignalSummary]


class L4SignalSummaryResponse(BaseModel):
    scope: Literal["project", "global"]
    project_count: int
    signal_level: Literal["L4"]
    authorized_for_training: Literal[False]
    disclaimer: str
    total_signals: int
    dimensions: list[L4DimensionSignalSummary]
