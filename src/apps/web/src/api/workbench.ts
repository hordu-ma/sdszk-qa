import request from "./request";
import type {
  KnowledgeDocument,
  ClassProfile,
  ExportArtifactResponse,
  MemoryRef,
  ModelStatus,
  PinnedItem,
  ProjectVersion,
  RetrieveBasisResponse,
  SkillStepResponse,
  TaskRun,
  TeachingProject,
  UserPreference,
  VersionDiff,
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

export function generateSection(projectId: number, memoryRefs: MemoryRef[]) {
  return request.post<unknown, SkillStepResponse>("/workbench/skills/generate-section", {
    project_id: projectId,
    section_name: "课时设计",
    guidance: "保留教师确认点，突出依据引用与课堂证据",
    memory_refs: memoryRefs,
  });
}

export function diagnoseArtifact(projectId: number, memoryRefs: MemoryRef[]) {
  return request.post<unknown, SkillStepResponse>("/workbench/skills/diagnose-artifact", {
    project_id: projectId,
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
