/**
 * 工作流参数传递工具
 *
 * 提供节点间参数引用的核心能力：
 * - 获取上游节点（通过边关系）
 * - 获取节点输出参数列表（用于下拉选择）
 * - 构建上游可引用变量选项
 */
import type { WfNode, WfEdge, NodeType, OutputParamOption, OutputVariableMapping } from '@/types/workflow'
import { NODE_OUTPUT_PARAMS } from '@/types/workflow'

/**
 * 节点类型中文名映射
 */
const NODE_TYPE_LABELS: Record<string, string> = {
  start: '开始',
  end: '结束',
  condition: '条件分支',
  loop: '循环',
  human: '人工介入',
  variable_assign: '变量赋值',
  template_render: '模板渲染',
  llm: 'LLM 生成',
  rag: 'RAG 检索',
  code: '代码执行',
  http: 'HTTP 请求',
  tool: '外部工具'
}

/**
 * 获取节点的显示名
 */
export function getNodeDisplayName(node: WfNode): string {
  return node.name || NODE_TYPE_LABELS[node.type] || node.id
}

/**
 * 获取上游节点（通过边关系找到的前置节点）
 */
export function getUpstreamNodes(nodeId: string, nodes: WfNode[], edges: WfEdge[]): WfNode[] {
  const upstreamIds = edges
    .filter(e => e.target === nodeId)
    .map(e => e.source)
  return nodes.filter(n => upstreamIds.includes(n.id))
}

/**
 * 获取下游节点（通过边关系找到的后续节点）
 */
export function getDownstreamNodes(nodeId: string, nodes: WfNode[], edges: WfEdge[]): WfNode[] {
  const downstreamIds = edges
    .filter(e => e.source === nodeId)
    .map(e => e.target)
  return nodes.filter(n => downstreamIds.includes(n.id))
}

/**
 * 获取节点的输出参数列表
 *
 * 优先使用用户自定义的 output_variables，否则使用 NODE_OUTPUT_PARAMS 默认值
 */
export function getNodeOutputParams(node: WfNode): OutputParamOption[] {
  const displayName = getNodeDisplayName(node)
  const nodeType = node.type as NodeType

  // 优先使用用户自定义的 output_variables
  const customOutputs = node.data?.config?.output_variables as OutputVariableMapping[] | undefined
  const outputDefs = customOutputs?.length
    ? customOutputs
    : (NODE_OUTPUT_PARAMS[nodeType] || [{ name: 'result' }])

  return outputDefs.map(p => ({
    name: `${displayName}.${p.name}`,
    path: `\${${node.id}.${p.name}}`
  }))
}

/**
 * 获取开始节点的输入变量作为输出参数（开始节点的输入变量即为其产出）
 */
export function getStartNodeOutputParams(node: WfNode): OutputParamOption[] {
  const displayName = getNodeDisplayName(node)
  const inputVars = node.data?.config?.input_variables as Array<{ name: string }> | undefined
  if (inputVars?.length) {
    return inputVars.map(v => ({
      name: `${displayName}.${v.name}`,
      path: `\${${node.id}.${v.name}}`
    }))
  }
  return []
}

/**
 * 构建上游所有可引用变量选项（用于下拉选择）
 *
 * 遍历所有上游节点，收集它们的输出参数
 */
export function getUpstreamOutputOptions(
  nodeId: string,
  nodes: WfNode[],
  edges: WfEdge[]
): OutputParamOption[] {
  const upstreamNodes = getUpstreamNodes(nodeId, nodes, edges)
  return upstreamNodes.flatMap(node => {
    if (node.type === 'start') {
      return getStartNodeOutputParams(node)
    }
    return getNodeOutputParams(node)
  })
}

/**
 * 获取所有节点（除当前节点外）的输出参数（用于结束节点等）
 */
export function getAllNodesOutputOptions(
  currentNodeId: string,
  nodes: WfNode[]
): OutputParamOption[] {
  return nodes
    .filter(n => n.id !== currentNodeId && n.type !== 'end')
    .flatMap(node => {
      if (node.type === 'start') {
        return getStartNodeOutputParams(node)
      }
      return getNodeOutputParams(node)
    })
}
