<template>
  <Teleport to="body">
    <Transition name="workflow-float">
      <section v-if="co.visible" class="workflow-float" :class="{ compact: co.collapsed }" aria-label="多智能体协作过程">
        <header>
          <div class="wf-brand"><span class="wf-brand-icon"><SIcon name="sparkle" :size="20" /></span><div><span>多智能体协作</span><h2>{{ co.title }}</h2></div></div>
          <div class="wf-controls"><button :aria-expanded="!co.collapsed" :aria-label="co.collapsed ? '展开协作过程' : '收起协作过程'" @click="co.collapsed = !co.collapsed"><SIcon :name="co.collapsed ? 'up' : 'down'" :size="15" /></button><button v-if="!co.running" aria-label="关闭协作窗口" @click="co.visible = false"><SIcon name="x" :size="15" /></button></div>
        </header>
        <div class="wf-now" role="status" aria-live="polite"><span class="wf-status" :class="{ live: co.running || co.replaying, failed: co.terminal === 'failed' }"><i></i>{{ co.currentStep }}</span><span class="wf-count">{{ co.replaying ? '调用记录回放' : co.running ? '实时更新' : co.terminal === 'failed' ? '任务中断' : '本次任务已结束' }}</span></div>
        <ol class="wf-flow" aria-label="任务阶段"><li v-for="step in co.steps" :key="step.id" :class="step.state" :aria-current="step.state === 'working' ? 'step' : undefined" :aria-label="step.label + '：' + stepLabel(step.state)"><span class="wf-segment"></span><span>{{ step.label }}<SIcon v-if="step.state === 'done'" name="check" :size="11" /><SIcon v-else-if="['failed', 'warning'].includes(step.state)" name="warn" :size="11" /></span></li></ol>
        <template v-if="!co.collapsed">
          <div class="wf-body">
            <div class="wf-dispatch"><span class="wf-dispatch-icon"><SIcon :name="co.latestDispatch?.agent === 'system' ? 'map' : 'sparkle'" :size="16" /></span><div><b>{{ dispatchTitle }}</b><p>{{ dispatchNote }}</p></div><span v-if="co.dispatches.length" class="wf-round">第 {{ co.latestDispatch?.round || co.dispatches.length }} 轮</span></div>
            <div class="wf-roster-heading"><h3>本次参与</h3><span>{{ participants.length }} 个角色<span v-if="activeCount">，{{ activeCount }} 个执行中</span></span></div>
            <div v-if="participants.length" class="wf-participants"><button v-for="agent in participants" :key="agent.id" class="wf-agent" :class="agentState(agent.id)" :aria-expanded="selected === agent.id" :aria-label="agent.name + '：' + statusLabel(agent.id)" @click="selected = selected === agent.id ? '' : agent.id"><span class="wf-agent-icon"><SIcon :name="agent.icon" :size="17" /></span><span class="wf-agent-copy"><b>{{ agent.name }}</b><small>{{ statusLabel(agent.id) }}</small></span><SIcon v-if="agentState(agent.id) === 'done'" name="check" :size="14" /><SIcon v-else-if="agentState(agent.id) === 'failed'" name="warn" :size="14" /><i v-else-if="agentState(agent.id) === 'working'" class="wf-ring"></i></button></div>
            <p v-else class="wf-empty">{{ co.running || co.replaying ? '正在接收任务，参与角色将在分工后出现。' : '本次由流程直接完成，未调用协作角色。' }}</p>
            <div v-if="selected && co.last[selected]" class="wf-detail"><b>{{ co.last[selected].role }}</b><p v-if="co.last[selected].detail">{{ co.last[selected].detail }}</p></div>
            <details class="wf-more"><summary>查看协作详情<SIcon name="down" :size="13" /></summary><div class="wf-more-content"><div v-if="co.dispatches.length" class="wf-log"><h4>分工记录</h4><p v-for="(event, index) in co.dispatches" :key="index"><b>{{ event.source === 'policy' ? '规则追加' : `第 ${event.round || index + 1} 轮` }}</b><span>{{ (event.agents || []).map(id => co.catalog.find(a => a.id === id)?.name || co.last[id]?.name || id).join('、') || '管家直接回复' }}</span></p></div><div v-if="standbyAgents.length" class="wf-standby"><h4>其余角色待命</h4><div><span v-for="agent in standbyAgents" :key="agent.id">{{ agent.name }}</span></div></div><p v-if="co.catalogError" class="wf-hint">角色清单暂未连接，当前调用仍按真实记录显示。</p><p v-if="co.reserved.length" class="wf-hint">图表、演示与图片生成角色尚未启用。</p></div></details>
          </div>
          <footer :class="{ 'wf-error': co.error }"><SIcon :name="co.error ? 'warn' : co.running || co.replaying ? 'clock' : 'check'" :size="13" /><span>{{ co.error || (co.replaying ? '正在回放真实调用，回复已可阅读' : co.running ? '按实际任务阶段与调用记录更新' : '本次记录已保存，可从顶部再次查看') }}</span></footer>
        </template>
      </section>
    </Transition>
  </Teleport>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useCooperationStore } from '@/stores/cooperation'
import SIcon from './SIcon.vue'
const co = useCooperationStore()
const selected = ref('')
watch(() => co.trace.length, (length, previous) => { if (length === 0 || length < previous) selected.value = '' })
const planning = computed(() => (co.running || co.replaying) && co.last.concierge?.status === 'working' && co.last.concierge?.step === 'planning')
// 从真实轨迹生成参与名单；目录暂不可用时仍可显示已有调用。
const participants = computed(() => Object.entries(co.last).filter(([id]) => id !== 'system' && id !== 'review').map(([id, event]) => ({ id, name: co.catalog.find(a => a.id === id)?.name || event.name, icon: co.catalog.find(a => a.id === id)?.icon || 'sparkle' })).sort((a, b) => Number(agentState(b.id) === 'working') - Number(agentState(a.id) === 'working')))
const activeCount = computed(() => participants.value.filter(agent => agentState(agent.id) === 'working').length)
const standbyAgents = computed(() => co.catalog.filter(agent => !co.last[agent.id]))
const dispatchTitle = computed(() => planning.value ? '管家正在理解任务' : co.latestDispatch?.source === 'policy' ? '追加协作分工' : co.latestDispatch?.agent === 'system' ? '实战任务已分工' : co.latestDispatch ? '本轮分工已确定' : co.running ? '等待任务分工' : '本次协作记录')
const dispatchNote = computed(() => planning.value ? '根据目标选择合适的角色' : co.latestDispatch ? co.latestDispatch.agents?.length ? `安排 ${co.latestDispatch.agents.length} 个角色参与本轮任务` : '由管家直接完成本轮回复' : '按任务需要安排协作角色')
function stepLabel(state: string) { return ({ done:'完成', skipped:'本次无需', pending:'等待安排', working:'进行中', warning:'包含降级', failed:'中断' } as Record<string,string>)[state] || '等待安排' }
function statusLabel(id: string) {
  const event = co.last[id]
  if (!event) return '待命'
  if (agentState(id) === 'failed') return event.status === 'working' ? '调用中断' : '调用异常'
  if (agentState(id) === 'ended') return '本次已结束'
  return event.status === 'working' ? (co.replaying ? '过程回放' : '正在执行') : '已完成'
}
function agentState(id: string) { const status = co.last[id]?.status || 'pending'; if (status === 'working' && !co.replaying && !co.running) return co.terminal === 'failed' ? 'failed' : co.terminal === 'done' ? 'ended' : status; return status }
</script>
<style scoped lang="scss">
@use '@/styles/tokens' as *;
.workflow-float { position:fixed; right:24px; bottom:22px; z-index:2400; width:382px; max-width:calc(100vw - 24px); max-height:calc(100dvh - 105px); display:flex; flex-direction:column; overflow:hidden; background:#fff; color:#2c4f6d; border:1px solid #cfdff0; border-radius:17px 5px 17px 5px; box-shadow:0 14px 48px #234e7521; font-family:$font-sans; }
header { display:flex; align-items:center; justify-content:space-between; gap:10px; padding:18px 19px 13px; }
.wf-brand { display:flex; gap:11px; align-items:center; min-width:0; >div { min-width:0; } span:not(.wf-brand-icon) { font-size:10px; color:$color-text-secondary; } h2 { font-size:14px; line-height:1.6; font-weight:600; margin:3px 0 0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; } }
.wf-brand-icon { display:grid; place-items:center; width:35px; height:35px; flex-shrink:0; background:#edf6ff; color:$color-text-link; border-radius:10px 3px 10px 3px; }
.wf-controls { display:flex; gap:2px; flex-shrink:0; button { display:grid; place-items:center; width:29px; height:29px; padding:0; background:transparent; color:$color-text-secondary; border:0; border-radius:6px; cursor:pointer; &:hover { background:#f0f6fc; color:$color-text-link; } } }
.wf-now { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:0 20px 15px; }
.wf-status { display:flex; align-items:center; gap:7px; font-size:13px; font-weight:500; i { width:6px; height:6px; border-radius:50%; background:#4aab8a; flex-shrink:0; } &.live i { background:#4992d7; animation:wf-pulse 1.8s ease-in-out infinite; } &.failed i { background:#ce9756; } }
.wf-count { color:$color-text-secondary; font-size:10px; }
.wf-flow { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:7px; list-style:none; padding:0 20px 18px; margin:0; flex-shrink:0; li { min-width:0; display:flex; flex-direction:column; gap:8px; color:$color-text-secondary; font-size:10px; >span:last-child { display:flex; align-items:center; gap:3px; white-space:nowrap; } } .wf-segment { height:4px; background:#e8eff6; border-radius:4px; } .done { color:#446d5f; .wf-segment { background:#89bea9; } } .working { color:$color-text-link; .wf-segment { background:#4794df; } } .failed,.warning { color:#7c6039; .wf-segment { background:#d9af73; } } .skipped .wf-segment { background:repeating-linear-gradient(90deg,#dfe8f1 0 5px,transparent 5px 8px); } }
.wf-body { min-height:0; overflow-y:auto; scrollbar-width:thin; padding:0 20px 15px; border-top:1px solid #eaf0f7; }
.wf-dispatch { display:flex; align-items:center; gap:10px; padding:15px 0; border-bottom:1px solid #eaf0f7; >div { flex:1; min-width:0; } b { font-size:12px; font-weight:500; } p { font-size:11px; color:$color-text-secondary; margin:5px 0 0; line-height:1.6; } }
.wf-dispatch-icon { color:$color-text-secondary; flex-shrink:0; }
.wf-round { font-size:10px; color:$color-text-secondary; white-space:nowrap; }
.wf-roster-heading { display:flex; align-items:center; justify-content:space-between; gap:10px; padding:16px 0 11px; h3 { font-size:12px; font-weight:500; margin:0; } >span { font-size:10px; color:$color-text-secondary; } }
.wf-participants { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:7px; }
.wf-agent { display:flex; align-items:center; gap:8px; min-width:0; padding:10px; background:#f8fbfd; border:1px solid #e8eff6; border-radius:8px 3px 8px 3px; text-align:left; color:$color-text-secondary; font-family:inherit; cursor:pointer; transition:background .2s,border-color .2s; .wf-agent-icon { color:$color-text-secondary; flex-shrink:0; display:grid; place-items:center; } .wf-agent-copy { flex:1; min-width:0; } b { display:block; font-size:11px; font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; } small { display:block; margin-top:4px; font-size:10px; color:$color-text-secondary; } >svg { flex-shrink:0; color:#4d6b5f; } &.working { background:#f0f7ff; border-color:#b9d6f0; color:$color-text-link; .wf-agent-icon { color:$color-text-link; } small { color:$color-text-secondary; } } &.failed { color:#7d5f3c; background:#fffaf4; border-color:#efdfc7; } &[aria-expanded=true] { border-color:#7faed5; } }
.wf-ring { width:12px; height:12px; border:1.5px solid #d4e5f4; border-top-color:#569ada; border-radius:50%; flex-shrink:0; animation:wf-turn .9s linear infinite; }
.wf-empty { font-size:11px; color:$color-text-secondary; line-height:1.8; padding:3px 0 10px; margin:0; }
.wf-detail { padding:11px 13px; margin-top:10px; background:#f1f7fc; border-radius:8px; font-size:11px; line-height:1.8; b { font-weight:500; } p { margin:5px 0 0; color:$color-text-secondary; } }
.wf-more { margin-top:14px; summary { display:flex; align-items:center; justify-content:space-between; cursor:pointer; list-style:none; color:$color-text-secondary; font-size:11px; padding:8px 0; &::-webkit-details-marker { display:none; } } &[open] summary >svg { transform:rotate(180deg); } }
.wf-more-content { border-top:1px solid #edf2f7; padding-top:10px; h4 { font-size:11px; font-weight:500; color:$color-text-secondary; margin:0 0 10px; } }
.wf-log { margin-bottom:15px; p { display:flex; gap:10px; margin:9px 0; font-size:10px; line-height:1.8; color:$color-text-secondary; b { font-weight:400; flex-shrink:0; color:$color-text-secondary; } } }
.wf-standby >div { display:flex; flex-wrap:wrap; gap:7px 12px; font-size:10px; line-height:1.7; color:$color-text-secondary; }
.wf-hint { color:$color-text-secondary; font-size:10px; line-height:1.7; margin:12px 0 0; }
footer { display:flex; align-items:flex-start; gap:6px; padding:11px 20px; border-top:1px solid #eaf0f7; background:#fafcfe; color:$color-text-secondary; font-size:10px; line-height:1.7; flex-shrink:0; svg { flex-shrink:0; margin-top:2px; } &.wf-error { color:#895a3a; } }
.compact header { padding-bottom:10px; }
.compact .wf-now { padding-bottom:12px; }
.compact .wf-flow { padding-bottom:15px; }
button:focus-visible,summary:focus-visible { outline:2px solid #6bace8; outline-offset:3px; }
.workflow-float-enter-active,.workflow-float-leave-active { transition:opacity .22s,transform .26s; }
.workflow-float-enter-from,.workflow-float-leave-to { opacity:0; transform:translateY(12px); }
@keyframes wf-turn { to { transform:rotate(360deg); } }
@keyframes wf-pulse { 50% { opacity:.4; } }
@media(max-width:600px) { .workflow-float { right:12px; bottom:12px; width:calc(100vw - 24px); max-height:55dvh; } }
@media(prefers-reduced-motion:reduce) { *,*::before,*::after { animation:none!important; transition:none!important; } }
</style>
