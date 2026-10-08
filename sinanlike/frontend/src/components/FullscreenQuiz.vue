<template>
  <Teleport to="body"><Transition name="quiz-screen"><section v-if="modelValue" class="quiz-screen" role="dialog" aria-modal="true" aria-labelledby="quiz-screen-title" ref="screen" tabindex="-1" @keydown="trapFocus">
    <header><span class="fq-brand"><img :src="logo" alt="旅鸢" />旅鸢   抽题测验</span><button :disabled="pending" @click="$emit('update:modelValue',false)"><SIcon name="back" :size="14" />回到学习对话</button></header>
    <nav aria-label="学习与答题流程"><span class="finished"><i>✓</i>题目准备</span><b></b><span :class="quiz ? 'current' : 'finished'"><i>{{ quiz ? '2' : '✓' }}</i>抽题测验</span><b></b><span :class="{ current: !quiz }"><i>3</i>反馈巩固</span><b></b><span><i>4</i>实战应用</span></nav>
    <main><aside><span class="fq-eyebrow">练习，连接知识与应用</span><h2 id="quiz-screen-title">用一次作答<br />检验与巩固知识</h2><p>旅鸢会依据作答结果解释错因，并调整后续难度。随机抽题也可以用来了解自己的知识基础。</p><div class="fq-mastery"><span>当前主题</span><b>{{ quiz?.knowledge_point_title || '反馈巩固' }}</b><small v-if="quiz?.progress">已完成 {{ quiz.progress.done }} 道，共 {{ quiz.progress.total }} 道</small></div><GuofengLandscape class="fq-landscape" /></aside>
      <div class="fq-workspace"><Transition name="fq-question" mode="out-in"><div :key="quiz?.question_id || 'feedback'" class="fq-card">
        <template v-if="quiz"><div class="fq-meta"><span>{{ quiz.type === 'essay' ? '进阶简答题' : '主题选择题' }}</span><span v-if="quiz.difficulty_level">难度 {{ quiz.difficulty_level }} 级</span></div><h3>{{ quiz.prompt }}</h3>
          <div v-if="quiz.options?.length" class="fq-options"><button v-for="(option,index) in quiz.options" :key="index" :class="{ selected: selected === letter(option,index) }" :disabled="pending" @click="selected = letter(option,index)"><span>{{ letter(option,index) }}</span>{{ option.replace(/^[A-Da-d][.、．]\s*/, '') }}</button></div>
          <textarea v-else v-model="answer" aria-label="简答题回答" rows="6" placeholder="写下你的判断、理由和处理步骤……" :disabled="pending"></textarea>
          <div class="fq-submit"><span>{{ pending ? '测评角色正在判分，协作过程可在悬浮窗查看' : '确认答案后提交，旅鸢会给出反馈' }}</span><button class="primary" :disabled="pending || !(quiz.options?.length ? selected : answer.trim())" @click="submit">{{ pending ? '判分中…' : '提交作答' }}<SIcon name="right" :size="14" /></button></div>
        </template>
        <template v-else><span class="fq-eyebrow">本轮作答反馈</span><h3>看看哪里已经掌握，哪里还需巩固</h3><MarkdownViewer :content="feedback || '反馈已保存在学习对话中。'" /><button class="primary fq-back" @click="$emit('update:modelValue',false)">继续学习<SIcon name="right" :size="14" /></button></template>
      </div></Transition></div>
    </main>
  </section></Transition></Teleport>
</template>
<script setup lang="ts">
import { nextTick, onUnmounted, ref, watch } from 'vue'
import type { TeachingQuiz } from '@/api/messages'
import SIcon from './SIcon.vue'
import MarkdownViewer from './MarkdownViewer.vue'
import GuofengLandscape from './GuofengLandscape.vue'
import logo from '@/assets/lvyuan-logo.jpg'
const props = defineProps<{ modelValue:boolean; quiz:TeachingQuiz | null; pending:boolean; feedback:string }>()
const emit = defineEmits<{ 'update:modelValue':[boolean]; answer:[string] }>()
const answer = ref(''), selected = ref(''), screen = ref<HTMLElement | null>(null)
let previousFocus:HTMLElement | null = null, previousOverflow = ''
function letter(option:string,index:number) { return option.match(/^([A-Da-d])[.、．]/)?.[1]?.toUpperCase() || String.fromCharCode(65+index) }
function submit() { emit('answer', props.quiz?.options?.length ? `我选 ${selected.value}` : `我的回答：${answer.value.trim()}`) }
function restore() { document.body.style.overflow = previousOverflow; previousFocus?.focus() }
watch(() => props.quiz?.question_id, () => { answer.value=''; selected.value=''; if(props.modelValue) nextTick(() => screen.value?.focus()) })
watch(() => props.modelValue, async open => {
  if(open) { previousFocus = document.activeElement as HTMLElement; previousOverflow = document.body.style.overflow; document.body.style.overflow='hidden'; await nextTick(); screen.value?.focus() }
  else restore()
})
function trapFocus(event:KeyboardEvent) {
  if (event.key === 'Escape' && !props.pending) { emit('update:modelValue',false); return }
  if(event.key !== 'Tab') return
  const nodes = [...screen.value?.querySelectorAll<HTMLElement>('button:not(:disabled),textarea:not(:disabled)') || []].filter(el => el.offsetParent !== null)
  if(!nodes.length) { event.preventDefault(); return }
  const first=nodes[0], last=nodes[nodes.length-1]
  if(event.shiftKey && (document.activeElement === first || document.activeElement === screen.value)) { event.preventDefault(); last.focus() }
  else if(!event.shiftKey && (document.activeElement === last || document.activeElement === screen.value)) { event.preventDefault(); first.focus() }
}
onUnmounted(() => { if(props.modelValue) restore() })
</script>
<style scoped lang="scss">
.quiz-screen { position:fixed; inset:0; z-index:1900; display:flex; flex-direction:column; background:#f5f9fd; color:#244964; overflow:auto; }
header { display:flex; align-items:center; justify-content:space-between; padding:22px 5vw; background:#fff; border-bottom:1px solid #e0ebf5; flex-shrink:0; .fq-brand { display:flex; align-items:center; gap:12px; font-size:17px; font-weight:600; img { width:34px; height:34px; } } button { display:flex; gap:7px; align-items:center; background:none; border:0; color:#42586e; cursor:pointer; font-size:13px; } }
nav { display:flex; align-items:center; justify-content:center; gap:25px; padding:27px 24px; flex-shrink:0; span { display:flex; align-items:center; gap:9px; font-size:14px; color:#42586e; i { width:28px; height:28px; display:grid; place-items:center; border-radius:50%; border:1px solid #d8e5f0; font-style:normal; } &.current { color:#1d5e99; font-weight:600; i { background:#338ff2; color:white; border-color:#338ff2; } } &.finished { color:#277156; } } >b { height:1px; width:55px; background:#d4e4f3; } }
main { display:grid; grid-template-columns:minmax(240px,310px) minmax(0,740px); gap:55px; padding:30px 5vw 60px; margin:auto; width:100%; max-width:1240px; box-sizing:border-box; flex:1; align-items:start; }
aside { position:relative; overflow:hidden; padding:28px 0 120px; h2 { font-family:'Noto Serif SC','SimSun',serif; font-size:29px; line-height:1.65; margin:15px 0; } >p { font-size:14px; line-height:1.9; color:#42586e; } }
.fq-eyebrow { font-size:12px; letter-spacing:2px; color:#1d5e99; }
.fq-mastery { margin-top:29px; border-top:1px solid #d7e7f6; padding-top:23px; span,small { display:block; font-size:12px; color:#42586e; } b { display:block; font-size:16px; line-height:1.7; margin:9px 0; } }
.fq-landscape { position:absolute; left:0; right:0; bottom:-20px; height:145px; opacity:.24; color:#71ade0; pointer-events:none; }
.fq-card { background:#fff; border:1px solid #d9e8f7; border-radius:25px 7px 25px 7px; padding:35px; box-shadow:0 12px 40px #3479b309; h3 { font-size:22px; line-height:1.85; margin:21px 0 28px; } textarea { width:100%; box-sizing:border-box; background:#f8fbfe; border:1px solid #d6e7f6; border-radius:12px; padding:18px; font:inherit; font-size:16px; resize:vertical; color:#244964; } }
.fq-meta { display:flex; justify-content:space-between; align-items:center; font-size:12px; color:#42586e; span:first-child { color:#1d5e99; background:#edf6ff; border-radius:6px; padding:6px 10px; } }
.fq-options { display:flex; flex-direction:column; gap:13px; button { display:flex; align-items:center; gap:14px; text-align:left; border:1px solid #dce9f5; border-radius:13px; padding:16px 19px; color:#345b7a; background:#fff; font-size:16px; line-height:1.7; cursor:pointer; transition:background .2s,border-color .2s; span { width:29px; height:29px; border-radius:8px; background:#f0f6fc; display:grid; place-items:center; flex-shrink:0; color:#1d5e99; font-size:13px; } &.selected { background:#eef7ff; border-color:#65a9e8; color:#2271b9; span { background:#338ff2; color:#fff; } } } }
.fq-submit { display:flex; align-items:center; justify-content:space-between; gap:15px; margin-top:28px; padding-top:24px; border-top:1px solid #e7eff7; >span { font-size:12px; color:#42586e; line-height:1.8; } }
.primary { display:flex; align-items:center; justify-content:center; gap:9px; flex-shrink:0; padding:13px 20px; background:#338ff2; color:#fff; border:0; border-radius:11px; font-size:14px; cursor:pointer; &:disabled { opacity:.5; cursor:default; } }
.fq-back { margin-top:20px; }
.quiz-screen-enter-active,.quiz-screen-leave-active { transition:opacity .3s,transform .4s cubic-bezier(.22,1,.36,1); }.quiz-screen-enter-from,.quiz-screen-leave-to { opacity:0; transform:translateY(24px); }
.fq-question-enter-active,.fq-question-leave-active { transition:opacity .18s,transform .22s; }.fq-question-enter-from,.fq-question-leave-to { opacity:0; transform:translateY(10px); }
@media(max-width:900px) { main { grid-template-columns:1fr; gap:15px; padding-top:0; } aside { padding:0; h2 { font-size:22px; } >p,.fq-landscape,.fq-eyebrow { display:none; } h2 br { display:none; } .fq-mastery { border:0; padding:0; margin:0; } } nav { gap:10px; >b { width:20px; } span { font-size:12px; } } }
@media(max-width:500px) { header { padding:15px; .fq-brand { font-size:14px; gap:7px; } button { font-size:11px; } } nav { padding:20px 10px; gap:7px; >b { display:none; } span { gap:5px; font-size:11px; i { width:22px; height:22px; } } } .fq-card { padding:20px; h3 { font-size:19px; } } .fq-submit { align-items:stretch; flex-direction:column; } }
@media(prefers-reduced-motion:reduce) { * { animation:none!important; transition:none!important; } }
</style>
