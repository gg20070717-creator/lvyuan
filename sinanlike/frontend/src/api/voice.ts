import client from './client'

export interface VoiceHotspot {
  id: string
  name: string
  yaw: number
  pitch: number
  point_index: number
  knowledge_point_id: string | null
  point: string
}

export interface VoiceScene {
  scene_id: string
  title: string
  location: string
  task: string
  duration_sec: number
  points: string[]
  knowledge: string[]
  knowledge_point_ids: string[]
  panorama: string | null
  hotspots: VoiceHotspot[]
}

export interface VoiceReport {
  total_score: number
  coverage: { total: number; covered: string[]; missed: string[]; coverage_score: number }
  strengths: string[]
  weaknesses: string[]
  suggestions: string[]
  summary: string
  learn: { keyword: string; knowledge_point_ids: string[] }
}

export function getVoiceScenes(): Promise<{ scenes: VoiceScene[] }> {
  return client.get('/voice/scenes') as unknown as Promise<{ scenes: VoiceScene[] }>
}

export interface VoiceSpeechMetrics {
  char_count: number
  speech_duration: number
  speech_rate: number
  pause_count: number
  pause_seconds: number
  max_pause: number
}

export function transcribeAudio(file: Blob, filename = 'guide.webm'): Promise<{ text: string; language: string; duration: number; speech: VoiceSpeechMetrics }> {
  const fd = new FormData()
  fd.append('file', file, filename)
  // 必须显式声明 multipart：axios 实例默认 Content-Type 是 application/json，
  // 若不带 multipart 头，FastAPI 会收不到 file 字段返回 422（已实测三种方式验证）。
  return client.post('/voice/transcribe', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }) as unknown as Promise<{ text: string; language: string; duration: number; speech: VoiceSpeechMetrics }>
}

export function evaluateVoice(payload: { scene_id: string; transcript: string; hotspot_id?: string }): Promise<{
  scene: VoiceScene
  transcript: string
  report: VoiceReport
}> {
  return client.post('/voice/evaluate', payload) as unknown as Promise<{
    scene: VoiceScene
    transcript: string
    report: VoiceReport
  }>
}

// ── 学习翻译 / 多语种发音（旅鸢讲解 · 个性化资源） ──
export function translateLearnText(
  text: string,
  lang: string,
  mode: 'plain' | 'markdown' = 'plain',
): Promise<{ translated: string; lang: string; mode: string }> {
  return client.post('/voice/translate', { text, lang, mode }) as unknown as Promise<{ translated: string; lang: string; mode: string }>
}

export function speakLearnText(
  text: string,
  lang: string,
): Promise<{ audio_b64: string; transcript: string; lang: string; voice: string }> {
  return client.post('/voice/speak', { text, lang }) as unknown as Promise<{ audio_b64: string; transcript: string; lang: string; voice: string }>
}
