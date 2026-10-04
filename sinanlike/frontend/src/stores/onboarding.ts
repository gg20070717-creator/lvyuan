import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchOnboardingState, getQaState } from '@/api/onboarding'
import type { OnbPersona } from '@/api/onboarding'

const LS_KEY = 'boc_onboarding_done'

export const useOnboardingStore = defineStore('onboarding', () => {
  const loading = ref(false)
  const loaded = ref(false)
  const done = ref(localStorage.getItem(LS_KEY) === '1')
  const identityDone = ref(false)
  const persona = ref<OnbPersona | null>(null)
  const groupStatus = ref<Record<string, string> | null>(null)

  async function loadQa(userId: string): Promise<boolean> {
    try {
      const st = await getQaState(userId)
      identityDone.value = !!st.identity_done
    } catch { /* ignore */ }
    return identityDone.value
  }

  async function load(userId: string): Promise<boolean> {
    loading.value = true
    try {
      const st = await fetchOnboardingState(userId)
      done.value = !!st.done
      persona.value = st.profile?.persona ?? null
      groupStatus.value = st.profile?.group_status ?? null
      try { localStorage.setItem(LS_KEY, done.value ? '1' : '0') } catch { /* ignore */ }
      return done.value
    } catch {
      // 后端不可用：不阻塞（按已完成放行，避免误锁）
      return done.value
    } finally {
      loaded.value = true
      loading.value = false
    }
  }

  function markDone(p: OnbPersona | null, gs: Record<string, string> | null) {
    done.value = true
    persona.value = p
    groupStatus.value = gs
    try { localStorage.setItem(LS_KEY, '1') } catch { /* ignore */ }
  }

  function reset() {
    done.value = false
    persona.value = null
    groupStatus.value = null
    try { localStorage.setItem(LS_KEY, '0') } catch { /* ignore */ }
  }

  return { loading, loaded, done, identityDone, persona, groupStatus, load, loadQa, markDone, reset }
})
