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

// ==================== Cases ====================
export interface CaseListItem {
  id: number;
  title: string;
  difficulty: string;
  department: string;
  is_active: boolean;
  created_at: string;
}

export interface CaseDetail {
  id: number;
  title: string;
  difficulty: string;
  department: string;
  patient_info: Record<string, unknown>;
  chief_complaint: string;
  present_illness: string;
  past_history: Record<string, unknown>;
  physical_exam: Record<string, unknown>;
  available_tests: Record<string, unknown>[];
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
  case_difficulty: string;
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
  case_difficulty: string;
  status: string;
  started_at: string;
  ended_at: string | null;
  messages: MessageItem[];
}
