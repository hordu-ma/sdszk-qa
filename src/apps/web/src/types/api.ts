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
  valid_from: string | null;
  valid_until: string | null;
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
  page_number: number | null;
  paragraph_start: number | null;
  paragraph_end: number | null;
  content: string;
  relevance: number;
}

export interface RetrieveBasisResponse {
  skill_run_id: number;
  skill_id: string;
  skill_version: string;
  insufficient_basis: boolean;
  insufficiency_reason: string | null;
  retrieval_mode: string;
  citations: BasisCitation[];
}

export interface MemoryRef {
  memory_type: "user_preference" | "class_context_profile";
  memory_id: number;
}

export interface UserPreference {
  id: number;
  default_stage: string | null;
  default_course_type: string | null;
  textbook_version: string | null;
  export_template: string | null;
  extra: Record<string, unknown>;
  updated_at: string;
}

export interface ClassProfile {
  id: number;
  name: string;
  context: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface PinnedItem {
  id: number;
  item_type: "project" | "template";
  project_id: number | null;
  name: string;
  payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export type EvaluationDataOrigin =
  | "synthetic"
  | "internal_authored"
  | "customer_provided"
  | "expert_authored";

export interface EvaluationDataset {
  id: number;
  project_id: number;
  owner_id: number;
  dataset_key: string;
  version_number: number;
  name: string;
  description: string | null;
  data_origin: EvaluationDataOrigin;
  review_status: string;
  review_note: string | null;
  reviewed_by: number | null;
  reviewed_at: string | null;
  status: "draft" | "frozen";
  content_hash: string | null;
  case_count: number;
  frozen_at: string | null;
  created_at: string;
}

export interface EvaluationCase {
  id: number;
  dataset_id: number;
  case_key: string;
  query: string;
  expected_document_ids: number[];
  expected_insufficient_basis: boolean;
  case_metadata: Record<string, unknown>;
  gold_status:
    | "not_applicable"
    | "pending"
    | "single_review"
    | "consensus"
    | "disputed"
    | "arbitrated";
  created_at: string;
}

export interface EvaluationCaseInput {
  case_key: string;
  query: string;
  expected_document_ids?: number[];
  expected_insufficient_basis?: boolean;
  case_metadata?: Record<string, unknown>;
}

export interface EvaluationCaseReview {
  id: number;
  case_id: number;
  reviewer_id: number;
  review_kind: "independent" | "arbitration";
  expected_document_ids: number[];
  expected_insufficient_basis: boolean;
  critical_error_tags: string[];
  rationale: string;
  created_at: string;
}

export interface EvaluationLatestRunSummary {
  id: number;
  status: string;
  total_cases: number;
  matched_cases: number;
  failed_cases: number;
  error_cases: number;
  dataset_hash: string;
}

export interface EvaluationDatasetReport {
  dataset_id: number;
  data_origin: EvaluationDataOrigin;
  review_status: string;
  dataset_status: string;
  total_cases: number;
  placeholder_cases: number;
  gold_status_counts: Record<string, number>;
  ready_for_freeze: boolean;
  latest_run: EvaluationLatestRunSummary | null;
}

export interface ProjectVersion {
  id: number;
  project_id: number;
  version_number: number;
  status: string;
  content: Record<string, unknown>;
  created_by: number;
  created_at: string;
}

export interface ProfessionalInputConflict {
  conflict_id: string;
  severity: "blocking" | "needs_confirmation";
  field: string;
  message: string;
  resolution: string;
}

export interface ProfessionalInputPayload {
  topic: string;
  core_question: string;
  basis_query: string;
  course_basis: string;
  learning_objectives: string;
  class_context: string;
  course_type: string;
  activity_format: "讲授" | "讨论" | "实践" | "混合";
  intended_use: "日常教学" | "公开课" | "教研展示";
  lesson_minutes: number;
  available_minutes: number;
  teacher_intent: string;
  available_resources: string;
  assumptions_confirmed: boolean;
}

export interface ProfessionalInputResponse {
  skill_run_id: number;
  skill_id: "skill.confirm_professional_input";
  skill_version: string;
  rule_set_version: string;
  confirmed_input: Omit<ProfessionalInputPayload, "assumptions_confirmed">;
  conflicts: ProfessionalInputConflict[];
  assumptions: string[];
  assumptions_confirmed: boolean;
  ready_for_alignment: boolean;
  invalidated_sections: string[];
  version_number: number;
}

export interface VersionDiff {
  project_id: number;
  from_version: number;
  to_version: number;
  changed_sections: Array<{
    section: string;
    before: unknown;
    after: unknown;
  }>;
}

export interface SkillStepResponse {
  skill_run_id: number;
  skill_id: string;
  skill_version: string;
  version_number: number;
  [key: string]: unknown;
}

export interface ExportArtifactResponse extends SkillStepResponse {
  export_id: number;
  filename: string;
  download_url: string;
  template_version: string;
}

export interface ModelStatus {
  logical_model: string;
  provider: string;
  provider_model: string;
  degraded: boolean;
  content_mode: "synthetic" | "production";
  content_disclaimer: string;
}
