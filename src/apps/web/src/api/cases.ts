import request from "./request";
import type {
  TopicListItem,
  TopicDetail,
} from "../types";

// 获取主题列表
export function getTopicList(params?: {
  skip?: number;
  limit?: number;
}) {
  return request.get<any, TopicListItem[]>("/topics/", { params });
}

// 获取主题详情
export function getTopicDetail(id: number) {
  return request.get<any, TopicDetail>(`/topics/${id}`);
}

// Re-export types
export type {
  TopicListItem,
  TopicDetail,
};
