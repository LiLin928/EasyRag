import type { Router } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const whiteList = ['/login', '/404']

export function setupRouterGuard(router: Router) {
  router.beforeEach((to, _from, next) => {
    const authStore = useAuthStore()
    const isAuthenticated = authStore.isAuthenticated

    // 设置页面标题
    if (to.meta.title) {
      document.title = 'EasyRAG - ' + String(to.meta.title)
    }

    // 已登录访问登录页，跳转到首页
    if (to.path === '/login' && isAuthenticated) {
      next('/')
      return
    }

    // 白名单直接放行
    if (whiteList.includes(to.path)) {
      next()
      return
    }

    // 需要鉴权
    if (to.meta.requiresAuth) {
      if (isAuthenticated) {
        next()
      } else {
        next('/login?redirect=' + encodeURIComponent(to.path))
      }
    } else {
      next()
    }
  })
}
