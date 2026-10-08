import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { useAppStore } from './app'
import { useAccountsStore } from './accounts'
import { getAgentCatalog, getLearningStatus } from '@/api/cooperation'
import type { AgentInfo, LearningStatus } from '@/api/cooperation'
import type { AgentTrace, TeachingSnapshot } from '@/api/messages'
import { canonicalAgent, lastAgentEvents, workflowStates } from '@/utils/workflow'

export const useCooperationStore = defineStore('cooperation', () => {
  const app = useAppStore()
  const accounts = useAccountsStore()
  const catalog = ref<AgentInfo[]>([])
  const reserved = ref<string[]>([])
  const catalogError = ref(false)
  const title = ref('多智能体协作')
  const trace = ref<AgentTrace[]>([])
  const shownTrace = ref<AgentTrace[]>([])
  const running = ref(false)
  const terminal = ref<'' | 'done' | 'failed'>('')
  const visible = ref(false)
  const collapsed = ref(false)
  const error = ref('')
  const learning = ref<LearningStatus | null>(null)
  const teaching = ref<TeachingSnapshot | null>(null)
  const practice = ref<{ title: string; index: number; total: number } | null>(null)
  let generation = 0
  let statusRequest = 0
  let teachingRevision = 0
  const cursor = ref(0)
  let displayTimer: ReturnType<typeof setTimeout> | undefined
  const replaying = computed(() => !running.value && cursor.value < trace.value.length)
  const last = computed(() => lastAgentEvents(shownTrace.value))
  const activeAgents = computed(() => running.value || replaying.value ? catalog.value.filter(a => last.value[a.id]?.status === 'working') : [])
  const calledAgents = computed(() => catalog.value.filter(a => !!last.value[a.id]))
  const dispatches = computed(() => shownTrace.value.filter(e => e.event === 'dispatch'))
  const latestDispatch = computed(() => dispatches.value.at(-1))
  const steps = computed(() => workflowStates(shownTrace.value, replaying.value ? '' : terminal.value))
  const currentStep = computed(() => steps.value.find(s => s.state === 'working')?.label || (terminal.value === 'failed' ? '协作中断' : terminal.value === 'done' ? '交付完成' : '等待管家接收'))

  async function loadCatalog() {
    try { const res = await getAgentCatalog(); catalog.value = res.agents; reserved.value = res.reserved; catalogError.value = false }
    catch { catalogError.value = true }
  }
  function begin(label: string): number | null {
    if (running.value) return null
    generation++
    if (displayTimer) clearTimeout(displayTimer)
    title.value = label; trace.value = []; shownTrace.value = []; cursor.value = 0
    running.value = true; terminal.value = ''; visible.value = true; collapsed.value = false; error.value = ''
    if (!catalog.value.length) void loadCatalog()
    return generation
  }
  function present() {
    displayTimer = undefined
    if (cursor.value >= trace.value.length) return
    // 同一轮并行帽作为一组出现；批量到达的快速任务回放有明确标识。
    const next = trace.value[cursor.value]
    shownTrace.value.push(next); cursor.value++
    if (next.status === 'working' && next.agent.endsWith('_hat')) {
      while (cursor.value < trace.value.length && trace.value[cursor.value].status === 'working' && trace.value[cursor.value].agent.endsWith('_hat')) {
        shownTrace.value.push(trace.value[cursor.value++])
      }
    }
    if (cursor.value < trace.value.length) displayTimer = setTimeout(present, trace.value.length - cursor.value > 16 ? 70 : 220)
  }
  function receive(events: AgentTrace[], token: number) {
    if (token !== generation) return
    trace.value = events.map(e => ({ ...e, agent: canonicalAgent(e.agent) }))
    if (!displayTimer) present()
  }
  function finish(token: number, message = '') {
    if (token !== generation) return
    running.value = false; error.value = message; terminal.value = message ? 'failed' : 'done'
    void refreshLearning()
  }
  async function refreshLearning() {
    if (!accounts.isSignedIn) return
    const request = ++statusRequest
    const revision = teachingRevision
    const user = app.userId, session = app.sessionId
    try {
      const value = await getLearningStatus(user, session)
      if (request === statusRequest && app.userId === user && app.sessionId === session) {
        learning.value = value
        if (revision === teachingRevision) teaching.value = value.teaching
      }
    } catch { /* 保留最近有效状态，离线不编造进度 */ }
  }
  function syncTeaching(value: TeachingSnapshot | null) { if(value?.session_id === app.sessionId || !value) { teachingRevision++; teaching.value = value } }
  function reset() {
    generation++; statusRequest++; if (displayTimer) clearTimeout(displayTimer); displayTimer = undefined
    running.value = false; visible.value = false; trace.value = []; shownTrace.value = []; terminal.value = ''; cursor.value = 0
    learning.value = null; teaching.value = null; practice.value = null
  }
  watch(() => app.userId, reset)
  watch(() => app.sessionId, reset)
  return { catalog, reserved, catalogError, title, trace, shownTrace, running, terminal, visible, collapsed, error,
    learning, teaching, practice, replaying, last, activeAgents, calledAgents, dispatches, latestDispatch, steps, currentStep,
    loadCatalog, begin, receive, finish, refreshLearning, syncTeaching, reset }
})
