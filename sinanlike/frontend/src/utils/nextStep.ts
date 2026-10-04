// 统一的「下一步建议」：沿学习路线（目录顺序）找第一个掌握度 <60% 的章节。
// 首页推荐条与学情中心共用，保证全系统只有一个“下一步”口径。
import type { SkillNode } from '@/api/knowledge'

export interface NextStep {
  bookTitle: string
  chapterTitle: string
  mastery: number // 0-100
}

function chapterMastery(chapter: SkillNode, scores: Record<string, number>): number {
  const vals: number[] = []
  const walk = (nodes: SkillNode[]) => {
    for (const n of nodes) {
      if (n.type === 'skill') {
        const v = scores[n.id]
        vals.push(typeof v === 'number' && !Number.isNaN(v) ? v : 0)
      }
      if (n.children) walk(n.children)
    }
  }
  walk(chapter.children || [])
  if (!vals.length) return 0
  return vals.reduce((a, b) => a + b, 0) / vals.length
}

export function nextStepFromTree(tree: SkillNode[], scores: Record<string, number>): NextStep | null {
  // 目录顺序：按 书 → （分组）→ 章 深度优先；遇到第一个章节均分 <60% 即返回
  const stack: Array<{ node: SkillNode; bookTitle: string }> = []
  for (const b of tree || []) {
    if (b.type === 'book') stack.push({ node: b, bookTitle: b.title || '' })
  }
  while (stack.length) {
    const { node, bookTitle } = stack.pop()!
    if (node.children) {
      const items = [...node.children].reverse()
      for (const c of items) {
        stack.push({ node: c, bookTitle })
      }
    }
    if (node.type === 'chapter') {
      const avg = chapterMastery(node, scores)
      if (avg < 0.6) return { bookTitle, chapterTitle: node.title || '', mastery: Math.round(avg * 100) }
    }
  }
  return null
}