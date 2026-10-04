<template>
  <div class="md-viewer" v-html="rendered" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = defineProps<{ content: string }>()

marked.setOptions({ gfm: true, breaks: true })

/** 资产文件（Markdown）安全渲染：marked 解析 + DOMPurify 消毒，杜绝 XSS。 */
const rendered = computed(() => {
  const src = props.content || ''
  if (!src.trim()) return '<p class="md-empty">（暂无正文内容）</p>'
  const html = marked.parse(src, { async: false }) as string
  return DOMPurify.sanitize(html, { ADD_ATTR: ['target'] })
})
</script>

<style scoped>
.md-viewer {
  font-size: 14px;
  line-height: 1.85;
  color: $color-text;
  word-break: break-word;
  & :deep(.md-empty) { color: #9a9a9a; font-size: 13px; }
  & :deep(h1), & :deep(h2), & :deep(h3), & :deep(h4) {
    font-family: $font-serif;
    color: $color-primary;
    margin: 18px 0 8px;
    line-height: 1.4;
    &:first-child { margin-top: 0; }
  }
  & :deep(h1) { font-size: 20px; border-bottom: 1px solid rgba(24,58,99,.12); padding-bottom: 6px; }
  & :deep(h2) { font-size: 17px; }
  & :deep(h3) { font-size: 15px; }
  & :deep(h4) { font-size: 14px; }
  & :deep(p) { margin: 8px 0; }
  & :deep(ul), & :deep(ol) { margin: 8px 0; padding-left: 22px; }
  & :deep(li) { margin: 3px 0; }
  & :deep(strong) { color: #338FF2; font-weight: 700; }
  & :deep(em) { color: #256CA7; }
  & :deep(a) { color: #338FF2; text-decoration: underline; }
  & :deep(blockquote) {
    margin: 10px 0; padding: 6px 14px;
    border-left: 3px solid rgba(51,143,242,.55);
    background: rgba(51,143,242,.07);
    color: #6f6f6f; border-radius: 0 8px 8px 0;
  }
  & :deep(code) {
    background: rgba(24,58,99,.07); padding: 1px 6px;
    border-radius: 4px; font-size: 12.5px; font-family: Consolas, monospace;
    color: #338FF2;
  }
  & :deep(pre) {
    background: #338FF2; color: #e8edf4; padding: 12px 14px;
    border-radius: 10px; overflow-x: auto; margin: 10px 0;
    & code { background: transparent; color: inherit; padding: 0; font-size: 12.5px; }
  }
  & :deep(table) {
    border-collapse: collapse; margin: 10px 0; width: 100%;
    font-size: 13px;
  }
  & :deep(th), & :deep(td) {
    border: 1px solid rgba(24,58,99,.15); padding: 6px 10px; text-align: left;
  }
  & :deep(th) { background: rgba(24,58,99,.06); color: $color-primary; font-weight: 600; }
  & :deep(hr) { border: none; border-top: 1px dashed rgba(24,58,99,.18); margin: 14px 0; }
  & :deep(img) { max-width: 100%; border-radius: 8px; }
}
</style>
