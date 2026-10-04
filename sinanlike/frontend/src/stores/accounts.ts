import { defineStore } from 'pinia'
import { ref } from 'vue'
import { deleteUserData } from '@/api/profile'
import { fetchOnboardingGroups, submitOnboarding } from '@/api/onboarding'

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

function uid(): string {
  return (crypto as any).randomUUID ? crypto.randomUUID() : 'u_' + Date.now() + '_' + Math.random().toString(36).slice(2, 10)
}
function lsGet(k: string): string { try { return localStorage.getItem(k) || '' } catch { return '' } }
function lsSet(k: string, v: string) { try { localStorage.setItem(k, v) } catch { /* ignore */ } }

function readAccounts(): Account[] {
  try { return JSON.parse(lsGet(LS_ACCOUNTS) || '[]') || [] } catch { return [] }
}
function writeAccounts(list: Account[]) { lsSet(LS_ACCOUNTS, JSON.stringify(list)) }

export const useAccountsStore = defineStore('accounts', () => {
  const accounts = ref<Account[]>([])
  const activeId = ref('')

  function ensureAccounts(): void {
    let list = readAccounts()
    if (!list.length) {
      // 迁移：现有单用户（boc_user_id）→ 账户 1，并保留其会话/技能会话/引导标记
      const legacyId = lsGet('boc_user_id') || uid()
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
    if (!act || !list.some((a) => a.id === act)) act = list[0].id
    activeId.value = act
  }

  const current = (): Account => accounts.value.find((a) => a.id === activeId.value) || accounts.value[0]
  const currentName = (): string => current()?.name || '账户'

  /** 切换账户：先保存当前账户本地键，再恢复目标账户键，最后整页重载让所有状态以新账户重建 */
  function switchTo(id: string): void {
    ensureAccounts()
    if (id === activeId.value) return
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
    location.reload()
  }

  /** 新建账户：可选测试画像一键种好，或从 0 开始重新做引导题 */
  async function createAccount(opts: { name?: string; answers?: Record<string, string> } = {}): Promise<void> {
    ensureAccounts()
    backupActive()
    const n = accounts.value.length + 1
    const acct: Account = {
      id: uid(),
      name: opts.name || `账户 ${n}`,
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
    location.reload()
  }

  function createNew(): void { void createAccount() }

  /** 删除当前账户：清服务端数据 + 移除本地账户条目（删最后一个则重建账户1） */
  async function removeCurrent(): Promise<void> {
    ensureAccounts()
    const acct = current()
    if (!acct) return
    try { await deleteUserData(acct.id) } catch (e) { /* ignore */ }
    let list = accounts.value.filter((a) => a.id !== acct.id)
    if (!list.length) {
      const fresh: Account = { id: uid(), name: '账户 1', session: uid(), kp: '{}', done: '0', created_at: new Date().toISOString() }
      list = [fresh]
    }
    const next = list[0]
    accounts.value = list
    activeId.value = next.id
    lsSet(LS_ACTIVE, next.id)
    lsSet('boc_user_id', next.id)
    lsSet(K_SESSION, next.session || uid())
    lsSet(K_KP, next.kp || '{}')
    lsSet(K_DONE, next.done || '0')
    writeAccounts(accounts.value)
    location.reload()
  }

  /** 清空当前账户全部积累（服务端按 user_id 删除 + 本地键重置为全新） */
  async function clearCurrent(): Promise<void> {
    ensureAccounts()
    const acct = current()
    if (!acct) return
    try { await deleteUserData(acct.id) } catch { /* ignore */ }
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
    const a = current()
    if (!a) return
    a.session = lsGet(K_SESSION) || a.session || uid()
    a.kp = lsGet(K_KP) || a.kp || '{}'
    a.done = lsGet(K_DONE) || a.done || '0'
  }

  return { accounts, activeId, ensureAccounts, current, currentName, switchTo, createAccount, createNew, clearCurrent, removeCurrent }
})
