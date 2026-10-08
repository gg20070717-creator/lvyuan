<template>
  <section class="assessment-entry" :class="`assessment-${section}`">
    <div class="assessment-heading">
      <div><h1>{{ content.title }}</h1><p v-if="section === 'portrait'">{{ content.description }}</p></div>
      <span class="assessment-status"><i :class="{ ready: onb.done }"></i>{{ onb.done ? '画像已就绪' : '学前准备' }}</span>
    </div>
    <template v-if="section === 'portrait'">
      <div class="portrait-layout">
        <div class="portrait-action">
          <div class="portrait-illustration" aria-hidden="true">
            <svg class="portrait-orbit" viewBox="0 0 280 200" fill="none">
              <circle cx="140" cy="98" r="67" stroke="#bfd8ee" />
              <circle cx="140" cy="98" r="85" stroke="#d6e6f4" stroke-dasharray="3 8" />
              <path d="M74 56C95 30 130 22 159 33M204 80C213 117 195 149 169 159M91 147C68 135 59 113 63 91" stroke="#83aed3" stroke-linecap="round" />
              <path d="M100 98H79M184 98H205M140 54V38M140 143V159" stroke="#d0e1f0" />
              <circle cx="159" cy="33" r="3" fill="#7ea9cf" />
              <circle cx="169" cy="159" r="3" fill="#7ea9cf" />
              <circle cx="63" cy="91" r="3" fill="#7ea9cf" />
              <path d="M38 167H61M31 174H69M207 35H232M215 42H240" stroke="#c4daed" stroke-linecap="round" />
              <path d="M116 180H164" stroke="#c5daed" stroke-linecap="round" />
            </svg>
            <span class="portrait-figure"><SIcon name="user" :size="43" /><span v-if="onb.done" class="portrait-stamp"><SIcon name="check" :size="11" /></span></span>
            <span class="portrait-node node-experience"><SIcon name="book" :size="20" /></span>
            <span class="portrait-node node-goal"><SIcon name="target" :size="21" /></span>
            <span class="portrait-node node-route"><SIcon name="map" :size="17" /></span>
          </div>
          <button class="primary-action" @click="start">{{ actionLabel }}<SIcon name="right" :size="15" /></button>
        </div>
        <div class="portrait-preview">
          <div class="preview-top"><span>你的学习名片</span><SIcon name="sparkle" :size="17" /></div>
          <div class="portrait-person"><span class="portrait-avatar"><SIcon name="user" :size="30" /></span><div><h3>{{ onb.persona?.label || '期待认识你' }}</h3><p>{{ onb.done ? '专属学习画像' : '从经验、目标与偏好出发' }}</p></div></div>
          <p class="persona-summary">{{ onb.persona?.summary || '你的经历和期待，会成为安排学习内容的重要依据。' }}</p>
          <div class="portrait-qualities"><span><SIcon name="user" :size="14" />学习身份</span><span><SIcon name="book" :size="14" />经验基础</span><span><SIcon name="target" :size="14" />学习目标</span></div>
          <div class="preview-footer"><i></i>{{ onb.done ? '已建立画像，随时查看学情' : '完成学前测试后点亮你的画像' }}</div>
        </div>
      </div>
      <div class="portrait-foundations">
        <div v-for="item in foundations" :key="item.title"><span class="foundation-icon"><SIcon :name="item.icon" :size="19" /></span><div><h3>{{ item.title }}</h3><p>{{ item.description }}</p></div></div>
      </div>
    </template>
    <div v-else-if="section === 'diagnostic'" class="diagnostic-layout">
      <div class="diagnostic-main">
        <div class="diagnostic-top"><span class="eyebrow">测验准备</span><span class="quiet-label"><SIcon name="bookcheck" :size="14" />全屏作答</span></div>
        <LearningSceneVisual kind="diagnostic" class="diagnostic-visual" />
        <div class="diagnostic-scope"><span><SIcon name="book" :size="14" />基础知识</span><span><SIcon name="globe" :size="14" />文化理解</span><span><SIcon name="msg" :size="14" />接待应用</span></div>
        <div class="diagnostic-action"><button class="primary-action" @click="start">{{ actionLabel }}<SIcon name="right" :size="15" /></button></div>
        <div class="diagnostic-record"><SIcon name="clock" :size="16" /><span>累计作答</span><b>{{ co.learning?.questions_answered ?? '—' }}</b><span>题</span><router-link v-if="onb.done" to="/app/profile">查看学情<SIcon name="right" :size="12" /></router-link></div>
      </div>
      <aside class="diagnostic-guide">
        <div class="diagnostic-guide-top"><SIcon name="notebook" :size="16" />测验反馈</div>
        <ul><li v-for="item in diagnosticGuide" :key="item.title"><span class="guide-icon"><SIcon :name="item.icon" :size="21" /></span><h3>{{ item.title }}</h3></li></ul>
      </aside>
    </div>
    <template v-else>
      <div class="plan-layout">
        <div class="plan-recommendation">
          <span class="eyebrow"><SIcon name="map" :size="16" />专属路线</span>
          <LearningSceneVisual kind="plan" class="plan-visual" />
          <p v-if="onb.done && co.learning" class="plan-next-step"><SIcon name="target" :size="15" />{{ co.learning.recommendation.label }}</p>
          <button class="primary-action" :title="onb.done ? co.learning?.recommendation.reason : undefined" @click="start">{{ actionLabel }}<SIcon name="right" :size="15" /></button>
          <router-link v-if="onb.done" class="text-link" to="/app/path">查看完整学习路线<SIcon name="right" :size="12" /></router-link>
        </div>
        <aside class="plan-overview">
          <div class="mastery-label"><span>当前掌握度</span><b v-if="co.learning?.mastery != null">{{ co.learning.mastery }}<small>%</small></b><span v-else class="pending-label">待记录</span></div>
          <div v-if="co.learning?.mastery != null" class="mastery-track"><span :style="{ width: `${co.learning.mastery}%` }"></span></div>
          <div v-else class="mastery-empty" aria-hidden="true"><span><SIcon name="bookcheck" :size="32" /></span><i></i><i></i></div>
          <div class="plan-records"><div><b v-if="co.learning">{{ co.learning.questions_answered }}</b><SIcon v-else name="bookcheck" :size="22" /><span>已答题目</span></div><div><b v-if="co.learning">{{ co.learning.practice_count }}</b><SIcon v-else name="trend" :size="22" /><span>实战记录</span></div></div>
        </aside>
      </div>
      <div class="plan-journey"><router-link to="/app/home?section=portrait"><SIcon :name="onb.done ? 'check' : 'user'" :size="16" />认识自己</router-link><SIcon name="right" :size="13" /><router-link to="/app/home?section=diagnostic"><SIcon name="bookcheck" :size="16" />摸清起点</router-link><SIcon name="right" :size="13" /><router-link to="/app/home?activity=quiz"><SIcon name="target" :size="16" />开始练习</router-link></div>
    </template>
  </section>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAccountsStore } from '@/stores/accounts'
import { useOnboardingStore } from '@/stores/onboarding'
import { useCooperationStore } from '@/stores/cooperation'
import SIcon from './SIcon.vue'
import LearningSceneVisual from './LearningSceneVisual.vue'
const props = defineProps<{ section: string }>()
const emit = defineEmits<{ diagnostic: [] }>()
const router = useRouter(), accounts = useAccountsStore(), onb = useOnboardingStore(), co = useCooperationStore()
const foundations = [
  { icon: 'user', title: '了解你的经历', description: '从学习身份与接待经验出发' },
  { icon: 'target', title: '明确学习方向', description: '把你的目标放在学习的中心' },
  { icon: 'map', title: '安排专属路线', description: '按基础与节奏逐步展开练习' },
]
const diagnosticGuide = [
  { icon: 'bookcheck', title: '知识优势' },
  { icon: 'target', title: '待巩固内容' },
  { icon: 'map', title: '练习方向' },
]
const content = computed(() => {
  if (props.section === 'diagnostic') return { title: '知识摸底', description: '用一次测验，让学习更有方向。' }
  if (props.section === 'plan') return { title: '学习建议', description: '根据你的起点与表现，安排接下来的学习。' }
  return { title: '自我画像', description: '认识你的起点，找到适合自己的学习方式。' }
})
const actionLabel = computed(() => !onb.done ? (props.section === 'portrait' ? '建立我的画像' : '先完善自我画像') : props.section === 'portrait' ? '查看我的画像' : props.section === 'diagnostic' ? '开始摸底测验' : co.learning ? '按建议开始学习' : '查看学习路线')
function start() {
  const destination = `/app/home?section=${props.section}`
  if (!accounts.isSignedIn) accounts.openAccess(destination)
  else if (!onb.done) accounts.openOnboarding(destination)
  else if (props.section === 'diagnostic') emit('diagnostic')
  else void router.push(props.section === 'portrait' ? '/app/profile' : co.learning?.recommendation.path || '/app/path')
}
</script>
<style scoped lang="scss">
@use '@/styles/tokens' as *;
.assessment-entry { max-width:1120px; width:100%; margin:0 auto; padding:30px 28px 40px; overflow-y:auto; flex:1; color:#254866; }
.assessment-heading { display:flex; align-items:center; justify-content:space-between; gap:20px; margin-bottom:26px; h1 { margin:0; font:600 24px/1.4 $font-serif; } p { margin:8px 0 0; font-size:13px; color:$color-text-secondary; line-height:1.7; } }
.assessment-diagnostic,.assessment-plan { .assessment-heading { margin-bottom:20px; h1 { font:500 17px/1.5 $font-sans; } } }
.assessment-status { display:flex; align-items:center; gap:7px; flex-shrink:0; color:$color-text-secondary; font-size:12px; i { width:6px; height:6px; border-radius:50%; background:#afc2d3; &.ready { background:#43ad8a; } } }
.eyebrow { display:flex; align-items:center; gap:8px; color:$color-text-link; font-size:12px; font-weight:600; letter-spacing:1px; }
.primary-action { display:inline-flex; justify-content:center; align-items:center; gap:18px; min-height:44px; padding:12px 21px; border:0; border-radius:10px 3px 10px 3px; background:#3188e5; color:#fff; font:600 14px/1.4 $font-sans; cursor:pointer; box-shadow:0 5px 14px #3188e51a; transition:background .2s,transform .2s; &:hover { background:#2677ce; transform:translateY(-1px); } }
.portrait-layout { display:grid; grid-template-columns:.75fr 1.25fr; gap:32px; align-items:center; background:linear-gradient(115deg,#edf6ff,#f9fcff); border:1px solid #deebf7; border-radius:20px 5px 20px 5px; padding:28px; position:relative; overflow:hidden; &::after { content:''; position:absolute; left:0; bottom:0; width:190px; height:48px; background:url('../assets/ruyi-cloud.svg') center/contain no-repeat; opacity:.1; pointer-events:none; } }
.portrait-action { position:relative; z-index:1; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:17px; padding:8px 0 14px; .primary-action { min-width:196px; min-height:50px; font-size:15px; } }
.portrait-illustration { position:relative; width:260px; max-width:100%; aspect-ratio:7/5; }
.portrait-orbit { display:block; width:100%; height:100%; }
.portrait-figure { position:absolute; left:50%; top:49%; transform:translate(-50%,-50%); display:grid; place-items:center; width:84px; height:84px; color:#3875a8; background:#fff; border:1px solid #c6ddf0; border-radius:24px 7px 24px 7px; box-shadow:0 8px 20px #427eaa09; &::before { content:''; position:absolute; top:7px; right:7px; width:8px; height:8px; border-top:1px solid #b1cfe7; border-right:1px solid #b1cfe7; } }
.portrait-node { position:absolute; display:grid; place-items:center; width:42px; height:42px; color:#477da8; border:1px solid #cde0f0; background:#fafdff; border-radius:12px 4px 12px 4px; &.node-experience { left:12%; top:20%; } &.node-goal { right:6%; top:40%; } &.node-route { left:22%; bottom:12%; width:34px; height:34px; border-radius:9px 3px 9px 3px; } }
.portrait-stamp { position:absolute; right:-6px; bottom:-6px; display:grid; place-items:center; width:22px; height:22px; border:3px solid #edf6ff; border-radius:50%; background:#3388d6; color:#fff; }
.portrait-preview { position:relative; background:#fff; border:1px solid #dfebf5; border-radius:16px 4px 16px 4px; padding:24px; box-shadow:0 10px 24px #3178ae08; &::before { content:''; position:absolute; top:8px; right:8px; width:11px; height:11px; border-top:1px solid #b8d5ec; border-right:1px solid #b8d5ec; } }
.preview-top { display:flex; align-items:center; justify-content:space-between; color:$color-text-secondary; font-size:11px; }
.portrait-person { display:flex; gap:13px; align-items:center; margin:23px 0 17px; h3 { font:600 18px/1.5 $font-serif; margin:0; } p { font-size:11px; color:$color-text-secondary; margin:5px 0 0; } }
.portrait-avatar { display:grid; place-items:center; width:58px; height:58px; flex-shrink:0; background:#edf6ff; color:$color-text-link; border-radius:50%; }
.persona-summary { font-size:12px; line-height:1.8; color:$color-text-secondary; margin:0 0 20px; }
.portrait-qualities { display:flex; flex-wrap:wrap; gap:9px 15px; color:$color-text-link; font-size:11px; span { display:flex; align-items:center; gap:5px; } }
.preview-footer { margin-top:22px; padding-top:14px; border-top:1px solid #edf2f8; display:flex; align-items:center; gap:7px; font-size:11px; color:$color-text-secondary; i { width:5px; height:5px; border-radius:50%; background:#9fc5e7; } }
.portrait-foundations { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); margin-top:25px; >div { display:flex; align-items:center; gap:12px; padding:8px 22px; border-right:1px solid #dde9f4; &:first-child { padding-left:4px; } &:last-child { border:0; } } h3 { font-weight:500; font-size:13px; margin:0; } p { font-size:11px; line-height:1.6; color:$color-text-secondary; margin:6px 0 0; } }
.foundation-icon { color:$color-text-secondary; }
.diagnostic-layout { display:grid; grid-template-columns:minmax(0,1.55fr) minmax(0,1fr); gap:22px; align-items:stretch; }
.diagnostic-layout > *, .plan-layout > * { min-width:0; }
.diagnostic-main { display:flex; flex-direction:column; border:1px solid #dce9f5; border-radius:18px 5px 18px 5px; background:#fff; padding:28px 30px 24px; }
.diagnostic-top { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.quiet-label { display:flex; align-items:center; gap:6px; font-size:11px; color:$color-text-secondary; }
.diagnostic-visual { width:290px; max-width:100%; margin:18px auto 8px; }
.diagnostic-scope { display:flex; justify-content:center; flex-wrap:wrap; gap:12px 20px; margin:0 0 23px; span { display:flex; align-items:center; gap:6px; color:$color-text-secondary; font-size:11px; } }
.diagnostic-action { display:flex; justify-content:center; }
.diagnostic-record { display:flex; align-items:center; gap:8px; padding-top:17px; margin-top:24px; border-top:1px solid #eaf0f7; font-size:11px; color:$color-text-secondary; b { color:#436d90; font-size:15px; font-weight:600; } a { margin-left:auto; display:flex; align-items:center; gap:4px; color:$color-text-link; text-decoration:none; } }
.diagnostic-guide { display:flex; flex-direction:column; justify-content:center; background:#eef5fc; border:1px solid #e2edf7; border-radius:16px 4px 16px 4px; padding:27px; ul { list-style:none; display:grid; gap:16px; padding:0; margin:0; } li { display:flex; align-items:center; gap:16px; min-height:72px; padding:13px 16px; border:1px solid #dce9f4; border-radius:12px 4px 12px 4px; background:#ffffffb3; h3 { font-size:13px; font-weight:500; margin:0; } } }
.diagnostic-guide-top { display:flex; align-items:center; gap:7px; color:$color-text-secondary; font-size:11px; margin-bottom:22px; }
.guide-icon { display:grid; place-items:center; width:37px; height:37px; flex-shrink:0; border-radius:10px 3px 10px 3px; background:#edf5fc; color:#3e739e; }
.plan-layout { display:grid; grid-template-columns:minmax(0,1.5fr) minmax(0,1fr); background:#fff; border:1px solid #dce9f5; border-radius:18px 5px 18px 5px; overflow:hidden; }
.plan-recommendation { display:flex; flex-direction:column; align-items:center; padding:28px 30px; position:relative; .eyebrow { align-self:flex-start; } }
.plan-visual { width:330px; max-width:100%; margin:15px auto 19px; }
.plan-next-step { display:flex; justify-content:center; align-items:center; gap:7px; font-size:12px; color:$color-text-secondary; line-height:1.7; margin:0 0 16px; }
.text-link { display:flex; align-items:center; gap:5px; margin-top:16px; color:$color-text-secondary; font-size:12px; text-decoration:none; }
.plan-overview { display:flex; flex-direction:column; justify-content:center; background:#f9fcff; border-left:1px solid #e6eef6; padding:30px; }
.mastery-label { display:flex; align-items:baseline; justify-content:space-between; gap:12px; color:$color-text-secondary; font-size:12px; b { color:$color-text-link; font-size:26px; font-weight:500; line-height:1; small { font-size:13px; margin-left:3px; } } .pending-label { font-size:10px; } }
.mastery-empty { position:relative; width:138px; height:138px; margin:18px auto 23px; display:grid; place-items:center; border:1px solid #dce9f4; border-radius:50%; &::before { content:''; position:absolute; inset:10px; border:1px dashed #d8e6f2; border-radius:50%; } span { display:grid; place-items:center; width:72px; height:72px; border:1px solid #d7e6f3; background:#fff; border-radius:18px 5px 18px 5px; color:#4b789b; } i { position:absolute; left:12px; top:18px; width:6px; height:6px; border:2px solid #f9fcff; box-sizing:content-box; border-radius:50%; background:#a8c6dc; &:last-child { left:auto; top:auto; bottom:18px; right:12px; } } }
.mastery-track { height:5px; background:#e5eef7; border-radius:5px; margin-top:15px; overflow:hidden; span { display:block; height:100%; background:#74afe7; border-radius:5px; } }
.plan-records { display:flex; justify-content:space-around; gap:24px; padding-top:20px; margin-top:25px; border-top:1px solid #e1ebf5; div { display:flex; align-items:center; flex-direction:column; gap:8px; color:#446f93; } b { font-size:22px; font-weight:500; } span { font-size:11px; color:$color-text-secondary; } }
.plan-journey { display:flex; justify-content:center; align-items:center; gap:24px; padding:25px 10px; font-size:12px; color:$color-text-secondary; >span { font-size:11px; color:$color-text-secondary; margin-right:7px; } a { display:flex; align-items:center; gap:7px; color:$color-text-secondary; text-decoration:none; &:hover { color:$color-text-link; } } }
button:focus-visible,a:focus-visible { outline:2px solid #6bace8; outline-offset:4px; }
@media(max-width:900px) { .portrait-layout { gap:28px; padding:28px; } .diagnostic-main,.diagnostic-guide { padding:24px; } .portrait-foundations >div { padding:8px 14px; } }
@media(max-width:650px) { .assessment-entry { padding:24px 16px; } .assessment-heading { align-items:flex-start; h1 { font-size:22px; } } .assessment-status { margin-top:5px; font-size:11px; } .portrait-layout,.diagnostic-layout,.plan-layout { grid-template-columns:1fr; } .portrait-layout { padding:24px; gap:20px; } .portrait-action { padding:0 0 4px; gap:12px; } .portrait-illustration { width:220px; } .portrait-foundations { grid-template-columns:1fr; gap:16px; >div { padding:0 4px; border:0; } } .diagnostic-visual { width:250px; } .diagnostic-guide ul { gap:10px; } .diagnostic-guide li { min-height:62px; } .plan-recommendation,.plan-overview { padding:25px; } .plan-overview { border-left:0; border-top:1px solid #e6eef6; } .plan-journey { flex-wrap:wrap; gap:12px; } }
@media(prefers-reduced-motion:reduce) { .primary-action { transition:none; transform:none!important; } }
</style>
