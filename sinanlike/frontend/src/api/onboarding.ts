import client from './client'

export interface OnbOption { id: string; label: string }
export interface OnbQuestion { id: string; question: string; options: OnbOption[] }

export interface OnbGroup { id: string; title: string; type: string; book_id: string; book_title: string; skill_count: number; skill_ids?: string[] }
export interface OnbDomain { id: string; title: string; groups: OnbGroup[] }

export interface OnbPersona {
  persona_id: string
  label: string
  summary: string
  description: string
  identity: string
  basis: string
  language: string
  goal: string
  pace: string
  style: string
  default_master_books?: string[]
}

export interface OnbState {
  user_id: string
  done: boolean
  profile: { persona?: OnbPersona; identity_answers?: Record<string, string>; group_status?: Record<string, string> } | null
}

export interface RouteStats { groups: number; before_start: number; learning_path: number; total_skills: number }
export interface RouteGroupRow {
  id: string
  title: string
  type?: string
  book_id?: string
  book_title?: string
  skill_count?: number
  skill_ids?: string[]
}

export interface LearningRoute {
  group_order: string[]
  groups?: RouteGroupRow[]
  before_start_skill_ids: string[]
  path_skill_ids: string[]
  stats: RouteStats
  note?: string
}
export interface PlanResult {
  ok: boolean
  version: number
  fallback: boolean
  attempts: number
  error: string
  note?: string
  route: LearningRoute
}

export interface QaQuestion { id: string; question: string; options: OnbOption[] }
export interface QaState {
  pending: boolean
  identity_done: boolean
  step: number
  total: number
  answers?: Record<string, string>
  question?: QaQuestion | null
  lead?: string
}

export async function getQaState(userId: string): Promise<QaState> {
  return (await client.get('/onboarding/qa/state', { params: { user_id: userId } })) as QaState
}

export async function answerQa(payload: { user_id: string; question_id: string; option_id: string }): Promise<QaState> {
  return (await client.post('/onboarding/qa/answer', payload)) as QaState
}

export async function fetchOnboardingQuestions(): Promise<OnbQuestion[]> {
  const r = (await client.get('/onboarding/questions')) as any
  return r.questions || []
}

export async function fetchOnboardingGroups(): Promise<{ domains: OnbDomain[]; total_groups: number; order: string[] }> {
  const r = (await client.get('/onboarding/groups')) as any
  return { domains: r.domains || [], total_groups: r.total_groups || 0, order: r.order || [] }
}

export async function fetchOnboardingState(userId: string): Promise<OnbState> {
  return (await client.get('/onboarding/state', { params: { user_id: userId } })) as OnbState
}

export async function getLatestLearningPath(userId: string): Promise<{ found: boolean; version?: number; status?: string; created_at?: string; route?: LearningRoute }> {
  return (await client.get('/learning-path/latest', { params: { user_id: userId } })) as any
}

export interface BlindSpot { group_id: string; group_title: string; book_title: string; book_id?: string; skills_total: number; weak_skills: number; avg_mastery: number }
export interface DomainGroup { id: string; title: string; mastered: boolean; avg_mastery: number; weak_skills: number; skills_total: number }
export interface DomainRadar { id: string; title: string; avg_mastery: number; groups: DomainGroup[] }
export interface BlindspotResult { domains: DomainRadar[]; blindspots: BlindSpot[] }
export interface OnbSnapshot { version: number; persona?: OnbPersona; source: string; created_at?: string }
export interface RecordsResult {
  persona?: OnbPersona | null
  updated_at?: string
  profile_snapshots: OnbSnapshot[]
  learning_paths: Array<{ version: number; status: string; note: string; created_at: string }>
}

export async function getBlindspots(userId: string): Promise<BlindspotResult> {
  return (await client.get('/learning-path/blindspots', { params: { user_id: userId } })) as BlindspotResult
}

export async function refreshProfile(userId: string): Promise<{ ok: boolean; version: number; persona: OnbPersona }> {
  return (await client.post('/onboarding/refresh-profile', { user_id: userId })) as any
}

export interface InsightText { persona_analysis: string; blindspot_analysis: string; next_actions: string }

export async function getInsight(userId: string): Promise<{ ok: boolean; insight: InsightText }> {
  return (await client.get('/onboarding/insight', { params: { user_id: userId } })) as any
}

export async function generateInsight(userId: string): Promise<{ ok: boolean; insight: InsightText }> {
  return (await client.post('/onboarding/insight', { user_id: userId })) as any
}

export async function getOnboardingRecords(userId: string): Promise<RecordsResult> {
  return (await client.get('/onboarding/records', { params: { user_id: userId } })) as any
}

export async function submitOnboarding(payload: {
  user_id: string
  answers: Record<string, string>
  group_status: Record<string, string>
}): Promise<{ ok: boolean; done: boolean; persona: OnbPersona; counts: any; group_status: Record<string, string> }> {
  return (await client.post('/onboarding/submit', payload)) as any
}

export async function planLearningPath(userId: string, feedback = ''): Promise<PlanResult> {
  return (await client.post('/learning-path/plan', { user_id: userId, feedback })) as PlanResult
}
