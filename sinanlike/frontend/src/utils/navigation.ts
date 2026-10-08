export type LearningSection = 'assessment' | 'practice' | 'integrated'
export interface NavigationItem { id: string; label: string; icon: string; path: string }
export const learningNavigation: { id: LearningSection; label: string; icon: string; items: NavigationItem[] }[] = [
  { id: 'assessment', label: '学前测试', icon: 'user', items: [
    { id: 'portrait', label: '自我画像', icon: 'user', path: '/app/home?section=portrait' },
    { id: 'diagnostic', label: '知识摸底', icon: 'bookcheck', path: '/app/home?section=diagnostic' },
    { id: 'plan', label: '学习建议', icon: 'trend', path: '/app/home?section=plan' },
  ] },
  { id: 'practice', label: '专项练习', icon: 'bookcheck', items: [
    { id: 'quiz', label: '做题练习', icon: 'bookcheck', path: '/app/home?activity=quiz' },
    { id: 'communication', label: '沟通训练', icon: 'msg', path: '/app/training?focus=communication' },
    { id: 'emergency', label: '应急处理', icon: 'shield', path: '/app/training?focus=emergency' },
  ] },
  { id: 'integrated', label: '综合实战', icon: 'map', items: [
    { id: 'pre', label: '行前定制', icon: 'notebook', path: '/app/training?focus=integrated&phase=pre' },
    { id: 'mid', label: '行中接待', icon: 'globe', path: '/app/training?focus=integrated&phase=mid' },
    { id: 'post', label: '行后复盘', icon: 'check', path: '/app/training?focus=integrated&phase=post' },
  ] },
]

export function resolveLearningNavigation(path: string, query: Record<string, unknown>) {
  if (path === '/app/profile') return { section: 'assessment' as const, item: 'portrait' }
  if (path === '/app/home') {
    const section = String(query.section || '')
    if (['portrait', 'diagnostic', 'plan'].includes(section)) return { section: 'assessment' as const, item: section }
    return { section: 'practice' as const, item: 'quiz' }
  }
  if (path === '/app/training') {
    if (query.focus === 'emergency') return { section: 'practice' as const, item: 'emergency' }
    if (query.focus === 'communication' || query.focus === 'narrate') return { section: 'practice' as const, item: 'communication' }
    return { section: 'integrated' as const, item: integratedPhase(query.phase) }
  }
  return null
}

export function integratedPhase(value: unknown): 'pre' | 'mid' | 'post' {
  return value === 'mid' || value === 'post' ? value : 'pre'
}

// 行中分类保留跨文化全程场景；分课和终阶场景都可进入，前置要求仍由训练页校验。
export function inIntegratedPhase(templateId: string, phase: 'pre' | 'mid' | 'post') {
  return templateId.startsWith(`t_${phase}_`) || templateId === `t_ff_${phase}_trip` || (phase === 'mid' && templateId === 't_ff_culture_bridge')
}
