import type { RouteRecordRaw } from 'vue-router'
import AppLayout from '@/layouts/AppLayout.vue'

export const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/LoginView.vue'),
    meta: { title: '登录', requiresAuth: false }
  },
  {
    path: '/',
    component: AppLayout,
    redirect: '/chat',
    children: [
      {
        path: 'chat',
        name: 'Chat',
        component: () => import('@/views/chat/ChatView.vue'),
        meta: { title: '智能对话', icon: 'ChatDotRound', requiresAuth: true }
      },
      {
        path: 'chat/:conversationId',
        name: 'ChatConversation',
        component: () => import('@/views/chat/ChatView.vue'),
        meta: { title: '智能对话', icon: 'ChatDotRound', requiresAuth: true }
      },
      {
        path: 'knowledge',
        name: 'Knowledge',
        component: () => import('@/views/knowledge/KnowledgeListView.vue'),
        meta: { title: '知识库管理', icon: 'Folder', requiresAuth: true }
      },
      {
        path: 'knowledge/:kbId',
        name: 'KnowledgeDetail',
        component: () => import('@/views/knowledge/KbDetailView.vue'),
        meta: { title: '知识库详情', icon: 'Folder', requiresAuth: true }
      },
      {
        path: 'knowledge/:kbId/docs/:docId',
        name: 'DocDetail',
        component: () => import('@/views/knowledge/docs/DocDetailView.vue'),
        meta: { title: '文档详情', icon: 'Document', requiresAuth: true }
      },
      {
        path: 'workflows',
        name: 'Workflows',
        component: () => import('@/views/workflow/WorkflowsView.vue'),
        meta: { title: '工作流列表', icon: 'Share', requiresAuth: true }
      },
      {
        path: 'todos',
        name: 'Todos',
        component: () => import('@/views/todos/TodosView.vue'),
        meta: { title: '待办中心', icon: 'List', requiresAuth: true }
      },
      {
        path: 'agents',
        name: 'Agents',
        component: () => import('@/views/agents/AgentsView.vue'),
        meta: { title: '智能体', icon: 'User', requiresAuth: true }
      },
      {
        path: 'tools',
        name: 'Tools',
        component: () => import('@/views/tools/ToolsView.vue'),
        meta: { title: '工具', icon: 'Tools', requiresAuth: true }
      },
      {
        path: 'skills',
        name: 'Skills',
        component: () => import('@/views/skills/SkillsView.vue'),
        meta: { title: '技能', icon: 'MagicStick', requiresAuth: true }
      },
      {
        path: 'mcp',
        name: 'Mcp',
        component: () => import('@/views/mcp/McpView.vue'),
        meta: { title: 'MCP 服务', icon: 'Connection', requiresAuth: true }
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/settings/SettingsView.vue'),
        meta: { title: '系统设置', icon: 'Setting', requiresAuth: true }
      }
    ]
  },
  {
    path: '/workflows/editor/:id',
    name: 'WorkflowEditor',
    component: () => import('@/views/workflow/WorkflowEditorView.vue'),
    meta: { title: '工作流编辑器', requiresAuth: true }
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { title: '404', requiresAuth: false }
  }
]
