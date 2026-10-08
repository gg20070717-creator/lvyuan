<template>
  <button type="button" class="scenario-card" :class="{ 'scenario-integrated': integrated, 'scenario-capstone': capstone, locked, completed }" :aria-disabled="locked" @click="$emit('select', scenario)">
    <div class="scenario-symbol"><SIcon :name="icon" :size="capstone ? 28 : 23" /></div>
    <div class="scenario-content">
      <div class="scenario-meta"><span>{{ integrated ? (capstone ? '全流程任务' : '分项任务') : scenario.category }}</span><span v-if="completed" class="complete-label"><SIcon name="check" :size="12" />已完成</span><span v-else>{{ scenario.stage_count }} 个阶段</span></div>
      <h3>{{ scenario.title }}</h3>
      <p :title="display(scenario.task || scenario.location)">{{ display(scenario.task || scenario.location) }}</p>
      <ol v-if="integrated && scenario.stage_titles?.length" class="scenario-stages"><li v-for="(title, index) in scenario.stage_titles.slice(0, 3)" :key="index"><i>{{ index + 1 }}</i>{{ display(title) }}</li><li v-if="scenario.stage_titles.length > 3" class="stages-more">等 {{ scenario.stage_count }} 个阶段</li></ol>
      <div v-else class="scenario-location"><SIcon name="pin" :size="12" />{{ display(scenario.location) }}</div>
    </div>
    <div class="scenario-bottom">
      <span class="scenario-difficulty"><i v-for="level in 3" :key="level" :class="{ filled: level <= scenario.difficulty }"></i>{{ difficultyLabel }}</span>
      <span class="scenario-action"><SIcon v-if="locked" name="lock" :size="13" />{{ locked ? '完成前置练习后解锁' : completed ? '再次练习' : capstone ? '进入实战' : '开始练习' }}<SIcon v-if="!locked" name="right" :size="14" /></span>
    </div>
  </button>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import type { SandboxTemplate } from '@/api/sandbox'
import { cleanDisplayText as display } from '@/utils/displayText'
import SIcon from './SIcon.vue'
const props = defineProps<{ scenario: SandboxTemplate; integrated?: boolean; capstone?: boolean; locked?: boolean; completed?: boolean; icon: string }>()
defineEmits<{ select: [scenario: SandboxTemplate] }>()
const difficultyLabel = computed(() => props.scenario.difficulty >= 3 ? '进阶' : props.scenario.difficulty === 2 ? '提升' : '基础')
</script>
<style scoped lang="scss">
@use '@/styles/tokens' as *;
.scenario-card { position:relative; width:100%; min-width:0; text-align:left; display:grid; grid-template-columns:46px minmax(0,1fr); gap:17px; padding:24px; background:#fff; border:1px solid #dce9f5; border-radius:16px 4px 16px 4px; color:#294f70; font-family:$font-sans; cursor:pointer; transition:border-color .2s,box-shadow .2s,transform .2s; &::before { content:''; position:absolute; top:7px; right:7px; width:10px; height:10px; border-top:1px solid #bed8ec; border-right:1px solid #bed8ec; } &:hover { border-color:#94bfe7; box-shadow:0 6px 20px #2c6da50a; transform:translateY(-2px); } &:focus-visible { outline:2px solid #338ff2; outline-offset:3px; } }
.scenario-symbol { display:grid; place-items:center; flex-shrink:0; width:46px; height:46px; color:$color-text-link; background:#edf6ff; border:1px solid #e2edf8; border-radius:12px 3px 12px 3px; }
.scenario-meta { display:flex; align-items:center; gap:10px; color:$color-text-secondary; font-size:10px; line-height:1.5; >span:last-child { margin-left:auto; white-space:nowrap; } .complete-label { display:flex; gap:3px; align-items:center; color:#406d5d; } }
.scenario-content { min-width:0; h3 { font-size:16px; font-weight:600; line-height:1.65; margin:9px 0 8px; } >p { color:$color-text-secondary; font-size:12px; line-height:1.85; margin:0; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; } }
.scenario-location { display:flex; align-items:center; gap:5px; color:$color-text-secondary; font-size:11px; margin-top:14px; line-height:1.7; }
.scenario-bottom { grid-column:1/-1; display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:12px; padding-top:17px; border-top:1px solid #edf2f7; }
.scenario-difficulty { display:flex; align-items:center; gap:3px; color:$color-text-secondary; font-size:10px; i { height:9px; width:3px; border-radius:2px; background:#e0eaf3; &:nth-child(2) { height:12px; } &:nth-child(3) { height:15px; margin-right:5px; } &.filled { background:#8bb8df; } } }
.scenario-action { display:flex; align-items:center; justify-content:center; gap:9px; padding:7px 12px; border-radius:7px 2px 7px 2px; background:#eff6fe; color:$color-text-link; font-size:12px; font-weight:500; white-space:nowrap; }
.scenario-stages { display:flex; flex-wrap:wrap; gap:10px 16px; list-style:none; padding:0; margin:17px 0 0; li { display:flex; align-items:center; gap:6px; font-size:11px; color:$color-text-secondary; line-height:1.7; } i { display:grid; place-items:center; width:17px; height:17px; background:#eef5fb; border-radius:50%; font-size:9px; font-style:normal; color:$color-text-secondary; } .stages-more { font-size:10px; color:$color-text-secondary; } }
.scenario-integrated { grid-template-columns:38px minmax(0,1fr); padding:22px; .scenario-symbol { width:38px; height:38px; } .scenario-content h3 { font-size:15px; } }
.scenario-capstone { grid-template-columns:62px minmax(0,1fr) auto; gap:23px; padding:29px; background:linear-gradient(110deg,#eef6ff,#fff 70%); border-color:#c8dff2; .scenario-symbol { width:62px; height:62px; background:#fff; border-color:#d8e7f5; } .scenario-content h3 { font:600 20px/1.6 $font-serif; } .scenario-meta { justify-content:flex-start; gap:15px; >span:last-child { margin-left:0; } } .scenario-bottom { grid-column:3; flex-direction:column; justify-content:center; align-items:flex-end; border:0; padding:0; } .scenario-action { background:#3188e5; color:#fff; padding:12px 19px; font-size:13px; } }
.locked { background:#f9fbfd; cursor:not-allowed; .scenario-symbol { background:#f0f4f8; color:$color-text-secondary; } .scenario-action { color:$color-text-secondary; background:#ecf1f6; font-size:11px; } &:hover { transform:none; box-shadow:none; border-color:#dce9f5; } }
@media(max-width:700px) { .scenario-card { padding:20px; gap:14px; } .scenario-capstone { grid-template-columns:46px minmax(0,1fr); .scenario-symbol { width:46px; height:46px; } .scenario-bottom { grid-column:1/-1; flex-direction:row; align-items:center; justify-content:space-between; border-top:1px solid #e3edf6; padding-top:17px; } .scenario-content h3 { font-size:18px; } } }
@media(prefers-reduced-motion:reduce) { .scenario-card { transition:none; transform:none!important; } }
</style>
