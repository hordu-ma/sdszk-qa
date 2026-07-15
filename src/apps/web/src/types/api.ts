/**
 * API 响应类型定义
 * 与后端 Pydantic schemas 对齐
 */

// ==================== Auth ====================
export interface Token {
  access_token: string;
  token_type: string;
}

export interface UserResponse {
  id: number;
  username: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

// ==================== Topics ====================
export interface TopicListItem {
  id: number;
  title: string;
  difficulty: string;
  department: string;
  is_active: boolean;
  created_at: string;
}

export interface TopicDetail {
  id: number;
  title: string;
  difficulty: string;
  department: string;
  context_info: Record<string, unknown>;
  core_question: string;
  scenario_text: string;
  supplementary_info: Record<string, unknown>;
}

// ==================== Sessions ====================
export interface SessionResponse {
  id: number;
  case_id: number;
  status: string;
  started_at: string;
}

export interface SessionCreateRequest {
  mode?: "fixed" | "custom";
  case_id?: number;
  topic?: string;
}

export interface SessionListItem {
  id: number;
  case_id: number;
  case_title: string;
  status: string;
  started_at: string;
  ended_at: string | null;
  message_count: number;
}

export interface SessionListResponse {
  items: SessionListItem[];
  total: number;
  skip: number;
  limit: number;
}

export interface MessageItem {
  id: number;
  role: "user" | "assistant" | "system";
  content: string;
  tokens: number | null;
  latency_ms: number | null;
  created_at: string;
}

export interface SessionDetail {
  id: number;
  case_id: number;
  case_title: string;
  status: string;
  started_at: string;
  ended_at: string | null;
  messages: MessageItem[];
}

// ==================== Stage 1A Workbench ====================
export interface TeachingProject {
  id: number;
  title: string;
  stage: string;
  course_type: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeDocument {
  id: number;
  project_id: number;
  filename: string;
  content_type: string;
  checksum_sha256: string;
  status: "processing" | "ready" | "failed";
  review_status: string;
  version_number: number;
  error_message: string | null;
  created_at: string;
}

export interface TaskRun {
  id: number;
  project_id: number | null;
  task_type: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  progress: number;
  attempt: number;
  input_payload: Record<string, unknown>;
  output_payload: Record<string, unknown> | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface BasisCitation {
  document_id: number;
  filename: string;
  chunk_id: number;
  location_label: string;
  content: string;
  relevance: number;
}

export interface RetrieveBasisResponse {
  skill_run_id: number;
  skill_id: string;
  skill_version: string;
  insufficient_basis: boolean;
  citations: BasisCitation[];
}

export interface ModelStatus {
  logical_model: string;
  provider: string;
  provider_model: string;
  degraded: boolean;
}
