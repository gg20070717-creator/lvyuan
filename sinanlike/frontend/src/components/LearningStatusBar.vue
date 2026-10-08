<template>
  <section class="learning-status-bar" :class="{ compact }" aria-label="当前学习状态" aria-live="polite">
    <nav v-if="!compact" aria-label="学习总流程">
      <button v-for="(step,index) in steps" :key="step.label" :class="{ current:index === stageIndex, evidenced:evidence(index) }" :aria-current="index === stageIndex ? 'step' : undefined" @click="go(step.path,index)">
        <span><SIcon v-if="evidence(index) && index !== stageIndex" name="check" :size="11" /><template v-else>{{ index + 1 }}</template></span>{{ step.label }}
      </button>
    </nav>
    <div class="ls-live"><i :class="{ busy: co.running }"></i><b>{{ status }}</b><span v-if="co.running">{{ co.activeAgents.length }} 个角色协作</span><span v-else-if="co.practice">第 {{ co.practice.index + 1 }} 阶段，共 {{ co.practice.total }} 阶段</span><span v-else-if="co.learning?.mastery != null">掌握 {{ co.learning.mastery }}%</span>
      <button v-if="co.trace.length || co.running" @click="co.visible = true; co.collapsed = false"><SIcon name="sparkle" :size="12" />协作过程</button>
      <button v-if="!compact && !co.running && accounts.isSignedIn && co.learning" :title="co.learning.recommendation.reason" @click="router.push(co.learning.recommendation.path)">{{ co.learning.recommendation.label }}<SIcon name="right" :size="11" /></button>
    </div>
  </section>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAccountsStore } from '@/stores/accounts'
import { useOnboardingStore } from '@/stores/onboarding'
import { useCooperationStore } from '@/stores/cooperation'
import { cleanNumberedTitle } from '@/utils/displayText'
import SIcon from './SIcon.vue'
const route = useRoute(), router = useRouter()
defineProps<{ compact?: boolean }>()
const accounts = useAccountsStore(), onb = useOnboardingStore(), co = useCooperationStore()
const steps = [
  { label:'学前画像',path:'/app/profile' },{ label:'知识学习',path:'/app/knowledge-tree' },
  { label:'抽题测验',path:'/app/home?activity=quiz' },{ label:'专项练习',path:'/app/training?focus=communication' },
  { label:'综合实战',path:'/app/training?focus=integrated' },
]
const stageIndex = computed(() => {
  if (!accounts.isSignedIn || !onb.done || route.path === '/app/profile' || ['portrait','diagnostic','plan'].includes(String(route.query.section))) return 0
  if (route.path === '/app/training') return route.query.focus === 'integrated' || !route.query.focus ? 4 : 3
  if (route.path === '/app/knowledge-tree' || route.path === '/app/knowledge') return 1
  if (route.query.activity === 'quiz' || co.teaching?.stage === 'practicing') return 2
  return 1
})
const status = computed(() => {
  if (!accounts.isSignedIn) return '游客浏览'
  if (accounts.flowOpen) return accounts.flowStage === 'onboarding' ? '完善学前画像' : '注册、登录'
  if (co.running) return co.title
  if (route.path === '/app/home' && route.query.section) return ({ portrait:'查看自我画像', diagnostic:'准备知识摸底', plan:'查看学习建议' } as Record<string,string>)[String(route.query.section)] || '学前准备'
  if (route.path === '/app/profile') return '查看自我画像与学情'
  if (route.path === '/app/knowledge') return '浏览定制学习资源'
  if (route.path === '/app/knowledge-tree') return '知识学习'
  if (route.path === '/app/training' && co.practice) return cleanNumberedTitle(co.practice.title)
  if (route.path === '/app/training') return stageIndex.value === 4 ? '选择综合实战场景' : route.query.focus === 'emergency' ? '选择应急处理场景' : '选择沟通训练场景'
  if (route.query.activity === 'quiz' && co.teaching?.stage !== 'practicing') return '准备抽题测验'
  const labels:Record<string,string> = { goal_setting:'确定学习目标',teaching:'知识学习中',checking:'确认理解',practicing:'答题测验中',feedback:'分析错因与巩固',closing:'学习复盘',idle:'准备开始学习' }
  return labels[co.teaching?.stage || 'idle'] || '准备开始学习'
})
function evidence(index:number) {
  if (index === 0) return accounts.isSignedIn && onb.done
  if (index === 1) return !!co.teaching?.topics.length && ['checking','practicing','feedback','closing'].includes(co.teaching.stage)
  if (index === 2) return !!co.teaching?.topic_done || !!co.teaching?.topic_finished
  if (index === 3) return (co.learning?.specialty_count || 0) > 0
  return (co.learning?.integrated_count || 0) > 0
}
function go(path:string,index:number) {
  if (index === 0 && accounts.isSignedIn && !onb.done) accounts.openOnboarding()
  else router.push(path)
}
</script>
<style scoped lang="scss">
.learning-status-bar { flex-shrink:0; display:flex; align-items:center; justify-content:space-between; gap:18px; padding:12px 28px; border-bottom:1px solid #dce9f6; background:#fff; color:#42586e; font-size:14px; }
.learning-status-bar.compact { padding:0; border:0; min-width:0; flex-shrink:1;
  .ls-live { min-width:0; padding:0; gap:7px; b { font-size:11px; font-weight:400; max-width:170px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; } >span { white-space:nowrap; } button { padding:5px 7px; background:transparent; border-color:transparent; white-space:nowrap; } i { flex-shrink:0; } }
}
@media(max-width:1000px) { .learning-status-bar.compact .ls-live >span { display:none; } }
nav { display:flex; align-items:center; gap:6px; min-width:0; overflow:auto; scrollbar-width:none; button { position:relative; display:flex; align-items:center; gap:7px; padding:6px 10px; border:0; background:transparent; color:#42586e; white-space:nowrap; font:inherit; cursor:pointer; border-radius:9px; span { width:21px; height:21px; border:1px solid #dce7f1; border-radius:50%; display:grid; place-items:center; font-size:10px; } &.current { background:#edf6ff; color:#1d5e99; font-weight:600; span { background:#338ff2; color:#fff; border-color:#338ff2; } } &.evidenced:not(.current) span { color:#207159; background:#eaf7f1; border-color:#d6eade; } } }
.ls-live { display:flex; align-items:center; gap:8px; flex-shrink:0; i { width:6px; height:6px; border-radius:50%; background:#4ab38d; &.busy { background:#338ff2; animation:ls-pulse 1.5s infinite; } } b { font-size:12px; font-weight:600; } >span { color:#42586e; font-size:11px; } button { display:flex; align-items:center; gap:5px; padding:6px 9px; color:#1d5e99; background:#f2f8ff; border:1px solid #e0edfa; border-radius:7px; cursor:pointer; font-size:11px; } }
@keyframes ls-pulse { 50% { opacity:.4; } }
@media(max-width:1200px) { .learning-status-bar { flex-wrap:wrap; gap:5px; padding:10px 18px; } nav { width:100%; } .ls-live { padding:2px 10px; } }
@media(max-width:600px) { .learning-status-bar { padding:8px; } nav { gap:0; } nav button { padding:6px; font-size:11px; } }
@media(prefers-reduced-motion:reduce) { .ls-live i { animation:none!important; } }
</style>
