import { defineStore } from 'pinia'
import { ref } from 'vue'
import { checkBackendHealth } from '@/api/client'

// ── 生成持久的用户标识 ──
function getOrCreateUserId(): string {
  const key = 'boc_user_id'
  let id = localStorage.getItem(key)
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem(key, id)
  }
  return id
}

export const useAppStore = defineStore('app', () => {
  // ── 侧栏折叠 ──
  const sidebarCollapsed = ref(false)

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  // ── 页面标题 ──
  const pageTitle = ref('首页')

  function setPageTitle(title: string) {
    pageTitle.value = title
  }

  // ── 用户身份（会话持久化，保证跨刷新连续） ──
  const userId = ref(getOrCreateUserId())

  function getOrCreateSessionId(): string {
    const key = 'boc_session_id'
    let id = localStorage.getItem(key)
    if (!id) {
      id = crypto.randomUUID()
      localStorage.setItem(key, id)
    }
    return id
  }
  const sessionId = ref(getOrCreateSessionId())

  function newSession() {
    sessionId.value = crypto.randomUUID()
    localStorage.setItem('boc_session_id', sessionId.value)
  }

  /** 打开应用默认使用新窗口对话：
   * 同一标签页内（sessionStorage 存活）刷新保持会话；新打开应用/新标签页 → 自动新建会话。
   * 旧会话仍可通过「历史对话」列表切换。 */
  function ensureFreshSession() {
    try {
      if (!sessionStorage.getItem('boc_app_opened')) {
        newSession()
        sessionStorage.setItem('boc_app_opened', '1')
      }
    } catch {
      /* sessionStorage 不可用（隐私模式等）则不强制新建 */
    }
  }

  // ── 后端连接状态 ──
  const backendOnline = ref(false)
  let healthCheckTimer: ReturnType<typeof setInterval> | null = null

  async function checkHealth(): Promise<boolean> {
    const ok = await checkBackendHealth()
    backendOnline.value = ok
    return ok
  }

  /** 启动定期健康检查（每 30 秒） */
  function startHealthCheck() {
    checkHealth() // 立即检查一次
    healthCheckTimer = setInterval(checkHealth, 30_000)
  }

  function stopHealthCheck() {
    if (healthCheckTimer) {
      clearInterval(healthCheckTimer)
      healthCheckTimer = null
    }
  }


  // ── 技能点专属对话：每个技能点一条独立会话（切走自动归档，回来可继续） ──
  const SKILL_MAP_KEY = 'boc_kp_sessions'

  function loadSkillSessions(): Record<string, string> {
    try {
      return JSON.parse(localStorage.getItem(SKILL_MAP_KEY) || '{}') || {}
    } catch {
      return {}
    }
  }

  /** 取（或新建）某技能点的专属会话 id，不切换当前活动会话 */
  function sessionForSkill(kpId: string): string {
    const map = loadSkillSessions()
    if (map[kpId]) return map[kpId]
    const sid = crypto.randomUUID()
    map[kpId] = sid
    try { localStorage.setItem(SKILL_MAP_KEY, JSON.stringify(map)) } catch { /* 忽略 */ }
    return sid
  }

  /** 激活某个会话为当前对话（会写入 localStorage，刷新/重开也能接着） */
  function activateSession(sid: string) {
    sessionId.value = sid
    try { localStorage.setItem('boc_session_id', sid) } catch { /* 忽略 */ }
  }

  return {
    sidebarCollapsed,
    toggleSidebar,
    pageTitle,
    setPageTitle,
    userId,
    sessionId,
    newSession,
    ensureFreshSession,
    sessionForSkill,
    activateSession,
    backendOnline,
    checkHealth,
    startHealthCheck,
    stopHealthCheck,
  }
})
