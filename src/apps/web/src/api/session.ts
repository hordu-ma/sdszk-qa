import request from "./request";
import type {
  SessionResponse,
  SessionListResponse,
  SessionListItem,
  SessionDetail,
} from "../types";

// 获取会话列表
export function getSessions(params?: {
  status?: string;
  skip?: number;
  limit?: number;
}) {
  return request.get<any, SessionListResponse>("/sessions/", { params });
}

// 创建会话（custom 模式支持自定义主题）
export function createSession(data: {
  mode?: "fixed" | "custom";
  case_id?: number;
  topic?: string;
}) {
  const timeout = 10000;
  return request.post<any, SessionResponse>("/sessions/", data, { timeout });
}

// 获取会话详情
export function getSession(sessionId: number) {
  return request.get<any, SessionDetail>(`/sessions/${sessionId}`);
}

// 获取会话消息历史（从 SessionDetail 中获取）
export function getSessionMessages(sessionId: number) {
  return getSession(sessionId).then((res) => res.messages);
}

// Re-export types for convenience
export type {
  SessionResponse,
  SessionListResponse,
  SessionListItem,
  SessionDetail,
};
