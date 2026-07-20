import request from "./request";
import type {
  KnowledgeDocument,
  ClassProfile,
  ExportArtifactResponse,
  EvaluationCase,
  EvaluationCaseInput,
  EvaluationCaseReview,
  EvaluationDataOrigin,
  EvaluationDataset,
  EvaluationDatasetReport,
  EvaluationGateReport,
  MemoryRef,
  ModelStatus,
  PinnedItem,
  ProjectVersion,
  ProfessionalInputPayload,
  ProfessionalInputResponse,
  RetrieveBasisResponse,
  SkillStepResponse,
  TaskRun,
  TeachingProject,
  UserPreference,
  VersionDiff,
  StructuredGenerationResponse,
  TeachingArtifactKind,
  DiagnosisStructureNode,
  DiagnosisDecisionAction,
  ApplyRevisionResponse,
  L4SignalSummary,
  SpotCheckDetail,
  SpotCheckQueue,
  SpotCheckReview,
  SpotCheckVerdict,
} from "../types/api";

export function listProjects() {
  return request.get<unknown, TeachingProject[]>("/workbench/projects");
}

export function createProject(data: {
  title: string;
  stage: string;
  course_type: string;
}) {
  return request.post<unknown, TeachingProject>("/workbench/projects", data);
}

export function listDocuments(projectId: number) {
  return request.get<unknown, KnowledgeDocument[]>(
    `/workbench/projects/${projectId}/documents`,
  );
}

export function uploadDocument(projectId: number, file: File) {
  const body = new FormData();
  body.append("file", file);
  return request.post<unknown, { document: KnowledgeDocument; task: TaskRun }>(
    `/workbench/projects/${projectId}/documents`,
    body,
    { timeout: 30000 },
  );
}

export function reviewDocument(
  documentId: number,
  reviewStatus: "approved" | "rejected" | "disabled",
) {
  return request.post<unknown, KnowledgeDocument>(
    `/workbench/documents/${documentId}/review`,
    { review_status: reviewStatus },
  );
}

export function retrieveBasis(projectId: number, query: string, memoryRefs: MemoryRef[] = []) {
  return request.post<unknown, RetrieveBasisResponse>(
    "/workbench/skills/retrieve-basis",
    { project_id: projectId, query, limit: 5, memory_refs: memoryRefs },
  );
}

export function listTasks(projectId?: number) {
  return request.get<unknown, TaskRun[]>("/workbench/tasks", {
    params: projectId ? { project_id: projectId } : undefined,
  });
}

export function cancelTask(taskId: number) {
  return request.post<unknown, TaskRun>(`/workbench/tasks/${taskId}/cancel`);
}

export function retryTask(taskId: number) {
  return request.post<unknown, TaskRun>(`/workbench/tasks/${taskId}/retry`);
}

export function getModelStatus() {
  return request.get<unknown, ModelStatus>("/workbench/model-status");
}

export function getPreference() {
  return request.get<unknown, UserPreference | null>("/workbench/memory/preference");
}

export function savePreference(data: {
  default_stage: string | null;
  default_course_type: string | null;
  textbook_version: string | null;
  export_template: string | null;
}) {
  return request.put<unknown, UserPreference>("/workbench/memory/preference", {
    ...data,
    extra: {},
  });
}

export function listClassProfiles() {
  return request.get<unknown, ClassProfile[]>("/workbench/memory/class-profiles");
}

export function createClassProfile(data: { name: string; context: Record<string, unknown> }) {
  return request.post<unknown, ClassProfile>("/workbench/memory/class-profiles", data);
}

export function deleteClassProfile(profileId: number) {
  return request.delete(`/workbench/memory/class-profiles/${profileId}`);
}

export function listPinnedItems() {
  return request.get<unknown, PinnedItem[]>("/workbench/memory/pinned-items");
}

export function pinProject(project: TeachingProject) {
  return request.post<unknown, PinnedItem>("/workbench/memory/pinned-items", {
    item_type: "project",
    project_id: project.id,
    name: project.title,
    payload: { stage: project.stage, course_type: project.course_type },
  });
}

export function createProfessionalInputTemplate(
  name: string,
  payload: Record<string, unknown>,
) {
  return request.post<unknown, PinnedItem>("/workbench/memory/pinned-items", {
    item_type: "template",
    project_id: null,
    name,
    payload,
  });
}

export function deletePinnedItem(itemId: number) {
  return request.delete(`/workbench/memory/pinned-items/${itemId}`);
}

export function clearMemory() {
  return request.post<unknown, {
    cleared_preference: boolean;
    cleared_class_profiles: number;
    cleared_pinned_items: number;
  }>("/workbench/memory/clear");
}

export function listProjectVersions(projectId: number) {
  return request.get<unknown, ProjectVersion[]>(`/workbench/projects/${projectId}/versions`);
}

export function saveProjectVersion(
  projectId: number,
  content: Record<string, unknown>,
  sourceVersion: number,
) {
  return request.post<unknown, ProjectVersion>(`/workbench/projects/${projectId}/versions`, {
    content,
    status: "draft",
    source_version: sourceVersion,
  });
}

export function updateProjectVersionLocks(
  projectId: number,
  sourceVersion: number,
  lockedPaths: string[],
) {
  return request.post<unknown, ProjectVersion>(
    `/workbench/projects/${projectId}/versions/locks`,
    { source_version: sourceVersion, locked_paths: lockedPaths },
  );
}

export function restoreProjectVersion(
  projectId: number,
  sourceVersion: number,
  restoreVersion: number,
) {
  return request.post<unknown, ProjectVersion>(
    `/workbench/projects/${projectId}/versions/restore`,
    { source_version: sourceVersion, restore_version: restoreVersion },
  );
}

export function previewDiagnosisStructure(projectId: number) {
  return request.get<unknown, DiagnosisStructureNode[]>(
    `/workbench/projects/${projectId}/diagnosis/structure`,
  );
}

export function confirmDiagnosisStructure(
  projectId: number,
  sourceVersion: number,
  nodes: DiagnosisStructureNode[],
) {
  return request.post<unknown, ProjectVersion>(
    `/workbench/projects/${projectId}/diagnosis/structure`,
    { source_version: sourceVersion, nodes },
  );
}

export function decideDiagnosisItem(
  projectId: number,
  itemId: string,
  sourceVersion: number,
  action: DiagnosisDecisionAction,
  editedSuggestion?: string,
) {
  return request.post<unknown, ProjectVersion>(
    `/workbench/projects/${projectId}/diagnosis/items/${itemId}/decision`,
    {
      source_version: sourceVersion,
      action,
      edited_suggestion: editedSuggestion || null,
    },
  );
}

export function applyDiagnosisRevision(
  projectId: number,
  sourceVersion: number,
  memoryRefs: MemoryRef[] = [],
) {
  return request.post<unknown, ApplyRevisionResponse>("/workbench/skills/apply-revision", {
    project_id: projectId,
    source_version: sourceVersion,
    memory_refs: memoryRefs,
  });
}

export function confirmProfessionalInput(
  projectId: number,
  data: ProfessionalInputPayload,
  memoryRefs: MemoryRef[],
) {
  return request.post<unknown, ProfessionalInputResponse>(
    "/workbench/skills/confirm-professional-input",
    { project_id: projectId, ...data, memory_refs: memoryRefs },
  );
}

export function compareVersions(projectId: number, fromVersion: number, toVersion: number) {
  return request.get<unknown, VersionDiff>(`/workbench/projects/${projectId}/versions/diff`, {
    params: { from_version: fromVersion, to_version: toVersion },
  });
}

export function createAlignmentCard(data: {
  project_id: number;
  topic: string;
  core_question: string;
  basis_query: string;
  memory_refs: MemoryRef[];
}) {
  return request.post<unknown, SkillStepResponse>("/workbench/skills/alignment-card", data);
}

export function createDesignBlueprint(projectId: number, memoryRefs: MemoryRef[]) {
  return request.post<unknown, SkillStepResponse>("/workbench/skills/design-blueprint", {
    project_id: projectId,
    lesson_minutes: 45,
    memory_refs: memoryRefs,
  });
}

export function generateSection(
  projectId: number,
  memoryRefs: MemoryRef[],
  options: {
    artifact_kind?: TeachingArtifactKind;
    target_path?: string;
    guidance?: string;
    source_version?: number;
  } = {},
) {
  return request.post<unknown, StructuredGenerationResponse>(
    "/workbench/skills/generate-section",
    {
    project_id: projectId,
    section_name: "课时设计",
    guidance: options.guidance || "保留教师确认点，突出依据引用与课堂证据",
    artifact_kind: options.artifact_kind || "lesson_design",
    target_path: options.target_path,
    source_version: options.source_version,
    memory_refs: memoryRefs,
    },
  );
}

export function diagnoseArtifact(
  projectId: number,
  sourceVersion: number,
  memoryRefs: MemoryRef[],
) {
  return request.post<unknown, SkillStepResponse>("/workbench/skills/diagnose-artifact", {
    project_id: projectId,
    source_version: sourceVersion,
    memory_refs: memoryRefs,
  });
}

export function exportArtifact(projectId: number, memoryRefs: MemoryRef[]) {
  return request.post<unknown, ExportArtifactResponse>("/workbench/skills/export-artifact", {
    project_id: projectId,
    template_name: "standard-v2",
    memory_refs: memoryRefs,
  });
}

export function downloadExport(downloadUrl: string) {
  return request.get<unknown, Blob>(downloadUrl.replace(/^\/api/, ""), {
    responseType: "blob",
  });
}

export function listEvaluationDatasets(projectId: number) {
  return request.get<unknown, EvaluationDataset[]>("/workbench/evaluation/datasets", {
    params: { project_id: projectId },
  });
}

export function listEvaluationReviewQueue() {
  return request.get<unknown, EvaluationDataset[]>("/workbench/evaluation/review-queue");
}

export function createEvaluationDataset(data: {
  project_id: number;
  dataset_key: string;
  name: string;
  description: string | null;
  data_origin: EvaluationDataOrigin;
}) {
  return request.post<unknown, EvaluationDataset>("/workbench/evaluation/datasets", data);
}

export function reviewEvaluationDataset(
  datasetId: number,
  reviewStatus: "approved" | "rejected",
  reviewNote: string,
) {
  return request.post<unknown, EvaluationDataset>(
    `/workbench/evaluation/datasets/${datasetId}/review`,
    { review_status: reviewStatus, review_note: reviewNote },
  );
}

export function importEvaluationCases(datasetId: number, cases: EvaluationCaseInput[]) {
  return request.post<unknown, EvaluationCase[]>(
    `/workbench/evaluation/datasets/${datasetId}/cases/import`,
    { cases },
  );
}

export function listEvaluationCases(datasetId: number) {
  return request.get<unknown, EvaluationCase[]>(
    `/workbench/evaluation/datasets/${datasetId}/cases`,
  );
}

export function submitEvaluationCaseReview(
  caseId: number,
  data: {
    review_kind: "independent" | "arbitration";
    expected_document_ids: number[];
    expected_insufficient_basis: boolean;
    critical_error_tags: string[];
    rationale: string;
  },
) {
  return request.post<unknown, EvaluationCaseReview>(
    `/workbench/evaluation/cases/${caseId}/reviews`,
    data,
  );
}

export function getEvaluationDatasetReport(datasetId: number) {
  return request.get<unknown, EvaluationDatasetReport>(
    `/workbench/evaluation/datasets/${datasetId}/report`,
  );
}

export function getEvaluationRegressionGate(datasetId: number) {
  return request.get<unknown, EvaluationGateReport>(
    `/workbench/evaluation/datasets/${datasetId}/regression-gate`,
  );
}

export function freezeEvaluationDataset(datasetId: number) {
  return request.post<unknown, EvaluationDataset>(
    `/workbench/evaluation/datasets/${datasetId}/freeze`,
  );
}

export function runEvaluationDataset(datasetId: number) {
  return request.post(`/workbench/evaluation/datasets/${datasetId}/runs`);
}

export function sampleSpotChecks(data: { skill_id?: string; sample_size?: number }) {
  return request.post<unknown, SpotCheckQueue>("/workbench/spot-checks/sample", data);
}

export function listSpotChecks(statusFilter?: string) {
  return request.get<unknown, SpotCheckQueue>("/workbench/spot-checks", {
    params: statusFilter ? { status_filter: statusFilter } : {},
  });
}

export function getSpotCheckDetail(itemId: number) {
  return request.get<unknown, SpotCheckDetail>(`/workbench/spot-checks/${itemId}`);
}

export function submitSpotCheckReview(
  itemId: number,
  data: {
    review_kind: "independent" | "arbitration";
    verdict: SpotCheckVerdict;
    issue_tags: string[];
    rubric_feedback?: string | null;
    rationale: string;
  },
) {
  return request.post<unknown, SpotCheckReview>(
    `/workbench/spot-checks/${itemId}/reviews`,
    data,
  );
}

export function getL4SignalSummary(projectId?: number | null) {
  return request.get<unknown, L4SignalSummary>("/workbench/signals/l4-summary", {
    params: projectId ? { project_id: projectId } : {},
  });
}
