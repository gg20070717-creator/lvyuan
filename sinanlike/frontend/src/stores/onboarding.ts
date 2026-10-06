import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchOnboardingState, getQaState } from '@/api/onboarding'
import type { OnbPersona } from '@/api/onboarding'
import { clearOnboardingDraft, readOnboardingDraft } from '@/utils/onboardingDraft'

const LS_KEY = 'boc_onboarding_done'

export const useOnboardingStore = defineStore('onboarding', () => {
  const loading = ref(false)
  const loaded = ref(false)
  const done = ref(localStorage.getItem(LS_KEY) === '1' && !readOnboardingDraft(localStorage.getItem('boc_user_id') || ''))
  const identityDone = ref(false)
  const persona = ref<OnbPersona | null>(null)
  const groupStatus = ref<Record<string, string> | null>(null)
  const loadedUserId = ref('')
  let loadVersion = 0

  async function loadQa(userId: string): Promise<boolean> {
    try {
      const st = await getQaState(userId)
      if (loadedUserId.value === userId) identityDone.value = !!st.identity_done
    } catch { /* ignore */ }
    return identityDone.value
  }

  async function load(userId: string): Promise<boolean> {
    const version = ++loadVersion
    if (loadedUserId.value !== userId) { loaded.value = false; done.value = false; identityDone.value = false; persona.value = null; groupStatus.value = null }
    loadedUserId.value = userId
    loading.value = true
    try {
      const st = await fetchOnboardingState(userId)
      if (version !== loadVersion) return false
      // 提交画像后，服务端已有 profile；本地引导继续到路线确认后才结束。
      done.value = !!st.done && !readOnboardingDraft(userId)
      persona.value = st.profile?.persona ?? null
      groupStatus.value = st.profile?.group_status ?? null
      try { localStorage.setItem(LS_KEY, done.value ? '1' : '0') } catch { /* ignore */ }
      return done.value
    } catch {
      // 后端不可用：不阻塞（按已完成放行，避免误锁）
      return done.value
    } finally {
      if (version === loadVersion) { loaded.value = true; loading.value = false }
    }
  }

  function markDone(p: OnbPersona | null, gs: Record<string, string> | null) {
    done.value = true
    persona.value = p
    groupStatus.value = gs
    try { localStorage.setItem(LS_KEY, '1') } catch { /* ignore */ }
  }

  function reset() {
    clearOnboardingDraft(localStorage.getItem('boc_user_id') || '')
    done.value = false
    persona.value = null
    groupStatus.value = null
    try { localStorage.setItem(LS_KEY, '0') } catch { /* ignore */ }
  }
  function clearSession() {
    loadVersion++; loadedUserId.value = ''; loading.value = false; loaded.value = false
    done.value = false; identityDone.value = false; persona.value = null; groupStatus.value = null
  }

  return { loading, loaded, loadedUserId, done, identityDone, persona, groupStatus, load, loadQa, markDone, reset, clearSession }
})
