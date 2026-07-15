import request from "./request";
import type {
  KnowledgeDocument,
  ModelStatus,
  RetrieveBasisResponse,
  TaskRun,
  TeachingProject,
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

export function retrieveBasis(projectId: number, query: string) {
  return request.post<unknown, RetrieveBasisResponse>(
    "/workbench/skills/retrieve-basis",
    { project_id: projectId, query, limit: 5 },
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
