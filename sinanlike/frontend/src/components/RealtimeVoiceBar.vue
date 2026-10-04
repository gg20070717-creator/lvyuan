<template>
  <div class="rvc">
    <div class="rvc-bar">
      <span class="rvc-tag">实时语音 · {{ langLabel }}</span>
      <span v-if="voice" class="rvc-voice">音色 {{ voice }}</span>
      <span class="rvc-status" :class="{ on: connected }">{{ statusText }}</span>
      <span class="rvc-spacer"></span>
      <button v-if="!connected" class="rvc-btn main" :disabled="connecting" @click="connect">
        <SIcon name="mic" :size="13" :color="connecting ? '#bbb' : '#fff'" /> {{ connecting ? '连接中…' : '接通游客语音' }}
      </button>
      <button v-else class="rvc-btn stop" @click="hangup"><SIcon name="x" :size="12" /> 挂断</button>
    </div>
    <div class="rvc-hint">接通后直接对麦克风说{{ langLabel }}，游客会语音回复；也可在下方输入文字发送。</div>
    <div class="rvc-row">
      <input v-model="text" class="rvc-input" type="text"
             :placeholder="'以导游身份输入一句 ' + langLabel + ' 台词…'" @keydown.enter.prevent="sendText" />
      <button class="rvc-send" :disabled="!text.trim()" @click="sendText"><SIcon name="msg" :size="13" color="#fff" /> 发送</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import SIcon from '@/components/SIcon.vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import client from '@/api/client'

const props = defineProps<{ sessionId: string; userId: string; language: string; voice: string }>()
const emit = defineEmits<{
  (e: 'guide-message', text: string): void
  (e: 'customer-message', text: string): void
}>()

const LANGS: Record<string, string> = {
  en: 'English', ja: '日本語', zh: '中文', fr: 'Français', de: 'Deutsch',
  ko: '한국어', es: 'Español', ru: 'Русский', ar: 'العربية',
  it: 'Italiano', pt: 'Português', vi: 'Tiếng Việt', id: 'Bahasa', th: 'ไทย', tr: 'Türkçe',
}
const langLabel = computed(() => LANGS[props.language] || props.language || 'English')

const statusText = ref('未连接')
const connecting = ref(false)
const connected = ref(false)
const text = ref('')

let ws: WebSocket | null = null
let audioCtx: AudioContext | null = null
let micStream: MediaStream | null = null
let scriptNode: ScriptProcessorNode | null = null
let srcNode: MediaStreamAudioSourceNode | null = null
let ds: Downsampler | null = null
let schedTime = 0
let touristAcc = ''
let closing = false

class Downsampler {
  step: number
  data: number[] = []
  cursor = 0
  constructor(inRate: number) { this.step = inRate / 16000 }
  push(ch: Float32Array) {
    for (let i = 0; i < ch.length; i++) this.data.push(ch[i])
    this.drain()
  }
  drain() {
    const frame = 1600
    while (this.cursor + this.step * frame <= this.data.length) {
      const out = new Int16Array(frame)
      for (let o = 0; o < frame; o++) {
        const sp = this.cursor + o * this.step
        const i0 = Math.floor(sp)
        const i1 = Math.min(i0 + 1, this.data.length - 1)
        const f = sp - i0
        const v = this.data[i0] + (this.data[i1] - this.data[i0]) * f
        out[o] = (Math.max(-1, Math.min(1, v)) * 32767) | 0
      }
      this.cursor += this.step * frame
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'audio', audio: b64Int16(out) }))
      }
    }
    if (this.cursor > this.step * 16000 * 2) {
      this.data = this.data.slice(this.cursor)
      this.cursor = 0
    }
  }
}

function b64Int16(arr: Int16Array): string {
  const bytes = new Uint8Array(arr.buffer)
  let s = ''
  const CH = 0x8000
  for (let i = 0; i < bytes.length; i += CH) s += String.fromCharCode.apply(null, bytes.subarray(i, i + CH) as unknown as number[])
  return btoa(s)
}

function wsUrl(): string {
  const base = (client.defaults.baseURL as string) || '/api'
  let root: string
  if (/^https?:/i.test(base)) {
    const u = new URL(base)
    root = `${u.protocol === 'https:' ? 'wss' : 'ws'}://${u.host}`
  } else {
    root = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}${base}`
  }
  if (!root.endsWith('/')) root += '/'
  return `${root}voice/realtime/${props.sessionId}?user_id=${encodeURIComponent(props.userId)}`
}

async function startMic() {
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)()
    await audioCtx.resume()
  }
  micStream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  })
  srcNode = audioCtx.createMediaStreamSource(micStream)
  scriptNode = audioCtx.createScriptProcessor(4096, 1, 1)
  ds = new Downsampler(audioCtx.sampleRate)
  srcNode.connect(scriptNode)
  scriptNode.connect(audioCtx.destination)
  scriptNode.onaudioprocess = (e) => { if (ds) ds.push(e.inputBuffer.getChannelData(0)) }
}

function stopMic() {
  try { if (scriptNode) scriptNode.disconnect() } catch (e) { /* noop */ }
  try { if (srcNode) srcNode.disconnect() } catch (e) { /* noop */ }
  try { if (micStream) micStream.getTracks().forEach((t) => t.stop()) } catch (e) { /* noop */ }
  scriptNode = null
  srcNode = null
  micStream = null
  ds = null
}

function playPcm24k(b64: string) {
  if (!audioCtx) return
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
  const t = Math.max(audioCtx.currentTime + 0.02, schedTime)
  src.start(t)
  schedTime = t + buf.duration
}

function handleEvent(m: any) {
  const t = m.type || ''
  if (t === 'session.meta') {
    statusText.value = `已连接 · ${m.language || ''}`
  } else if (t === 'ready') {
    connected.value = true
    connecting.value = false
    statusText.value = '对话中 · 直接对麦克风说话'
  } else if (t === 'response.audio.delta') {
    if (m.delta) playPcm24k(m.delta)
  } else if (t === 'response.audio_transcript.delta') {
    touristAcc += m.delta || ''
  } else if (t === 'response.audio_transcript.done') {
    const full = (m.transcript || touristAcc).trim()
    touristAcc = ''
    if (full) emit('customer-message', full)
  } else if (t === 'conversation.item.input_audio_transcription.completed') {
    const txt = (m.transcript || '').trim()
    if (txt) emit('guide-message', txt)
  } else if (t === 'error') {
    statusText.value = '出错'
    ElMessage.error('实时语音错误：' + JSON.stringify(m.error || m).slice(0, 200))
  } else if (t === 'closed') {
    cleanup()
  }
}

function cleanup() {
  connected.value = false
  connecting.value = false
  if (!closing) statusText.value = '已断开'
  stopMic()
  if (ws) { try { ws.onmessage = null; ws.close() } catch (e) { /* noop */ } }
  ws = null
}

async function connect() {
  if (connecting.value || connected.value) return
  // 回声提醒：实时语音同时开麦克风与扬声器，不戴耳机容易互相打断
  try {
    await ElMessageBox.confirm(
      '实时语音会同时开启麦克风与扬声器，未佩戴耳机时游客声音会回传造成回声、互相打断。\n\n请佩戴耳机后再开启实时语音。',
      '请先佩戴耳机',
      { confirmButtonText: '确认我已佩戴', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return  // 用户取消：不开启语音
  }
  connecting.value = true
  statusText.value = '连接中…'
  try {
    await startMic()
  } catch (e: any) {
    ElMessage.warning('麦克风不可用（仍可打字发送）：' + (e && e.message ? e.message : e))
  }
  const connTimer = window.setTimeout(() => {
    if (!connected.value) {
      connecting.value = false
      statusText.value = '连接超时'
      ElMessage.error('语音连接超时：请确认后端已启动（http://127.0.0.1:18000）')
      cleanup()
    }
  }, 12000)
  try {
    ws = new WebSocket(wsUrl())
    ws.onopen = () => { /* wait ready */ }
    ws.onmessage = (ev) => { try { handleEvent(JSON.parse(ev.data)) } catch (e) { /* noop */ } }
    ws.onclose = () => { window.clearTimeout(connTimer); cleanup() }
    ws.onerror = () => { if (!closing) statusText.value = '连接出错' }
  } catch (e: any) {
    window.clearTimeout(connTimer)
    connecting.value = false
    statusText.value = '连接失败'
    ElMessage.error('连接失败：' + (e && e.message ? e.message : e))
  }
}

function hangup() {
  closing = true
  cleanup()
  closing = false
  statusText.value = '已挂断'
}

function sendText() {
  const v = text.value.trim()
  if (!v) return
  text.value = ''
  emit('guide-message', v)
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'text', text: v }))
  } else {
    ElMessage.warning('尚未接通语音，仅记录了你的台词')
  }
}

onUnmounted(() => {
  closing = true
  cleanup()
  if (audioCtx) { try { audioCtx.close() } catch (e) { /* noop */ } }
})
</script>

<style lang="scss" scoped>
.rvc { display: flex; flex-direction: column; gap: 8px; }
.rvc-bar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.rvc-tag { font-weight: 600; color: #256CA7; font-size: 12.5px;
  background: rgba(51,143,242,.14); border: 1px solid rgba(51,143,242,.35);
  padding: 4px 10px; border-radius: 20px; }
.rvc-voice { font-size: 12px; color: #666; }
.rvc-status { font-size: 12px; color: #999; }
.rvc-status.on { color: #3fa45b; }
.rvc-spacer { flex: 1; }
.rvc-btn { border: 0; border-radius: 9px; padding: 6px 13px; font-size: 12.5px; cursor: pointer;
  display: inline-flex; align-items: center; gap: 5px; }
.rvc-btn.main { background: linear-gradient(135deg, #338FF2, #b28c46); color: #fff; }
.rvc-btn.stop { background: #EDF5FD; color: #b3543f; }
.rvc-btn:disabled { opacity: .55; cursor: not-allowed; }
.rvc-hint { font-size: 11.5px; color: #a49a86; }
.rvc-row { display: flex; gap: 8px; }
.rvc-input { flex: 1; border: 1px solid #C7DCF1; border-radius: 10px; padding: 9px 12px;
  font-size: 13px; outline: none; background: #fff; }
.rvc-send { border: 0; border-radius: 10px; padding: 0 16px; font-size: 13px; cursor: pointer;
  background: linear-gradient(135deg, #338FF2, #b28c46); color: #fff; display: inline-flex; align-items: center; gap: 5px; }
.rvc-send:disabled { opacity: .5; cursor: not-allowed; }
</style>