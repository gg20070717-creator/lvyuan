import type { AgentTrace } from '@/api/messages'

export const WORKFLOW_STEPS = [
  { id: 'planning', label: '理解目标' }, { id: 'dispatch', label: '确定分工' },
  { id: 'collaboration', label: '协作执行' }, { id: 'delivery', label: '汇总交付' },
]
const aliases: Record<string, string> = { draft: 'text_generator', trainer: 'training_analyzer', analyzer: 'training_analyzer', essay: 'essay_question', planner: 'learning_planner' }
export function canonicalAgent(id: string) { return aliases[id] || id }
export function lastAgentEvents(trace: AgentTrace[]) {
  const last: Record<string, AgentTrace> = {}
  // 分工完成事件同时结束管家的本轮判断；等待工具返回期间不计入工作数量。
  for (const ev of trace) last[canonicalAgent(ev.agent)] = ev
  return last
}
export function workflowStates(trace: AgentTrace[], terminal: '' | 'done' | 'failed') {
  const latest = trace.at(-1)
  const current = latest ? latest.step || (latest.agent === 'concierge' ? 'planning' : 'collaboration') : terminal === 'failed' ? 'planning' : undefined
  return WORKFLOW_STEPS.map(step => {
    const events = trace.filter(ev => ev.step === step.id)
    let state = 'pending'
    if (terminal === 'done') state = events.length ? (events.some(e => e.status === 'failed') ? 'warning' : 'done') : 'skipped'
    else if (step.id === current) state = terminal === 'failed' ? 'failed' : 'working'
    else if (events.length) state = events.at(-1)?.status === 'failed' ? 'failed' : 'done'
    return { ...step, state }
  })
}
