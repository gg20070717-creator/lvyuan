<template>
  <section class="onboarding-dialog ow-screen" role="dialog" aria-modal="true" aria-label="先验学情画像">
      <header class="ow-header">
        <div class="ow-brand"><img :src="brandLogo" alt="旅鸢飞鸟与书本 logo" /><span>旅鸢</span></div>
        <span class="ow-header-divider" aria-hidden="true"></span><h1>先验学情画像</h1>
        <span class="ow-header-note">为你找到合适的学习起点</span>
        <button class="ow-return" :disabled="busy" @click="emit('cancel')">稍后继续</button>
      </header>
    <div class="ow-screen-body">
    <nav class="ow-flow" aria-label="学情画像完整流程"><ol>
      <li v-for="(item, index) in flow" :key="item.id" :class="{ current: stage === item.id, done: stageIndex > index }">
        <button :disabled="busy || index > reachableStage" :aria-current="stage === item.id ? 'step' : undefined" @click="goStage(item.id)">
          <span class="ow-node"><SIcon v-if="stageIndex > index" name="check" :size="16" /><template v-else>{{ String(index + 1).padStart(2, '0') }}</template></span>
          <span><strong>{{ item.title }}</strong><small>{{ stage === item.id ? '进行中' : stageIndex > index ? '已完成' : item.note }}</small></span>
        </button>
      </li>
    </ol></nav>
    <main ref="mainRef" class="ow-main" :aria-busy="busy">
      <div v-if="loading" class="ow-empty" role="status"><span class="ow-spinner"></span><p>正在准备你的学情测试…</p></div>
      <div v-else-if="!ready" class="ow-empty"><SIcon name="warn" :size="28" /><h2>测试内容暂时无法加载</h2><p role="alert">{{ error }}</p><button class="ow-btn primary" @click="initialize">重新加载</button></div>
      <Transition v-else name="ow-stage" mode="out-in" @after-enter="focusContent">
      <div :key="stage" class="ow-stage-view">
        <header class="ow-intro"><span class="ow-eyebrow">{{ stageCopy.eyebrow }}</span><h2>{{ stageCopy.title }}</h2><p>{{ stageCopy.description }}</p></header>
        <div class="ow-layout" :class="{ 'ow-layout-single': stage === 'persona' || stage === 'plan' }">
        <aside v-if="stage === 'qa' || stage === 'groups'" class="ow-sidebar">
          <nav v-if="stage === 'qa'" class="ow-directory" aria-label="身份题目录">
            <button v-for="(q, index) in questions" :key="q.id" :class="{ active: questionIndex === index, answered: !!answers[q.id] && index < serverStep }"
              :disabled="busy || index > serverStep" :aria-current="questionIndex === index ? 'step' : undefined" @click="reviewQuestion(index)">
              <span>{{ questionTopic(q, index) }}</span><SIcon v-if="answers[q.id] && index < serverStep" name="check" :size="14" />
            </button>
          </nav>
          <nav v-else-if="stage === 'groups'" class="ow-directory ow-domain-directory" aria-label="能力自评知识域">
            <button v-for="(domain, index) in domains" :key="domain.id" :class="{ active: domainIndex === index }" :disabled="busy" :aria-current="domainIndex === index ? 'step' : undefined" @click="selectDomain(index)">
              <span>{{ domain.title }}</span><small v-if="domainIndex === index">当前</small>
            </button>
          </nav>
        </aside>
        <div class="ow-content">
          <div v-if="error" class="ow-error" role="alert"><SIcon name="warn" :size="16" /><span>{{ error }}</span></div>
          <Transition name="ow-question" mode="out-in" @before-leave="holdPanelSpace" @after-enter="releasePanelSpace">
          <section v-if="stage === 'qa' && currentQuestion" :key="currentQuestion.id" class="ow-panel" aria-labelledby="ow-question-title">
            <div class="ow-meta"><span>身份与目标</span><span>第 {{ questionIndex + 1 }} 题，共 {{ questions.length }} 题</span><div class="ow-question-progress" aria-hidden="true"><i v-for="(_, index) in questions" :key="index" :class="{ filled: index <= questionIndex }"></i></div></div>
            <h2 id="ow-question-title" ref="headingRef" tabindex="-1">{{ currentQuestion.question }}</h2><p class="ow-help">选择最符合你当前情况的一项。</p>
            <fieldset class="ow-options"><legend class="ow-sr-only">{{ currentQuestion.question }}</legend>
              <label v-for="(option, index) in currentQuestion.options" :key="option.id" class="ow-option" :class="{ selected: answers[currentQuestion.id] === option.id, disabled: busy }">
                <span class="ow-option-letter" aria-hidden="true">{{ String.fromCharCode(65 + index) }}</span><span class="ow-option-text">{{ option.label }}</span>
                <input type="radio" name="onboarding-identity" :value="option.id" :checked="answers[currentQuestion.id] === option.id" :disabled="busy" @change="selectAnswer(option.id)" />
              </label>
            </fieldset>
            <p class="ow-panel-note"><SIcon name="book" :size="15" />根据实际情况作答，旅鸢会结合你的起点安排学习内容。</p>
          </section>
          <section v-else-if="stage === 'groups' && currentDomain" :key="currentDomain.id" class="ow-panel" aria-labelledby="ow-domain-title">
            <div class="ow-meta"><span>{{ currentDomain.title }}</span><span>第 {{ domainIndex + 1 }} 域，共 {{ domains.length }} 域</span></div>
            <h2 id="ow-domain-title" ref="headingRef" tabindex="-1">确认当前知识域的掌握情况</h2><p class="ow-help">选择已掌握或需要学习的内容。</p>
            <div class="ow-domain-toolbar"><div class="ow-segments">
              <button class="ow-mini" :disabled="busy" :aria-pressed="domainStatusOf(currentDomain) === 'mastered'" @click="setDomain(currentDomain, 'mastered')">本域已掌握</button>
              <button class="ow-mini" :disabled="busy" :aria-pressed="domainStatusOf(currentDomain) === 'learning'" @click="setDomain(currentDomain, 'learning')">本域需要学习</button>
            </div></div>
            <div v-for="group in currentDomain.groups" :key="group.id" class="ow-group">
              <div class="ow-group-title"><strong>{{ group.title }}</strong></div>
              <fieldset class="ow-segments"><legend class="ow-sr-only">{{ group.title }}的掌握情况</legend>
                <label class="ow-mini" :class="{ selected: groupStatus[group.id] === 'mastered' }"><input type="radio" :name="`onboarding-group-${group.id}`" value="mastered" :checked="groupStatus[group.id] === 'mastered'" :disabled="busy" @change="setGroup(group.id, 'mastered')" />已掌握</label>
                <label class="ow-mini" :class="{ selected: groupStatus[group.id] === 'learning' }"><input type="radio" :name="`onboarding-group-${group.id}`" value="learning" :checked="groupStatus[group.id] === 'learning'" :disabled="busy" @change="setGroup(group.id, 'learning')" />需要学习</label>
              </fieldset>
            </div>
          </section>
          <section v-else-if="stage === 'persona' && persona" key="persona" class="ow-panel" aria-labelledby="ow-persona-title">
            <div class="ow-meta"><span><SIcon name="sparkle" :size="15" />你的先验学情画像</span></div><h2 id="ow-persona-title" ref="headingRef" tabindex="-1">{{ persona.label }}</h2>
            <p class="ow-persona-summary">{{ persona.summary }}</p><p class="ow-persona-description">{{ persona.description }}</p>
            <dl class="ow-persona-stats"><div><dt>已掌握分组</dt><dd>{{ masteredCount }}<small>组</small></dd></div><div><dt>需要学习分组</dt><dd>{{ totalGroups - masteredCount }}<small>组</small></dd></div><div><dt>已有基础技能点</dt><dd>{{ masteredSkills }}<small>个</small></dd></div></dl>
            <dl class="ow-profile-details"><div v-for="(question, index) in questions" :key="question.id"><dt>{{ questionTopic(question, index) }}</dt><dd>{{ answerLabel(question) }}</dd></div></dl>
            <p class="ow-panel-note"><SIcon name="map" :size="15" />接下来，旅鸢将根据这份画像为你安排学习顺序。</p>
          </section>
          <section v-else-if="stage === 'plan'" key="plan" class="ow-panel" aria-labelledby="ow-plan-title">
            <div id="ow-plan-title" ref="headingRef" tabindex="-1" class="ow-meta"><span>专属学习路径</span><span>根据画像与自评生成</span></div>
            <div v-if="planning && !plan" class="ow-plan-loading" role="status"><span class="ow-spinner"></span><strong>旅鸢正在安排学习顺序</strong><p>结合你的目标与已有基础，规划 {{ totalGroups }} 个分组。</p></div>
            <template v-else-if="plan">
              <p v-if="plan.fallback" class="ow-fallback">已准备基础学习顺序，可按你的想法继续调整。</p>
              <ol class="ow-route-list"><li v-for="(id, index) in visibleRoute" :key="id"><span class="ow-route-number">{{ String(index + 1).padStart(2, '0') }}</span><div><strong>{{ cleanNumberedTitle(groupTitle(id)) }}</strong><small>{{ groupBook(id) }}</small></div><span v-if="groupStatus[id] === 'mastered'" class="ow-mastered-tag">已有基础</span></li></ol>
              <button v-if="plan.route.group_order.length > 5" class="ow-route-expand" :aria-expanded="routeExpanded" @click="routeExpanded = !routeExpanded">{{ routeExpanded ? '收起完整路线' : `展开完整学习路线（${plan.route.group_order.length} 组）` }}<SIcon :name="routeExpanded ? 'up' : 'down'" :size="14" /></button>
              <div class="ow-feedback"><label class="ow-sr-only" for="ow-feedback">希望调整学习顺序？</label><textarea id="ow-feedback" v-model="feedback" rows="3" :disabled="busy" placeholder="希望调整学习顺序？写下你的想法…"></textarea><button v-if="feedback.trim()" class="ow-btn secondary" :disabled="busy" @click="generatePlan(true)">{{ planning ? '正在调整…' : '按反馈调整路线' }}</button></div>
            </template>
            <div v-else class="ow-plan-loading"><p>为你规划合适的学习顺序。</p><button class="ow-btn primary" :disabled="busy" @click="generatePlan()">{{ error ? '重新生成学习路径' : '生成学习路径' }}</button></div>
          </section>
          </Transition>
        </div>
        </div>
      </div>
      </Transition>
    </main>
    <footer class="ow-footer"><div class="ow-footer-inner">
      <span class="ow-footer-status" aria-live="polite"><span v-if="busy" class="ow-spinner"></span><SIcon v-else name="check" :size="15" />{{ footerStatus }}</span>
      <div class="ow-footer-actions"><button class="ow-btn secondary" :disabled="busy || !ready || (stage === 'qa' && questionIndex === 0)" @click="previous">{{ stage === 'groups' && domainIndex > 0 ? '上一知识域' : '上一步' }}</button><button class="ow-btn primary" :disabled="!canContinue" @click="next">{{ nextLabel }}<SIcon v-if="!busy" name="right" :size="16" /></button></div>
    </div></footer>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import brandLogo from '@/assets/lvyuan-logo.jpg'
import SIcon from '@/components/SIcon.vue'
import { useAppStore } from '@/stores/app'
import { useOnboardingStore } from '@/stores/onboarding'
import { answerQa, fetchOnboardingGroups, fetchOnboardingQuestions, getLatestLearningPath, getQaState, planLearningPath, submitOnboarding } from '@/api/onboarding'
import type { OnbDomain, OnbPersona, OnbQuestion, PlanResult, QaState } from '@/api/onboarding'
import { clearOnboardingDraft, readOnboardingDraft, saveOnboardingDraft } from '@/utils/onboardingDraft'
import type { OnboardingStage } from '@/utils/onboardingDraft'
import { cleanNumberedTitle } from '@/utils/displayText'

const emit = defineEmits<{ (e: 'done'): void; (e: 'cancel'): void }>()
const store = useAppStore()
const onb = useOnboardingStore()
const userId = store.userId
let disposed = false
const flow: Array<{ id: OnboardingStage; title: string; note: string }> = [
  { id: 'qa', title: '身份与目标', note: '认识你的起点' },
  { id: 'groups', title: '能力自评', note: '确认已有基础' },
  { id: 'persona', title: '学情画像', note: '梳理学习需求' },
  { id: 'plan', title: '学习路径', note: '确认专属路线' },
]
const stage = ref<OnboardingStage>('qa')
const loading = ref(true)
const ready = ref(false)
const answering = ref(false)
const submitting = ref(false)
const planning = ref(false)
const error = ref('')
const questions = ref<OnbQuestion[]>([])
const qaState = ref<QaState | null>(null)
const questionIndex = ref(0)
const answers = ref<Record<string, string>>({})
const domains = ref<OnbDomain[]>([])
const domainIndex = ref(0)
const groupStatus = ref<Record<string, string>>({})
const persona = ref<OnbPersona | null>(null)
const plan = ref<(Pick<PlanResult, 'version' | 'note' | 'route'> & { fallback?: boolean }) | null>(null)
const feedback = ref('')
const routeExpanded = ref(false)
const visibleRoute = computed(() => routeExpanded.value ? plan.value?.route.group_order || [] : plan.value?.route.group_order.slice(0, 5) || [])
const mainRef = ref<HTMLElement | null>(null)
const headingRef = ref<HTMLElement | null>(null)
const busy = computed(() => loading.value || answering.value || submitting.value || planning.value)
const currentQuestion = computed(() => questions.value[questionIndex.value])
const currentDomain = computed(() => domains.value[domainIndex.value])
const serverStep = computed(() => Math.min(qaState.value?.step || 0, questions.value.length))
const identityDone = computed(() => !!qaState.value?.identity_done)
const stageIndex = computed(() => flow.findIndex((item) => item.id === stage.value))
const reachableStage = computed(() => persona.value ? (plan.value ? 3 : 2) : identityDone.value ? 1 : 0)
const allGroups = computed(() => domains.value.flatMap((domain) => domain.groups))
const totalGroups = computed(() => allGroups.value.length)
const masteredCount = computed(() => allGroups.value.filter((group) => groupStatus.value[group.id] === 'mastered').length)
const masteredSkills = computed(() => allGroups.value.reduce((sum, group) => sum + (groupStatus.value[group.id] === 'mastered' ? group.skill_count : 0), 0))
const groupMap = computed(() => new Map(allGroups.value.map((group) => [group.id, group])))
const stageCopy = computed(() => ({
  qa: { eyebrow: '认识你的起点', title: '从了解你开始', description: `${questions.value.length} 个问题，帮助旅鸢了解你的经验、目标与学习偏好。` },
  groups: { eyebrow: '能力自评', title: '哪些内容你已经掌握？', description: '按知识域确认已有基础与学习需求，可逐项调整。' },
  persona: { eyebrow: '你的学习起点', title: '更清晰地认识自己', description: '结合经验、目标与能力自评，梳理你的已有基础和学习需求。' },
  plan: { eyebrow: '学习路径', title: '你的下一段旅程，从这里开始', description: '确认学习顺序，即可进入首页开始实训。' },
}[stage.value]))
const footerStatus = computed(() => {
  if (loading.value) return '正在加载测试内容'
  if (answering.value) return '正在保存回答'
  if (submitting.value) return '正在生成学情画像'
  if (planning.value) return '正在规划学习路径'
  if (!ready.value) return '重新加载后继续'
  if (stage.value === 'qa') return `单选   第 ${questionIndex.value + 1} 题，共 ${questions.value.length} 题   可返回修改`
  if (stage.value === 'groups') return '逐域确认，支持批量选择'
  if (stage.value === 'persona') return '确认你的学习起点，继续生成专属路线'
  return plan.value ? '确认路线后，即可进入首页开始学习' : '生成学习路径后继续'
})
const nextLabel = computed(() => {
  if (answering.value) return '保存中…'
  if (submitting.value) return '生成中…'
  if (planning.value) return '规划中…'
  if (stage.value === 'qa') return questionIndex.value === questions.value.length - 1 ? '进入能力自评' : '下一题'
  if (stage.value === 'groups') return domainIndex.value === domains.value.length - 1 ? '生成学情画像' : '下一知识域'
  if (stage.value === 'persona') return '生成学习路径'
  return plan.value ? '确认并进入首页' : '生成学习路径'
})
const canContinue = computed(() => {
  if (busy.value || !ready.value) return false
  if (stage.value === 'qa') return !!currentQuestion.value && !!answers.value[currentQuestion.value.id]
  if (stage.value === 'groups') return !!currentDomain.value && questions.value.every((question) => !!answers.value[question.id])
  return !!persona.value
})
const topicNames: Record<string, string> = { identity: '职业身份', basis: '接待经验', language: '外语水平', goal: '学习方向', pace: '学习节奏', style: '训练偏好' }
function questionTopic(question: OnbQuestion, index: number) { return topicNames[question.id] || `问题 ${index + 1}` }
function answerLabel(question: OnbQuestion) { return question.options.find((option) => option.id === answers.value[question.id])?.label || '尚未选择' }
function groupTitle(id: string) { return groupMap.value.get(id)?.title || plan.value?.route.groups?.find((group) => group.id === id)?.title || id }
function groupBook(id: string) { return groupMap.value.get(id)?.book_title || '' }
function chosenCountOf(domain: OnbDomain) { return domain.groups.filter((group) => !!groupStatus.value[group.id]).length }
function domainStatusOf(domain: OnbDomain) {
  const statuses = domain.groups.map((group) => groupStatus.value[group.id])
  return statuses.length && statuses.every((value) => value === 'mastered') ? 'mastered' : statuses.length && statuses.every((value) => value === 'learning') ? 'learning' : ''
}
function saveDraft() {
  if (!disposed) saveOnboardingDraft(userId, { stage: stage.value, answers: answers.value, groupStatus: groupStatus.value, questionIndex: questionIndex.value, domainId: currentDomain.value?.id || '' })
}
async function focusContent() { await nextTick(); if (disposed) return; mainRef.value?.scrollTo({ top: 0 }); headingRef.value?.focus({ preventScroll: true }) }
function holdPanelSpace(element: Element) { const parent = element.parentElement; if (parent) parent.style.minHeight = `${element.getBoundingClientRect().height}px` }
function releasePanelSpace(element: Element) { const parent = element.parentElement; if (parent) parent.style.minHeight = ''; void focusContent() }
function errorMessage(cause: unknown, fallback: string) { const detail = (cause as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail; return typeof detail === 'string' ? detail : fallback }

async function initialize() {
  loading.value = true; ready.value = false; error.value = ''
  try {
    const [questionList, groupData, state] = await Promise.all([fetchOnboardingQuestions(), fetchOnboardingGroups(), getQaState(userId)])
    if (disposed) return
    if (!questionList.length || !groupData.domains.length || !groupData.domains.some((domain) => domain.groups.length)) throw new Error('empty onboarding data')
    questions.value = questionList; domains.value = groupData.domains; qaState.value = state; onb.identityDone = !!state.identity_done
    let draft = readOnboardingDraft(userId)
    // 学习数据重置后，抛弃与服务端进度不一致的旧草稿。
    if (draft && draft.stage !== 'qa' && !state.step && !onb.persona) { clearOnboardingDraft(userId); draft = null }
    const mergedAnswers = { ...state.answers, ...draft?.answers }
    answers.value = Object.fromEntries(questionList.flatMap((question) => question.options.some((option) => option.id === mergedAnswers[question.id]) ? [[question.id, mergedAnswers[question.id]]] : []))
    const savedGroups = draft?.groupStatus || onb.groupStatus || {}
    groupStatus.value = Object.fromEntries(allGroups.value.map((group) => [group.id, ['mastered', 'learning'].includes(savedGroups[group.id]) ? savedGroups[group.id] : '']))
    questionIndex.value = Math.min(draft?.questionIndex ?? state.step, state.step, questionList.length - 1)
    domainIndex.value = Math.max(0, domains.value.findIndex((domain) => domain.id === draft?.domainId))
    persona.value = draft && ['persona', 'plan'].includes(draft.stage) ? onb.persona : null
    plan.value = null
    stage.value = persona.value ? draft!.stage : state.identity_done && draft?.stage !== 'qa' ? 'groups' : 'qa'
    if (stage.value === 'plan') {
      try { const latest = await getLatestLearningPath(userId); if (latest.found && latest.route) plan.value = { version: latest.version || 1, route: latest.route, note: latest.route.note } }
      catch { error.value = '暂时无法恢复学习路线，请重试生成。' }
    }
    ready.value = true; saveDraft()
  } catch (cause) { error.value = errorMessage(cause, '暂时无法连接学情测试服务，请稍后重试。') }
  finally { loading.value = false; void focusContent() }
}
function invalidateResults() { persona.value = null; plan.value = null; error.value = '' }
function selectAnswer(optionId: string) {
  if (busy.value || !currentQuestion.value || answers.value[currentQuestion.value.id] === optionId) return
  answers.value = { ...answers.value, [currentQuestion.value.id]: optionId }; invalidateResults(); saveDraft()
}
function reviewQuestion(index: number) { if (busy.value || index > serverStep.value) return; questionIndex.value = Math.min(index, questions.value.length - 1); error.value = ''; saveDraft(); void focusContent() }
function goStage(target: OnboardingStage) { if (busy.value || flow.findIndex((item) => item.id === target) > reachableStage.value) return; stage.value = target; error.value = ''; saveDraft(); void focusContent() }
function selectDomain(index: number) { domainIndex.value = index; error.value = ''; saveDraft(); void focusContent() }
function setDomain(domain: OnbDomain, status: string) { if (busy.value) return; for (const group of domain.groups) groupStatus.value[group.id] = status; invalidateResults(); saveDraft() }
function setGroup(id: string, status: string) { if (busy.value) return; groupStatus.value = { ...groupStatus.value, [id]: status }; invalidateResults(); saveDraft() }
function previous() {
  if (busy.value) return
  error.value = ''
  if (stage.value === 'qa') questionIndex.value = Math.max(0, questionIndex.value - 1)
  else if (stage.value === 'groups' && domainIndex.value > 0) domainIndex.value--
  else if (stage.value === 'groups') { stage.value = 'qa'; questionIndex.value = questions.value.length - 1 }
  else if (stage.value === 'persona') stage.value = 'groups'
  else stage.value = 'persona'
  saveDraft(); void focusContent()
}
async function nextIdentity() {
  const question = currentQuestion.value
  if (!question || !answers.value[question.id]) return
  answering.value = true; error.value = ''
  try {
    // 旧题可回看并修改；最终 submit 携带整套答案。新题通过原有顺序接口保存。
    if (questionIndex.value >= serverStep.value && !identityDone.value) { const state = await answerQa({ user_id: userId, question_id: question.id, option_id: answers.value[question.id] }); qaState.value = state; onb.identityDone = !!state.identity_done }
    if (questionIndex.value < questions.value.length - 1) questionIndex.value++; else stage.value = 'groups'
    saveDraft(); void focusContent()
  } catch (cause) {
    error.value = errorMessage(cause, '回答暂时未保存，请保留当前选择并重试。')
    if ((cause as { response?: { status?: number } })?.response?.status === 409) {
      try {
        const state = await getQaState(userId)
        qaState.value = state
        onb.identityDone = !!state.identity_done
        answers.value = { ...state.answers, ...answers.value }
        questionIndex.value = Math.min(serverStep.value, questions.value.length - 1)
        saveDraft(); void focusContent()
      } catch { /* 保留选择供重试 */ }
    }
  } finally { answering.value = false }
}
async function submit() {
  if (!totalGroups.value || !questions.value.every((question) => answers.value[question.id])) return
  submitting.value = true; error.value = ''; saveDraft()
  try {
    const resolved = Object.fromEntries(allGroups.value.map((group) => [group.id, groupStatus.value[group.id] === 'mastered' ? 'mastered' : 'learning']))
    const result = await submitOnboarding({ user_id: userId, answers: answers.value, group_status: resolved })
    if (!result.ok || !result.persona) throw new Error('invalid profile response')
    groupStatus.value = result.group_status || resolved; persona.value = result.persona; onb.persona = result.persona; onb.groupStatus = groupStatus.value; plan.value = null; stage.value = 'persona'; saveDraft(); void focusContent()
  } catch (cause) { error.value = errorMessage(cause, '画像暂时未生成，你的选择已保留，请重试。') }
  finally { submitting.value = false }
}
async function generatePlan(withFeedback = false) {
  if (busy.value || !persona.value) return
  stage.value = 'plan'; planning.value = true; routeExpanded.value = false; error.value = ''; saveDraft(); void focusContent()
  try { const result = await planLearningPath(userId, withFeedback ? feedback.value.trim() : ''); if (!result.ok || !result.route?.group_order?.length) throw new Error('invalid learning path response'); plan.value = result; saveDraft() }
  catch (cause) { error.value = errorMessage(cause, '学习路径暂时未生成，请稍后重试。') }
  finally { planning.value = false }
}
function confirmDone() { if (busy.value || !persona.value || !plan.value) return; clearOnboardingDraft(userId); onb.markDone(persona.value, groupStatus.value); emit('done') }
async function next() {
  if (!canContinue.value) return
  if (stage.value === 'qa') await nextIdentity()
  else if (stage.value === 'groups') { if (domainIndex.value < domains.value.length - 1) selectDomain(domainIndex.value + 1); else await submit() }
  else if (stage.value === 'persona' || !plan.value) await generatePlan()
  else confirmDone()
}
onMounted(initialize)
onBeforeUnmount(() => { disposed = true })
</script>

<style lang="scss">
@use '@/styles/tokens' as *;
.onboarding-dialog.ow-screen { width: 100%; display: flex; flex-direction: column; height: 100dvh; margin: 0; padding: 0; background: $color-bg;
  .ow-screen-body { flex: 1; min-height: 0; display: flex; flex-direction: column; padding: 0; color: $color-text; }
}
</style>
<style lang="scss" scoped>
@use '@/styles/tokens' as *;
.ow-header { min-height: 88px; padding: 20px clamp(20px, 4vw, 64px); display: flex; align-items: center; gap: 20px; background: $color-surface; border-bottom: 1px solid $color-border; h1 { font-size: 18px; font-weight: 500; margin: 0; } }
.ow-brand { display: flex; align-items: center; gap: 12px; flex-shrink: 0; img { width: 40px; height: 40px; object-fit: contain; } span { font: 600 23px/1.2 $font-serif; letter-spacing: 4px; } }
.ow-header-divider { width: 1px; height: 23px; background: $color-border; }
.ow-header-note { margin-left: auto; font-size: 14px; color: $color-text-secondary; }
.ow-return { padding: 8px 0 8px 12px; background: transparent; border: 0; color: $color-text-secondary; font: inherit; font-size: 14px; cursor: pointer; &:hover { color: $color-text-link; } }
.ow-flow { flex-shrink: 0; background: $color-surface; padding: 28px 40px;
  ol { max-width: 1050px; margin: auto; list-style: none; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); }
  li { position: relative; &:not(:last-child)::after { content: ''; position: absolute; left: 180px; right: 28px; top: 20px; height: 1px; background: $color-border; } }
  button { position: relative; z-index: 1; border: 0; background: $color-surface; display: flex; align-items: center; gap: 13px; text-align: left; font: inherit; color: $color-text-secondary; padding: 2px 12px 2px 0; cursor: pointer; }
  button:disabled { cursor: default; opacity: 1; } strong { display: block; font-weight: 500; font-size: 17px; white-space: nowrap; } small { display: block; font-size: 13px; margin-top: 4px; }
  .current { strong { color: $color-text; } .ow-node { color: #fff; background: $color-primary; border-color: $color-primary; box-shadow: 0 0 0 5px $color-secondary-bg; } }
  .done .ow-node { color: $color-text-link; background: $color-secondary-bg; border-color: $color-border; }
}
.ow-node { width: 36px; height: 36px; flex-shrink: 0; border: 1px solid $color-border; border-radius: 50%; display: grid; place-items: center; font-size: 14px; transition: background .28s ease, color .28s ease, box-shadow .28s ease; }
.ow-main { flex: 1; min-height: 0; overflow-y: auto; overscroll-behavior: contain; padding: 30px clamp(20px, 4vw, 64px); }
.ow-intro { text-align: center; margin: 0 auto 30px; max-width: 800px; h2 { font-size: 28px; font-weight: 500; line-height: 1.5; margin: 12px 0 10px; } p { color: $color-text-secondary; font-size: 14px; line-height: 1.8; margin: 0; } }
.ow-layout { display: grid; grid-template-columns: 180px minmax(0, 1fr); gap: 36px; align-items: start; max-width: 1000px; margin: auto; }
.ow-layout-single { grid-template-columns: minmax(0, 1fr); max-width: 780px; }
.ow-sidebar { position: sticky; top: 0; padding: 0; }
.ow-eyebrow { color: $color-text-link; font-size: 12px; letter-spacing: 1px; }
.ow-directory { display: flex; flex-direction: column; gap: 6px;
  button { display: flex; align-items: center; gap: 12px; width: 100%; padding: 15px 12px; border: 0; border-radius: 8px; background: transparent; font: inherit; color: $color-text-secondary; font-size: 15px; line-height: 1.45; text-align: left; cursor: pointer; transition: background .24s ease, color .24s ease;
    > span { flex: 1; min-width: 0; overflow-wrap: anywhere; }
    &:hover:not(:disabled):not(.active) { background: $color-secondary-bg; }
  }
  button.active { background: $color-secondary-bg; color: $color-primary-dark; } button:disabled { cursor: default; opacity: .85; }
  small, svg { margin-left: auto; flex-shrink: 0; font-size: 12px; }
}
.ow-content { min-width: 0; }
.ow-panel { position: relative; padding: 30px 32px; background: $color-surface; border: 1px solid $color-border; border-radius: 16px; box-shadow: 0 8px 32px rgba(55, 117, 176, .045);
  &::before, &::after { content: ''; position: absolute; width: 13px; height: 13px; pointer-events: none; opacity: .6; } &::before { top: 10px; left: 10px; border-top: 1px solid $color-border-d10; border-left: 1px solid $color-border-d10; } &::after { bottom: 10px; right: 10px; border-bottom: 1px solid $color-border-d10; border-right: 1px solid $color-border-d10; }
  h2 { font-size: 22px; line-height: 1.6; font-weight: 500; margin: 15px 0 6px; overflow-wrap: anywhere; &:focus { outline: none; } }
}
.ow-meta { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; font-size: 14px; color: $color-text-secondary; > span:first-child { display: inline-flex; align-items: center; gap: 7px; color: $color-primary-dark; } }
.ow-meta:focus { outline: none; }
.ow-question-progress { margin-left: auto; display: flex; gap: 4px; i { width: 19px; height: 3px; border-radius: 3px; background: $color-secondary-bg; &.filled { background: $color-primary; } } }
.ow-help { color: $color-text-secondary; font-size: 14px; line-height: 1.8; margin-bottom: 22px; }
.ow-options, .ow-segments { border: 0; padding: 0; margin: 0; min-width: 0; }
.ow-options { display: flex; flex-direction: column; gap: 10px; }
.ow-option { display: flex; align-items: center; gap: 14px; min-height: 58px; padding: 14px 16px; border: 1px solid $color-border; border-radius: 10px; cursor: pointer; transition: background .15s, border-color .15s;
  &:hover, &.selected { border-color: $color-primary; background: $color-bg; } &.disabled { cursor: default; opacity: .65; } &:has(input:focus-visible) { outline: 2px solid $color-primary; outline-offset: 3px; } input { accent-color: $color-primary; width: 16px; height: 16px; flex-shrink: 0; cursor: inherit; }
}
.ow-option-letter { font-size: 14px; color: $color-text-secondary; }
.ow-option-text { flex: 1; font-size: 16px; line-height: 1.65; overflow-wrap: anywhere; }
.ow-panel-note { display: flex; align-items: flex-start; gap: 8px; color: $color-text-secondary; font-size: 14px; line-height: 1.8; margin-top: 24px; svg { flex-shrink: 0; margin-top: 3px; } }
.ow-domain-toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; padding: 0 0 6px; }
.ow-segments { display: flex; gap: 7px; flex-shrink: 0; flex-wrap: wrap; }
.ow-mini { display: inline-flex; align-items: center; gap: 5px; min-height: 34px; padding: 6px 10px; background: $color-surface; border: 1px solid $color-border; border-radius: 6px; color: $color-text-secondary; font: inherit; font-size: 14px; cursor: pointer;
  &[aria-pressed='true'], &.selected { color: $color-primary-dark; background: $color-secondary-bg; border-color: $color-primary; } input { accent-color: $color-primary; width: 13px; height: 13px; } &:has(input:focus-visible) { outline: 2px solid $color-primary; outline-offset: 2px; }
}
.ow-group { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 20px 0; border-bottom: 1px solid $color-border; }
.ow-group-title { min-width: 0; strong { display: block; font-weight: 400; font-size: 16px; line-height: 1.7; overflow-wrap: anywhere; } small { display: block; font-size: 13px; color: $color-text-secondary; margin-top: 4px; } }
.ow-persona-summary { font-size: 15px; line-height: 1.9; color: $color-primary-dark; margin: 15px 0; }
.ow-persona-description { font-size: 15px; line-height: 1.9; color: $color-text-secondary; }
.ow-persona-stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 20px; padding: 25px 0; margin: 20px 0 8px; border-top: 1px solid $color-border; border-bottom: 1px solid $color-border;
  dt { font-size: 14px; color: $color-text-secondary; } dd { margin: 8px 0 0; color: $color-primary-dark; font-size: 28px; font-weight: 500; font-variant-numeric: tabular-nums; } small { font-size: 13px; color: $color-text-secondary; margin-left: 7px; font-weight: 400; }
}
.ow-profile-details { > div { display: grid; grid-template-columns: 76px minmax(0, 1fr); gap: 14px; border-bottom: 1px solid $color-border; padding: 16px 0; font-size: 15px; line-height: 1.8; } dt { color: $color-text-secondary; } dd { margin: 0; } }
.ow-route-list { padding: 0; margin: 8px 0 0; list-style: none; li { display: flex; align-items: center; gap: 15px; padding: 16px 0; border-bottom: 1px solid $color-border; } strong { display: block; font-size: 16px; font-weight: 400; line-height: 1.7; } small { display: block; font-size: 13px; color: $color-text-secondary; margin-top: 3px; } }
.ow-route-number { width: 34px; height: 34px; border-radius: 50%; background: $color-secondary-bg; color: $color-primary-dark; display: grid; place-items: center; font-size: 14px; flex-shrink: 0; }
.ow-route-expand { display: inline-flex; align-items: center; gap: 8px; margin-top: 18px; padding: 6px 0; border: 0; background: transparent; color: $color-primary-dark; font: inherit; font-size: 14px; cursor: pointer; }
.ow-mastered-tag { margin-left: auto; color: $color-text-secondary; font-size: 13px; white-space: nowrap; }
.ow-feedback { margin-top: 22px; display: flex; align-items: flex-start; flex-direction: column; gap: 12px; textarea { width: 100%; min-height: 78px; padding: 12px 14px; border: 1px solid $color-border; border-radius: 8px; resize: vertical; font: inherit; font-size: 14px; line-height: 1.8; background: $color-bg; color: $color-text; } }
.ow-fallback { padding: 12px 14px; background: $color-secondary-bg; color: $color-text-secondary; font-size: 14px; line-height: 1.8; border-radius: 6px; }
.ow-footer { background: $color-surface; border-top: 1px solid $color-border; flex-shrink: 0; padding: 20px clamp(20px, 4vw, 64px); }
.ow-footer-inner { max-width: 1080px; margin: auto; display: flex; align-items: center; gap: 20px; justify-content: space-between; }
.ow-footer-status { display: flex; align-items: center; gap: 8px; color: $color-text-secondary; font-size: 12px; line-height: 1.8; }
.ow-footer-actions { display: flex; align-items: center; gap: 12px; flex-shrink: 0; }
.ow-btn { display: inline-flex; align-items: center; justify-content: center; gap: 9px; min-height: 42px; padding: 10px 22px; border-radius: 8px; border: 1px solid $color-border; font: inherit; font-size: 15px; cursor: pointer; background: $color-surface; color: $color-text;
  &.primary { background: $color-primary; border-color: $color-primary; color: #fff; &:hover { background: $color-primary-dark; } } &.secondary:hover { background: $color-secondary-bg; }
}
button:disabled, .ow-btn:disabled { opacity: .45; cursor: not-allowed; }
button:focus-visible, textarea:focus-visible { outline: 2px solid $color-primary; outline-offset: 3px; }
.ow-error { padding: 14px 18px; display: flex; align-items: flex-start; gap: 10px; border: 1px solid #efd4d3; border-radius: 8px; background: #fff6f5; color: #a34845; font-size: 15px; line-height: 1.8; margin-bottom: 16px; svg { flex-shrink: 0; margin-top: 4px; } }
.ow-empty { min-height: 240px; max-width: 640px; margin: 40px auto; text-align: center; color: $color-text-secondary; h2 { color: $color-text; font-size: 22px; font-weight: 500; margin: 16px 0; } p { font-size: 14px; line-height: 1.8; margin: 16px 0 24px; } }
.ow-plan-loading { padding: 48px 0; text-align: center; strong { display: block; font-weight: 500; font-size: 17px; margin-top: 16px; } p { font-size: 15px; color: $color-text-secondary; margin: 16px 0; line-height: 1.8; } }
.ow-spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid $color-border; border-top-color: $color-primary; border-radius: 50%; animation: ow-spin .8s linear infinite; flex-shrink: 0; }
.ow-sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
@keyframes ow-spin { to { transform: rotate(360deg); } }
.ow-stage-enter-active, .ow-question-enter-active { transition: opacity .28s ease, transform .36s cubic-bezier(.22,.75,.2,1); }
.ow-stage-leave-active, .ow-question-leave-active { transition: opacity .16s ease, transform .2s ease; }
.ow-stage-enter-from, .ow-question-enter-from { opacity: 0; transform: translateY(8px); }
.ow-stage-leave-to, .ow-question-leave-to { opacity: 0; transform: translateY(-4px); }
@media (max-width: 1050px) { .ow-layout:not(.ow-layout-single) { grid-template-columns: 165px minmax(0, 1fr); gap: 26px; } .ow-panel { padding: 26px; } .ow-flow li:not(:last-child)::after { left: 152px; right: 16px; } .ow-option { padding: 12px 14px; min-height: 56px; } }
@media (max-width: 760px) {
  .ow-header { min-height: 72px; padding: 16px 20px; gap: 14px; h1 { font-size: 15px; } } .ow-header-note { display: none; } .ow-return { margin-left: auto; } .ow-brand { gap: 7px; img { width: 32px; height: 32px; } span { font-size: 19px; letter-spacing: 2px; } }
  .ow-flow { padding: 23px 20px; ol { gap: 8px; } button { flex-direction: column; gap: 9px; padding: 0; text-align: center; width: 100%; } strong { font-size: 14px; } small { display: none; } li:not(:last-child)::after { left: calc(50% + 25px); right: calc(-50% + 25px); top: 16px; } } .ow-node { width: 32px; height: 32px; }
  .ow-main { padding: 24px 20px; } .ow-layout:not(.ow-layout-single) { grid-template-columns: 1fr; gap: 20px; } .ow-sidebar { position: static; } .ow-intro { margin-bottom: 22px; h2 { font-size: 24px; } p { font-size: 13px; } }
  .ow-directory { flex-direction: row; flex-wrap: wrap; gap: 6px; button { width: auto; padding: 8px 10px; font-size: 14px; gap: 7px; } small { display: none; } } .ow-domain-directory button { flex: 1 0 calc(33.33% - 6px); }
  .ow-panel { padding: 26px 22px; h2 { font-size: 22px; } } .ow-option-text { font-size: 15px; } .ow-footer { padding: 14px 20px; } .ow-footer-inner { flex-wrap: wrap; gap: 10px; } .ow-footer-status { flex-basis: 100%; font-size: 11px; } .ow-footer-actions { width: 100%; justify-content: flex-end; } .ow-persona-stats { gap: 12px; dd { font-size: 26px; } }
}
@media (max-width: 430px) { .ow-header { gap: 10px; padding: 14px 16px; } .ow-header-divider { display: none; } .ow-return { padding: 8px 0; font-size: 12px; } .ow-main { padding: 20px 14px; } .ow-panel { padding: 24px 18px; } .ow-question-progress { flex-basis: 100%; margin-left: 0; margin-top: 4px; } .ow-group { flex-wrap: wrap; gap: 10px; } .ow-group .ow-segments { width: 100%; } .ow-option { gap: 10px; padding: 13px 12px; } .ow-persona-stats { grid-template-columns: 1fr; gap: 14px; > div { display: flex; align-items: baseline; justify-content: space-between; } dd { margin: 0; } } .ow-profile-details > div { grid-template-columns: 1fr; gap: 5px; } .ow-domain-directory button { flex-basis: calc(50% - 6px); } .ow-footer { padding: 14px 16px; } .ow-btn { padding: 10px 15px; } }
@media (max-height: 900px) and (min-width: 761px) {
  .ow-header { min-height: 70px; padding-top: 14px; padding-bottom: 14px; }
  .ow-flow { padding-top: 18px; padding-bottom: 18px; }
  .ow-main { padding-top: 20px; padding-bottom: 20px; }
  .ow-panel { padding-top: 20px; padding-bottom: 20px; h2 { font-size: 22px; line-height: 1.5; margin-top: 12px; } }
  .ow-help { margin-bottom: 16px; }
  .ow-options { gap: 8px; }
  .ow-option { min-height: 44px; padding-top: 10px; padding-bottom: 10px; }
  .ow-panel-note { margin-top: 16px; font-size: 13px; }
  .ow-directory button { padding-top: 13px; padding-bottom: 13px; }
  .ow-intro { margin-bottom: 24px; h2 { font-size: 26px; margin-top: 8px; margin-bottom: 8px; } }
  .ow-footer { padding-top: 14px; padding-bottom: 14px; }
}
@media (prefers-reduced-motion: reduce) { .ow-spinner { animation: none; } .ow-option, .ow-directory button, .ow-stage-enter-active, .ow-stage-leave-active, .ow-question-enter-active, .ow-question-leave-active { transition: none; } .ow-stage-enter-from, .ow-stage-leave-to, .ow-question-enter-from, .ow-question-leave-to { transform: none; } }
</style>
