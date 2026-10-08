<template>
  <div class="tb-page">
    <header class="ph">
      <div class="ph-left"><h2 class="ph-title">工具箱</h2></div>
      <div class="ph-right"><span class="tb-count">{{ TOOLS.length }} 个工具</span></div>
    </header>

    <div class="tb-body">
      <div class="tb-inner">
        <!-- ══ 工具列表 ══ -->
        <template v-if="!activeTool">
          <div class="tb-feature grad">
            <div class="ic"><SIcon name="globe" :size="22" color="#338FF2" /></div>
            <div class="ft"><div class="h">AI 智能导游助手</div><div class="s">实时解答游客问题   多语言支持</div></div>
            <SIcon name="right" :size="16" color="rgba(51,143,242,0.7)" />
          </div>
          <div class="tb-grid">
            <button v-for="t in TOOLS" :key="t.id" class="tool-card" @click="openTool(t.id)">
              <span class="tb-demo-badge tb-card-badge" :class="{ live: cardBadge(t.id).live }">{{ cardBadge(t.id).txt }}</span>
              <div class="ic" :style="{ background: t.bg }"><SIcon :name="t.i" :size="19" :color="t.c" /></div>
              <div><div class="t">{{ t.l }}</div><div class="d">{{ t.d }}</div></div>
            </button>
          </div>
        </template>

        <!-- ══ 工具详情面板 ══ -->
        <template v-if="activeTool && activeToolObj">
          <button class="tb-back" @click="closeTool"><SIcon name="back" :size="13" /> 返回工具箱</button>
          <div class="tool-head">
            <div class="ic" :style="{ background: activeToolObj.bg }"><SIcon :name="activeToolObj.i" :size="24" :color="activeToolObj.c" /></div>
            <div class="th"><div class="t">{{ activeToolObj.l }}</div><div class="d">{{ activeToolObj.d }}</div></div>
            <span class="ai-badge" :style="{ background: activeToolObj.bg, border: `1px solid ${activeToolObj.c}33` }">AI 驱动</span>
            <span v-if="toolDataStatus" class="tb-demo-badge" :class="{ live: toolDataStatus!.live }">{{ toolDataStatus!.txt }}</span>
          </div>

          <!-- 1 AI翻译 -->
          <template v-if="activeTool === 'translate'">
            <div class="tb-block"><div class="lb"><SIcon name="lang" :size="12" color="#3B82F6" /> 语言方向</div>
              <div class="tb-row">
                <select class="tb-select" v-model="tr.src"><option>中文</option><option v-for="l in trLangs" :key="l">{{ l }}</option></select>
                <button class="tb-swap" @click="tbSwapLang" title="交换"><SIcon name="right" :size="15" /></button>
                <select class="tb-select" v-model="tr.tgt"><option v-for="l in trLangs" :key="l">{{ l }}</option></select>
              </div></div>
            <div class="tb-block"><div class="lb"><SIcon name="msg" :size="12" color="#3B82F6" /> 常用接待短语   点选即译</div>
              <div class="tb-row">
                <span v-for="(p, i) in ((PHRASES as any)[tr.tgt] || (PHRASES as any)['英语'])" :key="p[0]" class="tb-tag" :class="{ sel: tr.pick === i }" @click="tbPickPhrase(i)">{{ p[0] }}</span>
              </div></div>
            <div v-if="tr.out" class="tb-block"><div class="lb"><SIcon name="check" :size="12" color="#3B82F6" /> 译文</div>
              <div class="tb-result">{{ tr.src }}：{{ tr.inTxt }}<br>{{ tr.tgt }}：{{ tr.out }}</div>
              <div class="tb-row" style="margin-top:10px"><button class="tb-btn" @click="tbCopy(tr.out)"><SIcon name="clip" :size="12" color="#fff" /> 复制译文</button></div></div>
          </template>

          <!-- 2 礼仪检查 -->
          <template v-if="activeTool === 'etiquette'">
            <div class="tb-block"><div class="lb"><SIcon name="shield" :size="12" color="#8B5CF6" /> 接待礼仪自查清单   勾选本次做到的项</div>
              <div class="tb-list">
                <div v-for="(it, i) in ETQ_ITEMS" :key="it[0]" class="tb-check" :class="{ on: etq.checked[i] }" @click="tbEtqToggle(i)">
                  <span class="cb"><SIcon v-if="etq.checked[i]" name="check" :size="11" :stroke-width="3.5" color="#fff" /></span>
                  <span class="txt">{{ it[0] }}<span class="sub">   {{ it[1] }}</span></span>
                </div>
              </div>
              <div class="tb-row" style="margin-top:14px">
                <button class="tb-btn" style="background:linear-gradient(135deg,#8B5CF6,#7C3AED)" @click="tbEtqScore"><SIcon name="star" :size="12" color="#fff" /> 生成礼仪评估</button>
              </div></div>
            <div v-if="etq.out" class="tb-block"><div class="lb"><SIcon name="star" :size="12" color="#8B5CF6" /> 评估结果</div>
              <div class="tb-result"><span class="big">{{ etq.out.score }}</span> 分   {{ etq.out.grade }}<br>{{ etq.out.note }}</div></div>
          </template>

          <!-- 3 行程规划 -->
          <template v-if="activeTool === 'itinerary'">
            <div class="tb-block"><div class="lb"><SIcon name="map" :size="12" color="#10B981" /> 行程参数</div>
              <div class="tb-row">
                <select class="tb-select" v-model.number="itn.days"><option v-for="d in [1,2,3,4,5]" :key="d" :value="d">{{ d }} 天</option></select>
              </div>
              <div class="tb-row" style="margin-top:10px">
                <span v-for="t in ITN_THEMES" :key="t" class="tb-tag" :class="{ sel: itn.theme === t }" @click="itn.theme = t">{{ t }}</span>
              </div>
              <div class="tb-row" style="margin-top:14px">
                <button class="tb-btn" style="background:linear-gradient(135deg,#10B981,#059669)" @click="tbGenItinerary"><SIcon name="sparkle" :size="12" color="#fff" /> 生成行程</button>
              </div></div>
            <div v-if="itn.out" class="tb-block"><div class="lb"><SIcon name="check" :size="12" color="#10B981" /> 智能行程   {{ itn.days }}天   {{ itn.theme }}</div>
              <div class="tb-result">{{ itn.out }}</div>
              <div class="tb-row" style="margin-top:10px"><button class="tb-btn" @click="tbCopy(itn.out)"><SIcon name="clip" :size="12" color="#fff" /> 复制行程</button></div></div>
          </template>

          <!-- 4 AI导游词 -->
          <template v-if="activeTool === 'guide'">
            <div class="tb-block"><div class="lb"><SIcon name="pin" :size="12" color="#338FF2" /> 景点名称</div>
              <input type="text" v-model="gd.spot" placeholder="如：云冈石窟" />
              <div class="lb" style="margin-top:12px"><SIcon name="notebook" :size="12" color="#338FF2" /> 导游词类型</div>
              <div class="tb-row">
                <span v-for="t in Object.keys(GUIDE_TPL)" :key="t" class="tb-tag" :class="{ sel: gd.type === t }" @click="gd.type = t">{{ t }}</span>
              </div>
              <div class="tb-row" style="margin-top:14px">
                <button class="tb-btn gold" :disabled="!gd.spot.trim()" @click="tbGenGuide"><SIcon name="sparkle" :size="12" color="#fff" /> 生成导游词</button>
              </div></div>
            <div v-if="gd.out" class="tb-block"><div class="lb"><SIcon name="check" :size="12" color="#338FF2" /> 生成结果</div>
              <div class="tb-result">{{ gd.out }}</div>
              <div class="tb-row" style="margin-top:10px"><button class="tb-btn gold" @click="tbCopy(gd.out)"><SIcon name="clip" :size="12" color="#fff" /> 复制导游词</button></div></div>
          </template>

          <!-- 5 文化禁忌查询 -->
          <template v-if="activeTool === 'taboo'">
            <div class="tb-block"><div class="lb"><SIcon name="globe" :size="12" color="#F59E0B" /> 选择客源国、地区</div>
              <div class="tb-row">
                <span v-for="c in Object.keys(TABOO_DB)" :key="c" class="tb-tag" :class="{ sel: taboo.country === c }" @click="taboo.country = c">{{ c }}</span>
              </div></div>
            <div class="tb-block"><div class="lb"><SIcon name="warn" :size="12" color="#F59E0B" /> {{ taboo.country }}   接待禁忌要点</div>
              <div class="tb-list">
                <div v-for="it in (TABOO_DB as any)[taboo.country]" :key="it.t" class="tb-item">
                  <div class="ic2" style="background:rgba(245,158,11,.1)"><SIcon name="warn" :size="16" color="#F59E0B" /></div>
                  <div class="it-body"><div class="t">{{ it.t }}</div><div class="d">{{ it.d }}</div></div>
                </div>
              </div>
              <div class="tb-warn" style="margin-top:12px"><SIcon name="warn" :size="12" color="#DC2626" /> 服务外宾前务必确认其具体文化背景，以上为通用提示，个案请进一步核实。</div></div>
          </template>

          <!-- 6 汇率换算 -->
          <template v-if="activeTool === 'currency'">
            <div class="tb-block"><div class="lb"><SIcon name="calc" :size="12" color="#EF4444" /> 金额与币种</div>
              <div class="tb-row">
                <input type="text" style="max-width:130px" :value="curr.amt" @input="curr.amt = parseFloat(($event.target as HTMLInputElement).value) || 0" placeholder="金额" />
                <select class="tb-select" v-model="curr.from"><option v-for="c in CURR" :key="c[0]" :value="c[0]">{{ c[1] }}</option></select>
                <button class="tb-swap" @click="tbSwapCurr" title="交换"><SIcon name="right" :size="15" /></button>
                <select class="tb-select" v-model="curr.to"><option v-for="c in CURR" :key="c[0]" :value="c[0]">{{ c[1] }}</option></select>
              </div>
              <div class="tb-result" style="margin-top:14px"><span class="big">{{ currResult }}</span> {{ (CURR.find(c => c[0] === curr.to) || [])[1] }}<br>
                <span class="rate-line">1 {{ (CURR.find(c => c[0] === curr.from) || [])[1] }} ≈ {{ currRateLine }} {{ (CURR.find(c => c[0] === curr.to) || [])[1] }}   {{ currSrc === 'live' ? '实时汇率（open.er-api.com）' : '离线示例数据   实际以银行牌价为准' }}</span></div></div>
          </template>

          <!-- 7 时差查询 -->
          <template v-if="activeTool === 'timediff'">
            <div class="tb-block"><div class="lb"><SIcon name="clock" :size="12" color="#338FF2" /> 城市选择   本地时间实时计算（含夏令时）</div>
              <div class="tb-row">
                <select class="tb-select" v-model="tz.from"><option v-for="c in TZ_CITIES" :key="c.city" :value="c.city">{{ c.city }}</option></select>
                <button class="tb-swap" @click="tbSwapTz" title="交换"><SIcon name="right" :size="15" /></button>
                <select class="tb-select" v-model="tz.to"><option v-for="c in TZ_CITIES" :key="c.city" :value="c.city">{{ c.city }}</option></select>
              </div>
              <div class="tb-grid2" style="margin-top:14px">
                <div class="tb-result">{{ tz.from }}（{{ tzFromInfo.label }}）<br><span class="big">{{ tzFromInfo.time }}</span><br>
                  <span class="tz-note">{{ tzFromInfo.utcLabel }}   与北京{{ tzFromInfo.diffBjk === 0 ? '无时差' : tzFromInfo.diffBjk > 0 ? '早 ' + tzFromInfo.diffBjk + ' 小时' : '晚 ' + (-tzFromInfo.diffBjk) + ' 小时' }}</span></div>
                <div class="tb-result">{{ tz.to }}（{{ tzToInfo.label }}）<br><span class="big">{{ tzToInfo.time }}</span><br>
                  <span class="tz-note">{{ tzToInfo.utcLabel }}   与北京{{ tzToInfo.diffBjk === 0 ? '无时差' : tzToInfo.diffBjk > 0 ? '早 ' + tzToInfo.diffBjk + ' 小时' : '晚 ' + (-tzToInfo.diffBjk) + ' 小时' }}</span></div>
              </div>
              <div class="tb-result" style="margin-top:12px;font-size:12px;color:#42586e">
                {{ tz.to }} 比 {{ tz.from }} {{ tzDiff === 0 ? '时间相同' : tzDiff > 0 ? '早 ' + tzDiff + ' 小时' : '晚 ' + (-tzDiff) + ' 小时' }}   安排叫早与集合时间时请注意换算</div></div>
          </template>

          <!-- 8 天气查询 -->
          <template v-if="activeTool === 'weather'">
            <div class="tb-block"><div class="lb"><SIcon name="cloud" :size="12" color="#0EA5E9" /> 选择目的地   实时天气（Open-Meteo）</div>
              <div class="tb-row">
                <span v-for="c in Object.keys(WTHR_CITIES)" :key="c" class="tb-tag" :class="{ sel: wthr.city === c }" @click="wthr.city = c">{{ c }}</span>
              </div></div>
            <div class="tb-block"><div class="lb"><SIcon name="pin" :size="12" color="#0EA5E9" /> {{ wthr.city }}   今日天气<template v-if="wthr.loading">（加载中…）</template></div>
              <div class="tb-result"><div class="wx-row"><SIcon :name="wthrData.ic" :size="40" color="#0EA5E9" />
                <div><span class="big">{{ wthrData.temp }}</span><br>{{ wthrData.t }}   {{ wthrData.wind }}   湿度 {{ wthrData.hum }}</div></div></div>
              <div class="tb-result" style="margin-top:12px;font-size:12.5px"><SIcon name="warn" :size="12" color="#F59E0B" /> <b>带团提示：</b>{{ wthrData.adv }}<br>
                <span class="rate-line">{{ wthr.src === 'live' ? '实时天气   数据来源 Open-Meteo' : '离线示例数据   仅供参考' }}</span></div></div>
          </template>

          <!-- 9 紧急电话 -->
          <template v-if="activeTool === 'emergency'">
            <div class="tb-block"><div class="lb"><SIcon name="phone" :size="12" color="#DC2626" /> 搜索应急号码</div>
              <input type="text" v-model="emgQ" placeholder="输入国家、类型、号码" />
              <div class="tb-list" style="margin-top:12px">
                <template v-if="emgFiltered.length">
                  <div v-for="e in emgFiltered" :key="e[0]" class="tb-item">
                    <div class="ic2" style="background:rgba(220,38,38,.08)"><SIcon name="phone" :size="16" color="#DC2626" /></div>
                    <div class="it-body"><div class="t">{{ e[0] }}</div><div class="d">{{ e[2] }}</div></div>
                    <div class="em-num">{{ e[1] }}</div>
                  </div>
                </template>
                <div v-else class="tb-none">未找到匹配的号码</div>
              </div></div>
          </template>

          <!-- 10 景点推荐 -->
          <template v-if="activeTool === 'spots'">
            <div class="tb-block"><div class="lb"><SIcon name="pin" :size="12" color="#EC4899" /> 按主题筛选</div>
              <div class="tb-row">
                <span v-for="t in SPOT_THEMES" :key="t" class="tb-tag" :class="{ sel: spots.theme === t }" @click="spots.theme = t">{{ t }}</span>
              </div></div>
            <div class="tb-block"><div class="lb"><SIcon name="star" :size="12" color="#EC4899" /> 「{{ spots.theme }}」主题   {{ spotsFiltered.length }} 个推荐</div>
              <div class="tb-list">
                <template v-if="spotsFiltered.length">
                  <div v-for="s in spotsFiltered" :key="s.n" class="tb-item">
                    <div class="ic2" style="background:rgba(236,72,153,.08)"><SIcon name="pin" :size="16" color="#EC4899" /></div>
                    <div class="it-body"><div class="t">{{ s.n }} <span class="sp-cat">{{ s.cat }}</span></div><div class="d">{{ s.d }}</div><div class="d tip">💡 {{ s.tip }}</div></div>
                  </div>
                </template>
                <div v-else class="tb-none">该主题暂无推荐</div>
              </div></div>
          </template>

          <!-- 11 拍照翻译 -->
          <template v-if="activeTool === 'phototrans'">
            <div class="tb-block"><div class="lb"><SIcon name="camera" :size="12" color="#14B8A6" /> 上传路牌、菜单图片</div>
              <div class="photo-drop">
                <SIcon name="camera" :size="28" color="#14B8A6" />
                <div class="pd-txt">点击此处上传或拍摄图片</div>
              </div>
              <div class="tb-row" style="margin-top:14px">
                <button class="tb-btn" style="background:linear-gradient(135deg,#14B8A6,#0D9488)" @click="tbPhotoMock"><SIcon name="sparkle" :size="12" color="#fff" /> 模拟识别翻译</button>
              </div></div>
            <div v-if="photo.out" class="tb-block"><div class="lb"><SIcon name="check" :size="12" color="#14B8A6" /> 识别结果</div>
              <div class="tb-result">{{ photo.out }}</div></div>
          </template>

          <!-- 12 单位换算 -->
          <template v-if="activeTool === 'unit'">
            <div class="tb-block"><div class="lb"><SIcon name="target" :size="12" color="#6B7280" /> 换算类型</div>
              <div class="tb-row">
                <span v-for="[k, l] in UNIT_TYPES" :key="k" class="tb-tag" :class="{ sel: unit.type === k }" @click="tbUnitType(k)">{{ l }}</span>
              </div>
              <div class="tb-row" style="margin-top:14px">
                <input type="text" style="max-width:130px" :value="unit.amt" @input="unit.amt = parseFloat(($event.target as HTMLInputElement).value) || 0" placeholder="数值" />
                <select class="tb-select" v-model="unit.from"><option v-for="u in unitUnits" :key="u">{{ u }}</option></select>
                <button class="tb-swap" @click="tbSwapUnit" title="交换"><SIcon name="right" :size="15" /></button>
                <select class="tb-select" v-model="unit.to"><option v-for="u in unitUnits" :key="u">{{ u }}</option></select>
              </div>
              <div class="tb-result" style="margin-top:14px"><span class="big">{{ unitResult }}</span></div></div>
          </template>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import SIcon from '@/components/SIcon.vue'
import {
  TOOLS, CURR, TABOO_DB, EMER_DB, SPOT_DB, PHRASES, GUIDE_TPL, ETQ_ITEMS,
} from '@/data/content'

const activeTool = ref<string | null>(null)
const activeToolObj = computed(() => TOOLS.find(t => t.id === activeTool.value) || null)

function openTool(id: string) { activeTool.value = id }
function closeTool() { activeTool.value = null }

// ══ 1 AI翻译 ══
const tr = reactive({ src: '中文', tgt: '英语', pick: null as number | null, inTxt: '', out: '' })
const trLangs = Object.keys(PHRASES)
function tbSwapLang() { const s = tr.src; tr.src = tr.tgt; tr.tgt = s; tr.pick = null }
function tbPickPhrase(i: number) {
  const arr = (PHRASES as any)[tr.tgt] || (PHRASES as any)['英语']
  tr.pick = i; tr.inTxt = arr[i][0]; tr.out = arr[i][1]
}

// ══ 2 礼仪检查 ══
const etq = reactive({ checked: {} as Record<number, boolean>, out: null as any })
function tbEtqToggle(i: number) { etq.checked[i] = !etq.checked[i] }
function tbEtqScore() {
  const cnt = Object.keys(etq.checked).filter(k => etq.checked[+k]).length
  const score = Math.round(cnt / ETQ_ITEMS.length * 100)
  const grade = score >= 85 ? '礼仪标兵' : score >= 60 ? '规范得体' : score >= 40 ? '尚需完善' : '待提升'
  const note = score >= 60
    ? '整体接待礼仪规范到位，细节处体现专业素养。继续保持微笑与主动服务。'
    : '部分礼仪环节有遗漏，建议重点补齐未勾选项，对照清单逐项练习后再上岗。'
  etq.out = { score, grade, note }
}

// ══ 3 行程规划 ══
const itn = reactive({ days: 3, theme: '文化历史', out: '' })
const ITN_THEMES = ['文化历史', '自然风光', '美食探店', '亲子休闲', '夜游赏景']
function tbGenItinerary() {
  const per: Record<string, string[]> = {
    '文化历史': ['博物馆深度游', '古迹探访', '非遗手作体验'],
    '自然风光': ['观景台日出', '徒步栈道', '湖畔骑行'],
    '美食探店': ['老字号早茶', '特色市集', '主题晚宴'],
    '亲子休闲': ['亲子乐园', '科普展馆', '手工课堂'],
    '夜游赏景': ['灯光秀', '夜市漫步', '游船夜航'],
  }
  const arr = per[itn.theme]
  let txt = ''
  for (let d = 1; d <= itn.days; d++) {
    txt += `第${d}天\n  上午   ${arr[d % arr.length]}（约2.5小时）\n  中午   当地特色餐厅午餐，安排休息\n  下午   ${arr[(d + 1) % arr.length]}（约2.5小时）\n  傍晚   自由活动、集合清点\n\n`
  }
  txt += '备注：全程预留机动时间，可根据游客体力与兴趣灵活调整。'
  itn.out = txt
}

// ══ 4 AI导游词 ══
const gd = reactive({ spot: '', type: '开场欢迎', out: '' })
function tbGenGuide() {
  if (!gd.spot.trim()) { return }
  const fill: Record<string, string> = {
    '{intro}': '，这里承载着深厚的历史文化底蕴，每一处景观都诉说着独特的故事。',
    '{era}': '千年之前',
    '{history}': '历经岁月洗礼，这里见证了无数风云变迁，留下了珍贵的文化印记。',
    '{summary}': '我们一同领略了这里的历史与风光，感受了文化的魅力。',
  }
  let out = (GUIDE_TPL as any)[gd.type].replace(/\{spot\}/g, gd.spot.trim())
  for (const [k, v] of Object.entries(fill)) out = out.split(k).join(v)
  gd.out = out
}

// ══ 5 文化禁忌查询 ══
const taboo = reactive({ country: '法国' })

// ══ 6 汇率换算（实时汇率 + 离线降级）══
const curr = reactive({ amt: 100, from: 'USD', to: 'CNY' })
const liveCurr = ref<Record<string, number> | null>(null)   // 实时汇率：1 单位外币 = N 人民币
const currSrc = ref<'live' | 'offline'>('offline')
async function loadLiveRates() {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), 5000)
  try {
    const res = await fetch('https://open.er-api.com/v6/latest/CNY', { signal: ctrl.signal })
    if (!res.ok) throw new Error('HTTP ' + res.status)
    const data: any = await res.json()
    if (!data || data.result !== 'success' || !data.rates) throw new Error('汇率接口返回格式异常')
    const map: Record<string, number> = {}
    for (const c of CURR) {
      const r = data.rates[c[0]]
      if (typeof r === 'number' && r > 0) map[c[0]] = 1 / r
    }
    if (Object.keys(map).length < 2) throw new Error('汇率数据不完整')
    liveCurr.value = map
    currSrc.value = 'live'
  } catch (e) {
    console.warn('[Toolbox] 实时汇率获取失败，已降级为离线示例数据', e)
    liveCurr.value = null
    currSrc.value = 'offline'
  } finally {
    clearTimeout(timer)
  }
}
function currRate(code: string): number {
  const live = liveCurr.value?.[code]
  if (live !== undefined) return live
  const r = CURR.find(c => c[0] === code)
  if (!r) return 1
  return String(r[1]).includes('(100)') ? (r[2] as number) / 100 : (r[2] as number)
}
const currResult = computed(() => {
  const res = curr.amt * currRate(curr.from) / currRate(curr.to)
  return Number.isFinite(res) ? res.toFixed(2) : '—'
})
const currRateLine = computed(() => (currRate(curr.from) / currRate(curr.to)).toFixed(4))
function tbSwapCurr() { const s = curr.from; curr.from = curr.to; curr.to = s }

// ══ 7 时差查询（真实 UTC 偏移计算，含夏令时）══
interface TZCity { city: string; label: string; tz: string; utcOffset: number }
const TZ_CITIES: TZCity[] = [
  { city: '北京', label: '中国', tz: 'Asia/Shanghai', utcOffset: 8 },
  { city: '上海', label: '中国', tz: 'Asia/Shanghai', utcOffset: 8 },
  { city: '广州', label: '中国', tz: 'Asia/Shanghai', utcOffset: 8 },
  { city: '东京', label: '日本', tz: 'Asia/Tokyo', utcOffset: 9 },
  { city: '首尔', label: '韩国', tz: 'Asia/Seoul', utcOffset: 9 },
  { city: '新加坡', label: '新加坡', tz: 'Asia/Singapore', utcOffset: 8 },
  { city: '曼谷', label: '泰国', tz: 'Asia/Bangkok', utcOffset: 7 },
  { city: '巴黎', label: '法国', tz: 'Europe/Paris', utcOffset: 1 },
  { city: '伦敦', label: '英国', tz: 'Europe/London', utcOffset: 0 },
  { city: '纽约', label: '美国', tz: 'America/New_York', utcOffset: -5 },
  { city: '洛杉矶', label: '美国', tz: 'America/Los_Angeles', utcOffset: -8 },
  { city: '悉尼', label: '澳大利亚', tz: 'Australia/Sydney', utcOffset: 10 },
  { city: '迪拜', label: '阿联酋', tz: 'Asia/Dubai', utcOffset: 4 },
]
const nowTick = ref(Date.now())
const tz = reactive({ from: '北京', to: '巴黎' })
/** 当前时刻某时区的实际 UTC 偏移（小时），夏令时自动生效 */
function tzOffsetHours(timeZone: string): number {
  try {
    const now = new Date(nowTick.value)
    const dtf = new Intl.DateTimeFormat('en-US', {
      timeZone, year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, hourCycle: 'h23',
    })
    const p: Record<string, string> = {}
    for (const part of dtf.formatToParts(now)) p[part.type] = part.value
    const asUtc = Date.UTC(+p.year, +p.month - 1, +p.day, (+p.hour) % 24, +p.minute, +p.second)
    return (asUtc - now.getTime()) / 3600000
  } catch {
    const c = TZ_CITIES.find(x => x.tz === timeZone)
    return c ? c.utcOffset : 0
  }
}
function fmtCityTime(timeZone: string): string {
  try {
    return new Intl.DateTimeFormat('zh-CN', {
      timeZone, hour: '2-digit', minute: '2-digit', hour12: false, hourCycle: 'h23',
    }).format(new Date(nowTick.value))
  } catch {
    const c = TZ_CITIES.find(x => x.tz === timeZone)
    const off = c ? c.utcOffset : 0
    const now = new Date(nowTick.value)
    const h = ((now.getUTCHours() + off) % 24 + 24) % 24
    return String(h).padStart(2, '0') + ':' + String(now.getUTCMinutes()).padStart(2, '0')
  }
}
function tzCityInfo(city: string) {
  const c = TZ_CITIES.find(x => x.city === city) || TZ_CITIES[0]
  const off = Math.round(tzOffsetHours(c.tz))
  const diffBjk = off - 8
  const utcLabel = 'UTC' + (off >= 0 ? '+' + off : off)
  return { label: c.label, time: fmtCityTime(c.tz), utcLabel, diffBjk }
}
const tzFromInfo = computed(() => tzCityInfo(tz.from))
const tzToInfo = computed(() => tzCityInfo(tz.to))
const tzDiff = computed(() => {
  const from = TZ_CITIES.find(c => c.city === tz.from)!
  const to = TZ_CITIES.find(c => c.city === tz.to)!
  return Math.round(tzOffsetHours(to.tz) - tzOffsetHours(from.tz))
})
function tbSwapTz() { const s = tz.from; tz.from = tz.to; tz.to = s }

// ══ 8 天气查询（Open-Meteo 实时 + 离线降级）══
interface WeatherData { t: string; ic: string; temp: string; wind: string; hum: string; adv: string }
const WTHR_CITIES: Record<string, [number, number]> = {
  北京: [39.9042, 116.4074], 上海: [31.2304, 121.4737], 广州: [23.1291, 113.2644],
  深圳: [22.5431, 114.0579], 成都: [30.5728, 104.0668], 西安: [34.3416, 108.9398],
  桂林: [25.2736, 110.29], 杭州: [30.2741, 120.1551], 苏州: [31.2989, 120.5853],
  南京: [32.0603, 118.7969], 重庆: [29.563, 106.5516], 昆明: [24.8801, 102.8329],
}
/** WMO 天气代码 → 描述 / 图标 / 带团提示（Open-Meteo） */
const WMO: Record<number, { t: string; ic: string; adv: string }> = {
  0: { t: '晴', ic: 'sun', adv: '晴空万里，适合户外游览，注意防晒补水' },
  1: { t: '晴间多云', ic: 'sun', adv: '天气晴好，正常安排户外行程' },
  2: { t: '多云', ic: 'cloud', adv: '云量较多，体感舒适，正常安排行程' },
  3: { t: '阴', ic: 'cloud', adv: '天阴无雨，光线偏暗，拍照可适当补光' },
  45: { t: '雾', ic: 'cloud', adv: '能见度较低，提醒游客注意交通安全' },
  48: { t: '雾凇', ic: 'cloud', adv: '能见度低，路面可能结冰，注意防滑' },
  51: { t: '毛毛雨', ic: 'rain', adv: '细雨绵绵，提醒游客备好雨具' },
  53: { t: '毛毛雨', ic: 'rain', adv: '细雨绵绵，提醒游客备好雨具' },
  55: { t: '毛毛雨', ic: 'rain', adv: '细雨绵绵，提醒游客备好雨具' },
  56: { t: '冻毛毛雨', ic: 'rain', adv: '有冻雨可能，路面湿滑，注意防滑' },
  57: { t: '冻毛毛雨', ic: 'rain', adv: '有冻雨可能，路面湿滑，注意防滑' },
  61: { t: '小雨', ic: 'rain', adv: '有小雨，提醒游客备伞、放慢脚步' },
  63: { t: '中雨', ic: 'rain', adv: '雨势不小，户外项目建议调整或备好雨具' },
  65: { t: '大雨', ic: 'rain', adv: '雨量大，注意防滑防雷，谨慎安排户外行程' },
  66: { t: '冻雨', ic: 'rain', adv: '冻雨天气，路面结冰风险高，务必注意防滑' },
  67: { t: '冻雨', ic: 'rain', adv: '冻雨天气，路面结冰风险高，务必注意防滑' },
  71: { t: '小雪', ic: 'cloud', adv: '有降雪，气温低，提醒游客添衣防滑' },
  73: { t: '中雪', ic: 'cloud', adv: '降雪较大，路面积雪湿滑，注意保暖防滑' },
  75: { t: '大雪', ic: 'cloud', adv: '大雪天气，建议减少户外活动，注意保暖' },
  77: { t: '雪粒', ic: 'cloud', adv: '有雪粒，路面湿滑，提醒游客小心行走' },
  80: { t: '阵雨', ic: 'rain', adv: '有阵雨，建议携带雨具，随时关注天气变化' },
  81: { t: '阵雨', ic: 'rain', adv: '有阵雨，建议携带雨具，随时关注天气变化' },
  82: { t: '强阵雨', ic: 'rain', adv: '强阵雨来袭，注意避雨，谨防雷电' },
  85: { t: '阵雪', ic: 'cloud', adv: '有阵雪，注意保暖与防滑' },
  86: { t: '阵雪', ic: 'cloud', adv: '有阵雪，注意保暖与防滑' },
  95: { t: '雷阵雨', ic: 'rain', adv: '有雷雨，避免在空旷处停留，注意防雷' },
  96: { t: '雷雨伴冰雹', ic: 'rain', adv: '雷雨伴冰雹，尽快进入室内避险' },
  99: { t: '雷雨伴冰雹', ic: 'rain', adv: '雷雨伴冰雹，尽快进入室内避险' },
}
/** 离线降级数据（仅离线时展示，标注「离线示例数据」） */
const WTHR_FALLBACK: Record<string, WeatherData> = {
  北京: { t: '晴', ic: 'sun', temp: '24~32℃', wind: '南风2级', hum: '40%', adv: '紫外线较强，提醒游客防晒补水，户外活动建议安排在上午' },
  上海: { t: '多云', ic: 'cloud', temp: '26~33℃', wind: '东南风3级', hum: '70%', adv: '体感闷热，建议携带遮阳伞，午后注意防暑' },
  广州: { t: '雷阵雨', ic: 'rain', temp: '27~34℃', wind: '东南风2级', hum: '80%', adv: '午后多雷阵雨，提醒游客备伞并注意防滑' },
  深圳: { t: '多云', ic: 'cloud', temp: '27~33℃', wind: '东风3级', hum: '75%', adv: '体感湿热，注意补水防晒' },
  成都: { t: '阴', ic: 'cloud', temp: '22~28℃', wind: '微风', hum: '80%', adv: '云量较多、湿度较大，注意防潮' },
  西安: { t: '晴', ic: 'sun', temp: '23~34℃', wind: '东北风2级', hum: '45%', adv: '昼夜温差较大，提醒游客早晚添衣' },
  桂林: { t: '小雨', ic: 'rain', temp: '24~30℃', wind: '东风2级', hum: '85%', adv: '雨雾天气，山路湿滑，提醒游客穿防滑鞋' },
  杭州: { t: '小雨', ic: 'rain', temp: '23~29℃', wind: '东风2级', hum: '85%', adv: '路面湿滑，提醒游客放慢脚步，备好雨具' },
  苏州: { t: '多云', ic: 'cloud', temp: '25~31℃', wind: '东南风3级', hum: '75%', adv: '体感较闷热，注意补水' },
  南京: { t: '多云', ic: 'cloud', temp: '24~31℃', wind: '东风2级', hum: '70%', adv: '早晚凉爽，午后注意防晒' },
  重庆: { t: '多云', ic: 'cloud', temp: '26~34℃', wind: '微风', hum: '70%', adv: '山城坡道多，提醒游客穿舒适鞋履' },
  昆明: { t: '晴', ic: 'sun', temp: '17~25℃', wind: '西南风3级', hum: '60%', adv: '紫外线强但体感舒适，注意防晒补水' },
}
function mapWeather(c: any): WeatherData {
  const wmo = WMO[c.weather_code] || WMO[0]
  return {
    t: wmo.t, ic: wmo.ic,
    temp: Math.round(c.temperature_2m) + '℃',
    wind: Math.round(c.wind_speed_10m) + ' km/h',
    hum: (c.relative_humidity_2m ?? '—') + '%',
    adv: wmo.adv,
  }
}
const wthr = reactive({ city: '北京', data: null as WeatherData | null, src: 'offline' as 'live' | 'offline', loading: false })
const wthrCache: Record<string, { data: WeatherData; src: 'live' | 'offline' }> = {}
let wthrReqId = 0
const wthrData = computed<WeatherData>(() => wthr.data || WTHR_FALLBACK[wthr.city] || WTHR_FALLBACK['北京'])
async function loadWeather(city: string) {
  const hit = wthrCache[city]
  if (hit) { wthr.data = hit.data; wthr.src = hit.src; return }
  const id = ++wthrReqId
  wthr.loading = true
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), 5000)
  try {
    const ll = WTHR_CITIES[city]
    if (!ll) throw new Error('未配置城市坐标: ' + city)
    const url = `https://api.open-meteo.com/v1/forecast?latitude=${ll[0]}&longitude=${ll[1]}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m&timezone=auto`
    const res = await fetch(url, { signal: ctrl.signal })
    if (!res.ok) throw new Error('HTTP ' + res.status)
    const j: any = await res.json()
    if (!j || !j.current || typeof j.current.temperature_2m !== 'number') throw new Error('天气接口返回格式异常')
    const w = mapWeather(j.current)
    if (id === wthrReqId) { wthr.data = w; wthr.src = 'live'; wthrCache[city] = { data: w, src: 'live' } }
  } catch (e) {
    console.warn('[Toolbox] 实时天气获取失败，已降级为离线示例数据', city, e)
    if (id === wthrReqId) {
      const fb = WTHR_FALLBACK[city] || WTHR_FALLBACK['北京']
      wthr.data = fb; wthr.src = 'offline'; wthrCache[city] = { data: fb, src: 'offline' }
    }
  } finally {
    clearTimeout(timer)
    if (id === wthrReqId) wthr.loading = false
  }
}

// ══ 9 紧急电话 ══
const emgQ = ref('')
const emgFiltered = computed(() =>
  EMER_DB.filter(e => !emgQ.value || e[0].includes(emgQ.value) || e[1].includes(emgQ.value) || e[2].includes(emgQ.value))
)

// ══ 10 景点推荐 ══
const spots = reactive({ theme: '历史' })
const SPOT_THEMES = ['历史', '佛教', '古镇', '山水', '美食', '摄影', '亲子']
const spotsFiltered = computed(() => SPOT_DB.filter(s => s.tags.includes(spots.theme)))

// ══ 11 拍照翻译 ══
const photo = reactive({ out: '' })
function tbPhotoMock() {
  photo.out = '【原文】Sortie — Exit\n【译文】出口\n\n【原文】Toilettes 卫生间 →\n【译文】卫生间在右侧\n\n演示说明：正式版将调用 OCR + 翻译接口，实时识别路牌、菜单、标识牌并给出对照译文。'
}

// ══ 12 单位换算 ══
const UNIT_DB: Record<string, Record<string, number>> = {
  length: { '米': 1, '厘米': 0.01, '千米': 1000, '英尺': 0.3048, '码': 0.9144, '英里': 1609.344 },
  weight: { '克': 1, '千克': 1000, '斤': 500, '磅': 453.592, '盎司': 28.3495 },
}
const unit = reactive({ amt: 1, type: 'length', from: '米', to: '英尺' })
const UNIT_TYPES: [string, string][] = [['length', '长度'], ['weight', '重量'], ['temp', '温度']]
const unitUnits = computed(() => unit.type === 'temp' ? ['摄氏度', '华氏度'] : Object.keys(UNIT_DB[unit.type]))
const unitResult = computed(() => {
  const v = unit.amt || 0
  if (unit.type === 'temp') {
    return unit.from === '摄氏度' ? (v * 9 / 5 + 32).toFixed(1) + ' ℉' : ((v - 32) * 5 / 9).toFixed(1) + ' ℃'
  }
  const u = UNIT_DB[unit.type]
  return (v * u[unit.from] / u[unit.to]).toFixed(3) + ' ' + unit.to
})
function tbUnitType(t: string) {
  unit.type = t
  if (t === 'temp') { unit.from = '摄氏度'; unit.to = '华氏度' }
  else { unit.from = Object.keys(UNIT_DB[t])[0]; unit.to = Object.keys(UNIT_DB[t])[3] }
}
function tbSwapUnit() { const s = unit.from; unit.from = unit.to; unit.to = s }

// ══ 数据来源状态徽标 + 生命周期 ══
function toolBadge(id: string | null, short = false): { txt: string; live: boolean } | null {
  if (!id) return null
  if (id === 'currency') {
    const live = currSrc.value === 'live'
    return { txt: live ? (short ? '实时' : '实时汇率') : (short ? '离线' : '离线示例数据'), live }
  }
  if (id === 'weather') {
    const live = wthr.src === 'live'
    return { txt: live ? (short ? '实时' : '实时天气') : (short ? '离线' : '离线示例数据'), live }
  }
  if (id === 'timediff') return { txt: short ? '实时' : '实时计算', live: true }
  return { txt: short ? '示例' : '示例数据', live: false }
}
function cardBadge(id: string): { txt: string; live: boolean } {
  return toolBadge(id, true) || { txt: '示例', live: false }
}
const toolDataStatus = computed(() => toolBadge(activeTool.value))

let tzTimer: number | undefined
onMounted(() => {
  loadLiveRates()
  loadWeather(wthr.city)
  tzTimer = window.setInterval(() => { nowTick.value = Date.now() }, 30000)
})
watch(() => wthr.city, (c) => loadWeather(c))
onUnmounted(() => { if (tzTimer !== undefined) window.clearInterval(tzTimer) })

// 复制
function tbCopy(txt: string) {
  if (!txt) return
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(txt).catch(() => { /* 静默 */ })
  }
}
</script>

<style lang="scss" scoped>
@use '@/styles/tokens' as *;

.tb-page { display: flex; flex-direction: column; height: 100vh; overflow: hidden; background: $color-bg; }
.ph { display: flex; align-items: center; justify-content: space-between; padding: 16px 24px 10px; flex-shrink: 0; }
.ph-title { font-family: $font-serif; font-size: 19px; font-weight: 700; color: $color-text-link; }
.tb-count { font-size: 11.5px; padding: 5px 13px; border-radius: 20px; color: #256CA7;
  background: rgba(51,143,242,.12); border: 1px solid rgba(51,143,242,.3); }
.tb-body { flex: 1; min-height: 0; overflow-y: auto; }
.tb-inner { max-width: 1100px; margin: 0 auto; padding: 4px 24px 24px; }

/* 顶部推荐条 */
.tb-feature { padding: 16px 20px; display: flex; align-items: center; gap: 16px; cursor: pointer;
  border-radius: 16px; margin-bottom: 16px; transition: transform .16s, box-shadow .16s;
  &.grad { background: linear-gradient(135deg, #1C426E, #338FF2 55%, #122E4F); }
  &:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(24,58,99,.25); }
  .ic { width: 44px; height: 44px; border-radius: 12px; background: rgba(51,143,242,.14);
    display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .ft { flex: 1;
    .h { font-size: 14.5px; font-weight: 600; color: #F5FAFF; }
    .s { font-size: 11.5px; color: rgba(255,255,255,.6); margin-top: 3px; } } }

/* 工具网格 */
.tb-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.tool-card { position: relative; border-radius: 16px; padding: 16px; text-align: left; display: flex; flex-direction: column;
  gap: 10px; cursor: pointer; background: rgba(255,255,255,.85); border: 1px solid $color-border;
  box-shadow: 0 1px 4px rgba(24,58,99,.04); transition: transform .15s, box-shadow .15s, border-color .15s;
  font-family: $font-sans;
  &:hover { transform: translateY(-3px); box-shadow: 0 8px 20px rgba(24,58,99,.1); border-color: rgba(51,143,242,.4); }
  .ic { width: 40px; height: 40px; border-radius: 12px; display: flex; align-items: center; justify-content: center; }
  .t { font-size: 14px; font-weight: 500; color: $color-text; }
  .d { font-size: 11px; margin-top: 2px; color: $color-text-secondary; } }

/* 工具详情面板 */
.tb-back { display: inline-flex; align-items: center; gap: 5px; border: none; cursor: pointer;
  background: transparent; color: $color-text-link; font-size: 13px; padding: 6px 10px; border-radius: 8px;
  transition: background .12s; margin-bottom: 12px; font-family: $font-sans;
  &:hover { background: rgba(24,58,99,.06); } }
.tool-head { display: flex; align-items: center; gap: 14px; padding: 16px 20px; border-radius: 16px;
  margin-bottom: 16px; background: rgba(255,255,255,.88); border: 1px solid $color-border;
  .ic { width: 48px; height: 48px; border-radius: 14px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .th { flex: 1; min-width: 0;
    .t { font-size: 17px; font-weight: 700; color: $color-text-link; font-family: $font-serif; }
    .d { font-size: 12px; color: $color-text-secondary; margin-top: 3px; } } }
.ai-badge { color: $color-text-link; font-size: 11px; padding: 4px 12px; border-radius: 20px; white-space: nowrap; }
.tb-demo-badge { font-size: 10.5px; padding: 3px 10px; border-radius: 20px; white-space: nowrap;
  color: $color-text-secondary; background: #EAF3FC; border: 1px solid #DCEAF7;
  &.live { color: #1F7A4D; background: rgba(31,122,77,.08); border-color: rgba(31,122,77,.25); } }
.tb-card-badge { position: absolute; top: 10px; right: 10px; font-size: 10px; padding: 2px 8px; }
.tz-note { font-size: 11px; color: $color-text-secondary; }

/* 通用块 */
.tb-block { background: rgba(255,255,255,.88); border: 1px solid $color-border; border-radius: 16px;
  padding: 18px; margin-bottom: 14px;
  .lb { font-size: 12px; font-weight: 600; color: $color-text-secondary; margin-bottom: 8px;
    display: flex; align-items: center; gap: 6px; }
  input[type='text'] { width: 100%; border: 1px solid $color-border; border-radius: 10px; padding: 10px 12px;
    font-size: 13px; font-family: $font-sans; color: $color-text; background: #fff; outline: none;
    transition: border-color .15s; box-sizing: border-box;
    &:focus { border-color: $color-primary; } } }
.tb-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.tb-select { padding: 9px 12px; border: 1px solid $color-border; border-radius: 10px; font-size: 13px;
  font-family: $font-sans; color: $color-text; background: #fff; outline: none; cursor: pointer; min-width: 120px; }
.tb-btn { padding: 10px 20px; border: none; border-radius: 10px; cursor: pointer; font-size: 13px;
  font-weight: 600; font-family: $font-sans; color: #fff; background: linear-gradient(135deg, #338FF2, #26507f);
  transition: all .18s; display: inline-flex; align-items: center; gap: 6px;
  &:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 6px 16px rgba(24,58,99,.25); }
  &:disabled { opacity: .5; cursor: not-allowed; }
  &.gold { background: linear-gradient(135deg, #338FF2, #A8893C); } }
.tb-result { border-radius: 12px; padding: 14px 16px; background: rgba(24,58,99,.05);
  border: 1px solid rgba(24,58,99,.08); font-size: 13px; line-height: 1.7; color: $color-text;
  white-space: pre-wrap; word-break: break-word;
  .big { font-size: 26px; font-weight: 700; color: #256CA7; font-family: 'Liberation Mono', monospace; }
  .rate-line { font-size: 11px; color: $color-text-secondary; } }
.tb-list { display: flex; flex-direction: column; gap: 8px; }
.tb-item { display: flex; align-items: flex-start; gap: 10px; padding: 12px 14px; border-radius: 12px;
  background: rgba(255,255,255,.75); border: 1px solid $color-border; transition: all .15s;
  .ic2 { width: 34px; height: 34px; border-radius: 10px; display: flex; align-items: center;
    justify-content: center; flex-shrink: 0; }
  .it-body { flex: 1; min-width: 0;
    .t { font-size: 13px; font-weight: 600; color: $color-text-link;
      .sp-cat { font-size: 10px; color: #256CA7; font-weight: 500; } }
    .d { font-size: 11px; color: $color-text-secondary; margin-top: 2px; line-height: 1.5;
      &.tip { color: $color-text-secondary; } } }
  .em-num { font-family: 'Liberation Mono', monospace; font-weight: 700; color: #c42222; font-size: 15px;
    align-self: center; } }
.tb-none { color: $color-text-secondary; font-size: 12px; padding: 12px; }
.tb-tag { display: inline-block; padding: 5px 13px; border-radius: 20px; font-size: 12px;
  background: $color-secondary-bg; color: $color-text-secondary; cursor: pointer; transition: all .15s;
  border: 1px solid transparent; font-family: $font-sans;
  &:hover { border-color: $color-accent; }
  &.sel { background: $color-primary; color: #fff; } }
.tb-grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.tb-warn { padding: 10px 14px; border-radius: 10px; background: rgba(239,68,68,.07);
  border: 1px solid rgba(239,68,68,.2); font-size: 11.5px; color: #B91C1C; line-height: 1.6;
  display: flex; align-items: flex-start; gap: 7px; }
.tb-check { display: flex; align-items: center; gap: 10px; padding: 11px 14px; border-radius: 10px;
  background: rgba(255,255,255,.7); border: 1px solid $color-border; cursor: pointer; transition: all .15s;
  &:hover { border-color: rgba(139,92,246,.4); }
  .cb { width: 20px; height: 20px; border-radius: 6px; border: 2px solid $color-border;
    display: flex; align-items: center; justify-content: center; flex-shrink: 0; transition: all .15s; }
  .txt { font-size: 13px; color: $color-text;
    .sub { color: $color-text-secondary; font-size: 11px; } }
  &.on { .cb { background: #8B5CF6; border-color: #8B5CF6; }
    .txt { color: #6D28D9; font-weight: 500; } } }
.tb-swap { width: 36px; height: 36px; border-radius: 10px; border: 1px solid $color-border; background: #fff;
  cursor: pointer; display: flex; align-items: center; justify-content: center; color: $color-text-link;
  transition: all .15s; flex-shrink: 0;
  &:hover { background: $color-primary; color: #fff; } }
.wx-row { display: flex; align-items: center; gap: 14px; }
.photo-drop { border: 2px dashed $color-border; border-radius: 12px; padding: 28px; text-align: center;
  cursor: pointer; transition: border-color .15s;
  &:hover { border-color: #14B8A6; }
  .pd-txt { font-size: 12px; color: $color-text-secondary; margin-top: 8px; } }

@media (max-width: 800px) {
  .tb-grid { grid-template-columns: repeat(2, 1fr); }
  .tb-grid2 { grid-template-columns: 1fr; }
}
</style>
