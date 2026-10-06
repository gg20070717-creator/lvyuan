<template>
  <Teleport to="body">
    <Transition name="access-overlay" appear @after-enter="focusStep" @after-leave="restoreFocus">
      <div v-if="accounts.flowOpen" ref="overlay" class="access-overlay" :class="{ 'show-onboarding': accounts.flowStage === 'onboarding' }" @keydown="trapFocus">
        <Transition name="access-step" mode="out-in" appear @after-enter="focusStep">
          <section v-if="accounts.flowStage === 'access'" key="access" class="access-card" role="dialog" aria-modal="true" aria-labelledby="access-title" :aria-busy="busy">
            <aside class="access-intro">
              <div class="access-brand"><img :src="brandLogo" alt="旅鸢 logo" /><span>旅鸢</span></div>
              <span class="access-eyebrow">让专业生长，让旅途有温度</span>
              <h2>每一段学习，<br />都有自己的起点。</h2>
              <p>从你的经验与目标出发，找到合适的学习内容和训练节奏。</p>
              <ol><li><span>01</span>建立你的学情画像</li><li><span>02</span>获得专属学习路径</li><li><span>03</span>记录每一次成长</li></ol>
              <GuofengLandscape class="access-landscape" />
            </aside>
            <div class="access-form">
              <button class="access-close" :disabled="busy" aria-label="关闭注册，继续浏览" @click="accounts.closeFlow()"><SIcon name="x" :size="19" /></button>
              <template v-if="!loginMode">
                <span class="access-eyebrow">欢迎加入旅鸢</span><h1 id="access-title">注册，开启你的学习旅程</h1>
                <p class="access-description">先创建学习账户，再用几个问题认识你的起点。</p>
                <form @submit.prevent="register">
                  <label for="access-name">怎么称呼你？</label>
                  <input id="access-name" ref="nameInput" v-model="name" maxlength="20" autocomplete="nickname" placeholder="输入你的昵称" :disabled="busy" :aria-invalid="!!error" aria-describedby="access-error access-note" @input="error = ''" />
                  <p id="access-note" class="access-note">账户与学习记录保存在本设备，方便你随时继续。</p>
                  <p v-if="error" id="access-error" class="access-error" role="alert">{{ error }}</p>
                  <button class="access-primary" type="submit" :disabled="busy"><span v-if="busy" class="access-spinner"></span>{{ busy ? '正在准备你的学习空间…' : '注册并开始画像' }}<SIcon v-if="!busy" name="right" :size="17" /></button>
                </form>
                <button v-if="accounts.accounts.length" class="access-switch" :disabled="busy" @click="loginMode = true; error = ''">已有账户？登录并继续</button>
              </template>
              <template v-else>
                <span class="access-eyebrow">欢迎回来</span><h1 id="access-title">继续你的学习旅程</h1><p class="access-description">选择本设备上的学习账户，接着上次的进度。</p>
                <div class="access-accounts"><button v-for="account in accounts.accounts" :key="account.id" :disabled="busy" @click="login(account.id)"><span>{{ account.name.charAt(0) }}</span><strong>{{ account.name }}</strong><SIcon name="right" :size="16" /></button></div>
                <p v-if="error" class="access-error" role="alert">{{ error }}</p>
                <p v-if="busy" class="access-note" role="status">正在恢复你的学习进度…</p>
                <button class="access-switch" :disabled="busy" @click="loginMode = false; error = ''">创建新的学习账户</button>
              </template>
              <button class="access-later" :disabled="busy" @click="accounts.closeFlow()">先逛逛，稍后再开始</button>
            </div>
          </section>
          <OnboardingWizard v-else key="onboarding" @done="finish" @cancel="accounts.closeFlow()" />
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAccountsStore } from '@/stores/accounts'
import { useOnboardingStore } from '@/stores/onboarding'
import brandLogo from '@/assets/lvyuan-logo.jpg'
import GuofengLandscape from '@/components/GuofengLandscape.vue'
import OnboardingWizard from '@/components/OnboardingWizard.vue'
import SIcon from '@/components/SIcon.vue'

const accounts = useAccountsStore()
const onb = useOnboardingStore()
const router = useRouter()
const overlay = ref<HTMLElement | null>(null)
const nameInput = ref<HTMLInputElement | null>(null)
const name = ref('')
const loginMode = ref(false)
const busy = ref(false)
const error = ref('')
let previousFocus: HTMLElement | null = null
let previousOverflow = ''
let locked = false

watch(() => accounts.flowOpen, (open) => {
  if (open) {
    previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    previousOverflow = document.body.style.overflow; document.body.style.overflow = 'hidden'; locked = true
    if (accounts.flowStage === 'access') { loginMode.value = false; name.value = ''; error.value = '' }
  }
}, { flush: 'sync', immediate: true })
function unlock() { if (locked) { document.body.style.overflow = previousOverflow; locked = false } }
function restoreFocus() { unlock(); if (previousFocus?.isConnected) previousFocus.focus() }
onBeforeUnmount(unlock)
async function focusStep() {
  await nextTick()
  const target = accounts.flowStage === 'access' ? nameInput.value || overlay.value?.querySelector<HTMLElement>('.access-accounts button') : overlay.value?.querySelector<HTMLElement>('.ow-panel h2, .ow-return')
  target?.focus({ preventScroll: true })
}
function trapFocus(event: KeyboardEvent) {
  if (event.key === 'Escape' && accounts.flowStage === 'access' && !busy.value) { accounts.closeFlow(); return }
  if (event.key !== 'Tab') return
  const elements = [...(overlay.value?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), textarea:not(:disabled), [tabindex="0"]') || [])].filter((element) => element.getClientRects().length)
  const first = elements[0]; const last = elements[elements.length - 1]
  if (!first) { event.preventDefault(); return }
  if (event.shiftKey && (document.activeElement === first || !elements.includes(document.activeElement as HTMLElement))) { event.preventDefault(); last.focus() }
  else if (!event.shiftKey && (document.activeElement === last || !elements.includes(document.activeElement as HTMLElement))) { event.preventDefault(); first.focus() }
}
async function register() {
  if (busy.value) return
  const nickname = name.value.trim()
  if (!nickname) { error.value = '请先输入你的昵称。'; nameInput.value?.focus(); return }
  if (accounts.accounts.some((account) => account.name === nickname)) { error.value = '这个昵称已有账户，可选择“已有账户”继续学习。'; return }
  busy.value = true; error.value = ''
  try { await accounts.createAccount({ name: nickname }); await onb.load(accounts.userId); accounts.flowStage = 'onboarding' }
  catch { error.value = '账户暂时未创建，请稍后重试。' }
  finally { busy.value = false }
}
async function login(id: string) {
  if (busy.value) return
  busy.value = true; error.value = ''
  try { accounts.switchTo(id); await onb.load(accounts.userId); if (onb.done) finish(); else accounts.flowStage = 'onboarding' }
  catch { error.value = '进度暂时未恢复，请稍后重试。' }
  finally { busy.value = false }
}
function finish() { accounts.closeFlow(); void router.push(accounts.returnTo) }
</script>

<style lang="scss" scoped>
@use '@/styles/tokens' as *;
.access-overlay { position: fixed; inset: 0; z-index: 2100; display: grid; place-items: center; padding: 32px; overflow: hidden; background: rgba(27, 54, 79, .28); backdrop-filter: blur(7px); font-family: $font-sans; color: $color-text; transition: background .5s ease, backdrop-filter .5s ease; &.show-onboarding { padding: 0; background: $color-bg; backdrop-filter: blur(0); } }
.access-card { position: relative; width: min(880px, 100%); max-height: calc(100dvh - 64px); display: grid; grid-template-columns: .9fr 1.1fr; background: $color-surface; border: 1px solid $color-border; border-radius: 24px 8px 24px 8px; box-shadow: 0 24px 90px rgba(28, 66, 110, .16); overflow: auto; }
.access-intro { position: relative; padding: 38px 32px 160px; overflow: hidden; background: linear-gradient(150deg, #eef6fe, #f7fbff); border-right: 1px solid $color-border; h2 { font-family: $font-serif; font-size: 29px; line-height: 1.6; font-weight: 600; margin: 14px 0; } p { font-size: 14px; color: $color-text-secondary; line-height: 1.9; } ol { list-style: none; padding: 0; margin: 24px 0 0; display: grid; gap: 15px; font-size: 14px; } li { display: flex; align-items: center; gap: 12px; span { color: $color-primary; font-size: 12px; } } }
.access-brand { display: flex; align-items: center; gap: 10px; margin-bottom: 38px; img { width: 38px; height: 38px; object-fit: contain; } span { font: 600 25px/1.3 $font-serif; letter-spacing: 3px; } }
.access-eyebrow { display: block; font-size: 12px; color: $color-primary-dark; letter-spacing: 1.2px; }
.access-landscape { position: absolute; left: 0; bottom: 0; width: 100%; height: 160px; opacity: .8; pointer-events: none; }
.access-form { position: relative; padding: 70px 40px 36px; display: flex; flex-direction: column; justify-content: center; h1 { font-size: 24px; line-height: 1.55; margin: 12px 0; font-weight: 500; } form { margin-top: 24px; } label { font-size: 15px; display: block; margin-bottom: 10px; } input { width: 100%; padding: 14px 16px; border: 1px solid $color-border; border-radius: 9px; background: $color-bg; color: $color-text; font: inherit; font-size: 16px; transition: border-color .2s, box-shadow .2s; &:focus { outline: none; border-color: $color-primary; box-shadow: 0 0 0 3px $color-secondary-bg; } } }
.access-description { font-size: 14px; line-height: 1.85; color: $color-text-secondary; margin: 0; }
.access-close { position: absolute; top: 20px; right: 20px; padding: 8px; background: transparent; border: 0; border-radius: 50%; color: $color-text-secondary; cursor: pointer; &:hover { background: $color-secondary-bg; } }
.access-note { font-size: 12px; line-height: 1.8; color: $color-text-secondary; margin: 12px 0 24px; }
.access-error { font-size: 13px; line-height: 1.7; color: #a34845; margin: 10px 0 16px; }
.access-primary { width: 100%; min-height: 48px; display: flex; align-items: center; justify-content: center; gap: 8px; padding: 12px 18px; border: 0; border-radius: 9px; background: $color-primary; color: #fff; font: inherit; font-size: 15px; cursor: pointer; transition: background .2s, transform .2s; &:hover { background: $color-primary-dark; transform: translateY(-1px); } }
.access-switch, .access-later { background: transparent; border: 0; padding: 12px 4px; font: inherit; font-size: 13px; cursor: pointer; }
.access-switch { margin-top: 14px; color: $color-primary-dark; }
.access-later { margin-top: 14px; color: $color-text-secondary; }
.access-accounts { display: grid; gap: 10px; margin-top: 24px; max-height: 230px; overflow-y: auto; button { display: flex; align-items: center; gap: 12px; padding: 13px; border: 1px solid $color-border; border-radius: 9px; background: $color-bg; color: $color-text; cursor: pointer; text-align: left; &:hover { border-color: $color-primary; } span { width: 32px; height: 32px; display: grid; place-items: center; border-radius: 50%; color: $color-primary-dark; background: $color-secondary-bg; flex-shrink: 0; } strong { flex: 1; min-width: 0; overflow-wrap: anywhere; font-size: 15px; font-weight: 500; } svg { flex-shrink: 0; } } }
button:disabled { cursor: wait; opacity: .6; }
button:focus-visible { outline: 2px solid $color-primary; outline-offset: 3px; }
.access-spinner { width: 15px; height: 15px; border: 2px solid rgba(255,255,255,.45); border-top-color: #fff; border-radius: 50%; animation: access-spin .8s linear infinite; }
.access-overlay-enter-active, .access-overlay-leave-active { transition: opacity .32s ease, backdrop-filter .32s ease; }
.access-overlay-enter-from, .access-overlay-leave-to { opacity: 0; backdrop-filter: blur(0); }
.access-step-enter-active { transition: opacity .42s ease, transform .5s cubic-bezier(.2,.7,.2,1); }
.access-step-leave-active { transition: opacity .2s ease, transform .24s ease; }
.access-step-enter-from { opacity: 0; transform: translateY(20px) scale(.985); }
.access-step-leave-to { opacity: 0; transform: translateY(-12px) scale(.985); }
@keyframes access-spin { to { transform: rotate(360deg); } }
@media (max-width: 760px) { .access-overlay { padding: 20px; } .access-card { grid-template-columns: 1fr; max-height: calc(100dvh - 40px); } .access-intro { display: none; } .access-form { padding: 62px 28px 28px; } }
@media (max-width: 430px) { .access-overlay { padding: 14px; } .access-card { max-height: calc(100dvh - 28px); } .access-form { padding: 56px 22px 24px; h1 { font-size: 22px; } } }
@media (prefers-reduced-motion: reduce) { .access-overlay, .access-overlay-enter-active, .access-overlay-leave-active, .access-step-enter-active, .access-step-leave-active { transition: none; } .access-step-enter-from, .access-step-leave-to { transform: none; } .access-primary:hover { transform: none; } .access-spinner { animation: none; } }
</style>
