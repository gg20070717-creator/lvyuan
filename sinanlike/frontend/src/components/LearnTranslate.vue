<template>
  <div class="lt">
    <button v-if="!open" class="lt-trigger" title="翻译并朗读" @click="open = true">
      <SIcon name="msg" :size="10" /> 译
    </button>
    <div v-else class="lt-panel">
      <div class="lt-row">
        <select v-model="lang" class="lt-lang">
          <option v-for="o in LANG_OPTS" :key="o.k" :value="o.k">{{ o.label }}</option>
        </select>
        <template v-if="!renderMarkdown">
          <button class="lt-btn primary" :disabled="!!busy" @click="doTranslate(true)">
            {{ busy === 'both' ? '翻译并朗读中…' : '翻译并朗读' }}
          </button>
          <button class="lt-btn" :disabled="!!busy" @click="doTranslate(false)">仅翻译</button>
        </template>
        <button v-else class="lt-btn primary" :disabled="!!busy" @click="doTranslate(false)">
          {{ busy === 'text' ? '翻译中…' : '翻译（保留格式）' }}
        </button>
        <button class="lt-x" @click="reset"><SIcon name="x" :size="11" /></button>
      </div>
      <div v-if="error" class="lt-err">{{ error }}</div>
      <div v-if="truncated" class="lt-warn">内容较长，已译前 {{ truncated }} 字</div>
      <div v-if="translated" class="lt-out">
        <MarkdownViewer v-if="renderMarkdown" class="lt-md" :content="translated" />
        <div v-else class="lt-txt">{{ translated }}</div>
        <div v-if="hasAudio && !renderMarkdown" class="lt-audio">
          <button class="lt-btn small" @click="togglePlay">{{ playing ? '⏹ 停止' : '🔊 播放' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import SIcon from '@/components/SIcon.vue'
import MarkdownViewer from '@/components/MarkdownViewer.vue'
import { ElMessage } from 'element-plus'
import { translateLearnText, speakLearnText } from '@/api/voice'

const props = defineProps<{ text: string; mode?: 'plain' | 'markdown'; renderMarkdown?: boolean }>()
const renderMarkdown = computed(() => !!props.renderMarkdown || props.mode === 'markdown')

const LANG_OPTS = [
  { k: 'en', label: 'English 英语' },
  { k: 'ja', label: '日本語 日语' },
  { k: 'fr', label: 'Français 法语' },
  { k: 'de', label: 'Deutsch 德语' },
  { k: 'ko', label: '한국어 韩语' },
  { k: 'es', label: 'Español 西语' },
  { k: 'ru', label: 'Русский 俄语' },
  { k: 'ar', label: 'العربية 阿语' },
  { k: 'zh', label: '中文' },
]
const open = ref(false)
const lang = ref('en')
const busy = ref<'' | 'both' | 'text'>('')
const translated = ref('')
const hasAudio = ref(false)
const playing = ref(false)
const error = ref('')
const truncated = ref(0)
let audioCtx: AudioContext | null = null
let audioB64 = ''
let activeSrcs: AudioBufferSourceNode[] = []

async function ensureCtx() {
  if (!audioCtx) audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)()
  if (audioCtx.state === 'suspended') await audioCtx.resume()
  return audioCtx
}

/** 真正停止所有正在播放的音频（不是只改文案） */
function stopAll() {
  for (const s of activeSrcs) {
    try { s.onended = null; s.stop() } catch (e) { /* already stopped */ }
  }
  activeSrcs = []
  playing.value = false
}

/** 播放一段 24k PCM；播放前先停掉旧的，避免叠加/重复 */
function playB64(b64: string) {
  if (!audioCtx) return
  stopAll()
  const bin = atob(b64)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  const n = Math.floor(bytes.length / 2)
  if (!n) return
  const f32 = new Float32Array(n)
  for (let i = 0; i < n; i++) {
    let s = bytes[2 * i] | (bytes[2 * i + 1] << 8)
    if (s >= 32768) s -= 65536
    f32[i] = s / 32768
  }
  const buf = audioCtx.createBuffer(1, n, 24000)
  buf.copyToChannel(f32, 0)
  const src = audioCtx.createBufferSource()
  src.buffer = buf
  src.connect(audioCtx.destination)
  const t = Math.max(audioCtx.currentTime + 0.02, audioCtx.currentTime)
  src.start(t)
  activeSrcs.push(src)
  src.onended = () => {
    activeSrcs = activeSrcs.filter((x) => x !== src)
    if (!activeSrcs.length) playing.value = false
  }
  playing.value = true
}

async function doTranslate(withSpeak: boolean) {
  if (busy.value) return
  busy.value = withSpeak ? 'both' : 'text'
  error.value = ''
  truncated.value = 0
  let source = props.text
  try {
    if (source.length > 12000) {
      source = source.slice(0, 12000)
      truncated.value = 12000
    }
    const mode: 'plain' | 'markdown' = renderMarkdown.value ? 'markdown' : (props.mode || 'plain')
    const tr = await translateLearnText(source, lang.value, mode)
    translated.value = tr.translated || '（译文为空）'
    hasAudio.value = false
    if (withSpeak && !renderMarkdown.value) {
      if (source.length > 4000) {
        ElMessage.warning('内容较长，已翻译；朗读请分段使用')
      } else {
        const sp = await speakLearnText(tr.translated || source, lang.value)
        audioB64 = sp.audio_b64
        hasAudio.value = true
        await ensureCtx()
        playB64(audioB64)
      }
    }
  } catch (e: any) {
    error.value = '翻译失败：' + (e?.message || String(e))
  } finally {
    busy.value = ''
  }
}

async function togglePlay() {
  if (playing.value) { stopAll(); return }
  if (!hasAudio.value) return
  try { await ensureCtx(); playB64(audioB64) } catch (e: any) { ElMessage.error('播放失败：' + e.message) }
}

function reset() {
  stopAll()
  open.value = false
  translated.value = ''
  hasAudio.value = false
  audioB64 = ''
  error.value = ''
  truncated.value = 0
}

onUnmounted(() => {
  stopAll()
  if (audioCtx) { try { audioCtx.close() } catch (e) { /* noop */ } }
})
</script>

<style lang="scss" scoped>
.lt { margin-top: 8px; }
.lt-trigger { border: 1px solid rgba(51,143,242,.5); background: rgba(51,143,242,.1); color: #256CA7;
  border-radius: 14px; font-size: 11px; padding: 3px 10px; cursor: pointer; display: inline-flex; align-items: center; gap: 4px; }
.lt-trigger:hover { background: rgba(51,143,242,.2); }
.lt-panel { border: 1px dashed #BFD8F0; background: #F8FBFF; border-radius: 10px; padding: 8px 10px; margin-top: 4px; }
.lt-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.lt-lang { padding: 4px 8px; border: 1px solid #C7DCF1; border-radius: 8px; font-size: 12px; background: #fff; }
.lt-btn { border: 1px solid #C7DCF1; background: #fff; color: #4a463c; border-radius: 8px; font-size: 12px; padding: 5px 11px; cursor: pointer; }
.lt-btn.primary { background: linear-gradient(135deg, #338FF2, #b28c46); color: #fff; border: 0; }
.lt-btn.small { font-size: 11.5px; }
.lt-btn:disabled { opacity: .55; cursor: not-allowed; }
.lt-x { margin-left: auto; border: 0; background: none; color: #aaa; cursor: pointer; }
.lt-err { color: #c0504d; font-size: 12px; margin-top: 6px; }
.lt-warn { color: #b28c46; font-size: 12px; margin-top: 6px; }
.lt-out { margin-top: 8px; border-top: 1px dashed #DCEAF7; padding-top: 8px; }
.lt-txt { font-size: 13px; color: #333; line-height: 1.7; white-space: pre-wrap; word-break: break-word; }
.lt-md { font-size: 13px; }
.lt-audio { margin-top: 6px; }
</style>