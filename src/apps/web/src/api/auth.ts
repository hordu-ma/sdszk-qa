import request from './request'
import type { Token, UserResponse } from '../types'

export interface LoginParams {
  username: string
  password: string
}

// 登录
export function login(data: LoginParams) {
  return request.post<unknown, Token>('/auth/login', data)
}

// 获取当前用户信息
export function getUserInfo() {
  return request.get<unknown, UserResponse>('/auth/me')
}

// Re-export types
export type { Token, UserResponse }
