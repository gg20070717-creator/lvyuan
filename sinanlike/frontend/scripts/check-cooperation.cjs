const fs = require('node:fs')
const path = require('node:path')
const assert = require('node:assert/strict')
const { createRequire } = require('node:module')
const frontend = path.resolve(__dirname, '..')
const pkg = createRequire(path.join(frontend, 'package.json'))
const ts = pkg('typescript'), vue = pkg('vue'), pinia = pkg('pinia')
const app = vue.reactive({ userId:'u1', sessionId:'s1' })
const accounts = vue.reactive({ isSignedIn:true })
let learningRequest = async () => ({ teaching:null, mastery:0, recommendation:{ path:'/app/home' } })
const mocks = {
  './app':{ useAppStore:() => app }, './accounts':{ useAccountsStore:() => accounts },
  '@/api/cooperation': {
    getAgentCatalog:async () => ({ agents:['concierge','white_hat','black_hat','green_hat','yellow_hat','red_hat','blue_hat'].map(id=>({id,name:id,group:'六帽',role:'核查',icon:'shield'})),reserved:[] }),
    getLearningStatus:(...args) => learningRequest(...args),
  },
}
function source(file) {
  const code = ts.transpileModule(fs.readFileSync(path.join(frontend,'src',file),'utf8'), { compilerOptions:{ module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022 } }).outputText
  const exports = {}
  new Function('require','exports',code)(id => mocks[id] || pkg(id),exports)
  return exports
}
const workflow = source('utils/workflow.ts')
mocks['@/utils/workflow'] = workflow
const resources = source('utils/resourceOutline.ts')
const storeModule = source('stores/cooperation.ts')
pinia.setActivePinia(pinia.createPinia())
const co = storeModule.useCooperationStore()
const timers = new Map(); let timerId=0
const realSet = global.setTimeout, realClear = global.clearTimeout
global.setTimeout = callback => { timers.set(++timerId,callback); return timerId }
global.clearTimeout = id => timers.delete(id)
function tick() { const [id,fn] = timers.entries().next().value || []; if(fn) { timers.delete(id); fn() } }
function drain() { let guard=1000; while(timers.size && guard--) tick(); assert.ok(guard>0) }
;(async () => {
  await co.loadCatalog()
  const token = co.begin('审查学习材料')
  assert.equal(co.visible,true); assert.equal(co.begin('重复请求'),null)
  const events = [
    {agent:'concierge',role:'判断',status:'working',step:'planning'},
    {agent:'concierge',role:'分工',status:'done',step:'dispatch',event:'dispatch',round:1,agents:['white_hat','black_hat','green_hat','yellow_hat','red_hat','blue_hat']},
    ...['white_hat','black_hat','green_hat','yellow_hat','red_hat'].map(agent=>({agent,role:'并行核查',status:'working',step:'collaboration'})),
    ...['white_hat','black_hat','green_hat','yellow_hat','red_hat'].map(agent=>({agent,role:'并行核查',status:'done',step:'collaboration'})),
    {agent:'blue_hat',role:'汇总',status:'working',step:'collaboration'},
    {agent:'blue_hat',role:'汇总',status:'done',step:'collaboration'},
    {agent:'concierge',role:'交付',status:'done',step:'delivery'},
  ]
  co.receive(events,token); co.finish(token)
  assert.equal(co.replaying,true,'快速完成的调用要明确标记为回放')
  tick(); assert.equal(co.latestDispatch.agents.length,6)
  tick(); assert.equal(co.activeAgents.length,5,'五帽并行工作，已完成分工的管家等待工具结果')
  assert.deepEqual(co.activeAgents.filter(a=>a.id!=='concierge').map(a=>a.id),['white_hat','black_hat','green_hat','yellow_hat','red_hat'])
  drain(); assert.equal(co.replaying,false); assert.equal(co.activeAgents.length,0)
  assert.ok(co.steps.every(step=>step.state==='done'))
  const second = co.begin('下一次调用')
  co.receive(events,token); assert.equal(co.trace.length,0,'过期任务不能污染新窗口')
  co.receive([{agent:'concierge',role:'判断',status:'working',step:'planning'}],second)
  co.finish(second,'网络中断'); drain(); assert.equal(co.steps[0].state,'failed')
  await vue.nextTick()
  const pendingStatuses = []
  learningRequest = () => new Promise(resolve=>pendingStatuses.push(resolve))
  const oldStatus = co.refreshLearning(), newStatus = co.refreshLearning()
  pendingStatuses[1]({ mastery:82,teaching:{session_id:'s1',stage:'practicing'} }); await newStatus
  pendingStatuses[0]({ mastery:30,teaching:{session_id:'s1',stage:'teaching'} }); await oldStatus
  assert.equal(co.learning.mastery,82,'同一会话的乱序旧状态不能覆盖最新状态')
  const staleTeaching = co.refreshLearning()
  co.syncTeaching({session_id:'s1',stage:'feedback'})
  pendingStatuses[2]({ mastery:83,teaching:{session_id:'s1',stage:'practicing'} }); await staleTeaching
  assert.equal(co.teaching.stage,'feedback','对话交付的教学快照优先于请求前的状态')
  let release
  learningRequest = () => new Promise(resolve=>{ release=resolve })
  const pending = co.refreshLearning()
  app.userId='u2'; await vue.nextTick()
  release({ mastery:95,teaching:{session_id:'s1',stage:'teaching'} }); await pending
  assert.equal(co.learning,null,'旧账户状态不能覆盖新账户')
  assert.equal(co.visible,false)
  const outline = resources.resourceOutline('# 讲义\n导言\n## 要点\n- 服务表达\n```md\n# 代码里的标题\n```\n## 练习\n1. 核对需求\n')
  assert.deepEqual(outline.map(s=>s.title),['讲义','要点','练习'])
  assert.deepEqual(outline[1].points,['服务表达'])
  assert.deepEqual(outline[2].points,['核对需求'])
  assert.ok(outline[1].content.includes('# 代码里的标题'))
  console.log('PASS: concurrent hat presentation, fast-call replay, failure states, stale task/account protection, original-source resource outline.')
})().catch(e=>{console.error(e);process.exitCode=1}).finally(()=>{global.setTimeout=realSet;global.clearTimeout=realClear;co.reset()})
