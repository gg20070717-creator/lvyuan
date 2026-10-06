import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import { checkBackendHealth } from '@/api/client'
import { useAccountsStore } from '@/stores/accounts'

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
  const accounts = useAccountsStore()
  const userId = computed(() => accounts.userId)

  function getOrCreateSessionId(): string {
    const key = accounts.isSignedIn ? 'boc_session_id' : 'lvyuan_guest_session'
    const storage = accounts.isSignedIn ? localStorage : sessionStorage
    let id = storage.getItem(key)
    if (!id) {
      id = crypto.randomUUID()
      storage.setItem(key, id)
    }
    return id
  }
  const sessionId = ref(getOrCreateSessionId())
  watch(userId, () => { sessionId.value = getOrCreateSessionId() }, { flush: 'sync' })

  function newSession() {
    sessionId.value = crypto.randomUUID()
    if (accounts.isSignedIn) localStorage.setItem('boc_session_id', sessionId.value)
    else sessionStorage.setItem('lvyuan_guest_session', sessionId.value)
  }

  /** 打开应用默认使用新窗口对话：
   * 同一标签页内（sessionStorage 存活）刷新保持会话；新打开应用/新标签页 → 自动新建会话。
   * 旧会话仍可通过「历史对话」列表切换。 */
  function ensureFreshSession() {
    try {
      const openedKey = `boc_app_opened:${userId.value}`
      if (!sessionStorage.getItem(openedKey)) {
        newSession()
        sessionStorage.setItem(openedKey, '1')
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
