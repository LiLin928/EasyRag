// 工具 Mock 数据
import type { Tool, ToolTestResult } from '@/types/tool'

// Mock 工具列表
export const mockTools: Tool[] = [
  {
    id: 'tool1',
    name: '天气查询',
    type: 'HTTP',
    desc: '根据城市名称查询当前天气情况',
    sig: 'getWeather(city: string): Promise<WeatherData>',
    enabled: true,
    params: [
      { n: 'city', t: 'string', d: '北京' },
      { n: 'unit', t: 'string', d: 'celsius' }
    ],
    auth: { mode: 'none', key: '' },
    createdAt: '2026-07-25 10:30:00'
  },
  {
    id: 'tool2',
    name: '只读SQL查询',
    type: 'HTTP',
    desc: '执行只读SQL查询，返回查询结果（仅SELECT）',
    sig: 'executeReadOnlyQuery(sql: string, db: string): Promise<QueryResult>',
    enabled: true,
    params: [
      { n: 'sql', t: 'string', d: 'SELECT * FROM users LIMIT 10' },
      { n: 'db', t: 'string', d: 'primary' }
    ],
    auth: { mode: 'apikey', key: 'sk-xxxxxxxxxxxx' },
    createdAt: '2026-07-26 14:20:00'
  },
  {
    id: 'tool3',
    name: '邮件通知',
    type: '内置',
    desc: '发送邮件通知给指定收件人',
    sig: 'sendEmail(to: string[], subject: string, body: string): Promise<SendResult>',
    enabled: false,
    params: [
      { n: 'to', t: 'array', d: '[]' },
      { n: 'subject', t: 'string', d: '' },
      { n: 'body', t: 'string', d: '' }
    ],
    auth: { mode: 'none', key: '' },
    createdAt: '2026-07-27 09:15:00'
  },
  {
    id: 'tool4',
    name: '数据换算',
    type: 'Python',
    desc: '执行Python脚本进行数据格式转换和计算',
    sig: 'convertData(data: any, fromFormat: string, toFormat: string): Promise<any>',
    enabled: true,
    params: [
      { n: 'data', t: 'object', d: '{}' },
      { n: 'fromFormat', t: 'string', d: 'json' },
      { n: 'toFormat', t: 'string', d: 'csv' }
    ],
    auth: { mode: 'bearer', key: 'Bearer xxxxxxxxxxxxx' },
    createdAt: '2026-07-28 16:45:00'
  }
]

// 模拟测试结果
export function createMockTestResult(toolId: string, args: Record<string, any>): ToolTestResult {
  const tool = mockTools.find(t => t.id === toolId)

  if (!tool) {
    return {
      success: false,
      error: '工具不存在',
      duration: 0
    }
  }

  // 模拟延迟
  const duration = Math.floor(Math.random() * 1000) + 500

  // 根据不同工具返回不同结果
  switch (tool.name) {
    case '天气查询':
      return {
        success: true,
        data: {
          city: args.city || '北京',
          temperature: Math.floor(Math.random() * 30) + 5,
          weather: ['晴', '多云', '阴', '小雨'][Math.floor(Math.random() * 4)],
          humidity: Math.floor(Math.random() * 50) + 30,
          wind: Math.floor(Math.random() * 5) + 1
        },
        duration
      }

    case '只读SQL查询':
      return {
        success: true,
        data: {
          columns: ['id', 'name', 'email', 'created_at'],
          rows: [
            { id: 1, name: '张三', email: 'zhangsan@example.com', created_at: '2026-07-01' },
            { id: 2, name: '李四', email: 'lisi@example.com', created_at: '2026-07-02' },
            { id: 3, name: '王五', email: 'wangwu@example.com', created_at: '2026-07-03' }
          ],
          total: 3
        },
        duration
      }

    case '邮件通知':
      return {
        success: true,
        data: {
          messageId: 'msg_' + Date.now(),
          to: args.to || [],
          subject: args.subject || '',
          sentAt: new Date().toISOString()
        },
        duration
      }

    case '数据换算':
      return {
        success: true,
        data: {
          originalFormat: args.fromFormat || 'json',
          targetFormat: args.toFormat || 'csv',
          convertedData: 'id,name,value\n1,测试,100\n2,示例,200',
          recordCount: 2
        },
        duration
      }

    default:
      return {
        success: false,
        error: '未知工具类型',
        duration
      }
  }
}
