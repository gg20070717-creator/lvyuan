import client, { ApiErrorType } from './client'

export interface TeachingTopic {
  id: string
  title: string
}

export interface TeachingQuiz {
  question_id: string
  prompt: string
  options?: string[]           // 选择题才有；简答题无选项
  difficulty: string
  difficulty_level?: number  // 题库难度 1-5（星级展示）
  knowledge_point_title: string
  type?: 'choice' | 'essay'    // 选择题 / 简答题（缺省视为 choice）
  rubric?: string              // 简答题参考答案要点（可选展示）
  progress?: { done: number; total: number; exhausted: boolean }  // 主题选择题进度（done/total；exhausted=已做完）
}

/** 教学会话状态快照（一对一教学闭环：主题/阶段/最近一题） */
export interface TeachingSnapshot {
  session_id: string
  stage: 'goal_setting' | 'teaching' | 'checking' | 'practicing' | 'feedback' | 'closing' | 'idle' | string
  depth: string
  topics: TeachingTopic[]
  consecutive_correct: number
  consecutive_incorrect: number
  last_quiz: TeachingQuiz | null
  topic_done?: boolean
  topic_finished?: boolean
}

/** 实时多 Agent 工作轨迹节点（GET /tasks/{id} 流式返回，基于真实执行） */
export interface AgentTrace {
  agent: string       // 内部 agent 键（concierge/retrieval/draft/review/white_hat...）
  name: string        // 中文显示名（如 旅鸢管家 / 白帽 · 事实）
  role: string        // 当前动作说明
  status: 'working' | 'done' | 'failed'
  detail?: string     // 附加结果简述
  ts?: number
}

export interface MessagePayload {
  user_id: string
  session_id: string
  content: string
  knowledge_point_id?: string   // 硬挂钩：Agent 锁定该技能点教学
}

export interface MessageResult {
  task_id: string
  status: string
  content: string
  review: string
  tool_calls: string[]
  assets: Array<{ asset_id: string; title: string; asset_type: string }>
  trace?: AgentTrace[]
  teaching?: TeachingSnapshot | null
}

export interface TaskStatus {
  task_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  phase: 'queued' | 'working' | 'reviewing' | 'done' | 'failed'
  content: string
  review: string
  error: string
  tool_calls: string[]
  assets: Array<{ asset_id: string; title: string; asset_type: string }>
  trace?: AgentTrace[]
  teaching?: TeachingSnapshot | null
}

export type TaskPhase = TaskStatus['phase']

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * 发送消息（异步任务）并回调轮询阶段：
 * 1. POST /messages 入队，立即拿到 task_id
 * 2. 轮询 GET /tasks/{task_id} 直到 completed / failed，每次轮询回调 onPhase(task.phase)
 *    （queued / working / reviewing / done / failed），供前端展示任务阶段提示条。
 * 长路径（生成讲义+六帽审查）可长达数分钟，这里按 5s 间隔最多轮询 ~12 分钟。
 */
export async function sendMessageWithPhase(
  payload: MessagePayload,
  onPhase?: (phase: TaskPhase) => void,
  onTrace?: (trace: AgentTrace[]) => void,
): Promise<MessageResult> {
  const enqueued = (await client.post('/messages', payload)) as any
  const taskId = enqueued.task_id
  if (!taskId) {
    return enqueued as MessageResult
  }

  const maxTries = 480 // 480 × 1.5s ≈ 12 分钟
  for (let i = 0; i < maxTries; i++) {
    let task: TaskStatus
    try {
      task = (await client.get(`/tasks/${taskId}`)) as TaskStatus
    } catch (e: any) {
      // 任务不存在：多半是后端在任务执行期间热重载/重启，内存任务表被清空
      if (e?.response?.status === 404) {
        const lost = new Error('任务不存在（后端可能在请求期间热重载/重启）') as any
        lost._apiError = {
          type: ApiErrorType.TASK_LOST,
          message: '后端在任务执行期间重启，任务已中断，请重新发送',
          statusCode: 404,
          originalError: e,
        }
        throw lost
      }
      throw e
    }
    onPhase?.(task.phase)
    onTrace?.(task.trace || [])
    if (task.status === 'completed') {
      return {
        task_id: task.task_id,
        status: task.status,
        content: task.content,
        review: task.review,
        tool_calls: task.tool_calls || [],
        assets: task.assets || [],
        trace: task.trace || [],
        teaching: task.teaching ?? null,
      }
    }
    if (task.status === 'failed') {
      throw new Error(task.error || '任务处理失败')
    }
    await sleep(1500)
  }
  throw new Error('任务处理超时，请稍后重试')
}

/**
 * 发送消息（异步任务），兼容旧调用：不关心阶段时直接使用本函数。
 * 需要实时阶段回调请使用 sendMessageWithPhase。
 */
export async function sendMessage(payload: MessagePayload): Promise<MessageResult> {
  return sendMessageWithPhase(payload)
}
