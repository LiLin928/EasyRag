// 前端调试脚本 - 在浏览器控制台中运行

// 1. 检查环境变量
console.log('=== 环境变量 ===')
console.log('VITE_USE_MOCK:', import.meta.env.VITE_USE_MOCK)
console.log('VITE_API_BASE:', import.meta.env.VITE_API_BASE)

// 2. 检查 Store 状态
import { useToolStore } from './stores/tool'
import { useMcpStore } from './stores/mcp'
import { useSkillStore } from './stores/skill'

const toolStore = useToolStore()
const mcpStore = useMcpStore()
const skillStore = useSkillStore()

console.log('\n=== Store 状态 ===')
console.log('工具数量:', toolStore.tools.length)
console.log('工具列表:', toolStore.tools.map(t => t.name))
console.log('MCP数量:', mcpStore.mcps.length)
console.log('MCP列表:', mcpStore.mcps.map(m => m.name))
console.log('技能数量:', skillStore.skills.length)
console.log('技能列表:', skillStore.skills.map(s => s.name))

// 3. 手动加载数据
console.log('\n=== 手动加载数据 ===')
await toolStore.loadTools()
await mcpStore.loadMcps()
await skillStore.loadSkills()

console.log('加载后工具数量:', toolStore.tools.length)
console.log('加载后MCP数量:', mcpStore.mcps.length)
console.log('加载后技能数量:', skillStore.skills.length)

// 4. 检查 Mock 是否工作
console.log('\n=== 检查 Mock ===')
console.log('Mock 模式:', import.meta.env.VITE_USE_MOCK === 'true' ? '已启用' : '未启用')