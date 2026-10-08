export interface TestProfile {
  id: string
  label: string
  emoji: string
  desc: string
  answers: Record<string, string>
}

/** 演示用「测试画像」：新建用户时可一键选用（也可从 0 开始） */
export const TEST_PROFILES: TestProfile[] = [
  {
    id: 'tpl_student_cert',
    label: '在校学生   零基础考证',
    emoji: '🎓',
    desc: '目标导游资格证，从零开始，题库刷题型选手',
    answers: { identity: 'student', basis: 'zero', language: 'none', goal: 'cert_cn', pace: 'fulltime', style: 'quiz' },
  },
  {
    id: 'tpl_guide_return',
    label: '在职导游   回岗转入境',
    emoji: '🧭',
    desc: '老导游回岗，主攻入境定制与外宾接待',
    answers: { identity: 'guide', basis: 'guide_return', language: 'basic', goal: 'inbound_foreign', pace: 'parttime', style: 'practice' },
  },
  {
    id: 'tpl_travel_worker',
    label: '旅行社一线   补外语',
    emoji: '🗺️',
    desc: '有部分接待经验，想补外语接外团',
    answers: { identity: 'travel_worker', basis: 'partial', language: 'fluent', goal: 'inbound_foreign', pace: 'flex', style: 'coached' },
  },
  {
    id: 'tpl_switcher_custom',
    label: '跨专业转行   目标定制师',
    emoji: '💼',
    desc: '零基础跨行，冲旅游定制师高客单方向',
    answers: { identity: 'career_switcher', basis: 'zero', language: 'fluent', goal: 'custom_high', pace: 'fulltime', style: 'lecture' },
  },
  {
    id: 'tpl_culture_leader',
    label: '文化从业者   领队讲解',
    emoji: '🏛️',
    desc: '经验较足、外语好，想往出境领队、讲解发展',
    answers: { identity: 'culture_worker', basis: 'experienced', language: 'minority', goal: 'outbound_leader', pace: 'longterm', style: 'lecture' },
  },
]