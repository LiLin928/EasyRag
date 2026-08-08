// MCP Mock 数据
import type { Mcp, McpTestResult } from '@/types/mcp'

// Mock MCP 列表
export const mockMcps: Mcp[] = [
  {
    id: 'mcp1',
    name: 'filesystem',
    tp: 'stdio',
    cmd: 'npx -y @mcp/server-filesystem',
    status: 'on',
    toolCount: 5,
    env: [
      { k: 'ALLOWED_DIRECTORIES', v: '/Users/user/projects' }
    ],
    timeout: 30,
    createdAt: '2026-08-01 10:30:00'
  },
  {
    id: 'mcp2',
    name: 'github',
    tp: 'stdio',
    cmd: 'npx -y @mcp/server-github',
    status: 'on',
    toolCount: 8,
    env: [
      { k: 'GITHUB_TOKEN', v: 'ghp_xxxxxxxxxxxxx' }
    ],
    timeout: 60,
    createdAt: '2026-08-02 14:20:00'
  },
  {
    id: 'mcp3',
    name: 'postgres',
    tp: 'SSE',
    cmd: 'https://api.mcp.example.com/postgres',
    status: 'err',
    toolCount: 0,
    env: [
      { k: 'DATABASE_URL', v: 'postgresql://user:pass@localhost:5432/db' }
    ],
    timeout: 45,
    createdAt: '2026-08-03 09:15:00'
  },
  {
    id: 'mcp4',
    name: 'brave-search',
    tp: 'SSE',
    cmd: 'https://api.mcp.example.com/brave-search',
    status: 'on',
    toolCount: 3,
    env: [
      { k: 'BRAVE_API_KEY', v: 'BSxxxxxxxxxxxxx' }
    ],
    timeout: 30,
    createdAt: '2026-08-04 16:45:00'
  }
]

// 模拟测试结果
export function createMockTestResult(mcpId: string): McpTestResult {
  const mcp = mockMcps.find(m => m.id === mcpId)

  if (!mcp) {
    return {
      success: false,
      toolCount: 0,
      error: 'MCP 服务不存在',
      duration: 0
    }
  }

  // 模拟延迟
  const duration = Math.floor(Math.random() * 1000) + 500

  // 错误状态的服务返回失败
  if (mcp.status === 'err') {
    return {
      success: false,
      toolCount: 0,
      error: '连接超时，无法访问 MCP 服务',
      duration
    }
  }

  // 根据不同 MCP 服务返回不同工具列表
  switch (mcp.name) {
    case 'filesystem':
      return {
        success: true,
        toolCount: 5,
        tools: ['read_file', 'write_file', 'create_directory', 'list_directory', 'search_files'],
        duration
      }

    case 'github':
      return {
        success: true,
        toolCount: 8,
        tools: ['create_issue', 'get_issue', 'list_issues', 'create_pull_request', 'get_pull_request', 'list_pull_requests', 'add_comment', 'get_repository'],
        duration
      }

    case 'postgres':
      return {
        success: false,
        toolCount: 0,
        error: '数据库连接失败',
        duration
      }

    case 'brave-search':
      return {
        success: true,
        toolCount: 3,
        tools: ['brave_web_search', 'brave_news_search', 'brave_images_search'],
        duration
      }

    default:
      return {
        success: true,
        toolCount: mcp.toolCount,
        tools: ['unknown_tool'],
        duration
      }
  }
}
