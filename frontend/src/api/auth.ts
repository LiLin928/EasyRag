import request from './request'
import type { UserInfo } from '@/stores/auth'

export interface LoginParams {
  username: string
  password: string
  remember?: boolean
}

export interface LoginResult {
  access_token: string
  refresh_token: string
  expires_in: number
  user: UserInfo
}

export interface RefreshResult {
  access_token: string
  expires_in: number
}

// 登录
export function login(data: LoginParams): Promise<LoginResult> {
  return request.post('/auth/login', data)
}

// 刷新 token
export function refreshToken(refresh_token: string): Promise<RefreshResult> {
  return request.post('/auth/refresh', { refresh_token })
}

// 获取用户信息
export function getUserInfo(): Promise<UserInfo> {
  return request.get('/auth/user-info')
}

// 登出
export function logout(): Promise<void> {
  return request.post('/auth/logout')
}
