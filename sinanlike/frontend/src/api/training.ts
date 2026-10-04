import client from './client'
import type { Question } from './knowledge'

export interface QuizRequest {
  knowledge_point_ids: string[]
  difficulty: string
  book?: string
  chapter?: string
  limit?: number
}

export interface SubmissionRequest {
  user_id: string
  question_id: string
  answer: string
}

export interface SubmissionResult {
  submission: {
    submission_id: string
    user_id: string
    question_id: string
    score: number
    correct: boolean
    feedback: string
    misconception_tags: string[]
  }
  correct: boolean
  mastery_report: Record<string, any>
  adjustment: {
    action: 'advance' | 'downgrade' | 'maintain'
    knowledge_point_ids: string[]
  }
}

export function generateQuiz(payload: QuizRequest): Promise<{ questions: Question[] }> {
  return client.post('/training/quizzes', payload) as unknown as Promise<{ questions: Question[] }>
}

export function randomQuiz(payload: QuizRequest): Promise<{ questions: Question[] }> {
  return client.post('/training/random', payload) as unknown as Promise<{ questions: Question[] }>
}

export function submitAnswer(payload: SubmissionRequest): Promise<SubmissionResult> {
  return client.post('/training/submissions', payload) as unknown as Promise<SubmissionResult>
}

// ── 错题本 ──
export interface WrongAnswerItem {
  question_id: string
  knowledge_point_id: string | null
  skill_title: string
  prompt: string
  options: string[]
  user_answer: string
  correct_answer: string
  explanation: string
  difficulty: string
  source: string
  wrong_count: number
  last_wrong_at: string
}

export interface WrongAnswersResponse {
  user_id: string
  total: number
  by_skill: Array<{ skill_title: string; question_count: number; wrong_count: number }>
  items: WrongAnswerItem[]
}

export function getWrongAnswers(userId: string, limit = 100): Promise<WrongAnswersResponse> {
  return client.get('/training/wrong-answers', { params: { user_id: userId, limit } }) as unknown as Promise<WrongAnswersResponse>
}

export function deleteWrongAnswer(userId: string, questionId: string): Promise<{ ok: boolean }> {
  return client.delete('/training/wrong-answers', { params: { user_id: userId, question_id: questionId } }) as unknown as Promise<{ ok: boolean }>
}
