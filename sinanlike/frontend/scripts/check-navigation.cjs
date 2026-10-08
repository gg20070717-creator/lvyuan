const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict')
const frontend = path.resolve(__dirname, '..')
const pkg = require('node:module').createRequire(path.join(frontend, 'package.json'))
const vue = pkg('vue'), ts = pkg('typescript'), sfc = pkg('@vue/compiler-sfc')
const vueRouter = pkg('vue-router')
const accounts = vue.reactive({ userId:'guest', isSignedIn:false, flowOpen:false, flowStage:'access', returnTo:'', ensureAccounts() {}, openAccess(target) { this.flowOpen=true; this.returnTo=target }, openOnboarding(target) { this.flowOpen=true; this.flowStage='onboarding'; this.returnTo=target } })
const onb = vue.reactive({ done:false, loaded:true, loadedUserId:'guest', load:async()=>false, clearSession(){} })
const appStore = vue.reactive({ userId:'guest', sessionId:'s1', startHealthCheck(){}, stopHealthCheck(){} })
const co = { refreshLearning:async()=>{}, loadCatalog:async()=>{} }
global.document = { title:'' }
const mocks = {
  '@/stores/app':{useAppStore:()=>appStore}, '@/stores/accounts':{useAccountsStore:()=>accounts},
  '@/stores/onboarding':{useOnboardingStore:()=>onb}, '@/stores/cooperation':{useCooperationStore:()=>co},
  'vue':{...vue, Transition:vue.defineComponent({inheritAttrs:false, setup:(_, {slots})=>()=>slots.default?.()[0] || null})},
  'vue-router':vueRouter,
}
function evaluate(code) {
  const js = ts.transpileModule(code,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
  const exports={}; new Function('require','exports',js)(id=>mocks[id] || pkg(id),exports); return exports
}
function source(file) { return fs.readFileSync(path.join(frontend,'src',file),'utf8') }
const navigation = evaluate(source('utils/navigation.ts'))
mocks['@/utils/navigation']=navigation
const display = evaluate(source('utils/displayText.ts'))
function node(tag, text='') { return {tag,text,children:[],parent:null,props:{}} }
function detach(el) { if(el.parent) { const i=el.parent.children.indexOf(el); if(i>=0) el.parent.children.splice(i,1); el.parent=null } }
const renderer = vue.createRenderer({
  createElement:tag=>node(tag), createText:text=>node('#text',text), createComment:text=>node('#comment',text),
  setText:(el,text)=>el.text=text, setElementText:(el,text)=>{el.text=text;el.children=[]}, patchProp:(el,key,prev,next)=>el.props[key]=next,
  parentNode:el=>el.parent, nextSibling:el=>el.parent?.children[el.parent.children.indexOf(el)+1] || null,
  insert(el,parent,anchor=null) { if(el.parent) detach(el); const index=anchor ? parent.children.indexOf(anchor) : -1; parent.children.splice(index<0?parent.children.length:index,0,el); el.parent=parent },
  remove:detach,
})
const stub={ render:()=>vue.h('span') }
for(const component of ['AccountMenu','AccountFlow','AgentWorkflowFloat','LearningStatusBar','SIcon']) mocks[`@/components/${component}.vue`]={default:stub}
mocks['@/assets/lvyuan-logo.jpg']={default:'logo.jpg'}
let homeCreated=0, trainingCreated=0
const Home={setup(){homeCreated++; return()=>vue.h('div','保留学习草稿') }}
const Training={setup(){trainingCreated++; return()=>vue.h('div','保留训练会话') }}
mocks['@/views/HomeView.vue']={default:Home}
mocks['@/views/TrainingGroundView.vue']={default:Training}
for(const view of ['WelcomeView','KnowledgeBaseView','KnowledgeSkillTreeView','LearningPathView','ProfileView','ToolboxView']) mocks[`@/views/${view}.vue`]={default:stub}
const routerSource=source('router/index.ts').replace('createWebHashHistory','createMemoryHistory').replace('createWebHashHistory','createMemoryHistory')
const router=evaluate(routerSource).default
const descriptor=sfc.parse(source('layouts/MainLayout.vue')).descriptor
const Main=evaluate(sfc.compileScript(descriptor,{id:'nav-check',inlineTemplate:true}).content).default
mocks['@/layouts/MainLayout.vue']={default:Main}
const root=node('root'), instance=renderer.createApp({render:()=>vue.h(vueRouter.RouterView)})
function flatten(el){return el.text + el.children.map(flatten).join(' ')}
function find(el,predicate){return [ ...(predicate(el)?[el]:[]),...el.children.flatMap(child=>find(child,predicate)) ]}
async function go(target){await router.push(target);await vue.nextTick();await vue.nextTick()}
;(async()=>{
  assert.deepEqual(navigation.learningNavigation.map(g=>g.items.length),[3,3,3])
  const raw=fs.readFileSync(path.join(frontend,'../../brain_of_cloud/services/sandbox_templates.py'),'utf8')
  const ids=[...raw.matchAll(/template_id="(t_(?:pre_|mid_|post_|ff_)[^"]+)"/g)].map(m=>m[1])
  assert.equal(ids.length,16)
  for(const id of ids) assert.equal(['pre','mid','post'].filter(phase=>navigation.inIntegratedPhase(id,phase)).length,1,id)
  assert.equal(navigation.integratedPhase('unknown'),'pre')
  assert.deepEqual(display.cleanDisplayPayload({title:'电话\u00b7微信',path:'/asset/a\u00b7b',user_id:'u\u00b71',notes:['行前\u00b7行中']}),{title:'电话 微信',path:'/asset/a\u00b7b',user_id:'u\u00b71',notes:['行前 行中']})
  const markdown='| 内容 | 掌握度 |\n| --- | --- |\n| 电话/微信 | 高 |\n[原文](https://example.com/a/b)'
  assert.equal(display.cleanDisplayText('法律/业务 | 沟通\u00b7接待'),'法律、业务、沟通 接待')
  assert.deepEqual(display.cleanDisplayPayload({label:'学习/做题|实战',url:'https://example.com/a/b',mime_type:'text/markdown',content:markdown}),{label:'学习、做题、实战',url:'https://example.com/a/b',mime_type:'text/markdown',content:markdown})
  const blob=new Blob(['asset']);assert.equal(display.cleanDisplayPayload(blob),blob)
  await go('/app/home');instance.use(router).mount(root);await vue.nextTick()
  assert.equal(find(root,el=>el.props.class==='primary-nav')[0].children.filter(el=>el.tag==='a').length,3)
  assert.equal(homeCreated,1);assert.equal(accounts.flowOpen,false)
  for(const section of ['portrait','diagnostic','plan']) { await go('/app/home?section='+section);assert.ok(flatten(root).includes('自我画像'));assert.equal(accounts.flowOpen,false);assert.ok(document.title.startsWith(navigation.learningNavigation[0].items.find(x=>x.id===section).label)) }
  await go('/app/home?activity=quiz');assert.equal(homeCreated,1)
  await go('/app/training?focus=communication');assert.equal(accounts.flowOpen,false);assert.ok(flatten(root).includes('应急处理'))
  await go('/app/training?focus=emergency');assert.equal(trainingCreated,1)
  for(const phase of ['pre','mid','post']) { await go('/app/training?focus=integrated&phase='+phase);assert.ok(flatten(root).includes('行前定制'));assert.equal(trainingCreated,1) }
  await go('/app/home?activity=quiz');assert.equal(homeCreated,1);assert.ok(flatten(root).includes('保留学习草稿'))
  await go('/app/knowledge');assert.equal(router.currentRoute.value.path,'/app/home');assert.equal(accounts.returnTo,'/app/knowledge');assert.equal(accounts.flowOpen,true)
  accounts.isSignedIn=true;accounts.userId='learner';appStore.userId='learner';onb.loadedUserId='learner';accounts.flowOpen=false
  await go('/app/toolbox');assert.equal(accounts.flowStage,'onboarding');assert.equal(accounts.flowOpen,true)
  onb.done=true;accounts.flowOpen=false;await go('/app/toolbox');assert.equal(router.currentRoute.value.path,'/app/toolbox')
  const beforeHome=homeCreated;await go('/app/home?activity=quiz');await go('/app/knowledge');await go('/app/home?activity=quiz');assert.equal(homeCreated,beforeHome);assert.equal(homeCreated,2)
  const banned=String.fromCharCode(183)
  for(const dir of ['views','components']) for(const file of fs.readdirSync(path.join(frontend,'src',dir))) { if(!file.endsWith('.vue'))continue;const text=source(dir+'/'+file);assert.equal(text.includes(banned),false,file);const d=sfc.parse(text).descriptor;const result=sfc.compileTemplate({source:d.template.content,filename:file,id:file});assert.deepEqual(result.errors,[],file);if(dir==='views')assert.equal(result.ast.children.filter(n=>n.type!==3 && !(n.type===2 && !n.content.trim())).length,1,file) }
  console.log('PASS: three navigation groups, all integrated scenes reachable, guest browsing and account guards, persistent page instances, display separators, animated page roots.')
})().catch(error=>{console.error(error);process.exitCode=1}).finally(()=>instance.unmount())
