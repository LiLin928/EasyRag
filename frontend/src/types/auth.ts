// 认证模块类型定义

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
