import client from './client'

export interface SessionItem {
  session_id: string
  title: string
  message_count: number
  updated_at: string | null
}

export interface SessionMessage {
  role: 'user' | 'assistant'
  content: string
}

export function listSessions(userId: string): Promise<{ sessions: SessionItem[] }> {
  return client.get('/sessions', { params: { user_id: userId } }) as unknown as Promise<{ sessions: SessionItem[] }>
}

export function getSessionMessages(sessionId: string): Promise<{ messages: SessionMessage[] }> {
  return client.get(`/sessions/${sessionId}/messages`) as unknown as Promise<{ messages: SessionMessage[] }>
}
