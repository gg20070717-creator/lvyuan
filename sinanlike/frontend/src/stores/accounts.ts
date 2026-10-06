import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { deleteUserData } from '@/api/profile'
import { fetchOnboardingGroups, submitOnboarding } from '@/api/onboarding'
import { clearOnboardingDraft } from '@/utils/onboardingDraft'

export interface Account {
  id: string
  name: string
  session?: string      // 该账户的当前会话 id
  kp?: string           // 该账户的技能点会话表 JSON
  done?: string         // 该账户的 onboarding 完成标记
  created_at: string
}

const LS_ACCOUNTS = 'boc_accounts_v1'
const LS_ACTIVE = 'boc_active_account'
const K_SESSION = 'boc_session_id'
const K_KP = 'boc_kp_sessions'
const K_DONE = 'boc_onboarding_done'
const S_SIGNED_IN = 'lvyuan_signed_in_account'
const S_GUEST = 'lvyuan_guest_id'

function uid(): string {
  return (crypto as any).randomUUID ? crypto.randomUUID() : 'u_' + Date.now() + '_' + Math.random().toString(36).slice(2, 10)
}
function lsGet(k: string): string { try { return localStorage.getItem(k) || '' } catch { return '' } }
function lsSet(k: string, v: string) { try { localStorage.setItem(k, v) } catch { /* ignore */ } }
function ssGet(k: string): string { try { return sessionStorage.getItem(k) || '' } catch { return '' } }
function ssSet(k: string, v: string) { try { sessionStorage.setItem(k, v) } catch { /* ignore */ } }

function readAccounts(): Account[] {
  try { return JSON.parse(lsGet(LS_ACCOUNTS) || '[]') || [] } catch { return [] }
}
function writeAccounts(list: Account[]) { lsSet(LS_ACCOUNTS, JSON.stringify(list)) }

export const useAccountsStore = defineStore('accounts', () => {
  const accounts = ref<Account[]>([])
  const activeId = ref('')
  const signedInId = ref(ssGet(S_SIGNED_IN))
  const guestId = ssGet(S_GUEST) || uid()
  ssSet(S_GUEST, guestId)
  const isSignedIn = computed(() => !!signedInId.value && accounts.value.some((a) => a.id === signedInId.value))
  const userId = computed(() => isSignedIn.value ? signedInId.value : guestId)
  const flowOpen = ref(false)
  const flowStage = ref<'access' | 'onboarding'>('access')
  const returnTo = ref('/app/home')

  function ensureAccounts(): void {
    let list = readAccounts()
    if (!list.length && lsGet('boc_user_id')) {
      // 迁移：现有单用户（boc_user_id）→ 账户 1，并保留其会话/技能会话/引导标记
      const legacyId = lsGet('boc_user_id')
      list = [{
        id: legacyId,
        name: '账户 1',
        session: lsGet(K_SESSION) || uid(),
        kp: lsGet(K_KP) || '{}',
        done: lsGet(K_DONE) || '0',
        created_at: new Date().toISOString(),
      }]
      lsSet('boc_user_id', legacyId)
      writeAccounts(list)
    }
    accounts.value = list
    let act = lsGet(LS_ACTIVE)
    if (list.some((a) => a.id === signedInId.value)) act = signedInId.value
    if (!act || !list.some((a) => a.id === act)) act = list[0]?.id || ''
    if (!list.some((a) => a.id === signedInId.value)) signedInId.value = ''
    activeId.value = act
  }

  const current = (): Account | undefined => accounts.value.find((a) => a.id === activeId.value)
  const currentName = (): string => isSignedIn.value ? current()?.name || '学习账户' : '未登录'

  function openAccess(path = '/app/home') { returnTo.value = path; flowStage.value = 'access'; flowOpen.value = true }
  function openOnboarding(path = '/app/home') {
    if (!isSignedIn.value) { openAccess(path); return }
    returnTo.value = path; flowStage.value = 'onboarding'; flowOpen.value = true
  }
  function closeFlow() { flowOpen.value = false }
  function signOut() { backupActive(); signedInId.value = ''; ssSet(S_SIGNED_IN, ''); closeFlow() }

  /** 切换账户：保存当前账户本地键，再恢复目标账户键，由响应式身份更新各模块。 */
  function switchTo(id: string): void {
    ensureAccounts()
    if (id === signedInId.value && isSignedIn.value) return
    if (!accounts.value.some((a) => a.id === id)) return
    backupActive()
    activeId.value = id
    lsSet(LS_ACTIVE, id)
    const target = current()
    if (target) {
      lsSet('boc_user_id', target.id)
      lsSet(K_SESSION, target.session || uid())
      lsSet(K_KP, target.kp || '{}')
      lsSet(K_DONE, target.done || '0')
    }
    writeAccounts(accounts.value)
    signedInId.value = id
    ssSet(S_SIGNED_IN, id)
  }

  /** 新建账户：可选测试画像一键种好，或从 0 开始重新做引导题 */
  async function createAccount(opts: { name?: string; answers?: Record<string, string> } = {}): Promise<void> {
    ensureAccounts()
    backupActive()
    const n = accounts.value.length + 1
    const acct: Account = {
      id: uid(),
      name: opts.name?.trim().slice(0, 20) || `账户 ${n}`,
      session: uid(), kp: '{}', done: '0', created_at: new Date().toISOString(),
    }
    accounts.value.push(acct)
    activeId.value = acct.id
    lsSet(LS_ACTIVE, acct.id)
    lsSet('boc_user_id', acct.id)
    lsSet(K_SESSION, acct.session!)
    lsSet(K_KP, '{}')
    lsSet(K_DONE, '0')
    if (opts.answers) {
      try {
        const g = await fetchOnboardingGroups()
        const status: Record<string, string> = {}
        for (const gid of g.order || []) status[gid] = 'learning'
        const res = await submitOnboarding({ user_id: acct.id, answers: opts.answers, group_status: status })
        if (res && res.done) {
          acct.done = '1'
          lsSet(K_DONE, '1')
        }
      } catch (e) { /* 画像种入失败则按从 0 开始处理 */ }
    }
    writeAccounts(accounts.value)
    signedInId.value = acct.id
    ssSet(S_SIGNED_IN, acct.id)
  }

  function createNew(): void { void createAccount() }

  /** 删除当前账户，保留其它账户；删除最后一个后回到游客状态。 */
  async function removeCurrent(): Promise<void> {
    ensureAccounts()
    const acct = current()
    if (!acct) return
    try { await deleteUserData(acct.id) } catch (e) { /* ignore */ }
    clearOnboardingDraft(acct.id)
    const list = accounts.value.filter((a) => a.id !== acct.id)
    const next = list[0]
    accounts.value = list
    activeId.value = next?.id || ''
    lsSet(LS_ACTIVE, next?.id || '')
    lsSet('boc_user_id', next?.id || '')
    lsSet(K_SESSION, next?.session || '')
    lsSet(K_KP, next?.kp || '{}')
    lsSet(K_DONE, next?.done || '0')
    writeAccounts(accounts.value)
    signedInId.value = ''; ssSet(S_SIGNED_IN, '')
    location.reload()
  }

  /** 清空当前账户全部积累（服务端按 user_id 删除 + 本地键重置为全新） */
  async function clearCurrent(): Promise<void> {
    ensureAccounts()
    const acct = current()
    if (!acct) return
    try { await deleteUserData(acct.id) } catch { /* ignore */ }
    clearOnboardingDraft(acct.id)
    const session = uid()
    acct.session = session
    acct.kp = '{}'
    acct.done = '0'
    lsSet(K_SESSION, session)
    lsSet(K_KP, '{}')
    lsSet(K_DONE, '0')
    writeAccounts(accounts.value)
    location.reload()
  }

  function backupActive(): void {
    if (!isSignedIn.value) return
    const a = current()
    if (!a) return
    a.session = lsGet(K_SESSION) || a.session || uid()
    a.kp = lsGet(K_KP) || a.kp || '{}'
    a.done = lsGet(K_DONE) || a.done || '0'
  }

  ensureAccounts()
  return { accounts, activeId, isSignedIn, userId, flowOpen, flowStage, returnTo, openAccess, openOnboarding, closeFlow, signOut, ensureAccounts, current, currentName, switchTo, createAccount, createNew, clearCurrent, removeCurrent }
})
