export type OnboardingStage = 'qa' | 'groups' | 'persona' | 'plan'

export interface OnboardingDraft {
  stage: OnboardingStage
  answers: Record<string, string>
  groupStatus: Record<string, string>
  questionIndex: number
  domainId: string
}

const draftKey = (userId: string) => `lvyuan_onboarding_draft:${userId}`

export function readOnboardingDraft(userId: string): OnboardingDraft | null {
  if (!userId) return null
  try {
    const value = JSON.parse(localStorage.getItem(draftKey(userId)) || 'null')
    if (!value || !['qa', 'groups', 'persona', 'plan'].includes(value.stage)) return null
    const strings = (input: unknown): Record<string, string> => {
      if (!input || typeof input !== 'object' || Array.isArray(input)) return {}
      return Object.fromEntries(Object.entries(input).filter(([, v]) => typeof v === 'string'))
    }
    return {
      stage: value.stage,
      answers: strings(value.answers),
      groupStatus: strings(value.groupStatus),
      questionIndex: Number.isInteger(value.questionIndex) ? Math.max(0, value.questionIndex) : 0,
      domainId: typeof value.domainId === 'string' ? value.domainId : '',
    }
  } catch { return null }
}

export function saveOnboardingDraft(userId: string, draft: OnboardingDraft): void {
  try { localStorage.setItem(draftKey(userId), JSON.stringify(draft)) } catch { /* 无本地存储时仍可完成引导 */ }
}

export function clearOnboardingDraft(userId: string): void {
  try { localStorage.removeItem(draftKey(userId)) } catch { /* 无本地存储 */ }
}
