import { createRouter, createWebHistory } from 'vue-router'
import { routes } from './modules'
import { setupRouterGuard } from './guard'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

setupRouterGuard(router)

export default router
