<template>
  <section class="assessment-entry" :class="`assessment-${section}`">
    <div class="assessment-heading">
      <div><h1>{{ content.title }}</h1><p>{{ content.description }}</p></div>
      <span class="assessment-status"><i :class="{ ready: onb.done }"></i>{{ onb.done ? '画像已就绪' : '学前准备' }}</span>
    </div>
    <template v-if="section === 'portrait'">
      <div class="portrait-layout">
        <div class="portrait-action">
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
        <div class="diagnostic-top"><span class="eyebrow">知识起点测验</span><span class="quiet-label"><SIcon name="bookcheck" :size="14" />全屏作答</span></div>
        <h2>先找到你的知识起点</h2>
        <p>从熟悉的知识开始，发现优势与需要巩固的地方。</p>
        <div class="diagnostic-scope"><span>关注的能力</span><div><span>基础知识</span><span>文化理解</span><span>接待应用</span></div></div>
        <div class="diagnostic-action"><button class="primary-action" @click="start">{{ actionLabel }}<SIcon name="right" :size="15" /></button><span class="action-note">{{ onb.done ? '答题后查看反馈与待巩固知识点' : '先完善画像，再开启摸底测验' }}</span></div>
        <div class="diagnostic-record"><SIcon name="clock" :size="16" /><span>累计作答</span><b>{{ co.learning?.questions_answered ?? '—' }}</b><span>题</span><router-link v-if="onb.done" to="/app/profile">查看学情<SIcon name="right" :size="12" /></router-link></div>
      </div>
      <aside class="diagnostic-guide">
        <h3>一次测验，了解三个重点</h3>
        <ol><li v-for="(item, index) in diagnosticGuide" :key="item.title"><span>{{ String(index + 1).padStart(2, '0') }}</span><div><h4>{{ item.title }}</h4><p>{{ item.description }}</p></div></li></ol>
        <p class="guide-note"><SIcon name="sparkle" :size="15" />学习建议会结合答题表现更新</p>
      </aside>
    </div>
    <template v-else>
      <div class="plan-layout">
        <div class="plan-recommendation">
          <span class="eyebrow"><SIcon name="trend" :size="16" />你的下一步</span>
          <h2>{{ co.learning?.recommendation.label || '先建立自我画像' }}</h2>
          <p>{{ co.learning?.recommendation.reason || '了解你的经验与目标后，旅鸢会为你安排适合的学习内容。' }}</p>
          <button class="primary-action" @click="start">{{ actionLabel }}<SIcon name="right" :size="15" /></button>
          <router-link v-if="onb.done" class="text-link" to="/app/path">查看完整学习路线<SIcon name="right" :size="12" /></router-link>
        </div>
        <aside class="plan-overview"><h3>建议来自你的学习表现</h3><div class="mastery-label"><span>当前掌握度</span><b>{{ co.learning?.mastery ?? '—' }}<small v-if="co.learning?.mastery != null">%</small></b></div><div class="mastery-track"><span :style="{ width: `${co.learning?.mastery ?? 0}%` }"></span></div><p>{{ co.learning?.mastery != null ? '持续练习，逐步巩固薄弱知识' : '完成学习后更新掌握情况' }}</p><div class="plan-records"><div><b>{{ co.learning?.questions_answered ?? '—' }}</b><span>已答题目</span></div><div><b>{{ co.learning?.practice_count ?? '—' }}</b><span>实战记录</span></div></div></aside>
      </div>
      <div class="plan-journey"><span>循序向前</span><router-link to="/app/home?section=portrait"><SIcon :name="onb.done ? 'check' : 'user'" :size="16" />认识自己</router-link><SIcon name="right" :size="13" /><router-link to="/app/home?section=diagnostic"><SIcon name="bookcheck" :size="16" />摸清起点</router-link><SIcon name="right" :size="13" /><router-link to="/app/home?activity=quiz"><SIcon name="target" :size="16" />开始练习</router-link></div>
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
const props = defineProps<{ section: string }>()
const emit = defineEmits<{ diagnostic: [] }>()
const router = useRouter(), accounts = useAccountsStore(), onb = useOnboardingStore(), co = useCooperationStore()
const foundations = [
  { icon: 'user', title: '了解你的经历', description: '从学习身份与接待经验出发' },
  { icon: 'target', title: '明确学习方向', description: '把你的目标放在学习的中心' },
  { icon: 'map', title: '安排专属路线', description: '按基础与节奏逐步展开练习' },
]
const diagnosticGuide = [
  { title: '已掌握的知识', description: '看见已有积累，建立学习信心' },
  { title: '待巩固的内容', description: '根据答题反馈找到薄弱知识点' },
  { title: '合适的练习方向', description: '把摸底结果用于后续学习安排' },
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
.assessment-status { display:flex; align-items:center; gap:7px; flex-shrink:0; color:$color-text-secondary; font-size:12px; i { width:6px; height:6px; border-radius:50%; background:#afc2d3; &.ready { background:#43ad8a; } } }
.eyebrow { display:flex; align-items:center; gap:8px; color:$color-text-link; font-size:12px; font-weight:600; letter-spacing:1px; }
h2 { font:600 28px/1.65 $font-serif; letter-spacing:.3px; margin:14px 0 12px; }
.primary-action { display:inline-flex; justify-content:center; align-items:center; gap:18px; min-height:44px; padding:12px 21px; border:0; border-radius:10px 3px 10px 3px; background:#3188e5; color:#fff; font:600 14px/1.4 $font-sans; cursor:pointer; box-shadow:0 5px 14px #3188e51a; transition:background .2s,transform .2s; &:hover { background:#2677ce; transform:translateY(-1px); } }
.action-note { display:block; font-size:11px; color:$color-text-secondary; margin-top:12px; line-height:1.7; }
.portrait-layout { display:grid; grid-template-columns:.75fr 1.25fr; gap:32px; align-items:center; background:linear-gradient(115deg,#edf6ff,#f9fcff); border:1px solid #deebf7; border-radius:20px 5px 20px 5px; padding:28px; position:relative; overflow:hidden; &::after { content:''; position:absolute; left:0; bottom:0; width:190px; height:48px; background:url('../assets/ruyi-cloud.svg') center/contain no-repeat; opacity:.1; pointer-events:none; } }
.portrait-action { position:relative; z-index:1; display:flex; align-items:center; justify-content:center; padding:24px 0; .primary-action { min-width:196px; min-height:50px; font-size:15px; } }
.portrait-preview { position:relative; background:#fff; border:1px solid #dfebf5; border-radius:16px 4px 16px 4px; padding:24px; box-shadow:0 10px 24px #3178ae08; &::before { content:''; position:absolute; top:8px; right:8px; width:11px; height:11px; border-top:1px solid #b8d5ec; border-right:1px solid #b8d5ec; } }
.preview-top { display:flex; align-items:center; justify-content:space-between; color:$color-text-secondary; font-size:11px; }
.portrait-person { display:flex; gap:13px; align-items:center; margin:23px 0 17px; h3 { font:600 18px/1.5 $font-serif; margin:0; } p { font-size:11px; color:$color-text-secondary; margin:5px 0 0; } }
.portrait-avatar { display:grid; place-items:center; width:58px; height:58px; flex-shrink:0; background:#edf6ff; color:$color-text-link; border-radius:50%; }
.persona-summary { font-size:12px; line-height:1.8; color:$color-text-secondary; margin:0 0 20px; }
.portrait-qualities { display:flex; flex-wrap:wrap; gap:9px 15px; color:$color-text-link; font-size:11px; span { display:flex; align-items:center; gap:5px; } }
.preview-footer { margin-top:22px; padding-top:14px; border-top:1px solid #edf2f8; display:flex; align-items:center; gap:7px; font-size:11px; color:$color-text-secondary; i { width:5px; height:5px; border-radius:50%; background:#9fc5e7; } }
.portrait-foundations { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); margin-top:25px; >div { display:flex; align-items:center; gap:12px; padding:8px 22px; border-right:1px solid #dde9f4; &:first-child { padding-left:4px; } &:last-child { border:0; } } h3 { font-weight:500; font-size:13px; margin:0; } p { font-size:11px; line-height:1.6; color:$color-text-secondary; margin:6px 0 0; } }
.foundation-icon { color:$color-text-secondary; }
.diagnostic-layout { display:grid; grid-template-columns:1.55fr 1fr; gap:22px; align-items:stretch; }
.diagnostic-main { border:1px solid #dce9f5; border-radius:18px 5px 18px 5px; background:#fff; padding:30px; h2 { margin:29px 0 12px; } >p { font-size:13px; color:$color-text-secondary; line-height:1.8; margin:0; } }
.diagnostic-top { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.quiet-label { display:flex; align-items:center; gap:6px; font-size:11px; color:$color-text-secondary; }
.diagnostic-scope { margin:25px 0 29px; >span { font-size:11px; color:$color-text-secondary; } >div { display:flex; flex-wrap:wrap; gap:10px; margin-top:12px; span { padding:8px 13px; border:1px solid #e1edf8; border-radius:6px; background:#f7fbff; color:$color-text-secondary; font-size:12px; } } }
.diagnostic-record { display:flex; align-items:center; gap:8px; padding-top:20px; margin-top:27px; border-top:1px solid #eaf0f7; font-size:11px; color:$color-text-secondary; b { color:#436d90; font-size:15px; font-weight:600; } a { margin-left:auto; display:flex; align-items:center; gap:4px; color:$color-text-link; text-decoration:none; } }
.diagnostic-guide { background:#eef5fc; border-radius:16px 4px 16px 4px; padding:27px; h3 { font-size:14px; font-weight:600; margin:0 0 27px; } ol { list-style:none; padding:0; margin:0; } li { display:flex; gap:15px; margin-bottom:25px; >span { font:500 13px/1.7 $font-sans; color:$color-text-secondary; } h4 { font-size:13px; font-weight:500; margin:0 0 8px; } p { font-size:12px; color:$color-text-secondary; line-height:1.7; margin:0; } } }
.guide-note { display:flex; align-items:center; gap:7px; padding-top:16px; border-top:1px solid #dce9f4; font-size:11px; line-height:1.8; color:$color-text-secondary; margin:0; }
.plan-layout { display:grid; grid-template-columns:1.5fr 1fr; background:#fff; border:1px solid #dce9f5; border-radius:18px 5px 18px 5px; overflow:hidden; }
.plan-recommendation { padding:35px; position:relative; >p { color:$color-text-secondary; font-size:13px; line-height:1.9; max-width:450px; margin:0 0 26px; } &::after { content:''; position:absolute; right:20px; bottom:20px; width:110px; height:50px; background:url('../assets/ruyi-cloud.svg') center/contain no-repeat; opacity:.15; pointer-events:none; } }
.text-link { display:flex; align-items:center; gap:5px; margin-top:16px; color:$color-text-secondary; font-size:12px; text-decoration:none; }
.plan-overview { background:#f9fcff; border-left:1px solid #e6eef6; padding:30px; h3 { font-weight:500; font-size:13px; margin:0 0 30px; color:$color-text-secondary; } >p { font-size:11px; color:$color-text-secondary; margin:10px 0 26px; } }
.mastery-label { display:flex; align-items:baseline; justify-content:space-between; gap:12px; color:$color-text-secondary; font-size:12px; b { color:$color-text-link; font-size:32px; font-weight:500; line-height:1; small { font-size:13px; margin-left:3px; } } }
.mastery-track { height:5px; background:#e5eef7; border-radius:5px; margin-top:15px; overflow:hidden; span { display:block; height:100%; background:#74afe7; border-radius:5px; } }
.plan-records { display:flex; gap:35px; padding-top:20px; border-top:1px solid #e1ebf5; div { display:flex; flex-direction:column; gap:7px; } b { font-size:22px; font-weight:500; color:#446f93; } span { font-size:11px; color:$color-text-secondary; } }
.plan-journey { display:flex; justify-content:center; align-items:center; gap:24px; padding:25px 10px; font-size:12px; color:$color-text-secondary; >span { font-size:11px; color:$color-text-secondary; margin-right:7px; } a { display:flex; align-items:center; gap:7px; color:$color-text-secondary; text-decoration:none; &:hover { color:$color-text-link; } } }
button:focus-visible,a:focus-visible { outline:2px solid #6bace8; outline-offset:4px; }
@media(max-width:900px) { .portrait-layout { gap:28px; padding:28px; } h2 { font-size:24px; } .diagnostic-main,.diagnostic-guide { padding:24px; } .portrait-foundations >div { padding:8px 14px; } }
@media(max-width:650px) { .assessment-entry { padding:24px 16px; } .assessment-heading { align-items:flex-start; h1 { font-size:22px; } } .assessment-status { margin-top:5px; font-size:11px; } .portrait-layout,.diagnostic-layout,.plan-layout { grid-template-columns:1fr; } .portrait-layout { padding:24px; gap:20px; } .portrait-action { padding:8px 0; } .portrait-foundations { grid-template-columns:1fr; gap:16px; >div { padding:0 4px; border:0; } } .diagnostic-main h2 { margin-top:23px; } .plan-recommendation,.plan-overview { padding:25px; } .plan-overview { border-left:0; border-top:1px solid #e6eef6; } .plan-journey { flex-wrap:wrap; gap:12px; >span { width:100%; text-align:center; margin:0 0 3px; } } }
@media(prefers-reduced-motion:reduce) { .primary-action { transition:none; transform:none!important; } }
</style>
