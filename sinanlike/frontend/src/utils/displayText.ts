// 只处理可见文案，技术标识、文件地址和富文本结构保留原值。
export function cleanDisplayText(text: string): string { return text.replace(/\u00b7/g, ' ').replace(/\s*[\/|]+\s*/g, '、') }
// 已有序号徽标或独立进度时，标题只保留内容；正文、数量与技术标识不经过此函数。
export function cleanNumberedTitle(text: string): string {
  const original = cleanDisplayText(text).trim()
  const title = original
    .replace(/[①-⑳㉑-㉟㊱-㊿❶-❿]/gu, '')
    .replace(/^\s*(?:第\s*[\d零〇一二三四五六七八九十百]+\s*(?:阶段|部分|步|节|章)\s*[、:：.．-]?\s*|[（(]\s*[\d零〇一二三四五六七八九十百]+\s*[）)]\s*[、:：.．-]?\s*|\d+(?:[.．]\d+)+\s+|(?:\d+(?:[.．]\d+)*|[零〇一二三四五六七八九十百]+)[、.．)）:：](?!\d)\s*)/u, '')
    .replace(/\s+/g, ' ').trim()
  return title || original
}
export function cleanDisplayHtml(html: string): string {
  const template = document.createElement('template')
  template.innerHTML = html
  const walker = document.createTreeWalker(template.content, NodeFilter.SHOW_TEXT)
  let node: Node | null
  while ((node = walker.nextNode())) {
    if (!['STYLE', 'SCRIPT'].includes(node.parentElement?.tagName || '')) node.textContent = cleanDisplayText(node.textContent || '')
  }
  template.content.querySelectorAll<HTMLElement>('[title], [alt], [aria-label]').forEach(element => {
    for (const name of ['title', 'alt', 'aria-label']) if (element.hasAttribute(name)) element.setAttribute(name, cleanDisplayText(element.getAttribute(name) || ''))
  })
  return template.innerHTML
}
export function cleanDisplayPayload<T>(payload: T): T {
  if (typeof payload === 'string') return cleanDisplayText(payload) as T
  if (Array.isArray(payload)) return payload.map(value => cleanDisplayPayload(value)) as T
  if (payload && typeof payload === 'object' && Object.getPrototypeOf(payload) === Object.prototype) {
    return Object.fromEntries(Object.entries(payload).map(([key, value]) => [key,
      /(^id$|_id$|_ids$|^url$|_url$|^href$|^path$|_path$|^filename$|^mime_type$|^content_type$)/.test(key) || (typeof value === 'string' && /^(content|markdown|body|html)$/.test(key)) ? value : cleanDisplayPayload(value),
    ])) as T
  }
  return payload
}
