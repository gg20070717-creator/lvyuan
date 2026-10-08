export interface ResourceSection { title:string; content:string; points:string[] }
/** 从原文提取目录与要点，保持顺序与来源；代码围栏中的 # 不作为标题。 */
export function resourceOutline(markdown:string):ResourceSection[] {
  const sections:ResourceSection[] = []
  let current:ResourceSection = { title:'内容概览', content:'', points:[] }, inCode=false
  for(const line of markdown.split('\n')) {
    if(/^\s*```/.test(line)) inCode=!inCode
    const heading = !inCode ? line.match(/^#{1,4}\s+(.+)$/) : null
    if(heading) {
      if(current.content.trim()) sections.push(current)
      current = { title:heading[1].replace(/[*`]/g,''), content:'', points:[] }
    } else {
      current.content += line + '\n'
      const item = !inCode ? line.match(/^\s*(?:[-*+] |\d+[.、]\s*)(.+)/) : null
      if(item) current.points.push(item[1].replace(/[*`]/g,''))
    }
  }
  if(current.content.trim()) sections.push(current)
  return sections
}
export function resourceExcerpt(content:string) {
  return content.replace(/```[\s\S]*?```/g,'').replace(/[#*`>|]/g,'').replace(/\s+/g,' ').trim().slice(0,110)
}
