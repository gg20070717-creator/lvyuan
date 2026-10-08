<template>
  <section class="resource-overview">
    <div class="ro-top"><span><SIcon name="map" :size="16" />图解导览</span><small>{{ outline.length }} 个内容模块   按原文顺序整理</small></div>
    <div v-if="outline.length" class="ro-map" :class="{ timeline:type === 'plan' || type === 'practice_guide' }">
      <button v-for="(section,index) in outline" :key="index" :class="{ active:selected === index }" @click="selected = index"><span class="ro-number">{{ String(index+1).padStart(2,'0') }}</span><b>{{ display(section.title) }}</b><p>{{ display(section.points[0] || excerpt(section.content)) }}</p><span class="ro-connect" v-if="index < outline.length - 1"></span></button>
    </div>
    <div v-if="outline[selected]" class="ro-focus"><h4>{{ display(outline[selected].title) }}</h4><ul v-if="outline[selected].points.length"><li v-for="(point,index) in outline[selected].points.slice(0,6)" :key="index">{{ display(point) }}</li></ul><p v-else>{{ display(excerpt(outline[selected].content)) }}</p></div>
    <div class="ro-original"><button :aria-expanded="originalOpen" @click="originalOpen = !originalOpen"><SIcon :name="originalOpen ? 'up' : 'book'" :size="14" />{{ originalOpen ? '收起完整原文' : '阅读完整原文' }}</button><MarkdownViewer v-if="originalOpen" :content="content" /></div>
  </section>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { resourceOutline, resourceExcerpt } from '@/utils/resourceOutline'
import { cleanDisplayText as display } from '@/utils/displayText'
import SIcon from './SIcon.vue'
import MarkdownViewer from './MarkdownViewer.vue'
const props = defineProps<{ content:string; type:string }>()
const selected = ref(0), originalOpen = ref(false)
const outline = computed(() => resourceOutline(props.content))
const excerpt = resourceExcerpt
watch(() => props.content, () => { selected.value=0; originalOpen.value=false })
</script>
<style scoped lang="scss">
.resource-overview { color:#315878; padding:8px 0; }
.ro-top { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:9px; margin:10px 0 20px; span { display:flex; align-items:center; gap:8px; font-size:15px; font-weight:600; color:#1d5e99; } small { font-size:11px; color:#42586e; } }
.ro-map { display:grid; grid-template-columns:1fr 1fr; gap:12px; button { position:relative; text-align:left; padding:16px; background:#f8fbfe; border:1px solid #e0ebf6; border-radius:15px 5px 15px 5px; font:inherit; color:#335e82; cursor:pointer; transition:border-color .2s,background .2s; b { display:block; font-size:14px; line-height:1.6; margin:10px 0 7px; } p { margin:0; font-size:12px; color:#42586e; line-height:1.7; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; } &.active { background:#edf6ff; border-color:#88bae9; } } &.timeline { grid-template-columns:1fr; button { padding-left:60px; min-height:78px; .ro-number { position:absolute; top:21px; left:17px; } b { margin-top:0; } .ro-connect { position:absolute; width:1px; height:13px; background:#a9cce8; left:30px; bottom:-13px; } } } }
.ro-number { display:grid; place-items:center; width:26px; height:26px; background:#e6f2fd; border-radius:8px; color:#1d5e99; font-size:11px; font-weight:600; }
.ro-focus { margin:22px 0; padding:18px; border:1px solid #dce9f6; border-radius:12px; h4 { margin:0 0 14px; color:#1d5e99; font-size:15px; } ul { list-style:none; padding:0; margin:0; } li { position:relative; padding:9px 0 9px 18px; border-bottom:1px solid #edf3f9; font-size:13px; line-height:1.8; &::before { content:''; position:absolute; top:18px; left:2px; width:5px; height:5px; border-radius:50%; background:#68a9e2; } } p { color:#42586e; font-size:13px; line-height:1.9; } }
.ro-original >button { display:flex; align-items:center; gap:7px; background:#f0f7fe; color:#1d5e99; border:1px solid #dceaf7; border-radius:9px; padding:10px 14px; cursor:pointer; font-size:12px; margin-bottom:15px; }
@media(max-width:500px) { .ro-map { grid-template-columns:1fr; } }
@media(prefers-reduced-motion:reduce) { button { transition:none!important; } }
</style>
