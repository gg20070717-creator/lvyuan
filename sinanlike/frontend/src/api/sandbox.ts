/* 对话式沙盒 API 层 — 与后端 /sandbox/* 路由对应 */
import client from './client'
import { waitForTask } from './cooperation'
import type { AgentTrace } from './messages'

export interface SandboxTemplate {
  template_id: string
  mode: string
  // 解锁前置：非空表示需先完成这些分课（有评分记录）才能进入（如行前/行中/行后全流程）
  requires?: string[]
  title: string
  location: string
  task: string
  difficulty: number
  category: string
  opening: string
  stage_titles: string[]
  stage_count: number
}

export interface SandboxCustomer {
  name: string
  nationality: string
  age: string
  personality: string
  preferences: string
  quirks: string
  // 沙盒 v3：游客多维属性（后端动态生成，字段缺失时前端隐藏）
  gender?: string
  occupation?: string
  health?: string
  consumption?: string
  speech_style?: string
}

export interface SandboxMessage {
  role: 'customer' | 'guide'
  content: string
  mood?: string
}

export interface SandboxStage {
  index: number
  total: number
  title: string
  objective: string
  guide_hint: string
  kb_keywords: string[]
}

export interface RecommendedSkill {
  id: string
  title: string
  content: string
  source: string
}

export interface SandboxFeedback {
  strengths: string[]
  weaknesses: string[]
  suggestions: string[]
  skill_keywords: string[]
  recommended_skills: RecommendedSkill[]
  // 文化桥附加观察（不计入总分，仅报告展示）
  culture_bridge?: { score: number; summary: string } | null
}

export interface SandboxSession {
  session_id: string
  user_id: string
  mode: string
  template_id: string
  // 语音/外语训练：语言码（en/ja/...，空=传统文字）+ 音色
  language?: string
  voice?: string
  customer: SandboxCustomer
  messages: SandboxMessage[]
  stage: SandboxStage
  template: {
    template_id: string
    mode: string
    title: string
    location: string
    task: string
    difficulty: number
    category: string
    opening: string
  }
  status: string
  scene_complete: boolean
  score: number | null
  dims: Record<string, number> | null
  feedback: SandboxFeedback | null
  created_at: string
  ended_at: string | null
  // 沙盒 v2：游客心理状态（心情条展示）
  customer_state?: {
    trust: number
    mood: string
    hidden_revealed: boolean
    tension: boolean
  }
  // 沙盒 v3：场景结局（达成目标/搞砸/手动结束；字段缺失时前端优雅降级）
  scene_outcome?: 'success' | 'failed' | 'abandoned' | null
  scene_fail_reason?: string | null
}

export interface SandboxMessageResult {
  reply: string
  mood: string
  trust?: number
  hidden_revealed?: boolean
  tension?: boolean
  stage: number
  stage_total: number
  stage_title: string
  stage_advanced: boolean
  stage_tip: {
    type?: 'stage' | 'complete' | 'tension' | 'tension_resolved' | 'timeout'
    stage: number
    title: string
    objective?: string
    guide_hint?: string
    message?: string
    scene_complete?: boolean
  } | null
  scene_complete: boolean
}

export interface SandboxRecord {
  session_id: string
  mode: string
  template_id: string
  title: string
  score: number | null
  dims: Record<string, number> | null
  ended_at: string | null
}

export function listSandboxTemplates(mode?: string): Promise<{ templates: SandboxTemplate[] }> {
  return client.get('/sandbox/templates', { params: mode ? { mode } : {} }) as unknown as Promise<{ templates: SandboxTemplate[] }>
}

export async function createSandboxSession(user_id: string, template_id: string, language?: string, voice?: string, onTrace?: (trace:AgentTrace[]) => void): Promise<SandboxSession> {
  const result = await client.post('/sandbox/tasks/start', { user_id, template_id, language: language || '', voice: voice || '' }) as any
  return waitForTask<SandboxSession>(result.task_id, onTrace)
}

export interface SandboxVoiceMessageInput {
  role: 'guide' | 'customer'
  content: string
}

export function appendSandboxVoiceMessages(session_id: string, user_id: string, messages: SandboxVoiceMessageInput[]): Promise<SandboxSession> {
  return client.post(`/sandbox/sessions/${session_id}/voice-messages`, { user_id, messages }) as unknown as Promise<SandboxSession>
}

export function getSandboxSession(session_id: string): Promise<SandboxSession> {
  return client.get(`/sandbox/sessions/${session_id}`) as unknown as Promise<SandboxSession>
}

export async function sendSandboxMessage(session_id: string, user_id: string, content: string, onTrace?: (trace:AgentTrace[]) => void): Promise<SandboxMessageResult> {
  const result = await client.post(`/sandbox/sessions/${session_id}/messages/tasks`, { user_id, content }) as any
  return waitForTask<SandboxMessageResult>(result.task_id, onTrace)
}

export async function endSandboxSession(session_id: string, user_id: string, onTrace?: (trace:AgentTrace[]) => void): Promise<SandboxSession> {
  const result = await client.post(`/sandbox/sessions/${session_id}/end/tasks`, { user_id }) as any
  return waitForTask<SandboxSession>(result.task_id, onTrace)
}

export function listSandboxRecords(user_id: string): Promise<{ records: SandboxRecord[] }> {
  return client.get(`/sandbox/users/${user_id}/records`) as unknown as Promise<{ records: SandboxRecord[] }>
}
