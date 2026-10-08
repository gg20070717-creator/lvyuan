/* 旅鸢   训练成绩 store（历史记录 + 场景最高分回写 + localStorage 持久化） */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { SCENES, NARR_SCENES, ROUTE_SCENES } from '@/data/content'
import safeStorage from '@/utils/storage'

const REC_KEY = 'sinan_train_records_v1'

export interface TrainRecord {
  mode: string
  sceneId: number
  sceneName: string
  score: number
  date: number
}

export const useTrainRecordsStore = defineStore('trainRecords', () => {
  function load(): TrainRecord[] {
    try { return JSON.parse(safeStorage.getItem(REC_KEY) || '[]') } catch { return [] }
  }

  const history = ref<TrainRecord[]>(load())

  function persist() {
    try { safeStorage.setItem(REC_KEY, JSON.stringify(history.value)) } catch { /* 忽略 */ }
  }

  /** 成绩入册：记录历史 + 回写场景最高分/上次分 */
  function saveRecord(mode: string, sceneId: number, sceneName: string, score: number): { isNewBest: boolean; prevBest: number | null } {
    const pool: any[] = sceneId < 100 ? SCENES : sceneId < 200 ? NARR_SCENES : ROUTE_SCENES
    const sc = pool.find(s => s.id === sceneId)
    const prevBest = sc ? sc.best : null
    const isNewBest = prevBest === null || score > (prevBest as number)
    if (sc) {
      sc.last = score
      if (sc.best === null || score > sc.best) sc.best = score
    }
    history.value.push({ mode, sceneId, sceneName, score, date: Date.now() })
    if (history.value.length > 200) history.value.shift()
    persist()
    return { isNewBest, prevBest }
  }

  function lastRecordOf(sceneId: number): TrainRecord | null {
    for (let i = history.value.length - 1; i >= 0; i--) {
      if (history.value[i].sceneId === sceneId) return history.value[i]
    }
    return null
  }

  const stats = computed(() => {
    const n = history.value.length
    if (!n) return { n: 0, avg: 0, top: 0, last: null as TrainRecord | null }
    const avg = Math.round(history.value.reduce((s, r) => s + r.score, 0) / n)
    const top = Math.max(...history.value.map(r => r.score))
    return { n, avg, top, last: history.value[n - 1] }
  })

  return { history, saveRecord, lastRecordOf, stats }
})
