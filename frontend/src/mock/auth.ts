// 登录模块 Mock 数据
import type { UserInfo } from '@/stores/auth'

// Mock 用户
const mockUser: UserInfo = {
  id: 'u1',
  username: 'admin',
  nickname: '系统管理员',
  avatar: '',
  email: 'admin@easyrag.com',
  roles: ['admin']
}

// Mock 登录响应
export const mockLoginResponse = {
  code: 0,
  message: 'success',
  data: {
    access_token: 'mock-access-' + Date.now(),
    refresh_token: 'mock-refresh-' + Date.now(),
    expires_in: 7200,
    user: mockUser
  }
}

// Mock 刷新响应
export const mockRefreshResponse = {
  code: 0,
  message: 'success',
  data: {
    access_token: 'mock-access-refresh-' + Date.now(),
    expires_in: 7200
  }
}

// Mock 用户信息响应
export const mockUserInfoResponse = {
  code: 0,
  message: 'success',
  data: mockUser
}
