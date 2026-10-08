import client from './client'
import type { AgentTrace, TaskStatus, TeachingSnapshot } from './messages'

export interface AgentInfo { id: string; name: string; role: string; group: string; icon: string }
export interface LearningStatus {
  teaching: TeachingSnapshot | null
  mastery: number | null
  profile_done: boolean
  quiz_count: number
  questions_answered: number
  practice_count: number
  specialty_count: number
  integrated_count: number
  recommendation: { label: string; reason: string; path: string }
}
export function getAgentCatalog(): Promise<{ agents: AgentInfo[]; reserved: string[] }> {
  return client.get('/agents/catalog') as any
}
export function getLearningStatus(user_id: string, session_id: string): Promise<LearningStatus> {
  return client.get('/learning/status', { params: { user_id, session_id } }) as any
}
/** 实战也通过同一任务轮询接口读取真实轨迹。 */
export async function waitForTask<T>(taskId: string, onTrace?: (trace: AgentTrace[]) => void): Promise<T> {
  for (let i = 0; i < 480; i++) {
    const task = await client.get(`/tasks/${taskId}`) as unknown as TaskStatus & { payload: T }
    onTrace?.(task.trace || [])
    if (task.status === 'completed') return task.payload
    if (task.status === 'failed') throw new Error(task.error || '协作任务失败')
    await new Promise(resolve => setTimeout(resolve, 1000))
  }
  throw new Error('协作任务处理超时，请稍后重试')
}
