// 技能 Mock 数据
import type { Skill } from '@/types/skill'

// Mock 技能列表
export const mockSkills: Skill[] = [
  {
    id: 'skill1',
    ico: '📋',
    name: '标书资质审查 SOP',
    scope: 'builtin',
    ver: '1.0.0',
    desc: '标准化审查投标文件中的企业资质证书，确保符合招标文件要求',
    trigger: '当用户询问资质审查、证书有效性检查时触发',
    prompt: `你是一位专业的标书资质审查专家。你的任务是：

1. 识别投标文件中的企业资质证书类型
2. 检查证书的有效期和覆盖范围
3. 对比招标文件中的资质要求
4. 标注不符合项和风险点

请严格按照以下标准执行审查流程。`,
    tools: ['tool1'],
    docs: ['doc1', 'doc2'],
    wfs: [],
    examples: [
      {
        q: '请审查这份投标文件中的企业资质证书',
        a: '已识别到以下资质证书：营业执照、ISO9001认证、建筑业企业资质证书。其中建筑业资质证书将于3个月后到期，建议更新。'
      },
      {
        q: '这个公司的资质是否满足招标要求？',
        a: '经审查，该企业具备招标文件要求的所有资质条件，但需注意安全生产许可证即将到期。'
      }
    ],
    scripts: [
      {
        name: '资质证书识别.js',
        content: `// 从文本中识别企业资质证书
const patterns = ['营业执照', 'ISO\\d+', '资质证书', '安全生产许可证']
const found = []
for (const p of patterns) {
  const m = input.text.match(new RegExp(p, 'g'))
  if (m) found.push(...m)
}
return [...new Set(found)]`
      },
      {
        name: '有效期计算.js',
        content: `// 计算证书剩余有效天数，标注预警等级
const today = new Date()
const expire = new Date(input.expireDate)
const days = Math.ceil((expire - today) / 86400000)
return {
  daysRemaining: days,
  expiringSoon: days <= 90,
  level: days <= 30 ? '紧急' : days <= 90 ? '预警' : '正常'
}`
      }
    ],
    budget: 5000,
    used: 1240
  },
  {
    id: 'skill2',
    ico: '⚠️',
    name: '合同风险清单',
    scope: 'builtin',
    ver: '1.2.0',
    desc: '自动识别合同条款中的法律风险、商务风险和操作风险',
    trigger: '当用户需要合同审查、风险识别时触发',
    prompt: `你是一位资深的合同风险审查专家。请按照以下维度分析合同：

1. 法律风险：条款合法性、违约责任、争议解决
2. 商务风险：付款条件、交付标准、验收标准
3. 操作风险：履约能力、不可抗力、保密义务

对每个风险点标注等级（高/中/低）并给出修改建议。`,
    tools: ['tool2'],
    docs: ['doc4'],
    wfs: [],
    examples: [
      {
        q: '请帮我审查这份采购合同的风险',
        a: '发现3处高风险：1）违约金比例过高（20%）；2）验收标准过于模糊；3）缺少不可抗力条款。建议调整。'
      }
    ],
    scripts: [
      {
        name: '风险条款提取.js',
        content: `// 按关键词提取合同中的潜在风险条款
const keywords = ['违约', '赔偿', '解除', '不可抗力', '自动续约']
const clauses = input.text.split(/[；;\\n]/)
return clauses.filter(c => keywords.some(k => c.includes(k)))`
      },
      {
        name: '风险等级评估.js',
        content: `// 根据条款命中关键词评估风险等级
const weights = { 违约金: 3, 赔偿: 2, 解除: 2, 续约: 1 }
let score = 0
for (const [k, w] of Object.entries(weights)) {
  if (input.clause.includes(k)) score += w
}
return { score, level: score >= 5 ? '高' : score >= 3 ? '中' : '低' }`
      }
    ],
    budget: 8000,
    used: 3560
  },
  {
    id: 'skill3',
    ico: '📊',
    name: '研报摘要规范',
    scope: 'custom',
    ver: '1.0.0',
    desc: '按照固定格式生成行业研究报告的标准化摘要',
    trigger: '当用户需要研报摘要、文档总结时触发',
    prompt: `请按照以下格式生成研报摘要：

【核心观点】（3-5个要点）
【数据支撑】（关键数据和图表）
【行业趋势】（发展方向和预测）
【投资建议】（风险评估和建议）

保持客观中立，标注数据来源。`,
    tools: [],
    docs: [],
    wfs: [],
    examples: [
      {
        q: '生成这份AI行业研报的摘要',
        a: '【核心观点】1）大模型商业化加速；2）垂直领域应用爆发；3）算力需求持续增长。【数据支撑】市场规模预计2026年达XX亿元。【投资建议】关注基础设施层和垂直应用层。'
      }
    ],
    scripts: [],
    budget: 3000,
    used: 890
  },
  {
    id: 'skill4',
    ico: '🎧',
    name: '客服升级流程',
    scope: 'custom',
    ver: '1.1.0',
    desc: '标准化客户投诉升级处理流程，确保问题及时解决',
    trigger: '当客户投诉、问题升级时触发',
    prompt: `你是客户服务升级处理专家。按照以下流程处理：

1. 倾听并记录问题详情
2. 判断问题等级（P0-P3）
3. 根据等级匹配处理时效和权限
4. 升级到对应负责人
5. 跟踪处理进度并反馈

保持专业、耐心、同理心。`,
    tools: ['tool3'],
    docs: [],
    wfs: [],
    examples: [
      {
        q: '客户投诉系统故障无法使用',
        a: '已识别为P0级问题，已升级至技术负责人，承诺30分钟内响应，2小时内解决。'
      }
    ],
    scripts: [
      {
        name: '问题分级.js',
        content: `// 根据影响范围与紧急度判定问题等级 P0-P3
const { affectedUsers, downtimeMin } = input
if (affectedUsers > 100 && downtimeMin > 30) return 'P0'
if (affectedUsers > 10 || downtimeMin > 15) return 'P1'
if (affectedUsers > 1) return 'P2'
return 'P3'`
      },
      {
        name: '升级路由.js',
        content: `// 按问题等级路由到对应处理人并匹配 SLA
const routing = {
  P0: { owner: '技术总监', sla: 30 },
  P1: { owner: '研发负责人', sla: 60 },
  P2: { owner: '值班工程师', sla: 240 },
  P3: { owner: '客服组', sla: 1440 }
}
return routing[input.level] || routing.P3`
      }
    ],
    budget: 4000,
    used: 2100
  }
]
