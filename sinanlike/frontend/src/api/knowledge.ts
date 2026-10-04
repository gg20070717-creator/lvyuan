import client from './client'

// ── 类型定义 ──
export interface SkillNode {
  id: string
  type: 'book' | 'part' | 'chapter' | 'section' | 'skill'
  title: string
  difficulty?: number
  categories?: string[]
  status?: string
  question_count?: number
  stats?: Record<string, number>
  children?: SkillNode[]
}

export interface BookStats {
  books: SkillNode[]
  stats: { books: number; skills: number; questions: number }
}

export interface SkillDetail {
  id: string
  title: string
  content: string
  keywords: string[]
  categories: string[]
  difficulty: number
  status: string
  book: string
  chapter: string
  section: string
  path: string[]
  questions: Question[]
}

export interface SearchHit {
  skill_id: string
  title: string
  content: string
  source: string
  trust: number
  difficulty: number
}

export interface SearchResponse {
  query: string
  count: number
  results: SearchHit[]
}

export interface Question {
  question_id: string
  knowledge_point_id: string
  difficulty: string
  prompt: string
  answer_key: string
  rubric: string
  misconception_tags: string[]
  options: string[]
  answer: string
  explanation: string
  source: string
}

export interface ChapterGuide {
  book_title: string
  chapter_id: string
  chapter_title: string
  skill_count: number
  question_count: number
  difficulty_distribution: Record<string, number>
  skills: Array<{ id: string; title: string; difficulty: number; categories: string[] }>
}

// ── 知识库浏览 ──
export function getBooks(): Promise<BookStats> {
  return client.get('/knowledge/books') as unknown as Promise<BookStats>
}

export function getKnowledgeTree(): Promise<{ tree: SkillNode[] }> {
  return client.get('/knowledge/tree') as unknown as Promise<{ tree: SkillNode[] }>
}

export function getGuides(): Promise<{ guides: ChapterGuide[] }> {
  return client.get('/knowledge/guides') as unknown as Promise<{ guides: ChapterGuide[] }>
}

export function getSkillDetail(skillId: string): Promise<SkillDetail> {
  return client.get(`/knowledge/skills/${skillId}`) as unknown as Promise<SkillDetail>
}

export function searchKnowledge(params: {
  q: string
  top_k?: number
  book?: string
  chapter?: string
}): Promise<SearchResponse> {
  return client.get('/knowledge/search', { params }) as unknown as Promise<SearchResponse>
}

export function browseQuestions(params: {
  book?: string
  chapter?: string
  difficulty?: string
  knowledge_point_ids?: string
  limit?: number
}): Promise<{ total: number; questions: Question[] }> {
  return client.get('/knowledge/questions', { params }) as unknown as Promise<{ total: number; questions: Question[] }>
}


// ── 知识技能树（从知识库派生 + 节点名精确检索） ──
export interface KSTNode {
  id: string
  type: 'book' | 'part' | 'chapter' | 'section' | 'skill'
  name: string
  ic: string
  lit: boolean
  source: string
  reason: string
  mastery: number | null
  fill?: number
  mastery_detail?: Record<string, any>
  linked_count: number
  children?: KSTNode[]
}

export interface KnowledgeSkillTree {
  user_id: string
  counts: { books: number; parts: number; chapters: number; sections: number; skills: number }
  branches: KSTNode[]
}

export interface TreeSearchResult {
  id: string
  type: string
  name: string
  path: string[]
  skills: Array<{ id: string; title: string; difficulty: number; status: string; content_excerpt: string }>
}

export function getKnowledgeSkillTree(userId: string): Promise<KnowledgeSkillTree> {
  return client.get(`/skills/${userId}/knowledge-tree`) as unknown as Promise<KnowledgeSkillTree>
}

export function treeSearch(q: string): Promise<{ query: string; exact: boolean; count: number; results: TreeSearchResult[] }> {
  return client.get('/knowledge/tree-search', { params: { q } }) as unknown as Promise<{ query: string; exact: boolean; count: number; results: TreeSearchResult[] }>
}

