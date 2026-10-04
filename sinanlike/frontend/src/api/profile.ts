import client from './client'

export interface ProfileRequest {
  user_id: string
  background: string
  target_role?: string
  current_level?: string
}

export interface ProgressResponse {
  profile: any | null
  progress: any[]
  mastery_report: any | null
}

export interface UserStateResponse {
  user_id: string
  profile: any | null
  memories: Array<{
    memory_id: string
    memory_type: string
    content: string
    importance: number
    created_at: string
  }>
  mastery: any | null
  weak_point_titles: string[]
  progress: any[]
  stats: {
    total_skills: number
    attempted_skills: number
    mastered_skills: number
    weak_skills: number
    questions_answered: number
  }
}

export function createProfile(payload: ProfileRequest): Promise<{ profile: any }> {
  return client.post('/profiles', payload) as unknown as Promise<{ profile: any }>
}

export function getProgress(userId: string): Promise<ProgressResponse> {
  return client.get(`/progress/${userId}`) as unknown as Promise<ProgressResponse>
}

export function getTrainingReport(userId: string): Promise<{ report: any }> {
  return client.post('/training/report', { user_id: userId }) as unknown as Promise<{ report: any }>
}

export function getUserState(userId: string): Promise<UserStateResponse> {
  return client.get(`/users/${userId}/state`) as unknown as Promise<UserStateResponse>
}

export function getTrainingPlan(userId: string): Promise<{ plan: string; weak_point_titles: string[] }> {
  return client.post('/training/plan', { user_id: userId }) as unknown as Promise<{ plan: string; weak_point_titles: string[] }>
}

export function exportUserData(userId: string): Promise<Record<string, any>> {
  return client.get(`/users/${userId}/export`) as unknown as Promise<Record<string, any>>
}

export function deleteUserData(userId: string): Promise<{ status: string; user_id: string }> {
  return client.delete(`/users/${userId}/data`) as unknown as Promise<{ status: string; user_id: string }>
}
