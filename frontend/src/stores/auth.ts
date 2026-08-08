import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as authApi from '@/api/auth'

export interface UserInfo {
  id: string
  username: string
  nickname: string
  avatar?: string
  email?: string
  roles: string[]
}

export const useAuthStore = defineStore('auth', () => {
  // 状态
  const token = ref<string>('')
  const refreshToken = ref<string>('')
  const user = ref<UserInfo | null>(null)
  const tokenExpireTime = ref<number>(0)

  // 计算属性
  const isAuthenticated = computed(() => !!token.value)
  const username = computed(() => user.value?.username || '')
  const nickname = computed(() => user.value?.nickname || '')
  const roles = computed(() => user.value?.roles || [])

  // 设置 token
  function setToken(t: string, rt?: string) {
    token.value = t
    if (rt) refreshToken.value = rt
  }

  // 设置用户信息
  function setUser(u: UserInfo) {
    user.value = u
  }

  // 登录
  async function login(params: { username: string; password: string; remember?: boolean }) {
    try {
      const result = await authApi.login(params)
      
      // 存储 token
      setToken(result.access_token, result.refresh_token)
      tokenExpireTime.value = Date.now() + result.expires_in * 1000
      
      // 存储用户信息
      setUser(result.user)
      
      return result
    } catch (error) {
      throw error
    }
  }

  // 刷新 token
  async function refresh() {
    if (!refreshToken.value) {
      throw new Error('No refresh token')
    }
    
    try {
      const result = await authApi.refreshToken(refreshToken.value)
      token.value = result.access_token
      tokenExpireTime.value = Date.now() + result.expires_in * 1000
      return result
    } catch (error) {
      clearToken()
      throw error
    }
  }

  // 获取用户信息
  async function fetchUserInfo() {
    try {
      const info = await authApi.getUserInfo()
      setUser(info)
      return info
    } catch (error) {
      throw error
    }
  }

  // 登出
  async function logout() {
    try {
      await authApi.logout()
    } catch (error) {
      // 忽略登出错误
    } finally {
      clearToken()
    }
  }

  // 清空状态
  function clearToken() {
    token.value = ''
    refreshToken.value = ''
    user.value = null
    tokenExpireTime.value = 0
  }

  // 检查 token 是否即将过期（5分钟内）
  function isTokenExpiring() {
    if (!tokenExpireTime.value) return false
    const fiveMinutes = 5 * 60 * 1000
    return tokenExpireTime.value - Date.now() < fiveMinutes
  }

  return {
    // 状态
    token,
    refreshToken,
    user,
    tokenExpireTime,
    
    // 计算属性
    isAuthenticated,
    username,
    nickname,
    roles,
    
    // 方法
    setToken,
    setUser,
    login,
    refresh,
    fetchUserInfo,
    logout,
    clearToken,
    isTokenExpiring
  }
}, {
  persist: {
    key: 'easyrag-auth',
    paths: ['token', 'refreshToken', 'user', 'tokenExpireTime']
  }
})
