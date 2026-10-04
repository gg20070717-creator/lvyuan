import client from './client'
import type { TeachingSnapshot } from './messages'

/**
 * 获取当前会话的教学状态（主题/阶段/难度/最近一题）。
 * 用于对话页进入时的教学条初始化。
 */
export async function getTeachingState(
  sessionId: string,
  userId: string,
): Promise<TeachingSnapshot | null> {
  try {
    const data = (await client.get('/teaching/state', {
      params: { session_id: sessionId, user_id: userId },
    })) as TeachingSnapshot
    return data
  } catch {
    return null
  }
}

export interface DifficultyPoint {
  seq: number
  difficulty_level: number
  correct: boolean
}

export interface DifficultyCurve {
  points: DifficultyPoint[]
  current: {
    question_id: string
    difficulty_level: number | null
    knowledge_point_title: string
    stage: string
  }
  last_answer_correct: boolean | null
  next_difficulty_level: number | null
  all_done: boolean
  stars_max: number
  status: {
    code: 'idle' | 'good' | 'up' | 'weak' | 'all_done'
    text: string
    can_sandbox: boolean
  }
}

/** 获取当前教学会话的动态难度曲线（难度点序列 + 当前状态提示） */
export interface MasteryState {
  mastery: number
  objective: number
  objective_done?: number
  objective_total?: number
  concierge: number
  sandbox: number
  baseline?: number | null
  is_inbound?: boolean
  weights?: Record<string, number>
}

/** 某个技能点的综合掌握度明细（客观/管家/沙盒 + 综合分） */
export async function getMasteryState(
  userId: string,
  nodeId: string,
): Promise<MasteryState> {
  const data = (await client.get('/mastery/state', {
    params: { user_id: userId, node_id: nodeId },
  })) as MasteryState
  return data
}

export async function getDifficultyCurve(
  sessionId: string,
  userId: string,
): Promise<DifficultyCurve> {
  const data = (await client.get('/teaching/difficulty-curve', {
    params: { session_id: sessionId, user_id: userId },
  })) as DifficultyCurve
  return data
}
