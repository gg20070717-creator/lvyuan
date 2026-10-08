const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict')
const frontend = path.resolve(__dirname, '..')
const pkg = require('node:module').createRequire(path.join(frontend, 'package.json'))
const vue = pkg('vue'), ts = pkg('typescript'), sfc = pkg('@vue/compiler-sfc')
const errors = [], animationFrames = []
let reducedMotion = false, animationFailure = false
class HostNode {
  constructor(tag, text='') { Object.assign(this, {tag,text,children:[],parent:null,props:{},style:{},isConnected:true}) }
  get parentElement() { return this.parent }
  get tagName() { return this.tag.toUpperCase() }
  getRootNode() { return document }
  addEventListener() {}
  removeEventListener() {}
  get classList() { return { contains: value => String(this.props.class || '').split(' ').includes(value) } }
  getBoundingClientRect() { return this.classList.contains('access-card') ? {left:160,top:120,width:880,height:560} : {left:0,top:0,width:1200,height:800} }
  getClientRects() { return [this.getBoundingClientRect()] }
  querySelector(selector) { return find(this, node => selector.split(',').some(part => part.trim().startsWith('.') && node.classList.contains(part.trim().slice(1)) ))[0] || null }
  querySelectorAll() { return find(this, node => ['button','input','textarea'].includes(node.tag) && !node.props.disabled) }
  focus() { document.activeElement = this }
  scrollTo() {}
  animate(frames) { if(animationFailure) throw new Error('Animation unavailable');animationFrames.push(frames);return {finished:Promise.resolve(),cancel(){}} }
}
global.HTMLElement = HostNode
global.Document = class Document {}
global.ShadowRoot = class ShadowRoot {}
global.window = {matchMedia:()=>({matches:reducedMotion})}
global.document = Object.assign(new Document(),{activeElement:null,body:{style:{overflow:''}}})
const accounts = vue.reactive({
  flowOpen:false, flowStage:'access', userId:'guest', accounts:[], returnTo:'/app/home',
  async createAccount({name}) { this.accounts.push({id:'learner',name}); this.userId='learner' },
  closeFlow() { this.flowOpen=false }, switchTo(id) { this.userId=id },
})
const onb = {done:false,persona:null,groupStatus:{},load:async()=>false}
const Transition = vue.defineComponent({inheritAttrs:false,setup:(_,ctx)=>()=>vue.h(vue.BaseTransition,ctx.attrs,ctx.slots)})
const Teleport = vue.defineComponent({inheritAttrs:false,setup:(_,ctx)=>()=>ctx.slots.default?.()})
let wizardCreated = 0
let RealWizard
const Wizard = {inheritAttrs:false,setup(_,ctx) { wizardCreated++;return()=>vue.h(RealWizard,ctx.attrs) }}
const question = {id:'identity',question:'你现在更接近以下哪种身份？',options:[{id:'student',label:'在校学生'},{id:'guide',label:'导游'}]}
const mocks = {
  vue:{...vue,Transition,Teleport},
  'vue-router':{useRouter:()=>({push:async()=>{}})},
  '@/stores/accounts':{useAccountsStore:()=>accounts}, '@/stores/onboarding':{useOnboardingStore:()=>onb},
  '@/stores/app':{useAppStore:()=>({get userId(){return accounts.userId}})},
  '@/api/onboarding':{
    fetchOnboardingQuestions:async()=>[question],
    fetchOnboardingGroups:async()=>({domains:[{id:'law',title:'法律法规',groups:[{id:'g1',title:'接待规范',skill_count:1}]}]}),
    getQaState:async()=>({step:0,identity_done:false,answers:{}}),
  },
  '@/utils/onboardingDraft':{readOnboardingDraft:()=>null,saveOnboardingDraft(){},clearOnboardingDraft(){}},
  '@/assets/lvyuan-logo.jpg':{default:'logo.jpg'}, '@/components/GuofengLandscape.vue':{default:{render:()=>null}},
  '@/components/SIcon.vue':{default:{render:()=>null}}, '@/components/OnboardingWizard.vue':{default:Wizard},
}
const displayExports = {}
const displayCode = ts.transpileModule(fs.readFileSync(path.join(frontend,'src/utils/displayText.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
new Function('exports',displayCode)(displayExports)
mocks['@/utils/displayText'] = displayExports
function detach(node) { if(node.parent) { node.parent.children.splice(node.parent.children.indexOf(node),1);node.parent=null } }
const renderer = vue.createRenderer({
  createElement:tag=>new HostNode(tag),createText:text=>new HostNode('#text',text),createComment:text=>new HostNode('#comment',text),
  setText:(node,text)=>node.text=text,setElementText:(node,text)=>{node.text=text;node.children=[]},patchProp:(node,key,prev,next)=>node.props[key]=next,
  parentNode:node=>node.parent,nextSibling:node=>node.parent?.children[node.parent.children.indexOf(node)+1] || null,
  insert(node,parent,anchor=null) { detach(node);const index=anchor?parent.children.indexOf(anchor):-1;parent.children.splice(index<0?parent.children.length:index,0,node);node.parent=parent }, remove:detach,
})
function component(file) {
  const descriptor=sfc.parse(fs.readFileSync(path.join(frontend,'src/components',file),'utf8')).descriptor
  const code=ts.transpileModule(sfc.compileScript(descriptor,{id:'registration-check',inlineTemplate:true}).content,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
  const exportsObject={};new Function('require','exports',code)(id=>mocks[id] || pkg(id),exportsObject)
  return exportsObject.default
}
RealWizard=component('OnboardingWizard.vue')
function find(node,predicate) { return [...(predicate(node)?[node]:[]),...node.children.flatMap(child=>find(child,predicate))] }
function text(node) { return node.text + node.children.map(text).join(' ') }
async function flush() { for(let i=0;i<8;i++) { await vue.nextTick();await Promise.resolve() } }
const root=new HostNode('root'), app=renderer.createApp(component('AccountFlow.vue'))
app.config.errorHandler=error=>errors.push(error)
app.config.warnHandler=message=>{ if(!message.includes('Non-function value encountered for default slot')) errors.push(new Error(message)) }
;(async()=>{
  app.mount(root);accounts.flowOpen=true;await flush()
  assert.ok(text(root).includes('注册，开启你的学习旅程'))
  const input=find(root,node=>node.tag==='input')[0]
  input.props['onUpdate:modelValue']('注册回归检查')
  await find(root,node=>node.tag==='form')[0].props.onSubmit({preventDefault(){}})
  await flush()
  assert.equal(accounts.flowStage,'onboarding')
  assert.equal(wizardCreated,1,'Registration must mount the fullscreen wizard')
  assert.ok(text(root).includes('先验学情画像'),'The overlay must contain the next screen after registration')
  assert.ok(text(root).includes(question.question),'The real wizard must load and render its first question')
  assert.equal(errors.length,0,errors.map(String).join('\n'))
  assert.ok(animationFrames.some(frames=>frames[0].transform?.includes('scale(0.733')),'Registration card should expand to the fullscreen bounds')
  accounts.closeFlow();await flush();assert.equal(document.body.style.overflow,'')
  accounts.flowStage='access';accounts.flowOpen=true;await flush();accounts.flowStage='onboarding';await flush()
  assert.equal(wizardCreated,2,'The flow must also work when reopened')
  assert.ok(text(root).includes('先验学情画像'))
  for(const fallback of ['reduced-motion','animation-error']) {
    accounts.closeFlow();await flush()
    reducedMotion=fallback==='reduced-motion';animationFailure=fallback==='animation-error'
    accounts.flowStage='access';accounts.flowOpen=true;await flush()
    accounts.flowStage='onboarding';await flush()
    assert.ok(text(root).includes('先验学情画像'),fallback+' must still show the fullscreen wizard')
    assert.equal(errors.length,0,errors.map(String).join('\n'))
    accounts.closeFlow();await flush();assert.equal(document.body.style.overflow,'')
  }
  console.log('PASS: registration mounts the fullscreen wizard, expansion completes, closing and reopening work, reduced motion and animation failures remain visible.')
})().catch(error=>{console.error(error);process.exitCode=1}).finally(()=>app.unmount())
