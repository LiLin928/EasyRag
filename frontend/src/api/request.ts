import axios, { type AxiosInstance, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { setupMock } from '@/mock'

const BASE_URL = import.meta.env.VITE_API_BASE || '/api/v2'
const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

// 创建 axios 实例
const service: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 启用 Mock
if (USE_MOCK) {
  setupMock(service)
}

// 刷新队列
let isRefreshing = false
let refreshSubscribers: ((token: string) => void)[] = []

function subscribeTokenRefresh(cb: (token: string) => void) {
  refreshSubscribers.push(cb)
}

function onRefreshed(token: string) {
  refreshSubscribers.forEach(cb => cb(token))
  refreshSubscribers = []
}

// 请求拦截器
service.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const authStore = useAuthStore()
    if (authStore.token) {
      config.headers.Authorization = 'Bearer ' + authStore.token
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
service.interceptors.response.use(
  (response: AxiosResponse) => {
    const { code, message, data } = response.data

    // code === 0 成功
    if (code === 0) {
      return data
    }

    // 40100-40199 需要刷新 token
    if (code >= 40100 && code <= 40199) {
      const authStore = useAuthStore()
      
      if (!isRefreshing) {
        isRefreshing = true
        
        // 尝试刷新 token
        if (authStore.refreshToken) {
          return import('@/api/auth').then(({ refreshToken }) => {
            return refreshToken(authStore.refreshToken)
          }).then((res: any) => {
            authStore.setToken(res.access_token)
            onRefreshed(res.access_token)
            // 重试原请求
            response.config.headers.Authorization = 'Bearer ' + res.access_token
            return service(response.config)
          }).catch(() => {
            authStore.clearToken()
            window.location.href = '/login'
            return Promise.reject(new Error('Token expired'))
          }).finally(() => {
            isRefreshing = false
          })
        } else {
          authStore.clearToken()
          window.location.href = '/login'
        }
      } else {
        // 并发请求排队等待
        return new Promise((resolve) => {
          subscribeTokenRefresh((token: string) => {
            response.config.headers.Authorization = 'Bearer ' + token
            resolve(service(response.config))
          })
        })
      }
    }

    // 其他错误
    ElMessage.error(message || '请求失败')
    return Promise.reject(new Error(message || '请求失败'))
  },
  (error) => {
    ElMessage.error(error.message || '网络错误')
    return Promise.reject(error)
  }
)

export default service
