<template>
  <div class="tg-page">
    <!-- ══════════ 沙盒模拟 sandbox ══════════ -->
      <header class="ph">
        <div class="ph-left">
          <button v-if="scene !== null" class="ghost-btn" :disabled="sbSending || sbEnding || co.running" @click="exitScene">
            <SIcon name="back" :size="12" /> 返回
          </button>
          <h2 class="ph-title">{{ scene === null ? galleryTitle : modeTitle }}</h2>
        </div>
        <div class="ph-right">
          <span v-if="scene === null && sandboxStats.n" class="pill">
            <SIcon name="trophy" :size="11" /> 平均 {{ sandboxStats.avg }} 分
          </span>
          <span v-else-if="scene !== null && stage" class="pill gold-pill">
            <SIcon name="target" :size="11" /> {{ stage.title }}
          </span>
          <button v-if="scene !== null" class="ghost-btn" :disabled="sbSending || sbEnding || co.running" @click="resetScene">↺ 重开</button>
        </div>
      </header>

      <div class="tg-body">
        <!-- ══ 场景列表视图 ══ -->
        <Transition name="content-switch" mode="out-in">
        <div v-if="scene === null" :key="galleryKey" class="tg-list" :class="`gallery-${TRAIN_TABS[tab].k}`">
          <div class="gallery-intro" :class="{ integrated: tab === 0 }">
            <div class="gallery-intro-copy"><span class="gallery-eyebrow">{{ tab === 0 ? '完整任务，逐步进阶' : '聚焦一项能力' }}</span><h3>{{ galleryIntro.heading }}</h3><p>{{ galleryIntro.description }}</p></div>
            <ol v-if="tab === 0" class="gallery-process"><li v-for="(label, index) in galleryIntro.steps" :key="label"><span>{{ String(index + 1).padStart(2, '0') }}</span><b>{{ label }}</b></li></ol>
            <span v-else class="gallery-intro-symbol"><SIcon :name="TRAIN_TABS[tab].i" :size="35" /></span>
          </div>
          <!-- 成绩概览条 -->
          <div v-if="sandboxStats.n" class="tf-overview">
            <div class="ov-item"><div class="v">{{ sandboxStats.n }}</div><div class="k">累计挑战场次</div></div>
            <div class="ov-sep"></div>
            <div class="ov-item"><div class="v" style="color:#338FF2">{{ sandboxStats.avg }}<i>分</i></div><div class="k">平均得分</div></div>
            <div class="ov-sep"></div>
            <div class="ov-item"><div class="v">{{ sandboxStats.top }}<i>分</i></div><div class="k">历史最高</div></div>
            <div class="ov-sep"></div>
            <div class="ov-item ov-last"><div class="v">{{ sandboxStats.last?.score }}<i>分</i></div><div class="k">上次   {{ sandboxStats.last?.sceneName }}</div></div>
          </div>
          <div class="gallery-toolbar"><span>{{ tab === 0 ? '本阶段训练' : '选择练习场景' }}</span><div v-if="['communication', 'narrate'].includes(TRAIN_TABS[tab].k)" class="communication-modes"><button :class="{ active: tab === 1 }" @click="selectTab(1)">电话与微信</button><button :class="{ active: tab === 3 }" @click="selectTab(3)">即兴讲解</button></div><small>{{ currentList.length }} 个场景</small></div>
          <div v-if="templatesLoading" class="gallery-empty"><span class="sb-spinner"></span>正在加载场景</div>
          <div v-else-if="!currentList.length" class="gallery-empty">{{ templatesError ? '场景暂时未加载' : '暂无可用场景' }}<button v-if="templatesError" class="ghost-btn" @click="loadTemplates">重试</button></div>
          <template v-else-if="tab === 0">
            <div v-if="phaseLessons.length" class="phase-lessons"><div class="gallery-section-label"><h4>分项练习</h4><span>逐项熟悉本阶段任务</span></div><div class="scenario-grid integrated-grid"><TrainingScenarioCard v-for="s in phaseLessons" :key="s.template_id" :scenario="s" integrated :icon="scenarioIcon(s)" :locked="isLocked(s)" :completed="completedTplIds.has(s.template_id)" @select="guardScene" /></div></div>
            <div v-if="phaseCapstones.length" class="phase-capstones"><div class="gallery-section-label"><h4>全流程实战</h4><span>把各项能力串成完整任务</span></div><TrainingScenarioCard v-for="s in phaseCapstones" :key="s.template_id" :scenario="s" integrated capstone :icon="scenarioIcon(s)" :locked="isLocked(s)" :completed="completedTplIds.has(s.template_id)" @select="guardScene" /></div>
          </template>
          <div v-else class="scenario-grid" :class="{ 'emergency-grid': tab === 2 }"><TrainingScenarioCard v-for="s in currentList" :key="s.template_id" :scenario="s" :icon="scenarioIcon(s)" :locked="isLocked(s)" :completed="completedTplIds.has(s.template_id)" @select="guardScene" /></div>
          <p v-if="!templatesLoading && currentList.length" class="gallery-helper"><SIcon name="sparkle" :size="13" />{{ accounts.isSignedIn ? '自由对话，完成练习后查看表现反馈' : '可先浏览场景，登录并完善画像后开始训练' }}</p>
        </div>

        <!-- ══ 对话式模拟视图 ══ -->
        <div v-else-if="sbSession" key="session" class="sb-layout">
          <!-- 左侧：游客资料 + 阶段 + 操作 -->
          <aside class="sb-side">
            <div class="sb-customer">
              <div class="sc-avatar"><SIcon name="user" :size="26" color="#338FF2" /></div>
              <div class="sc-info">
                <div class="sc-name">{{ sbSession.customer.name }}<span class="sc-nat">{{ sbSession.customer.nationality }}   {{ sbSession.customer.age }}岁</span></div>
                <div class="sc-tag">性格   {{ sbSession.customer.personality }}</div>
                <!-- 沙盒 v3：游客多维属性（职业/健康/消费/说话风格，字段缺失时隐藏） -->
                <div v-if="scExtraRows.length" class="sc-multi">
                  <div v-for="(row, ri) in scExtraRows" :key="ri" class="sc-mrow">
                    <span v-for="(it, ii) in row" :key="ii" class="sc-item"><i>{{ it[0] }}</i>{{ it[1] }}</span>
                  </div>
                </div>
                <div class="sc-line"><span class="l">偏好</span>{{ sbSession.customer.preferences }}</div>
                <div class="sc-line"><span class="l">特点</span>{{ sbSession.customer.quirks }}</div>
              </div>
            </div>
            <!-- 沙盒 v2：游客心情条（信任度/情绪实时变化） -->
            <div class="sb-mood-bar" v-if="sbSession.customer_state" :class="{ tension: sbSession.customer_state.tension }">
              <div class="smb-head">
                <span class="smb-t">游客心情</span>
                <span class="smb-mood" :class="'m-' + sbSession.customer_state.mood">{{ moodLabel(sbSession.customer_state.mood) }}</span>
              </div>
              <div class="smb-track">
                <div class="smb-fill" :class="{ low: sbSession.customer_state.trust < 40, high: sbSession.customer_state.trust >= 70 }"
                     :style="{ width: sbSession.customer_state.trust + '%' }"></div>
              </div>
              <div class="smb-foot">
                <span>信任度 {{ sbSession.customer_state.trust }} 分</span>
                <span v-if="sbSession.customer_state.tension" class="smb-warn">⚠ 游客情绪紧张</span>
                <span v-else-if="sbSession.customer_state.hidden_revealed" class="smb-reveal">💬 已向你说出心里话</span>
              </div>
            </div>
            <div class="sb-stage">
              <div class="sb-stage-top">
                <span class="t"><SIcon name="map" :size="11" color="#338FF2" /> 带团进度   {{ sbSession.stage.title }}</span>
                <span class="pct">第 {{ sbSession.stage.index + 1 }} 阶段，共 {{ sbSession.stage.total }} 阶段</span>
              </div>
              <div class="track"><div class="fill" :style="{ width: Math.round((sbSession.stage.index + 1) / sbSession.stage.total * 100) + '%' }"></div></div>
              <div class="sb-stage-obj">{{ sbSession.stage.objective }}</div>
            </div>
            <div class="sb-actions">
              <button class="ctrl-btn" :class="{ on: kbOpen }" @click="toggleKb"><SIcon name="book" :size="14" /> 知识提示</button>
              <button class="ctrl-score" :disabled="sbEnding" @click="handleSandboxEnd">
                <SIcon name="star" :size="14" color="#fff" /> {{ sbEnding ? '评估中...' : '结束带团' }}
              </button>
            </div>
          </aside>

          <!-- 右侧：对话区 -->
          <div class="sb-main">
            <div v-if="showBridgeTip && sbSession" class="cb-tip">
              <SIcon name="star" :size="12" color="#256CA7" />
              <span>找找共通点、构建文化桥，在入境游接待中可能更加分哦</span>
              <button class="cb-close" @click="showBridgeTip = false"><SIcon name="x" :size="10" /></button>
            </div>
            <div ref="chatRef" class="sb-chat">
              <div class="sb-scene-card">
                <div class="sc-t">{{ sbSession.template.title }}</div>
                <div class="sc-d">{{ sbSession.template.task }}</div>
                <div class="sc-loc"><SIcon name="pin" :size="10" color="#338FF2" /> {{ sbSession.template.location }}</div>
              </div>
              <div v-if="stageBanner" class="sb-banner"><SIcon name="target" :size="12" color="#338FF2" /> {{ stageBanner }}</div>
              <div v-for="(m, i) in messages" :key="i" class="sb-row" :class="m.role">
                <div class="sb-av" :class="m.role">{{ m.role === 'customer' ? (sbSession.customer.name ? sbSession.customer.name[0] : '客') : '我' }}</div>
                <div class="sb-bubble">
                  <div v-if="m.role === 'customer' && m.mood" class="sb-mood">{{ moodLabel(m.mood) }}</div>
                  <div class="sb-text">{{ display(m.content) }}</div>
                </div>
              </div>
              <div v-if="sbSending" class="sb-row customer">
                <div class="sb-av">…</div>
                <div class="sb-bubble sb-thinking">游客正在思考…</div>
              </div>
            </div>
            <div class="sb-input">
              <RealtimeVoiceBar v-if="isVoiceSession"
                :session-id="sbSession!.session_id" :user-id="store.userId"
                :language="sbSession!.language || ''" :voice="sbSession!.voice || ''"
                @guide-message="onVoiceGuideMsg" @customer-message="onVoiceCustomerMsg" />
              <template v-else>
              <div class="sb-sugs">
                <button v-for="s in suggestions" :key="s" class="sug" @click="sbInput = s"><SIcon name="plus" :size="10" /> {{ s }}</button>
              </div>
              <div class="sb-input-row">
                <button class="mic-btn" :class="{ on: sbRecOn }" :disabled="sbTranscribing"
                        :title="sbRecOn ? '停止录音' : '语音输入'" @click="toggleSbMic">
                  <SIcon name="mic" :size="15" :color="sbRecOn ? '#fff' : '#338FF2'" />
                </button>
                <span v-if="sbRecLabel" class="mic-tag">{{ sbRecLabel }}</span>
                <textarea v-model="sbInput" rows="2" placeholder="以导游身份对游客说话…（自由发挥，游客会实时回应）" @keydown.enter.exact.prevent="handleSandboxSend" />
                <button class="send-btn" :disabled="sbSending || !sbInput.trim()" @click="handleSandboxSend">
                  <SIcon name="msg" :size="15" color="#fff" /> 发送
                </button>
              </div>
              </template>
            </div>
          </div>

          <!-- 知识提示面板 -->
          <div v-if="kbOpen" class="tr-panel sb-kb">
            <div class="hd"><SIcon name="book" :size="13" color="#338FF2" /><span class="t">知识提示   {{ sbSession.stage.title }}</span><button class="x" @click="kbOpen = false"><SIcon name="x" :size="11" /></button></div>
            <div class="sb-kb-hint">{{ sbSession.stage.guide_hint }}</div>
            <div v-if="kbHints.length" class="kb-facts">
              <div v-for="f in kbHints" :key="f.title" class="kb-fact"><div class="k">{{ f.title }}</div><div class="v">{{ display(f.content) }}</div></div>
            </div>
            <div v-else class="sb-kb-empty"><SIcon name="book" :size="12" color="#338FF2" /> 正在检索知识库…</div>
          </div>
        </div>

        <!-- ══ 场景搭建中（加载遮罩：居中 + loading + 三点循环） ══ -->
        <div v-else class="sb-building">
          <div class="sb-building-inner">
            <span class="sb-spinner"></span>
            <span class="sb-building-text">场景正在搭建中，请稍后</span>
            <span class="sb-dots"><i class="dot"></i><i class="dot"></i><i class="dot"></i></span>
          </div>
        </div>
        </Transition>
      </div>

      <!-- ══ 结算弹窗（AI 评估） ══ -->
      <div v-if="scoreOpen && settle" class="score-modal" @click.self="closeScore(false)">
        <div class="score-card sb-score-card">
          <div class="score-top">
            <div class="score-total">
              <svg width="96" height="96" style="transform:rotate(-90deg)">
                <circle cx="48" cy="48" r="42" stroke="#EAF3FC" stroke-width="7" fill="none"/>
                <circle cx="48" cy="48" r="42" :stroke="settle.total >= 60 ? '#338FF2' : '#F87171'" stroke-width="7" fill="none" stroke-linecap="round"
                  :stroke-dasharray="2 * Math.PI * 42" :stroke-dashoffset="2 * Math.PI * 42 * (1 - Math.min(settle.total, 100) / 100)"
                  style="transition:stroke-dashoffset 1.2s cubic-bezier(.4,0,.2,1)"/>
              </svg>
              <div class="num"><b>{{ settle.total }}</b><i>综合评分</i></div>
            </div>
            <div class="score-meta">
              <div class="t">{{ settle.modeLabel }}   AI 评估
              </div>
              <div class="s">{{ settle.sceneName }}   {{ settle.subLabel }}</div>
            </div>
            <button class="score-close" @click="closeScore(false)"><SIcon name="x" :size="12" /></button>
          </div>

          <!-- 沙盒 v3：场景结果徽标（成功=达成目标 / 失败=场景失败+原因；abandoned/未知不显示） -->
          <div v-if="settle.outcome === 'success' || settle.outcome === 'failed'" class="scene-badge" :class="settle.outcome">
            <span class="sb-ic">{{ settle.outcome === 'success' ? '✓' : '✗' }}</span>
            <span class="sb-txt">
              {{ settle.outcome === 'success' ? '达成目标' : '场景失败' }}
              <em v-if="settle.outcome === 'failed' && settle.failReason">{{ settle.failReason }}</em>
            </span>
          </div>
          <!-- 失败时在总分下方提示复盘 -->
          <div v-if="settle.outcome === 'failed'" class="score-fail-hint">这一局搞砸了，让旅鸢给你复盘</div>

          <!-- 五维能力条 -->
          <div class="score-dims">
            <div v-for="d in settle.dims" :key="d[0]" class="dim-row">
              <div class="top"><span class="l">{{ d[0] }}</span><span class="v">{{ d[1] }}.0</span></div>
              <div class="dim-bar"><div class="f" :style="{ width: d[1] * 20 + '%' }"></div></div>
            </div>
          </div>

          <!-- 文化桥   附加观察（不计入总分） -->
          <div v-if="settle.cultureBridge" class="sb-fb-sec">
            <div class="t gold"><SIcon name="star" :size="11" color="#338FF2" /> 文化桥   附加观察（不计入总分）</div>
            <div class="cb-score">评分 <b>{{ settle.cultureBridge.score }}</b>、5   依据：共通点讲得是否到位且真实</div>
            <div class="cb-summary">{{ settle.cultureBridge.summary }}</div>
          </div>

          <!-- 语音表现（语速 / 停顿） -->
          <div v-if="voicePerf" class="sb-fb-sec">
            <div class="t gold"><SIcon name="mic" :size="11" color="#338FF2" /> 语音表现</div>
            <div class="vp-perf">
              <div class="vp-item"><b>{{ voicePerf.rate }}</b> 字、分钟 <span class="note">{{ voicePerf.rateNote }}</span></div>
              <div class="vp-item"><b>{{ voicePerf.pauses }}</b> 次停顿（{{ voicePerf.pauseSec }}s）<span class="note">{{ voicePerf.pauseNote }}</span></div>
              <div class="vp-item"><b>{{ voicePerf.recordings }}</b> 段语音   共 {{ voicePerf.totalSec }}s</div>
            </div>
          </div>

          <div v-if="settle.strengths && settle.strengths.length" class="sb-fb-sec">
            <div class="t ok"><SIcon name="check" :size="11" color="#338FF2" /> 亮点</div>
            <ul><li v-for="s in settle.strengths" :key="s">{{ s }}</li></ul>
          </div>
          <div v-if="settle.weaknesses && settle.weaknesses.length" class="sb-fb-sec">
            <div class="t warn"><SIcon name="warn" :size="11" color="#F87171" /> 不足</div>
            <ul><li v-for="w in settle.weaknesses" :key="w">{{ w }}</li></ul>
          </div>
          <div v-if="settle.suggestions && settle.suggestions.length" class="sb-fb-sec">
            <div class="t gold"><SIcon name="target" :size="11" color="#338FF2" /> 提升建议</div>
            <ul><li v-for="s in settle.suggestions" :key="s">{{ s }}</li></ul>
          </div>
          <div v-if="settle.skills && settle.skills.length" class="sb-fb-sec">
            <div class="t gold"><SIcon name="book" :size="11" color="#338FF2" /> 关联技能点   建议复习</div>
            <div class="sb-skill-list">
              <div v-for="sk in settle.skills" :key="sk.id" class="sb-skill"><span class="k">{{ sk.title }}</span><span class="d">{{ display(sk.content) }}</span></div>
            </div>
          </div>

          <div v-if="settle.note" class="score-note"><div class="t"><SIcon name="star" :size="11" color="#338FF2" /> AI 点评</div><p>{{ settle.note }}</p></div>
          <div class="sq-actions">
            <button class="sq-btn ghost" @click="retryFromScore"><SIcon name="timer" :size="12" /> {{ settle.retryLabel }}</button>
            <button class="sq-btn primary" @click="closeScore(true)"><SIcon name="check" :size="12" color="#fff" /> 完成训练</button>
          </div>
          <!-- 沙盒 v3：带评价摘要去找旅鸢复盘（写入 localStorage → 跳首页自动发送） -->
          <div class="sq-review">
            <button class="sq-btn review" @click="goReviewWithSinan"><SIcon name="star" :size="12" color="#fff" /> 让旅鸢讲讲怎么提升</button>
          </div>
        </div>
      </div>

        <!-- 入境定制游全流程：进入前选择训练语言（语音实战） -->
        <div v-if="langModal.open" class="lm-mask" @click.self="langModal.open = false">
          <div class="lm-card">
            <div class="lm-title">选择训练语言   {{ langModal.tpl?.title }}</div>
            <div class="lm-sub">选择训练语言后进入「实时语音」实战（语言决定游客国籍与音色）；选「传统文字」则沿用原对话模式。</div>
            <div class="lm-opts">
              <button v-for="o in LANG_OPTIONS" :key="o.k" class="lm-opt" :class="{ on: langModal.lang === o.k }" @click="langModal.lang = o.k">
                <b>{{ o.label }}</b><span>{{ o.nat }}</span>
              </button>
            </div>
            <div class="lm-actions">
              <button class="ghost-btn" @click="langModal.open = false">取消</button>
              <button class="lm-go" @click="confirmLang">{{ langModal.lang ? '开始语音实战' : '进入场景' }}</button>
            </div>
          </div>
        </div>
      <div class="toast" :class="{ show: toastMsg !== '' }" id="globalToast">
        <SIcon name="check" :size="14" color="#fff" /> {{ toastMsg }}
      </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, onActivated, onDeactivated, ref, watch } from 'vue'
import { cleanDisplayText as display } from '@/utils/displayText'
import { useRouter, useRoute, onBeforeRouteUpdate } from 'vue-router'
import { classifyError } from '@/api/client'
import { ElMessage } from 'element-plus'
import { useAppStore } from '@/stores/app'
import { useAccountsStore } from '@/stores/accounts'
import { useOnboardingStore } from '@/stores/onboarding'
import SIcon from '@/components/SIcon.vue'
import TrainingScenarioCard from '@/components/TrainingScenarioCard.vue'
import { useCooperationStore } from '@/stores/cooperation'
import { integratedPhase, inIntegratedPhase } from '@/utils/navigation'
import RealtimeVoiceBar from '@/components/RealtimeVoiceBar.vue'
import {
  listSandboxTemplates, createSandboxSession, getSandboxSession,
  sendSandboxMessage, endSandboxSession, listSandboxRecords, appendSandboxVoiceMessages,
  type SandboxTemplate, type SandboxSession, type RecommendedSkill,
} from '@/api/sandbox'
import { transcribeAudio } from '@/api/voice'

const store = useAppStore()
const router = useRouter()
const route = useRoute()
const co = useCooperationStore()
const accounts = useAccountsStore(), onb = useOnboardingStore()

// ══════════════════ 沙盒（对话式   后端驱动）══════════════════

const TRAIN_TABS = [
  { k: 'integrated', l: '综合实战', s: '行前   行中   行后   一站式带团', i: 'map' },
  { k: 'communication', l: '沟通与接待训练', s: '电话   微信   跨文化接待', i: 'msg' },
  { k: 'emergency', l: '应急处理', s: '真实情境   自由对话   应变处理', i: 'shield' },
  { k: 'narrate', l: '即兴讲解训练', s: '游客追问   现场即兴讲解', i: 'mic' },
]

const templates = ref<SandboxTemplate[]>([])
const templatesLoading = ref(true), templatesError = ref(false)
const tab = ref(0)
const scene = ref<string | null>(null)
const sbSession = ref<SandboxSession | null>(null)
const sbSending = ref(false)
const sbEnding = ref(false)
const sbInput = ref('')
// ── 语音输入（录音 -> Whisper 转写 -> 填入对话；结算时展示语速/停顿表现）──
const sbRecOn = ref(false)
const sbTranscribing = ref(false)
const sbRecLabel = ref('')
// 语音表现累计（语速/停顿，来自 /voice/transcribe 的 speech 指标）
const sbSpeechAgg = ref({ recordings: 0, chars: 0, speakSec: 0, pauses: 0, pauseSec: 0 })
let sbMediaRec: MediaRecorder | null = null
let sbChunks: BlobPart[] = []
let sbRecTimer: ReturnType<typeof setInterval> | null = null
let sbRecSec = 0
const kbOpen = ref(false)
const stageBanner = ref('')
const showBridgeTip = ref(false)
const kbHints = ref<{ title: string; content: string }[]>([])
const chatRef = ref<HTMLElement | null>(null)
const toastMsg = ref('')
let toastTimer: ReturnType<typeof setTimeout> | null = null
let bannerTimer: ReturnType<typeof setTimeout> | null = null

// 成绩概览（后端沙盒记录）
const sandboxStats = ref({ n: 0, avg: 0, top: 0, last: null as { score: number; sceneName: string } | null })
const completedTplIds = ref<Set<string>>(new Set())

function listFor(key:string) {
  if(key === 'integrated') return templates.value.filter(t => t.mode === 'fullflow')
  if(key === 'communication') return templates.value.filter(t => t.mode === 'communication' || (t.mode === 'scenario' && t.category !== '应急处置'))
  if(key === 'emergency') return templates.value.filter(t => t.mode === 'scenario' && t.category === '应急处置')
  return templates.value.filter(t => t.mode === key)
}
const currentList = computed(() => {
  const items = listFor(TRAIN_TABS[tab.value].k)
  return tab.value === 0 ? items.filter(item => inIntegratedPhase(item.template_id, integratedPhase(route.query.phase))) : items
})
const galleryTitle = computed(() => tab.value === 0 ? ({ pre:'行前定制', mid:'行中接待', post:'行后复盘' }[integratedPhase(route.query.phase)]) : TRAIN_TABS[tab.value].l)
const galleryKey = computed(() => `${TRAIN_TABS[tab.value].k}-${tab.value === 0 ? integratedPhase(route.query.phase) : ''}`)
const phaseLessons = computed(() => currentList.value.filter(item => !item.template_id.startsWith('t_ff_')))
const phaseCapstones = computed(() => currentList.value.filter(item => item.template_id.startsWith('t_ff_')))
const galleryIntro = computed(() => {
  if (tab.value === 0) return {
    pre: { heading: '把需求变成一段好行程', description: '从需求访谈到方案确认，练习行前定制的完整过程。', steps: ['了解需求', '规划行程', '沟通确认'] },
    mid: { heading: '让每一程接待从容有序', description: '在真实带团情境中，串联接待、讲解与跨文化沟通。', steps: ['接待服务', '文化沟通', '现场应变'] },
    post: { heading: '让一次旅程成为下一次进步', description: '通过回访与复盘，整理服务表现和改进方向。', steps: ['游客回访', '服务复盘', '改进总结'] },
  }[integratedPhase(route.query.phase)]
  if (tab.value === 2) return { heading: '遇到变化，也能稳妥应对', description: '从识别问题、安抚情绪到提出方案，练习关键时刻的应变能力。', steps: [] }
  if (tab.value === 3) return { heading: '让文化讲解自然发生', description: '围绕现场情境与游客追问，练习清晰、有趣的即兴讲解。', steps: [] }
  return { heading: '把每一次沟通练到从容', description: '在电话、微信与接待情境中，练习倾听、表达和需求确认。', steps: [] }
})
function scenarioIcon(item: SandboxTemplate) {
  if (tab.value === 0) return { pre:'notebook', mid:'globe', post:'trend' }[integratedPhase(route.query.phase)]
  if (tab.value === 2) return 'shield'
  if (tab.value === 3) return 'mic'
  return /电话/.test(item.title) ? 'phone' : 'msg'
}
function applyFocus() {
  if(route.path !== '/app/training') return
  const index = TRAIN_TABS.findIndex(t => t.k === route.query.focus)
  if(index >= 0 && index !== tab.value && !sbSending.value && !sbEnding.value) { exitScene(); tab.value=index }
}
function selectTab(index:number) { void router.replace({ query:{ focus:TRAIN_TABS[index].k } }) }
watch(() => route.query.focus, applyFocus)
watch(() => route.query.phase, () => { if (route.path === '/app/training' && tab.value === 0) exitScene() })
onBeforeRouteUpdate((to, from) => {
  if (to.path === from.path && (to.query.focus !== from.query.focus || to.query.phase !== from.query.phase) && (sbSending.value || sbEnding.value || (scene.value !== null && co.running))) {
    ElMessage.info('当前协作完成后即可切换训练')
    return false
  }
})
onActivated(() => { applyFocus(); syncPractice(); void co.refreshLearning() })
onDeactivated(() => { co.practice=null })
function syncPractice() { if(route.path === '/app/training') co.practice=sbSession.value && scene.value ? { title:sbSession.value.stage.title,index:sbSession.value.stage.index,total:sbSession.value.stage.total } : null }
watch(sbSession, syncPractice, { deep:true })

const modeTitle = computed(() => {
  const t = templates.value.find(x => x.template_id === scene.value)
  return t ? (TRAIN_TABS[tab.value].l + '：' + t.title) : '实战训练'
})
const stage = computed(() => sbSession.value?.stage ?? null)
const messages = computed(() => sbSession.value?.messages ?? [])

// 沙盒 v3：游客多维属性（职业[含性别前缀]/健康/消费/说话风格，两两成行；字段缺失自动隐藏）
const scExtraRows = computed<[string, string][][]>(() => {
  const c = sbSession.value?.customer
  if (!c) return []
  const items: [string, string][] = []
  const job = [c.gender, c.occupation].filter(Boolean).join('   ')
  if (job) items.push(['职业', job])
  if (c.health) items.push(['健康', c.health])
  if (c.consumption) items.push(['消费', c.consumption])
  if (c.speech_style) items.push(['风格', c.speech_style])
  const rows: [string, string][][] = []
  for (let i = 0; i < items.length; i += 2) rows.push(items.slice(i, i + 2))
  return rows
})

// 快捷输入建议（按模式）
const suggestions = computed<string[]>(() => {
  const m = sbSession.value?.template?.mode ?? TRAIN_TABS[tab.value].k
  if (m === 'narrate') return ['各位请看，这件文物的来历很有意思', '我先给大家讲讲它的历史背景', '关于这点大家随时可以问我']
  if (m === 'fullflow') return ['您好，很高兴为您安排这次定制行程', '我先跟您确认几个需求细节，可以吗？', '行程结束后我会及时回访您']
  if (m === 'communication') return ['您好，请问怎么称呼您？', '我们先确认一下您的时间和同行人数', '我把刚才确认的需求整理给您']
  return ['您好，很抱歉给您带来困扰', '我来详细说明一下情况', '您有什么需要我帮忙的吗']
})

function showToast(msg: string) {
  toastMsg.value = msg
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toastMsg.value = '' }, 2600)
}
function showBanner(msg: string) {
  stageBanner.value = msg
  if (bannerTimer) clearTimeout(bannerTimer)
  bannerTimer = setTimeout(() => { stageBanner.value = '' }, 6000)
}
function moodLabel(m?: string): string {
  const map: Record<string, string> = { 满意: '🙂 满意', 一般: '😐 一般', 不满: '😕 不满' }
  return map[m || '一般'] || '😐 一般'
}
function scrollChat() {
  nextTick(() => { if (chatRef.value) chatRef.value.scrollTop = chatRef.value.scrollHeight })
}

async function loadTemplates() {
  templatesLoading.value = true; templatesError.value = false
  try {
    const { templates: ts } = await listSandboxTemplates()
    templates.value = ts
  } catch (e: any) {
    templatesError.value = true
    ElMessage.error('加载沙盒场景失败：' + classifyError(e).message)
  } finally { templatesLoading.value = false }
}

async function loadSandboxRecords() {
  if (!accounts.isSignedIn) return
  try {
    const { records } = await listSandboxRecords(store.userId)
    if (!records.length) {
      sandboxStats.value = { n: 0, avg: 0, top: 0, last: null }
      return
    }
    const scores = records.map(r => r.score ?? 0)
    sandboxStats.value = {
      n: records.length,
      avg: Math.round(scores.reduce((a, b) => a + b, 0) / records.length),
      top: Math.max(...scores),
      last: { score: records[0].score ?? 0, sceneName: records[0].title },
    }
    completedTplIds.value = new Set(records.filter(r => r.score != null).map(r => r.template_id))
  } catch { /* 后端不可用 */ }
}

async function loadKbHints() {
  if (!stage.value || !stage.value.kb_keywords.length) return
  const { searchKnowledge } = await import('@/api/knowledge')
  const out: { title: string; content: string }[] = []
  for (const k of stage.value.kb_keywords.slice(0, 2)) {
    try {
      const res = await searchKnowledge({ q: k, top_k: 2 })
      for (const h of res.results) {
        if (out.length >= 4) break
        out.push({ title: h.title, content: h.content.slice(0, 90) })
      }
    } catch { /* ignore */ }
  }
  kbHints.value = out
}

function toggleKb() {
  kbOpen.value = !kbOpen.value
  if (kbOpen.value) loadKbHints()
}

// ── 语音实战：全流程场景进入前选训练语言（决定游客国籍与音色） ──
const LANG_OPTIONS = [
  { k: 'en', label: 'English', nat: '美国、英国、澳大利亚' },
  { k: 'ja', label: '日本語', nat: '日本' },
  { k: 'fr', label: 'Français', nat: '法国' },
  { k: 'de', label: 'Deutsch', nat: '德国' },
  { k: 'ko', label: '한국어', nat: '韩国' },
  { k: 'es', label: 'Español', nat: '西班牙、墨西哥' },
  { k: 'ru', label: 'Русский', nat: '俄罗斯' },
  { k: 'ar', label: 'العربية', nat: '沙特阿拉伯' },
  { k: 'zh', label: '中文', nat: '中国' },
  { k: '', label: '传统文字', nat: '不开语音，沿用原对话模式' },
]
const langModal = ref<{ open: boolean; tpl: SandboxTemplate | null; lang: string }>({ open: false, tpl: null, lang: 'en' })
const isVoiceSession = computed(() => !!sbSession.value?.language)

function isLocked(s: SandboxTemplate): boolean {
  const reqs = s.requires ?? []
  return reqs.length > 0 && reqs.some(id => !completedTplIds.value.has(id))
}
function guardScene(s: SandboxTemplate) {
  if (!accounts.isSignedIn) { accounts.openAccess(route.fullPath); return }
  if (!onb.done) { accounts.openOnboarding(route.fullPath); return }
  if (isLocked(s)) {
    ElMessage.warning('请先完成前置分课沙盒，再挑战「' + s.title + '」')
    return
  }
  if(co.running) { ElMessage.info('当前协作仍在进行，请完成后再开始'); return }
  if(s.template_id === 't_comm_wechat') void startScene(s.template_id)
  else pickLanguage(s)
}
function pickLanguage(s: SandboxTemplate) {
  // 所有沙盒版块都支持「训练语言」进入语音实战；默认：fullflow=en，其余=传统文字
  langModal.value = { open: true, tpl: s, lang: s.mode === 'fullflow' ? 'en' : '' }
}
function confirmLang() {
  const t = langModal.value.tpl
  langModal.value.open = false
  if (t) startScene(t.template_id, langModal.value.lang)
}

// ══ 场景生命周期（对话式） ══
async function startScene(templateId: string, language = '') {
  if (!accounts.isSignedIn || !onb.done) return
  const token = co.begin('准备实战场景')
  if(token === null) return
  const requestUser = store.userId
  scene.value = templateId
  sbSession.value = null
  stageBanner.value = ''
  sbSpeechAgg.value = { recordings: 0, chars: 0, speakSec: 0, pauses: 0, pauseSec: 0 }
  try {
    const session = await createSandboxSession(store.userId, templateId, language, undefined, trace => co.receive(trace,token))
    co.finish(token)
    if(requestUser !== store.userId || scene.value !== templateId) return
    sbSession.value = session
    showBridgeTip.value = true
    scrollChat()
    if (session.language) showToast('已开启实时语音   ' + session.language + (session.voice ? '   ' + session.voice : ''))
  } catch (e: any) {
    co.finish(token,classifyError(e).message)
    if(requestUser !== store.userId || scene.value !== templateId) return
    ElMessage.error('启动模拟失败：' + classifyError(e).message)
    scene.value = null
  }
}

// 语音表现（语速/停顿），用于结算报告展示
const voicePerf = computed(() => {
  const a = sbSpeechAgg.value
  if (!a.recordings || !a.speakSec) return null
  const rate = Math.round((a.chars / a.speakSec) * 60)
  let rateNote = '语速适中'
  if (rate < 180) rateNote = '语速偏慢，可适当加快'
  else if (rate > 260) rateNote = '语速偏快，注意吐字清晰'
  const pausePerMin = a.pauses / (a.speakSec / 60)
  let pauseNote = '停顿自然'
  if (pausePerMin >= 2) pauseNote = '停顿偏多，易显生涩'
  else if (a.pauseSec / a.speakSec >= 0.25) pauseNote = '停顿占比偏高'
  return {
    recordings: a.recordings,
    rate, rateNote,
    pauses: a.pauses, pauseSec: a.pauseSec, pauseNote,
    totalSec: Math.round(a.speakSec),
  }
})

function toggleSbMic() {
  if (sbTranscribing.value) return
  if (sbRecOn.value) stopSbRec()
  else startSbRec()
}
async function startSbRec() {
  if (!navigator.mediaDevices || !window.MediaRecorder) {
    ElMessage.warning('当前环境不支持录音，请用 Chrome、Edge')
    return
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    sbChunks = []
    sbMediaRec = new MediaRecorder(stream)
    sbMediaRec.ondataavailable = (e) => { if (e.data.size) sbChunks.push(e.data) }
    sbMediaRec.onstop = () => { stream.getTracks().forEach((t) => t.stop()); sbUpload() }
    sbMediaRec.start()
    sbRecOn.value = true
    sbRecSec = 0
    sbRecLabel.value = '正在录音…'
    sbRecTimer = setInterval(() => { sbRecSec++; sbRecLabel.value = `正在录音 ${sbRecSec}s` }, 1000)
  } catch (e: any) {
    ElMessage.error('无法使用麦克风：' + e.message)
  }
}
function stopSbRec() {
  if (!sbRecOn.value || !sbMediaRec) return
  clearInterval(sbRecTimer as any)
  sbMediaRec.stop()
  sbRecOn.value = false
  sbTranscribing.value = true
  sbRecLabel.value = '语音识别中…'
}
async function sbUpload() {
  try {
    if (!sbChunks.length) { sbTranscribing.value = false; return }
    const blob = new Blob(sbChunks, { type: 'audio/webm' })
    const r = await transcribeAudio(blob)
    sbTranscribing.value = false
    sbRecLabel.value = ''
    if (r.speech) {
      sbSpeechAgg.value.recordings += 1
      sbSpeechAgg.value.chars += r.speech.char_count
      sbSpeechAgg.value.speakSec += r.speech.speech_duration
      sbSpeechAgg.value.pauses += r.speech.pause_count
      sbSpeechAgg.value.pauseSec += r.speech.pause_seconds
    }
    if (r.text && r.text.trim()) {
      sbInput.value = (sbInput.value ? sbInput.value + ' ' : '') + r.text.trim()
      showToast('已识别，可编辑后发送')
    } else {
      showToast('未识别到内容，请重录')
    }
  } catch (e: any) {
    sbTranscribing.value = false
    sbRecLabel.value = ''
    ElMessage.error('语音识别失败：' + classifyError(e).message)
  }
}

async function handleSandboxSend() {
  const text = sbInput.value.trim()
  if (!text || !sbSession.value || sbSending.value) return
  const token = co.begin('游客互动与场景判断')
  if(token === null) return
  const sid = sbSession.value.session_id
  const requestUser = store.userId
  sbSession.value.messages.push({ role: 'guide', content: text })
  sbInput.value = ''
  sbSending.value = true
  scrollChat()
  try {
    const result = await sendSandboxMessage(sid, requestUser, text, trace => co.receive(trace,token))
    co.finish(token)
    if(requestUser !== store.userId || sbSession.value?.session_id !== sid) return
    sbSession.value.messages.push({ role: 'customer', content: result.reply, mood: result.mood })
    if (sbSession.value.stage) {
      sbSession.value.stage = { ...sbSession.value.stage, index: result.stage, total: result.stage_total, title: result.stage_title }
    }
    // 沙盒 v2：游客心情条（信任度/情绪）
    if (typeof result.trust === 'number') {
      sbSession.value.customer_state = {
        trust: result.trust,
        mood: result.mood,
        hidden_revealed: !!result.hidden_revealed,
        tension: !!result.tension,
      }
    }
    if (result.stage_tip) {
      const tip = result.stage_tip
      if (tip.type === 'tension') {
        showBanner('⚠️ 游客情绪升级：' + (tip.message || '游客很不满，需要你安抚'))
      } else if (tip.type === 'tension_resolved') {
        showToast('游客情绪已安抚，继续带团')
      } else if (tip.type === 'timeout') {
        showBanner('⏱ ' + (tip.message || '本阶段话题已聊够，进入下一阶段'))
      } else if (tip.scene_complete) {
        showToast('全部阶段完成   可结束带团查看评估')
      } else {
        showBanner('进入下一阶段   ' + tip.title)
        loadKbHints()
      }
    }
    sbSession.value.scene_complete = result.scene_complete
  } catch (e: any) {
    co.finish(token,classifyError(e).message)
    if(requestUser !== store.userId || sbSession.value?.session_id !== sid) return
    ElMessage.error('发送失败：' + classifyError(e).message)
    try { const recovered = await getSandboxSession(sid); if(requestUser === store.userId && sbSession.value?.session_id === sid) sbSession.value = recovered } catch { /* 后端不可用 */ }
  } finally {
    sbSending.value = false
    scrollChat()
  }
}

async function handleSandboxEnd() {
  if (!sbSession.value || sbEnding.value) return
  const token = co.begin('实战评估与复盘')
  if(token === null) return
  const sid = sbSession.value.session_id
  const requestUser = store.userId
  sbEnding.value = true
  try {
    const ended = await endSandboxSession(sid, requestUser, trace => co.receive(trace,token))
    co.finish(token)
    if(requestUser !== store.userId || sbSession.value?.session_id !== sid) return
    sbSession.value = ended
    settle.value = buildSettle(ended)
    scoreOpen.value = true
    loadSandboxRecords()
  } catch (e: any) {
    co.finish(token,classifyError(e).message)
    if(requestUser !== store.userId || sbSession.value?.session_id !== sid) return
    ElMessage.error('结算失败：' + classifyError(e).message)
  } finally {
    sbEnding.value = false
  }
}

// ── 语音实战：台词回填消息流并落库（供结算评估） ──
function onVoiceGuideMsg(text: string) { pushVoiceMessage('guide', text) }
function onVoiceCustomerMsg(text: string) { pushVoiceMessage('customer', text) }
async function pushVoiceMessage(role: 'guide' | 'customer', content: string) {
  const s = sbSession.value
  if (!s) return
  s.messages.push({ role, content } as any)
  scrollChat()
  try {
    await appendSandboxVoiceMessages(s.session_id, store.userId, [{ role, content }])
  } catch (e: any) {
    console.warn('台词落库失败', e)
  }
}

function exitScene() {
  co.practice=null
  showBridgeTip.value = false
  scene.value = null
  sbSession.value = null
  kbOpen.value = false
  stageBanner.value = ''
  kbHints.value = []
  scoreOpen.value = false
}
function resetScene() {
  if (scene.value) startScene(scene.value)
}

// ══ 结算弹窗（AI 评估反馈） ══
interface SettleData {
  total: number; modeLabel: string; sceneName: string; subLabel: string
  rows: { sc: number }[]; dims: [string, number][]; note: string
  isNewBest: boolean; prevBest: number | null; retryLabel: string
  strengths?: string[]; weaknesses?: string[]; suggestions?: string[]
  skills?: RecommendedSkill[]
  cultureBridge?: { score: number; summary: string } | null
  // 沙盒 v3：场景结果（success 达成目标 / failed 搞砸 / abandoned 手动结束 / null 后端未返回）
  outcome: 'success' | 'failed' | 'abandoned' | null
  failReason: string
}
const scoreOpen = ref(false)
const settle = ref<SettleData | null>(null)

function buildSettle(s: SandboxSession): SettleData {
  const dims = Object.entries(s.dims ?? {}).map(([k, v]) => [k, v] as [string, number])
  return {
    total: s.score ?? 0,
    modeLabel: s.template.mode === 'narrate' ? '讲解训练' : s.template.mode === 'fullflow' ? '入境定制游全流程' : '情景模拟',
    sceneName: s.template.title,
    subLabel: `游客 ${s.customer.name}   ${s.customer.nationality}   对话 ${s.messages.length} 轮`,
    rows: [],
    dims,
    note: (s.feedback?.suggestions ?? []).slice(0, 1).join('') || 'AI 评估完成，请查看各维度反馈',
    isNewBest: false, prevBest: null,
    retryLabel: '再来一局',
    cultureBridge: s.feedback?.culture_bridge ?? null,
    strengths: s.feedback?.strengths ?? [],
    weaknesses: s.feedback?.weaknesses ?? [],
    suggestions: s.feedback?.suggestions ?? [],
    skills: s.feedback?.recommended_skills ?? [],
    outcome: s.scene_outcome ?? null,
    failReason: s.scene_fail_reason ?? '',
  }
}

function closeScore(back = false) {
  scoreOpen.value = false
  if (back) exitScene()
}
function retryFromScore() {
  scoreOpen.value = false
  resetScene()
}

// 沙盒 v3：「让旅鸢讲讲怎么提升」→ 评价摘要写 localStorage → 跳首页自动发送复盘请求
function goReviewWithSinan() {
  if (!settle.value) return
  const s = settle.value
  localStorage.setItem('boc_pending_sandbox', JSON.stringify({
    score: s.total,
    dims: Object.fromEntries(s.dims),
    strengths: s.strengths ?? [],
    weaknesses: s.weaknesses ?? [],
    suggestions: s.suggestions ?? [],
    scene_title: s.sceneName,
  }))
  router.push('/app/home')
  ElMessage.success('已带你的沙盒表现去找旅鸢复盘')
}

// ══ ESC 关闭结算弹窗 ══
function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && scoreOpen.value) { scoreOpen.value = false }
}

// ══ 生命周期 ══
onMounted(() => {
  loadTemplates()
  loadSandboxRecords()
  document.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
  if (toastTimer) clearTimeout(toastTimer)
  if (bannerTimer) clearTimeout(bannerTimer)
})
</script>

<style lang="scss" scoped>
@use '@/styles/tokens' as *;

.tg-page { display: flex; flex-direction: column; height: 100%; overflow: hidden; background: $color-bg; }

/* ══ 通用页头 ══ */
.ph { display: flex; align-items: center; justify-content: space-between; padding: 25px 28px 22px; flex-shrink: 0; max-width:1120px; width:100%; margin:0 auto; }
.ph-left { display: flex; align-items: center; gap: 10px; }
.ph-right { display: flex; align-items: center; gap: 10px; }
.ph-title { font-family: $font-serif; font-size: 24px; font-weight: 600; color: $color-text-link; margin:0; }
.ghost-btn {
  display: inline-flex; align-items: center; gap: 5px; font-size: 12.5px; padding: 7px 14px;
  border-radius: 10px; border: 1px solid rgba(24,58,99,0.15); background: #fff; color: $color-text-link;
  cursor: pointer; transition: all .15s; font-family: $font-sans;
  &:hover { border-color: $color-accent; color: #256CA7; }
}
.pill { display: inline-flex; align-items: center; gap: 5px; font-size: 11.5px; padding: 5px 13px; border-radius: 20px;
  color: #256CA7; background: rgba(51,143,242,.12); border: 1px solid rgba(51,143,242,.3); }

/* ══ 沙盒   body / 列表 ══ */
.tg-body { flex: 1; min-height: 0; overflow-y: auto; padding: 0 28px 35px; display: flex; flex-direction: column; }
.tg-list { max-width: 1064px; margin: 0 auto; width: 100%; }
.gallery-intro { display:flex; align-items:center; justify-content:space-between; gap:28px; margin-bottom:26px; padding:4px 4px 23px; border-bottom:1px solid #dfeaf4; h3 { font:600 23px/1.6 $font-serif; color:#294f70; margin:10px 0 7px; } p { font-size:13px; color:$color-text-secondary; line-height:1.8; margin:0; } &.integrated { padding:27px 30px; background:linear-gradient(110deg,#edf6ff,#f9fcff); border:1px solid #dce9f5; border-radius:18px 4px 18px 4px; } }
.gallery-eyebrow { font-size:11px; letter-spacing:1px; color:$color-text-link; }
.gallery-intro-symbol { display:grid; place-items:center; width:72px; height:72px; background:#ecf5fe; border:1px solid #e0edf8; color:$color-text-secondary; border-radius:18px 5px 18px 5px; flex-shrink:0; margin-right:7px; }
.gallery-process { display:flex; list-style:none; flex-shrink:0; gap:22px; margin:0; padding:0; li { position:relative; display:flex; flex-direction:column; gap:10px; align-items:center; &:not(:last-child)::after { content:''; position:absolute; top:14px; left:calc(50% + 18px); width:calc(100% - 14px); height:1px; background:#d5e6f5; } } span { display:grid; place-items:center; width:29px; height:29px; border-radius:50%; background:#fff; border:1px solid #d9e8f5; color:$color-text-secondary; font-size:10px; } b { font-size:11px; color:$color-text-secondary; font-weight:400; white-space:nowrap; } }
.scenario-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:18px; }
.integrated-grid { grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px; }
.gallery-section-label { display:flex; align-items:baseline; gap:14px; margin:0 0 13px; h4 { font-size:14px; color:#426782; font-weight:500; margin:0; } >span { font-size:11px; color:$color-text-secondary; } }
.phase-capstones { display:flex; flex-direction:column; gap:14px; margin-top:26px; .gallery-section-label { margin-bottom:0; } }
.gallery-helper { display:flex; align-items:center; gap:7px; margin:22px 0 0; font-size:11px; color:$color-text-secondary; line-height:1.7; }
.emergency-grid { grid-template-columns:1fr; :deep(.scenario-card) { grid-template-columns:46px minmax(0,1fr) auto; align-items:center; gap:22px; } :deep(.scenario-bottom) { grid-column:3; flex-direction:column; border:0; align-items:flex-end; padding:0; } :deep(.scenario-content > p) { -webkit-line-clamp:1; } }
@media(max-width:900px) { .integrated-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } .gallery-intro.integrated { align-items:flex-start; flex-direction:column; gap:22px; } .gallery-process { gap:32px; } }
@media(max-width:650px) { .ph { padding:22px 16px 18px; } .ph-title { font-size:21px; } .tg-body { padding:0 16px 28px; } .scenario-grid,.integrated-grid { grid-template-columns:1fr; } .gallery-intro { gap:18px; h3 { font-size:21px; } p { font-size:12px; } &.integrated { padding:23px; } } .gallery-intro-symbol { width:51px; height:51px; margin:0; } .gallery-process { gap:27px; } .emergency-grid { :deep(.scenario-card) { grid-template-columns:46px minmax(0,1fr); } :deep(.scenario-bottom) { grid-column:1/-1; flex-direction:row; align-items:center; border-top:1px solid #edf2f7; padding-top:17px; } } .gallery-section-label { flex-wrap:wrap; gap:6px 12px; } }
.gallery-toolbar { display:flex; align-items:center; gap:16px; margin:22px 0 16px; color:#426482; font-size:13px; small { margin-left:auto; font-size:11px; color:$color-text-secondary; } }
.gallery-empty { display:flex; align-items:center; justify-content:center; gap:12px; padding:70px 20px; color:$color-text-secondary; font-size:13px; .sb-spinner { width:17px; height:17px; } }
.scene-card:focus-visible { outline:2px solid #338ff2; outline-offset:3px; }
.communication-modes { display:flex; gap:3px; padding:3px; border:1px solid #dce9f6; border-radius:8px; background:#fff; button { padding:6px 10px; border:0; border-radius:5px; background:transparent; color:$color-text-secondary; cursor:pointer; font:inherit; font-size:12px; transition:color .2s,background .2s; &.active { color:$color-text-link; background:#eff6ff; } } }

/* ══ 概览条 + 模块标签 + 场景卡片 ══ */
.tf-overview {
  display: flex; align-items: stretch; border-radius: 16px; padding: 16px 22px; margin-bottom: 16px;
  background: linear-gradient(135deg, rgba(255,255,255,.9), rgba(255,255,255,.6));
  border: 1px solid $color-border; box-shadow: 0 4px 20px rgba(24,58,99,.05);
  .ov-item { flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 3px; padding: 0 8px;
    .v { font-size: 22px; font-weight: 700; color: $color-text-link; font-family: 'Liberation Mono', monospace; line-height: 1;
      i { font-size: 11px; font-style: normal; color: $color-text-secondary; font-weight: 400; margin-left: 2px; } }
    .k { font-size: 11px; color: $color-text-secondary; line-height: 1.4; }
    &.ov-last .k { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 150px; } }
  .ov-sep { width: 1px; background: $color-border; margin: 4px 0; }
  &.empty { align-items: center; justify-content: center; padding: 18px;
    .msg { display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: $color-text-secondary; } }
}
.train-tabs { display: flex; gap: 12px; margin-bottom: 20px; }
.train-tab {
  flex: 1; border-radius: 16px; padding: 16px 20px; cursor: pointer; border: 1px solid $color-border;
  background: rgba(255,255,255,.8); display: flex; gap: 12px; transition: all .18s;
  &:hover { transform: translateY(-2px); box-shadow: 0 6px 18px rgba(24,58,99,.08); }
  &.active { background: linear-gradient(135deg, #338FF2, #216CBD); border-color: transparent;
    .t { color: #F5FAFF; } .s, .n { color: rgba(255,255,255,.6); } }
  .ic { width: 40px; height: 40px; border-radius: 12px; background: rgba(51,143,242,.12);
    display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .t { font-size: 14px; font-weight: 600; color: $color-text-link; }
  .s { font-size: 11px; color: $color-text-secondary; margin-top: 2px; }
  .n { font-size: 10px; color: $color-text-secondary; margin-top: 4px; font-family: 'Liberation Mono', monospace; }
}
.sec-title { font-family: $font-serif; font-size: 15px; font-weight: 700; color: $color-text-link; margin: 8px 0 12px; }
.scene-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
.scene-card {
  border-radius: 16px; overflow: hidden; cursor: pointer; position: relative;
  background: rgba(255,255,255,.85); border: 1px solid $color-border; transition: all .2s;
  &:hover { transform: translateY(-3px); box-shadow: 0 8px 24px rgba(24,58,99,.1); }
  &.locked { opacity: .6; cursor: not-allowed; }
}
.scene-thumb { position: relative; height: 130px; background: linear-gradient(135deg, #DCEAF7, #D1E3F5);
  img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .ov { position: absolute; inset: 0; background: linear-gradient(to bottom, transparent 40%, rgba(0,0,0,.45)); }
  .cat { position: absolute; top: 8px; left: 8px; font-size: 10px; padding: 2px 8px; border-radius: 20px;
    background: rgba(24,58,99,.75); color: $color-text-link; }
  .lock { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; background: rgba(0,0,0,.35); }
  .best { position: absolute; bottom: 8px; right: 8px; font-size: 10px; padding: 2px 6px; border-radius: 6px;
    font-weight: 600; background: rgba(51,143,242,.9); color: #fff; }
}
.scene-info { padding: 10px 12px;
  .t { font-size: 14px; font-weight: 500; line-height: 1.3; color: $color-text; }
  .st { font-size: 11px; margin-top: 2px; color: $color-text-secondary; }
  .row { display: flex; align-items: center; justify-content: space-between; margin-top: 8px; }
  .stars { display: inline-flex; align-items: center; gap: 1px; }
  .unch { font-size: 10px; padding: 2px 8px; border-radius: 20px; background: $color-secondary-bg; color: #256CA7; }
  .lastscore { display: inline-flex; align-items: center; gap: 4px; font-size: 10px; padding: 2px 8px; border-radius: 20px;
    background: rgba(24,58,99,.07); color: $color-text-link; font-family: 'Liberation Mono', monospace; }
}
/* ══ 情景模拟训练台 ══
   布局说明：grid 双列（任务卡 | 主舞台），控制栏/知识面板独占整行。
   旧版用 flex 横排时，width:100% 的 .tr-ctrl 与 flex:1(basis 0) 的 .tr-right
   互相挤压，导致右侧作答区宽度坍缩为 0（文字竖排、场景图不可见）。 */
.tr-stage { display: grid; grid-template-columns: 230px minmax(0, 1fr); grid-template-rows: minmax(0, 1fr) auto; gap: 14px;
  max-width: 1200px; width: 100%; margin: 0 auto; align-items: stretch;
  flex: 1; min-height: 0;
  > .tr-ctrl { grid-column: 1 / -1; width: auto; max-width: none; margin: 0; }
  > .tr-panel { grid-column: 1 / -1; width: auto; max-width: none; margin: 0; } }
.tr-task {
  grid-row: 1; border-radius: 16px; background: rgba(255,255,255,.85);
  border: 1px solid $color-border; padding: 14px; display: flex; flex-direction: column; gap: 4px;
  .hd { display: flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 600; color: $color-text-link;
    padding-bottom: 10px; border-bottom: 1px dashed $color-border; margin-bottom: 8px;
    .t { margin-left: 2px; } }
  .bd { display: flex; flex-direction: column; gap: 14px; }
  .lbl { display: flex; align-items: center; gap: 4px; font-size: 10.5px; color: $color-text-secondary; margin-bottom: 5px; }
  .loc { font-size: 14px; font-weight: 600; color: $color-text-link; font-family: $font-serif; }
  .taskbox { font-size: 12px; color: $color-text; padding: 8px 10px; border-radius: 10px;
    background: rgba(51,143,242,.08); border: 1px solid rgba(51,143,242,.2); line-height: 1.5; }
  .q-dots { display: flex; gap: 6px; flex-wrap: wrap; }
  .q-dot { width: 22px; height: 22px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
    font-size: 10px; font-weight: 600; font-family: 'Liberation Mono', monospace; border: 1px solid $color-border;
    background: #fff; color: $color-text-secondary; transition: all .2s;
    &.cur { background: $color-primary; border-color: $color-primary; color: #fff; }
    &.done { background: rgba(51,143,242,.15); border-color: $color-accent; color: $color-text-link; } }
  .prog-row { display: flex; justify-content: space-between; margin-bottom: 5px;
    .lbl { margin: 0; } .pct-txt { font-size: 10px; font-weight: 600; color: $color-text-link; } }
  .track { height: 6px; border-radius: 3px; background: $color-muted-bg; overflow: hidden; }
  .fill { height: 100%; border-radius: 3px; background: linear-gradient(to right, #338FF2, #338FF2); transition: width .4s ease; }
  .reward-box { margin-top: 4px; border-radius: 12px; padding: 10px 12px; background: rgba(51,143,242,.08);
    border: 1px solid rgba(51,143,242,.25);
    .rw { display: flex; align-items: center; gap: 6px;
      .num { font-size: 12px; font-weight: 700; color: #256CA7; }
      .u { font-size: 10px; color: $color-text-secondary; } } }
}
.tr-right { grid-row: 1; min-width: 0; display: flex; flex-direction: row; gap: 12px; }
.tr-scene {
  position: relative; flex: 1; min-width: 0; border-radius: 16px; overflow: hidden;
  min-height: 420px; height: 100%;
  background: linear-gradient(135deg, #2a4a72, #338FF2);
  img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
  .vig { position: absolute; inset: 0; background: linear-gradient(to bottom, rgba(10,22,42,.1), rgba(10,22,42,.45)); }
}
.hint-bubble {
  position: absolute; top: 14px; left: 16px; right: 16px; max-width: 560px; z-index: 3;
  border-radius: 14px; padding: 12px 16px; background: rgba(255,255,255,.94); backdrop-filter: blur(8px);
  box-shadow: 0 4px 18px rgba(10,22,42,.2);
  .hh { display: flex; align-items: center; gap: 6px; font-size: 11px; font-weight: 600; color: #256CA7; margin-bottom: 6px;
    .timer { margin-left: auto; display: inline-flex; align-items: center; gap: 3px; font-family: 'Liberation Mono', monospace; } }
  p { font-size: 13px; line-height: 1.7; color: $color-text; }
}
.timer-track { position: absolute; top: 108px; left: 16px; max-width: 300px; z-index: 3; height: 4px;
  border-radius: 2px; overflow: hidden; background: rgba(255,255,255,.3); }
.timer-fill { height: 100%; border-radius: 2px; transition: width .9s linear; }
.scene-slots { position: absolute; bottom: 54px; left: 16px; z-index: 3; display: flex; flex-direction: column; gap: 8px; max-width: 360px; }
.tourist-bubble {
  max-width: 340px; border-radius: 14px; padding: 10px 14px; background: rgba(255,255,255,.95);
  box-shadow: 0 4px 14px rgba(10,22,42,.2);
  .who { display: flex; align-items: center; gap: 5px; font-size: 10.5px; font-weight: 600; color: $color-text-link; margin-bottom: 4px; }
  p { font-size: 12px; line-height: 1.6; color: $color-text; }
}
.kb-bubble {
  max-width: 360px; border-radius: 14px; padding: 10px 14px; background: rgba(255,255,255,.95);
  box-shadow: 0 4px 14px rgba(10,22,42,.2); border-left: 3px solid $color-accent;
  max-height: 260px; overflow-y: auto;
  .who { display: flex; align-items: center; gap: 5px; font-size: 10.5px; font-weight: 600; color: #256CA7; margin-bottom: 6px;
    .x { margin-left: auto; width: 18px; height: 18px; border: none; border-radius: 50%; cursor: pointer;
      background: $color-muted-bg; color: $color-text-secondary; display: flex; align-items: center; justify-content: center; flex-shrink: 0;
      &:hover { background: $color-border; } } }
  .kb-list { display: flex; flex-direction: column; gap: 5px; }
  .kb-item { font-size: 11px; line-height: 1.55; color: $color-text;
    .k { font-weight: 600; color: #256CA7; } }
}
.answer-toggle {
  position: absolute; bottom: 14px; right: 16px; z-index: 3; display: inline-flex; align-items: center; gap: 6px;
  font-size: 12px; font-weight: 600; padding: 9px 16px; border-radius: 12px; cursor: pointer;
  border: 1px solid rgba(255,255,255,.4); background: rgba(24,58,99,.55); color: #fff; backdrop-filter: blur(8px);
  transition: all .2s; font-family: $font-sans;
  &:hover { transform: translateY(-2px); background: linear-gradient(135deg, #338FF2, #54A6F8); border-color: transparent; }
}
.tr-choices {
  flex-shrink: 0; width: 0; overflow: hidden; opacity: 0; pointer-events: none;
  border-radius: 16px; background: rgba(255,255,255,.9); border: 0 solid $color-border;
  display: flex; flex-direction: column;
  transition: width .3s cubic-bezier(.4,0,.2,1), opacity .25s ease;
  &.open { width: 320px; border-width: 1px; opacity: 1; pointer-events: auto; }
  .hd { display: flex; align-items: center; gap: 8px; padding: 12px 14px; min-width: 300px;
    border-bottom: 1px solid $color-border; background: rgba(250,248,243,.5);
    .t { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 600; color: $color-text-link; white-space: nowrap; }
    .h { font-size: 10.5px; color: $color-text-secondary; }
    .collapse-btn { margin-left: auto; width: 24px; height: 24px; border: none; border-radius: 8px; cursor: pointer;
      background: $color-muted-bg; color: $color-text-secondary; display: flex; align-items: center; justify-content: center;
      transition: all .15s; flex-shrink: 0;
      &:hover { background: $color-border; color: $color-text-link; } } }
  .list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; padding: 12px; min-width: 300px; }
  .tr-confirm { min-width: 300px; }
}
.choice {
  display: flex; align-items: flex-start; gap: 10px; text-align: left; padding: 11px 14px; border-radius: 12px;
  border: 1px solid $color-border; background: #fff; cursor: pointer; transition: all .15s; font-family: $font-sans;
  &:hover { border-color: rgba(51,143,242,.5); }
  &.sel { border-color: $color-primary; background: rgba(24,58,99,.04); box-shadow: 0 0 0 2px rgba(24,58,99,.1); }
  .num { width: 22px; height: 22px; border-radius: 50%; flex-shrink: 0; display: flex; align-items: center;
    justify-content: center; font-size: 11px; font-weight: 700; font-family: 'Liberation Mono', monospace;
    background: $color-secondary-bg; color: $color-text-secondary; }
  &.sel .num { background: $color-primary; color: #fff; }
  .txt { font-size: 12.5px; line-height: 1.6; color: $color-text; }
}
.tr-confirm { margin-top: 12px; display: flex; flex-direction: column; gap: 8px; }
.confirm-btn {
  width: 100%; padding: 12px; border: none; border-radius: 12px; cursor: pointer; font-size: 13px;
  font-weight: 600; color: #fff; background: linear-gradient(135deg, #338FF2, #26507f); transition: all .18s;
  display: inline-flex; align-items: center; justify-content: center; gap: 6px; font-family: $font-sans;
  &:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(24,58,99,.3); }
  &:disabled { opacity: .5; cursor: not-allowed; }
}
.confirm-hint { font-size: 10px; color: $color-text-secondary; text-align: center; }
.tr-result { display: flex; align-items: center; gap: 16px; width: 100%; border-radius: 12px; padding: 10px 16px;
  background: #fff; border: 1px solid $color-border; box-shadow: 0 2px 12px rgba(24,58,99,.08);
  .ring { position: relative; width: 56px; height: 56px; flex-shrink: 0;
    .sc { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
      font-size: 16px; font-weight: 700; color: $color-text-link; } }
  .rt-wrap { flex: 1; min-width: 0; }
  .rt { display: flex; align-items: center; gap: 6px; margin-bottom: 3px;
    .t { font-size: 12px; font-weight: 600; color: $color-text-link; } }
  p { font-size: 11.5px; line-height: 1.6; color: $color-text-secondary; }
}
.tr-ctrl { display: flex; gap: 10px; }
.ctrl-btn {
  display: inline-flex; align-items: center; gap: 7px; font-size: 12.5px; font-weight: 500; padding: 10px 18px;
  border-radius: 12px; border: 1px solid $color-border; background: rgba(255,255,255,.9); color: $color-text-secondary;
  cursor: pointer; transition: all .18s; font-family: $font-sans;
  &:hover { border-color: rgba(51,143,242,.5); color: #256CA7; transform: translateY(-1px); }
  &.on { border-color: $color-accent; background: rgba(51,143,242,.1); color: #256CA7; }
  &.rec { border-color: #DC2626; color: #c42222; background: rgba(220,38,38,.06); }
  .rec-dot { width: 8px; height: 8px; border-radius: 50%; background: #DC2626; animation: recPulse 1.2s infinite; }
}
@keyframes recPulse { 0%, 100% { opacity: 1; } 50% { opacity: .35; } }
.ctrl-score {
  margin-left: auto; display: flex; align-items: center; gap: 8px; padding: 10px 22px; border-radius: 12px;
  cursor: pointer; border: none; color: #fff; font-size: 13px; font-weight: 600; font-family: $font-sans;
  background: linear-gradient(135deg, #338FF2, #A8893C); transition: all .18s;
  &:hover:not(:disabled):not(.disabled) { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(51,143,242,.55); }
  &:disabled, &.disabled { opacity: .45; cursor: not-allowed; }
}
.tr-panel { margin-top: 12px; border-radius: 14px; padding: 12px 14px;
  background: rgba(255,255,255,.92); border: 1px solid $color-border;
  .hd { display: flex; align-items: center; gap: 7px; font-size: 12px; font-weight: 600; color: $color-text-link;
    margin-bottom: 8px;
    .x { margin-left: auto; width: 24px; height: 24px; border: none; border-radius: 50%; cursor: pointer;
      background: $color-muted-bg; color: $color-text-secondary; display: flex; align-items: center; justify-content: center;
      &:hover { background: $color-border; } } }
  .kb-facts { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; }
  .kb-fact { padding: 8px 10px; border-radius: 10px; background: rgba(24,58,99,.04); border: 1px solid rgba(24,58,99,.06);
    .k { font-size: 10px; color: #256CA7; font-weight: 600; margin-bottom: 2px; }
    .v { font-size: 11px; line-height: 1.5; color: $color-text; } }
}
/* ══ 讲解训练 ══ */
.narr-page { max-width: 860px; margin: 0 auto; display: flex; flex-direction: column; gap: 12px; }
.narr-card { border-radius: 16px; background: rgba(255,255,255,.88); border: 1px solid $color-border; padding: 20px; }
.narr-top { display: flex; gap: 16px; align-items: flex-start; padding-bottom: 16px; border-bottom: 1px dashed $color-border;
  img { width: 150px; height: 100px; object-fit: cover; border-radius: 12px; flex-shrink: 0;
    background: linear-gradient(135deg, #DCEAF7, #D1E3F5); }
  .narr-info { flex: 1; min-width: 0;
    .cat { display: inline-block; font-size: 10px; padding: 2px 9px; border-radius: 20px;
      background: rgba(51,143,242,.12); color: #256CA7; border: 1px solid rgba(51,143,242,.3); }
    .t { font-family: $font-serif; font-size: 17px; font-weight: 700; color: $color-text-link; margin-top: 6px; }
    .topic { font-size: 12.5px; line-height: 1.7; color: $color-text; margin-top: 6px; }
    .meta { display: flex; align-items: center; gap: 5px; font-size: 11px; color: $color-text-secondary; margin-top: 8px; } }
}
.narr-points { padding: 14px 0; display: flex; flex-direction: column; gap: 8px; }
.narr-point { display: flex; align-items: center; gap: 10px; font-size: 12.5px; color: $color-text-secondary;
  padding: 9px 12px; border-radius: 10px; background: rgba(24,58,99,.03); transition: all .2s;
  .pt-dot { width: 22px; height: 22px; border-radius: 50%; flex-shrink: 0; display: flex; align-items: center;
    justify-content: center; font-size: 11px; font-weight: 600; background: #fff; border: 1px solid $color-border;
    color: $color-text-secondary; }
  &.done { background: rgba(51,143,242,.08); color: #256CA7; font-weight: 500;
    .pt-dot { background: linear-gradient(135deg, #338FF2, #A8893C); border-color: transparent; color: #fff; } }
}
.narr-mic { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 16px 0 8px; }
.big-mic { width: 74px; height: 74px; border-radius: 50%; cursor: pointer; display: flex; align-items: center;
  justify-content: center; background: $color-primary; box-shadow: 0 6px 20px rgba(24,58,99,.3); transition: all .2s;
  &:hover { transform: scale(1.06); }
  &.rec { background: #DC2626; box-shadow: 0 8px 24px rgba(220,38,38,.3); animation: recPulseBig 1.5s infinite; } }
@keyframes recPulseBig { 0%, 100% { box-shadow: 0 0 0 0 rgba(220,38,38,.35); } 50% { box-shadow: 0 0 0 12px rgba(220,38,38,0); } }
.narr-mic .hint { font-size: 12px; color: $color-text-secondary; }
.rec-badge { display: inline-flex; align-items: center; gap: 6px; font-size: 11px; font-weight: 600; color: #c42222;
  font-family: 'Liberation Mono', monospace; padding: 4px 12px; border-radius: 20px; background: rgba(220,38,38,.07);
  .rd { width: 7px; height: 7px; border-radius: 50%; background: #DC2626; animation: recPulse 1.2s infinite; } }
.narr-btns { display: flex; gap: 10px; margin-top: 8px; }
.narr-panel { max-width: 860px; margin-top: 0; }
/* ══ 路线带团 ══
   与 .tr-stage 同理：grid 双列，知识/路线面板独占整行，避免挤压站点区 */
.route-layout { display: grid; grid-template-columns: 380px minmax(0, 1fr); gap: 14px;
  max-width: 1200px; margin: 0 auto; align-items: start;
  > .tr-panel { grid-column: 1 / -1; width: auto; max-width: none; margin: 0; } }
.route-map-pane { grid-row: 1; display: flex; flex-direction: column; gap: 10px; }
.route-map-head { display: flex; align-items: center; gap: 8px; padding: 10px 14px; border-radius: 12px;
  background: rgba(255,255,255,.85); border: 1px solid $color-border;
  .t { font-size: 12px; font-weight: 600; color: $color-text-link; display: flex; align-items: center; gap: 6px; }
  .badge { font-size: 9px; padding: 2px 8px; border-radius: 20px; background: $color-secondary-bg; color: $color-text-secondary;
    &.real { background: rgba(51,143,242,.15); color: #256CA7; } } }
.map-up-btn { margin-left: auto; display: flex; align-items: center; gap: 5px; font-size: 11px; padding: 6px 12px;
  border-radius: 10px; cursor: pointer; border: 1px dashed $color-border; background: transparent;
  color: $color-text-secondary; transition: all .18s; font-family: $font-sans;
  &:hover { border-color: $color-accent; color: #256CA7; }
  & + .map-up-btn { margin-left: 0; } }
.route-map { position: relative; height: 340px; border-radius: 16px; overflow: hidden; border: 1px solid $color-border;
  background: radial-gradient(ellipse at 50% 46%, #F5F9FD 0%, #ECF4FC 55%, #DCEAF7 100%);
  box-shadow: 0 4px 18px rgba(24,58,99,.06);
  .real-img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; z-index: 0; }
  .schematic { position: absolute; inset: 0; width: 100%; height: 100%; z-index: 0; } }
.route-mk { position: absolute; transform: translate(-50%, -50%); width: 26px; height: 26px; border-radius: 50%;
  border: 2px solid #fff; cursor: pointer; display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 700; font-family: 'Liberation Mono', monospace; transition: all .2s; z-index: 2;
  box-shadow: 0 2px 8px rgba(24,58,99,.28); padding: 0;
  &.pending { background: #B7B2A4; color: #fff; }
  &.done { background: $color-primary; color: #fff; }
  &.active { background: $color-accent; color: #fff; transform: translate(-50%, -50%) scale(1.18);
    box-shadow: 0 0 0 6px rgba(51,143,242,.25); animation: mkPulse 1.8s ease infinite; }
  .mk-name { position: absolute; top: 118%; left: 50%; transform: translateX(-50%); white-space: nowrap;
    font-size: 10px; font-weight: 500; color: $color-text-link; background: rgba(255,255,255,.94); padding: 2px 8px;
    border-radius: 10px; border: 1px solid $color-border; opacity: 0; transition: opacity .2s; pointer-events: none;
    font-family: $font-sans; }
  &:hover .mk-name, &.active .mk-name { opacity: 1; } }
@keyframes mkPulse { 0%, 100% { box-shadow: 0 0 0 6px rgba(51,143,242,.25); } 50% { box-shadow: 0 0 0 10px rgba(51,143,242,.12); } }
.route-map-note { display: flex; align-items: flex-start; gap: 8px; padding: 10px 14px; border-radius: 12px;
  background: rgba(51,143,242,.07); border: 1px dashed rgba(51,143,242,.35); font-size: 10.5px; line-height: 1.6;
  color: $color-text-secondary; }
.route-stage { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 10px; }
.route-progress { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 12px 16px; border-radius: 12px;
  background: rgba(255,255,255,.85); border: 1px solid $color-border;
  .rp-lb { font-size: 11px; color: $color-text-secondary; }
  .track { flex: 1; min-width: 80px; height: 6px; border-radius: 3px; background: $color-muted-bg; overflow: hidden;
    .fill { height: 100%; border-radius: 3px; background: linear-gradient(to right, #338FF2, #338FF2); transition: width .4s ease; } }
  .pct { font-size: 11px; font-weight: 600; color: $color-text-link; font-family: 'Liberation Mono', monospace;
    &.gold { color: #256CA7; } } }
.route-node { display: flex; gap: 14px; align-items: flex-start; padding: 13px 16px; border-radius: 14px;
  background: rgba(255,255,255,.82); border: 1px solid $color-border; transition: all .2s; cursor: pointer;
  &:hover { border-color: rgba(51,143,242,.4); transform: translateX(4px); }
  &.active { border-color: $color-accent; background: rgba(51,143,242,.06); }
  &.done { opacity: .65; }
  .idx { width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: 700; flex-shrink: 0; background: $color-secondary-bg; color: $color-text-secondary;
    border: 1px solid $color-border; }
  &.active .idx { background: $color-accent; color: #fff; border-color: $color-accent; }
  &.done .idx { background: $color-primary; color: #fff; border-color: $color-primary; }
  .info { flex: 1; min-width: 0;
    .t { font-size: 13px; font-weight: 600; color: $color-text-link; }
    .s { font-size: 11px; color: $color-text-secondary; margin-top: 2px;
      .acc { color: #256CA7; font-family: 'Liberation Mono', monospace; } } }
  .tm { margin-left: auto; font-size: 11px; color: $color-text-secondary; font-family: 'Liberation Mono', monospace; } }
.route-ctrl { margin: 4px 0 0; }
.route-step { display: flex; align-items: center; gap: 8px; padding: 7px 2px; font-size: 12px; color: $color-text;
  .tm { width: 44px; flex-shrink: 0; color: #256CA7; font-family: 'Liberation Mono', monospace; font-size: 11px; }
  .dot { width: 7px; height: 7px; border-radius: 50%; background: $color-accent; flex-shrink: 0; }
  .txt { line-height: 1.5; } }

/* ══ 结算弹窗 ══ */
.score-modal { position: fixed; inset: 0; z-index: 300; display: flex; align-items: center; justify-content: center;
  background: rgba(10,22,42,.5); backdrop-filter: blur(4px); animation: fadeIn .2s ease; }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
.score-card { width: min(480px, 92vw); max-height: 86vh; overflow-y: auto; border-radius: 20px; padding: 24px;
  background: #fff; box-shadow: 0 24px 64px rgba(10,22,42,.35); animation: modalIn .28s cubic-bezier(.34,1.4,.64,1); }
@keyframes modalIn { from { opacity: 0; transform: translateY(24px) scale(.96); } to { opacity: 1; transform: translateY(0) scale(1); } }
.score-top { display: flex; align-items: center; gap: 20px; }
.score-total { position: relative; width: 96px; height: 96px; flex-shrink: 0;
  .num { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center;
    b { font-size: 26px; font-weight: 700; color: $color-text-link; line-height: 1; }
    i { font-size: 10px; color: $color-text-secondary; font-style: normal; margin-top: 2px; } } }
.score-meta { flex: 1; min-width: 0;
  .t { font-size: 15px; font-weight: 700; color: $color-text-link; font-family: $font-serif; margin-bottom: 4px; }
  .s { font-size: 11px; color: $color-text-secondary; line-height: 1.6; } }
.newbest { display: inline-flex; align-items: center; gap: 4px; font-size: 10px; font-weight: 700; padding: 3px 9px;
  border-radius: 20px; color: #fff; background: linear-gradient(135deg, #338FF2, #A8893C); vertical-align: 2px; margin-left: 4px; }
.score-close { width: 28px; height: 28px; border-radius: 50%; border: none; cursor: pointer; background: $color-secondary-bg;
  color: $color-text-secondary; display: flex; align-items: center; justify-content: center; transition: all .12s;
  flex-shrink: 0; align-self: flex-start;
  &:hover { background: $color-border; color: $color-text-link; } }
/* 沙盒 v3：场景结果徽标（成功=绿 / 失败=红+金原因） */
.scene-badge {
  margin-top: 14px; display: flex; align-items: center; gap: 8px;
  border-radius: 12px; padding: 10px 14px; font-size: 13px; font-weight: 700;
  &.success { color: #267249; background: rgba(47,143,91,.08); border: 1px solid rgba(47,143,91,.32); }
  &.failed { color: #c0392b; background: rgba(192,57,43,.07); border: 1px solid rgba(192,57,43,.3); }
  .sb-ic { width: 22px; height: 22px; border-radius: 50%; flex-shrink: 0; display: flex; align-items: center;
    justify-content: center; font-size: 13px; color: #fff; }
  &.success .sb-ic { background: #2f8f5b; }
  &.failed .sb-ic { background: #c0392b; }
  .sb-txt { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; line-height: 1.5;
    em { font-style: normal; font-size: 11.5px; font-weight: 500; color: #256CA7; } }
}
/* 失败时在总分下方提示复盘 */
.score-fail-hint { margin-top: 10px; padding-left: 116px; font-size: 12px; color: $color-text-secondary; }
.sq-wrap { margin-top: 18px; }
.sq-title { display: flex; align-items: center; gap: 6px; font-size: 11px; font-weight: 600; color: $color-text-secondary; margin-bottom: 10px; }
.sq-row { display: flex; align-items: center; gap: 10px; padding: 7px 0; border-bottom: 1px dashed $color-border;
  &:last-child { border-bottom: none; }
  .q-n { font-size: 11px; color: $color-text-secondary; width: 42px; flex-shrink: 0; }
  .sq-bar { flex: 1; height: 8px; border-radius: 4px; background: $color-secondary-bg; overflow: hidden;
    .f { height: 100%; border-radius: 4px; background: linear-gradient(to right, #338FF2, #338FF2); transition: width .9s ease; } }
  .sq-sc { font-size: 13px; font-weight: 700; font-family: 'Liberation Mono', monospace; width: 32px; text-align: right; flex-shrink: 0; } }
.score-dims { margin-top: 16px; display: flex; flex-direction: column; gap: 12px; }
.dim-row { .top { display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 5px;
    .l { color: #3a3a3a; font-weight: 500; }
    .v { color: #256CA7; font-weight: 700; font-family: 'Liberation Mono', monospace; } }
  .dim-bar { height: 6px; border-radius: 3px; background: $color-secondary-bg; overflow: hidden;
    .f { height: 100%; border-radius: 3px; background: linear-gradient(to right, #338FF2, #338FF2); transition: width 1s ease; } } }
.score-note { margin-top: 20px; border-radius: 12px; padding: 12px 14px; background: rgba(51,143,242,.08);
  border: 1px solid rgba(51,143,242,.25);
  .t { display: flex; align-items: center; gap: 6px; font-size: 11px; font-weight: 600; color: #256CA7; margin-bottom: 6px; }
  p { font-size: 12px; line-height: 1.7; color: #3a3a3a; } }
.sq-actions { display: flex; gap: 10px; margin-top: 18px; }
.sq-btn { flex: 1; padding: 12px; border-radius: 12px; cursor: pointer; font-size: 13px; font-weight: 600;
  transition: all .18s; display: flex; align-items: center; justify-content: center; gap: 6px; font-family: $font-sans;
  &.primary { border: none; color: #fff; background: linear-gradient(135deg, #338FF2, #26507f);
    &:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(24,58,99,.3); } }
  &.ghost { background: #fff; border: 1px solid $color-border; color: $color-text-secondary;
    &:hover { border-color: $color-accent; color: #256CA7; } } }
/* 沙盒 v3：让旅鸢讲讲怎么提升（金色主按钮，沿用 $color-accent 渐变） */
.sq-review { margin-top: 10px; }
.sq-btn.review { border: none; color: #fff; background: linear-gradient(135deg, #338FF2, #A8893C);
  &:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(51,143,242,.45); } }

@media (max-width: 900px) {
  .tr-stage, .route-layout { grid-template-columns: 1fr; }
  .tr-task, .tr-right, .route-map-pane, .route-stage { grid-row: auto; }
  .tr-right { flex-direction: column; }
  .tr-choices { &.open { width: 100%; } .hd, .list, .tr-confirm { min-width: 0; } }
  .tr-scene { min-height: 300px; }
  .scene-grid { grid-template-columns: repeat(2, 1fr); }
  .train-tabs { flex-direction: column; }
}

.toast {
  position: fixed; left: 50%; bottom: 34px; transform: translateX(-50%) translateY(20px);
  background: rgba(24,58,99,.94); color: #fff; font-size: 12.5px; padding: 11px 22px; border-radius: 12px;
  box-shadow: 0 8px 30px rgba(10,22,42,.3); opacity: 0; pointer-events: none;
  transition: all .28s cubic-bezier(.34,1.3,.64,1); display: flex; align-items: center; gap: 8px; z-index: 400;
  &.show { opacity: 1; transform: translateX(-50%) translateY(0); }
}

/* ══ 对话式沙盒 ══ */
.gold-pill { color: #256CA7 !important; background: rgba(51,143,242,.12) !important; border-color: rgba(51,143,242,.3) !important; }
.stage-badge {
  position: absolute; right: 8px; bottom: 8px; z-index: 3;
  background: rgba(24,58,99,.82); color: #fff; font-size: 10px; padding: 3px 8px; border-radius: 20px;
  display: flex; align-items: center; gap: 4px; backdrop-filter: blur(4px);
}

.sb-layout { flex: 1; min-height: 0; display: grid; grid-template-columns: 290px 1fr; gap: 16px; padding: 6px 24px 16px; max-width: 1180px; margin: 0 auto; width: 100%; box-sizing: border-box; }

.sb-side { display: flex; flex-direction: column; gap: 12px; min-height: 0; overflow-y: auto; }
.sb-customer { background: $color-surface; border: 1px solid $color-border; border-radius: 16px; padding: 16px; display: flex; gap: 12px; }

// ── 沙盒 v2：游客心情条 ──
.sb-mood-bar {
  background: $color-surface; border: 1px solid $color-border; border-radius: 16px; padding: 12px 14px; margin-top: 10px;
  &.tension { border-color: rgba(201, 110, 80, 0.5); background: rgba(201, 110, 80, 0.06); }
  .smb-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 7px; }
  .smb-t { font-size: 11.5px; font-weight: 700; color: $color-text-link; letter-spacing: 1px; }
  .smb-mood { font-size: 11px; font-weight: 700; padding: 1px 9px; border-radius: 999px;
    &.m-满意 { color: #267326; background: rgba(45, 138, 45, 0.1); }
    &.m-一般 { color: #256CA7; background: rgba(51, 143, 242, 0.18); }
    &.m-不满 { color: #9c4a30; background: rgba(201, 110, 80, 0.12); }
    &.m-愤怒 { color: #c0392b; background: rgba(192, 57, 43, 0.14); } }
  .smb-track { height: 7px; border-radius: 999px; background: rgba(24, 58, 99, 0.1); overflow: hidden; }
  .smb-fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, $color-primary, $color-accent);
    transition: width .4s ease; &.low { background: linear-gradient(90deg, #c96e50, #e8875b); }
    &.high { background: linear-gradient(90deg, #2d8a2d, #5cb85c); } }
  .smb-foot { display: flex; justify-content: space-between; margin-top: 6px; font-size: 10.5px; color: $color-text-secondary; }
  .smb-warn { color: #c0392b; font-weight: 700; }
  .smb-reveal { color: #256CA7; font-weight: 600; }
}
.sc-avatar { width: 46px; height: 46px; border-radius: 50%; background: rgba(51,143,242,.14); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.sc-info { min-width: 0; }
.sc-name { font-size: 15px; font-weight: 700; color: $color-text-link; display: flex; align-items: baseline; gap: 8px; }
.sc-nat { font-size: 11px; font-weight: 400; color: #256CA7; }
.sc-tag { margin-top: 6px; font-size: 11px; color: #6f6f6f; background: rgba(24,58,99,.05); padding: 3px 8px; border-radius: 8px; display: inline-block; }
.sc-line { margin-top: 6px; font-size: 11px; line-height: 1.6; color: #6f6f6f;
  .l { color: #256CA7; font-weight: 600; margin-right: 6px; } }
/* 沙盒 v3：游客多维属性（职业/健康/消费/说话风格，两两成行） */
.sc-multi { margin-top: 8px; display: flex; flex-direction: column; gap: 4px; }
.sc-mrow { display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 11px; line-height: 1.6; color: #6f6f6f; }
.sc-item i { color: #256CA7; font-weight: 600; font-style: normal; margin-right: 4px; }

.sb-stage { background: $color-surface; border: 1px solid $color-border; border-radius: 16px; padding: 14px 16px; }
.sb-stage-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;
  .t { font-size: 12px; font-weight: 600; color: #3a3a3a; display: flex; align-items: center; gap: 6px; }
  .pct { font-size: 11px; color: #256CA7; font-weight: 700; } }
.sb-stage .track { height: 6px; border-radius: 3px; background: $color-secondary-bg; overflow: hidden;
  .fill { height: 100%; border-radius: 3px; background: linear-gradient(to right, #338FF2, #338FF2); transition: width .7s ease; } }
.sb-stage-obj { margin-top: 10px; font-size: 11.5px; line-height: 1.7; color: #6f6f6f; }

.sb-actions { display: flex; flex-direction: column; gap: 8px; }
.sb-actions .ctrl-btn, .sb-actions .ctrl-score { width: 100%; justify-content: center; }

.sb-main { display: flex; flex-direction: column; min-height: 0; background: $color-surface; border: 1px solid $color-border; border-radius: 16px; overflow: hidden; }
.sb-chat { flex: 1; min-height: 0; overflow-y: auto; padding: 18px 20px 8px; display: flex; flex-direction: column; gap: 12px; }

.sb-scene-card { align-self: center; text-align: center; background: rgba(51,143,242,.08); border: 1px dashed rgba(51,143,242,.4); border-radius: 12px; padding: 12px 20px; max-width: 480px; width: 100%; margin-bottom: 4px;
  .sc-t { font-size: 13px; font-weight: 700; color: $color-text-link; }
  .sc-d { margin-top: 4px; font-size: 12px; line-height: 1.7; color: #6f6f6f; }
  .sc-loc { margin-top: 6px; font-size: 11px; color: #256CA7; display: flex; align-items: center; justify-content: center; gap: 4px; } }

.sb-banner { align-self: center; display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600; color: $color-text-link; background: rgba(24,58,99,.06); border: 1px solid rgba(24,58,99,.12); padding: 7px 16px; border-radius: 20px; animation: sb-fade-in .3s ease; }
@keyframes sb-fade-in { from { opacity: 0; transform: translateY(-6px); } to { opacity: 1; transform: none; } }

.sb-row { display: flex; gap: 8px; align-items: flex-start;
  &.customer { flex-direction: row; }
  &.guide { flex-direction: row-reverse; } }
.sb-av { width: 28px; height: 28px; border-radius: 50%; flex-shrink: 0; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700;
  &.customer { background: rgba(51,143,242,.18); color: #256CA7; }
  &.guide { background: rgba(24,58,99,.9); color: #fff; } }
.sb-bubble { max-width: 76%; padding: 10px 14px; border-radius: 14px; font-size: 13px; line-height: 1.75; color: #3a3a3a;
  &.customer { background: #EDF5FD; border: 1px solid rgba(51,143,242,.22); border-top-left-radius: 4px; }
  &.guide { background: #338FF2; color: #fff; border-top-right-radius: 4px; } }
.sb-mood { font-size: 10.5px; color: #256CA7; margin-bottom: 4px; }
.sb-thinking { color: $color-text-secondary; font-style: italic; }

.sb-input { border-top: 1px solid $color-border; padding: 10px 14px 12px; background: #fff; }
.sb-sugs { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
.sug { font-size: 11.5px; color: $color-text-link; background: rgba(24,58,99,.05); border: 1px solid rgba(24,58,99,.12); border-radius: 16px; padding: 5px 12px; cursor: pointer; transition: all .18s; display: flex; align-items: center; gap: 4px;
  &:hover { background: rgba(51,143,242,.14); border-color: rgba(51,143,242,.4); } }
.sb-input-row { display: flex; gap: 10px; align-items: flex-end; }
.sb-input-row textarea { flex: 1; resize: none; border: 1px solid $color-border; border-radius: 12px; padding: 10px 12px; font-size: 13px; line-height: 1.6; font-family: $font-sans; background: $color-bg; color: #3a3a3a; outline: none;
  &:focus { border-color: rgba(51,143,242,.6); background: #fff; } }
.send-btn { flex-shrink: 0; border: none; border-radius: 12px; background: linear-gradient(135deg, #338FF2, #26507f); color: #fff; padding: 11px 20px; font-size: 13px; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 6px; transition: all .18s; font-family: $font-sans;
  &:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(24,58,99,.3); }
  &:disabled { opacity: .45; cursor: not-allowed; } }

.sb-kb { position: static; width: auto; min-height: 0; }
.sb-kb-hint { font-size: 12.5px; line-height: 1.8; color: #3a3a3a; background: rgba(51,143,242,.08); border: 1px solid rgba(51,143,242,.22); border-radius: 10px; padding: 10px 12px; margin-bottom: 10px; }
.sb-kb-empty { font-size: 11.5px; color: $color-text-secondary; display: flex; align-items: center; gap: 6px; padding: 6px 2px; }

/* 评估弹窗增强 */
.sb-score-card { max-height: 86vh; overflow-y: auto; }
.sb-fb-sec { margin-top: 14px; }
.sb-fb-sec .t { font-size: 12px; font-weight: 700; display: flex; align-items: center; gap: 6px; margin-bottom: 6px;
  &.ok { color: #267249; } &.warn { color: #a5483e; } &.gold { color: #256CA7; } }
.sb-fb-sec ul { margin: 0; padding-left: 18px; font-size: 12.5px; line-height: 1.8; color: #3a3a3a; }
.vp-perf { display: flex; flex-wrap: wrap; gap: 10px 22px; }
.vp-item { font-size: 13px; color: $color-text-secondary; }
.vp-item b { font-size: 16px; color: $color-text-link; font-family: Consolas, monospace; }
.vp-item .note { color: $color-text-link; font-size: 12px; }
.mic-btn { width: 40px; height: 40px; border-radius: 12px; border: 1px solid #CBD5E0; background: #fff; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.mic-btn.on { background: #c0392b; border-color: #c0392b; }
.mic-tag { font-size: 12px; color: $color-text-link; white-space: nowrap; }
.sb-skill-list { display: flex; flex-direction: column; gap: 8px; }
.sb-skill { border: 1px solid rgba(51,143,242,.25); background: rgba(51,143,242,.06); border-radius: 10px; padding: 8px 12px;
  .k { display: block; font-size: 12px; font-weight: 600; color: $color-text-link; margin-bottom: 2px; }
  .d { display: block; font-size: 11px; color: #6f6f6f; line-height: 1.6; } }

@media (max-width: 900px) {
  .sb-layout { grid-template-columns: 1fr; padding: 6px 14px 16px; }
  .sb-side { flex-direction: row; flex-wrap: wrap; overflow: visible; }
  .sb-customer, .sb-stage { flex: 1 1 100%; }
  .sb-actions { flex-direction: row; }
  .sb-bubble { max-width: 88%; }
}
/* ══ 场景搭建中（加载遮罩） ══ */
.sb-building {
  flex: 1;
  min-height: 55vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: $color-bg;
}
.sb-building-inner {
  display: flex;
  align-items: center;
  gap: 12px;
  color: $color-text-secondary;
  font-size: 14px;
}
.sb-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(51, 143, 242, 0.3);
  border-top-color: $color-accent;
  border-radius: 50%;
  animation: sbSpin 0.8s linear infinite;
}
@keyframes sbSpin { to { transform: rotate(360deg); } }
.sb-dots { display: inline-flex; align-items: center; gap: 5px; }
.sb-dots .dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: $color-accent;
  opacity: 0;
  animation: sbDot 1.2s infinite ease-in-out;
}
.sb-dots .dot:nth-child(1) { animation-delay: 0s; }
.sb-dots .dot:nth-child(2) { animation-delay: 0.18s; }
.sb-dots .dot:nth-child(3) { animation-delay: 0.36s; }
@keyframes sbDot {
  0%, 60%, 100% { opacity: 0; transform: translateY(0); }
  30% { opacity: 1; transform: translateY(-4px); }
}

/* 语音实战   训练语言选择弹窗 */
.lm-mask { position: fixed; inset: 0; background: rgba(15,23,32,.45); z-index: 99;
  display: flex; align-items: center; justify-content: center; padding: 20px; }
.lm-card { background: #F8FBFF; border-radius: 16px; max-width: 640px; width: 100%;
  padding: 22px 24px; box-shadow: 0 18px 50px rgba(0,0,0,.25); }
.lm-title { font-family: $font-serif; font-size: 18px; font-weight: 700; color: $color-text-link; }
.lm-sub { font-size: 12.5px; color: $color-text-secondary; margin: 6px 0 14px; line-height: 1.6; }
.lm-opts { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px; }
.lm-opt { border: 1px solid #DCEAF7; background: #fff; border-radius: 10px; padding: 9px 10px;
  cursor: pointer; text-align: left; transition: all .15s; display: flex; flex-direction: column; gap: 2px; }
.lm-opt b { font-size: 13px; color: $color-text-link; }
.lm-opt span { font-size: 11px; color: $color-text-secondary; }
.lm-opt.on { border-color: $color-accent; background: rgba(51,143,242,.12); box-shadow: 0 0 0 1px $color-accent; }
.lm-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 16px; }
.lm-go { border: 0; border-radius: 10px; padding: 9px 20px; font-size: 13.5px; cursor: pointer;
  background: linear-gradient(135deg, #338FF2, #b28c46); color: #fff; }


/* 文化桥小提示 + 附加评分 */
.cb-tip { display: flex; align-items: center; gap: 8px; margin: 10px 18px 0; padding: 9px 14px;
  border-radius: 12px; background: rgba(51,143,242,.12); border: 1px dashed rgba(51,143,242,.45);
  color: #7a6230; font-size: 12.5px; line-height: 1.5; }
.cb-close { margin-left: auto; border: 0; background: transparent; color: #6c644d; cursor: pointer;
  display: inline-flex; padding: 2px; border-radius: 6px; }
.cb-close:hover { color: #7a6230; background: rgba(51,143,242,.2); }
.cb-score { font-size: 13px; color: $color-text-link; margin: 2px 0 6px; }
.cb-score b { color: $color-text-link; font-size: 16px; }
.cb-summary { font-size: 12.5px; color: $color-text-secondary; line-height: 1.7; }


/* 全流程大沙盒：前置分课未完成时锁定 */
.scene-card { position: relative; }
.scene-card.locked { cursor: not-allowed; }
.scene-lock { position: absolute; inset: 0; z-index: 3; border-radius: 16px;
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px;
  background: rgba(248,244,235,.88); color: #256CA7; }
.scene-lock .sl-ic { font-size: 26px; }
.scene-lock .sl-t { font-size: 12.5px; font-weight: 600; }

.train-tabs .train-tab { font-family:inherit; text-align:left; }
@media(max-width:800px) { .train-tabs { display:grid; grid-template-columns:1fr 1fr; } }
</style>
