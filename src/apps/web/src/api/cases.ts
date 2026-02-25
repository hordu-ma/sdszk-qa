import request from "./request";
import type {
  CaseListItem,
  CaseDetail,
} from "../types";

// 获取主题列表
export function getCaseList(params?: {
  difficulty?: string;
  department?: string;
  skip?: number;
  limit?: number;
}) {
  return request.get<any, CaseListItem[]>("/cases/", { params });
}

// 获取主题详情
export function getCaseDetail(id: number) {
  return request.get<any, CaseDetail>(`/cases/${id}`);
}

// Re-export types
export type {
  CaseListItem,
  CaseDetail,
};
