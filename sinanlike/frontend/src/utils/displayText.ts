// 只处理可见文案，技术标识、文件地址和富文本结构保留原值。
export function cleanDisplayText(text: string): string { return text.replace(/\u00b7/g, ' ').replace(/\s*[\/|]+\s*/g, '、') }
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
