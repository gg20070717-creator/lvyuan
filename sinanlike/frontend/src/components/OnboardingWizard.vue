<template>
  <div class="onb-wrap">
    <div class="onb-card">
      <div class="onb-head">
        <span class="onb-title"><i class="ob-dot"></i>先验学情画像</span>
        <span class="onb-step">{{ stepLabel }}</span>
      </div>

      <!-- ① 管家对话身份题 -->
      <div v-if="stage === 'qa'" class="ob-body qa">
        <div ref="qaScroll" class="ob-chat">
          <div v-for="(b, i) in bubbles" :key="i" class="bubble-row" :class="b.role">
            <span v-if="b.role === 'assistant'" class="b-av"><img :src="brandLogo" alt="旅鸢" /></span>
            <div class="b-main">
              <div class="bubble" :class="b.role">{{ b.text }}</div>
              <!-- 管家出的身份题卡 -->
              <div v-if="b.qa" class="qa-card">
                <div class="qa-q">{{ b.qa.question }}</div>
                <div class="qa-opts">
                  <button v-for="op in b.qa.options" :key="op.id" class="qa-opt"
                    :disabled="answering" @click="choose(b.qa!, op)">
                    <i></i>{{ op.label }}
                  </button>
                </div>
              </div>
            </div>
          </div>
          <div v-if="answering" class="bubble-row assistant">
            <span class="b-av"><img :src="brandLogo" alt="旅鸢" /></span><div class="b-main"><div class="bubble typing">…</div></div>
          </div>
        </div>
      </div>

      <!-- ② 7 域 / 84 组能力自评 -->
      <div v-else-if="stage === 'groups'" class="ob-body">
        <p class="ob-intro">管家已记下你的身份。下面按知识域勾选能力现状：<b>已掌握/不需要</b> 自动 100% 点亮并放路线最前；<b>要学</b> 进学习路线。点“展开组”可单组调整；再点一次已选态=取消。</p>
        <div v-for="dm in domains" :key="dm.id" class="ob-domain">
          <div class="ob-domain-row">
            <button class="ob-domain-expand" @click="toggleDomain(dm.id)"><SIcon :name="expanded.has(dm.id) ? 'up' : 'right'" :size="11" /></button>
            <span class="ob-domain-title">{{ dm.title }}</span>
            <span class="ob-domain-count">{{ masteredCountOf(dm) }}/{{ dm.groups.length }} 已掌握</span>
            <span class="ob-domain-seg">
              <button class="ob-mini" :class="{ on: domainStatusOf(dm) === 'mastered' }" @click="setDomain(dm, 'mastered')">全部已掌握</button>
              <button class="ob-mini" :class="{ on: domainStatusOf(dm) === 'learning' }" @click="setDomain(dm, 'learning')">全部要学</button>
            </span>
          </div>
          <div v-if="expanded.has(dm.id)" class="ob-domain-groups">
            <div v-for="g in dm.groups" :key="g.id" class="ob-group">
              <span class="ob-group-title" :title="g.title">{{ g.title }}</span>
              <span class="ob-group-meta">{{ g.skill_count }} 点</span>
              <span class="ob-group-seg">
                <button class="ob-mini" :class="{ on: groupStatus[g.id] === 'mastered' }" @click="setGroup(g.id, 'mastered')">已掌握</button>
                <button class="ob-mini" :class="{ on: groupStatus[g.id] === 'learning' }" @click="setGroup(g.id, 'learning')">要学</button>
              </span>
            </div>
          </div>
        </div>
        <div class="ob-actions"><button class="ob-btn primary" :disabled="submitting" @click="submit">{{ submitting ? '生成中…' : '生成我的画像' }}</button></div>
      </div>

      <!-- ③ 画像 + 学习路径 -->
      <div v-else class="ob-body">
        <div v-if="persona" class="ob-persona">
          <div class="ob-persona-head"><SIcon name="sparkle" :size="16" />你的先验画像</div>
          <div class="ob-persona-label">{{ persona.label }}</div>
          <div class="ob-persona-summary">{{ persona.summary }}</div>
          <div class="ob-persona-desc">{{ persona.description }}</div>
          <div class="ob-persona-stats">
            <span>已掌握分组 <b>{{ submitCounts?.mastered_group_count ?? 0 }}</b></span>
            <span>要学分组 <b>{{ submitCounts?.learning_group_count ?? 0 }}</b></span>
            <span>先验点亮技能点 <b>{{ submitCounts?.mastered_skills ?? 0 }}</b></span>
          </div>
        </div>

        <div v-if="plan" class="ob-plan">
          <div class="ob-plan-head"><SIcon name="map" :size="15" />学习路径规划
            <span class="ob-plan-tag" :class="{ fb: plan.fallback }">{{ plan.fallback ? '已用默认顺序兜底' : '管家已排好 · 第 ' + plan.version + ' 版' }}</span>
          </div>
          <p class="ob-plan-note">{{ plan.note || '已按你的画像生成学习顺序。' }}</p>
          <div class="ob-plan-stats">
            <span>84 组全排 <b>✓</b></span>
            <span>起点前 <b>{{ plan.route.stats.before_start }}</b></span>
            <span>学习路径 <b>{{ plan.route.stats.learning_path }}</b></span>
          </div>
          <div class="ob-plan-list">
            <div v-for="(gid, i) in plan.route.group_order" :key="gid" class="ob-plan-item"><span class="ob-plan-idx">{{ i + 1 }}</span>{{ groupTitle(gid) }}</div>
          </div>
          <div class="ob-replan">
            <textarea v-model="feedback" rows="2" placeholder="不满意？告诉旅鸢哪里要调整…" />
            <button class="ob-btn ghost" :disabled="replanning" @click="replan">{{ replanning ? '重新排中…' : '按反馈重排' }}</button>
          </div>
        </div>
        <div v-else-if="planning" class="ob-plan ob-loading"><span class="ma-spin"></span> 旅鸢正在排 84 个分组的学习顺序…</div>
        <div v-else-if="planError" class="ob-plan ob-error">{{ planError }}</div>

        <div class="ob-actions">
          <button v-if="!plan && !planning" class="ob-btn ghost" @click="stage = 'groups'">上一步</button>
          <button v-if="!plan && !planning" class="ob-btn primary" :disabled="!persona" @click="generatePlan">生成学习路径</button>
          <button v-if="plan && !planning && !replanning" class="ob-btn primary" @click="confirmDone"><SIcon name="check" :size="13" />满意，正式进入</button>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import brandLogo from '@/assets/lvyuan-logo.jpg'
import { computed, nextTick, onMounted, ref } from 'vue'
import SIcon from '@/components/SIcon.vue'
import { useAppStore } from '@/stores/app'
import { useOnboardingStore } from '@/stores/onboarding'
import {
  answerQa, fetchOnboardingGroups, getQaState, planLearningPath, submitOnboarding,
} from '@/api/onboarding'
import type { OnbDomain, OnbOption, OnbPersona, PlanResult, QaQuestion } from '@/api/onboarding'

const emit = defineEmits<{ (e: 'done'): void }>()
const store = useAppStore()
const onb = useOnboardingStore()

type Stage = 'qa' | 'groups' | 'persona'
const stage = ref<Stage>('qa')
const bubbles = ref<Array<{ role: 'assistant' | 'user'; text: string; qa?: QaQuestion | null }>>([])
const answering = ref(false)
const qaScroll = ref<HTMLElement | null>(null)

const domains = ref<OnbDomain[]>([])
const groupStatus = ref<Record<string, string>>({})
const expanded = ref<Set<string>>(new Set())
const submitting = ref(false)
const persona = ref<OnbPersona | null>(null)
const submitCounts = ref<any>(null)
const planning = ref(false)
const replanning = ref(false)
const plan = ref<PlanResult | null>(null)
const planError = ref('')
const feedback = ref('')

const stepLabel = computed(() =>
  stage.value === 'qa' ? '管家对话 · 身份问答' : stage.value === 'groups' ? '能力自评 · 7 域 / 84 组' : '画像与学习路径',
)
const groupTitleMap = computed(() => {
  const m: Record<string, string> = {}
  for (const d of domains.value) for (const g of d.groups) m[g.id] = g.title
  return m
})
function groupTitle(id: string): string { return groupTitleMap.value[id] || id }

function push(role: 'assistant' | 'user', text: string, qa?: QaQuestion | null) {
  bubbles.value.push({ role, text, qa })
  nextTick(() => { const el = qaScroll.value; if (el) el.scrollTop = el.scrollHeight })
}

async function scrollBottom() {
  await nextTick()
  const el = qaScroll.value
  if (el) el.scrollTop = el.scrollHeight
}

onMounted(async () => {
  try {
    const g = await fetchOnboardingGroups()
    domains.value = g.domains
    const init: Record<string, string> = {}
    for (const d of g.domains) for (const grp of d.groups) init[grp.id] = ''
    groupStatus.value = init
  } catch { /* ignore */ }
  // 管家开始身份对话
  try {
    const st = await getQaState(store.userId)
    if (st.identity_done) {
      push('assistant', '你的身份题已经答完啦。接下来做能力自评，确认每个知识域的掌握情况。')
      stage.value = 'groups'
      return
    }
    push('assistant', '你好，我是旅鸢。为了给你定制入境游向导的学习路线，先回答 6 个关于你的小问题（点选项即可）。')
    if (st.question) push('assistant', `第 ${st.step + 1}/${st.total} 题`, st.question)
  } catch {
    push('assistant', '先验画像服务暂时不可用，请刷新重试。')
  }
})

async function choose(q: QaQuestion, opt: OnbOption) {
  if (answering.value) return
  answering.value = true
  // 当前题目卡就地收起：转为用户气泡 + 管家推进
  bubbles.value = bubbles.value.map((b) => (b.qa && b.qa.id === q.id ? { role: b.role, text: b.text } : b))
  push('user', `我选 · ${opt.label}`)
  try {
    const st = await answerQa({ user_id: store.userId, question_id: q.id, option_id: opt.id })
    if (st.identity_done || !st.pending) {
      push('assistant', st.lead || '身份题已答完，接下来做能力自评。')
      stage.value = 'groups'
    } else {
      push('assistant', st.lead || '收到，我们继续。')
      if (st.question) push('assistant', `第 ${st.step + 1}/${st.total} 题`, st.question)
    }
  } catch (e: any) {
    push('assistant', '刚才没保存上，请再点一次选项。')
  } finally {
    answering.value = false
    await scrollBottom()
  }
}

function toggleDomain(id: string) {
  const next = new Set(expanded.value)
  if (next.has(id)) next.delete(id); else next.add(id)
  expanded.value = next
}
function masteredCountOf(dm: OnbDomain): number { return dm.groups.filter((g) => groupStatus.value[g.id] === 'mastered').length }
function domainStatusOf(dm: OnbDomain): string {
  const st = dm.groups.map((g) => groupStatus.value[g.id] || '')
  if (st.length && st.every((x) => x === 'mastered')) return 'mastered'
  if (st.length && st.every((x) => x === 'learning')) return 'learning'
  return ''
}
function setDomain(dm: OnbDomain, st: string) {
  const cur = domainStatusOf(dm)
  const setTo = cur === st ? '' : st
  const next = { ...groupStatus.value }
  for (const g of dm.groups) next[g.id] = setTo
  groupStatus.value = next
}
function setGroup(id: string, st: string) {
  const cur = groupStatus.value[id]
  groupStatus.value = { ...groupStatus.value, [id]: cur === st ? '' : st }
}

async function submit() {
  submitting.value = true
  planError.value = ''
  try {
    const resolved: Record<string, string> = {}
    for (const d of domains.value) for (const g of d.groups) {
      resolved[g.id] = groupStatus.value[g.id] === 'mastered' ? 'mastered' : 'learning'
    }
    const r = await submitOnboarding({ user_id: store.userId, answers: {}, group_status: resolved })
    persona.value = r.persona
    submitCounts.value = r.counts
    stage.value = 'persona'
  } catch (e: any) {
    planError.value = e?.response?.data?.detail || e?.message || '提交失败，请重试'
  } finally {
    submitting.value = false
  }
}

async function generatePlan() {
  planning.value = true
  planError.value = ''
  plan.value = null
  try { plan.value = await planLearningPath(store.userId) }
  catch (e: any) { planError.value = e?.response?.data?.detail || e?.message || '生成失败，请稍后重试' }
  finally { planning.value = false }
}

async function replan() {
  replanning.value = true
  planError.value = ''
  try { plan.value = await planLearningPath(store.userId, feedback.value) }
  catch (e: any) { planError.value = e?.response?.data?.detail || e?.message || '重排失败，请稍后重试' }
  finally { replanning.value = false }
}

function confirmDone() {
  onb.markDone(persona.value, groupStatus.value)
  emit('done')
}
</script>
<style lang="scss" scoped>
@use '@/styles/tokens' as *;

.onb-wrap { display: flex; justify-content: center; }
.onb-card { width: 100%; max-width: 760px; border-radius: 16px; overflow: hidden; background: #fff; border: 1px solid $color-border; box-shadow: $shadow-card-hover; }
.onb-head { display: flex; align-items: center; gap: 10px; padding: 14px 20px; background: linear-gradient(120deg, $color-primary, $color-primary-light);
  .onb-title { display: inline-flex; align-items: center; gap: 7px; color: #fff; font-size: 15px; font-weight: 700; letter-spacing: 1px; .ob-dot { width: 9px; height: 9px; border-radius: 50%; background: $color-accent; animation: obPing 1.6s ease-out infinite; } }
  .onb-step { margin-left: auto; color: rgba(255,255,255,.85); font-size: 12px; } }
.ob-body { padding: 16px 20px 20px; max-height: 66vh; overflow-y: auto; }
.ob-intro { color: $color-text-secondary; font-size: 13px; line-height: 1.8; margin: 0 0 12px; }

.ob-chat { display: flex; flex-direction: column; gap: 12px; max-height: 52vh; overflow-y: auto; padding: 4px 2px; }
.bubble-row { display: flex; gap: 8px; align-items: flex-start;
  &.user { flex-direction: row-reverse; }
  .b-av { width: 30px; height: 30px; border-radius: 50%; background: $color-primary; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700; flex-shrink: 0; }
  .b-main { max-width: 86%; display: flex; flex-direction: column; gap: 8px; align-items: flex-start;
    .bubble { padding: 9px 13px; border-radius: 12px; font-size: 13.5px; line-height: 1.75; color: $color-text; background: #fff; border: 1px solid $color-border; } }
  &.user .b-main { align-items: flex-end; }
  &.user .bubble { background: $color-primary; color: #fff; border: none; border-bottom-right-radius: 3px; } }
.qa-card { width: 100%; max-width: 560px; border: 1px solid $color-border; border-radius: 12px; background: #F8FBFF; padding: 12px 14px;
  .qa-q { font-size: 14px; font-weight: 700; color: $color-text; margin-bottom: 10px; }
  .qa-opts { display: flex; flex-direction: column; gap: 7px; }
  .qa-opt { display: flex; align-items: center; gap: 8px; padding: 8px 12px; border: 1px solid $color-border; border-radius: 9px; background: #fff; font-size: 13px; color: $color-text; cursor: pointer; text-align: left; transition: all .15s;
    i { width: 8px; height: 8px; border-radius: 50%; border: 1px solid $color-border-d10; background: #fff; flex-shrink: 0; }
    &:hover { border-color: $color-primary; i { background: $color-accent; border-color: $color-accent; } }
    &:disabled { opacity: .6; cursor: not-allowed; } } }

.ob-domain { border: 1px solid $color-border; border-radius: 12px; margin-bottom: 10px; overflow: hidden; }
.ob-domain-row { display: flex; align-items: center; gap: 8px; padding: 9px 12px; background: $color-secondary-bg; }
.ob-domain-expand { border: none; background: none; cursor: pointer; color: $color-text-secondary; display: inline-flex; }
.ob-domain-title { font-size: 13.5px; font-weight: 700; color: $color-text; }
.ob-domain-count { font-size: 11.5px; color: $color-text-secondary; }
.ob-domain-seg, .ob-group-seg { margin-left: auto; display: inline-flex; gap: 5px; }
.ob-mini { border: 1px solid $color-border; background: #fff; color: $color-text-secondary; font-size: 11.5px; padding: 3px 9px; border-radius: 999px; cursor: pointer;
  &.on { background: $color-primary; border-color: $color-primary; color: #fff; } }
.ob-domain-groups { padding: 6px 12px 8px 34px; display: flex; flex-direction: column; gap: 4px; }
.ob-group { display: flex; align-items: center; gap: 8px; padding: 5px 4px; }
.ob-group-title { font-size: 12.5px; color: $color-text; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 52%; }
.ob-group-meta { font-size: 11px; color: $color-text-secondary; flex-shrink: 0; }
.ob-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 16px; }
.ob-btn { border: none; border-radius: 999px; padding: 8px 18px; font-size: 13px; cursor: pointer; display: inline-flex; align-items: center; gap: 6px;
  &.primary { background: $color-primary; color: #fff; &:disabled { opacity: .5; cursor: not-allowed; } }
  &.ghost { background: $color-secondary-bg; color: $color-primary; border: 1px solid $color-border; } }

.ob-persona { border: 1px solid $color-border; border-radius: 12px; padding: 14px 16px; margin-bottom: 12px; }
.ob-persona-head { display: inline-flex; align-items: center; gap: 6px; color: $color-primary; font-weight: 700; font-size: 12px; letter-spacing: 1px; }
.ob-persona-label { font-size: 18px; font-weight: 800; color: $color-text; margin: 6px 0 2px; }
.ob-persona-summary { font-size: 13px; color: $color-accent-d15; font-weight: 600; margin-bottom: 6px; }
.ob-persona-desc { font-size: 12.5px; color: $color-text-secondary; line-height: 1.8; }
.ob-persona-stats { display: flex; gap: 18px; margin-top: 10px; flex-wrap: wrap; font-size: 12px; color: $color-text-secondary;
  b { color: $color-primary; font-size: 15px; margin-left: 4px; } }

.ob-plan { border: 1px dashed $color-border-d10; border-radius: 12px; padding: 12px 14px; margin-bottom: 12px; }
.ob-plan-head { display: flex; align-items: center; gap: 7px; font-weight: 700; color: $color-text; font-size: 13px; }
.ob-plan-tag { margin-left: auto; font-size: 11px; font-weight: 500; color: #fff; background: $color-primary; padding: 2px 9px; border-radius: 999px; &.fb { background: #b8953a; } }
.ob-plan-note { font-size: 12.5px; color: $color-text-secondary; line-height: 1.7; margin: 8px 0; }
.ob-plan-stats { display: flex; gap: 16px; font-size: 12px; color: $color-text-secondary; margin-bottom: 8px; b { color: $color-primary; } }
.ob-plan-list { display: flex; flex-direction: column; gap: 3px; max-height: 220px; overflow-y: auto; padding-right: 4px; }
.ob-plan-item { font-size: 12.5px; color: $color-text; display: flex; gap: 8px; }
.ob-plan-idx { width: 16px; height: 16px; border-radius: 50%; background: $color-accent; color: #fff; font-size: 10px; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; }
.ob-loading { display: flex; align-items: center; gap: 8px; color: $color-text-secondary; }
.ob-error { color: #c0504d; }
.ob-replan { display: flex; flex-direction: column; gap: 8px; margin-top: 10px; textarea { width: 100%; border: 1px solid $color-border; border-radius: 8px; padding: 8px 10px; font-size: 12.5px; resize: vertical; } }
.ma-spin { width: 14px; height: 14px; border-radius: 50%; border: 2px solid rgba(51,143,242,.3); border-top-color: $color-accent; animation: obSpin .7s linear infinite; display: inline-block; }
@keyframes obSpin { to { transform: rotate(360deg); } }
@keyframes obPing { 0% { box-shadow: 0 0 0 0 rgba(51,143,242,.45); } 70% { box-shadow: 0 0 0 6px rgba(51,143,242,0); } 100% { box-shadow: 0 0 0 0 rgba(51,143,242,0); } }
</style>
