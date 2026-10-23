// Run with node tests/direction_ui.cjs. No browser, network or model calls.
const vm = require('node:vm');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const {webcrypto} = require('node:crypto');
const nodes = new Map();
function node(tag = '') {
  return {tag, value:'', textContent:'', disabled:false, children:[], style:{},
    append(...items) { this.children.push(...items); },
    replaceChildren(...items) { this.children = items; },
    after() {}, addEventListener() {}, remove() {}};
}
for (const [, id] of fs.readFileSync('browser_companion/panel.html', 'utf8').matchAll(/id="([^"]+)"/g)) nodes.set(id, node());
nodes.get('workspace').value = 'ai-product-job-agent';
function storage(initial = {}) {
  const data = structuredClone(initial);
  return {data, async get(keys) {
    if (typeof keys === 'string') return {[keys]:structuredClone(data[keys])};
    return Object.fromEntries(keys.map(key => [key, structuredClone(data[key])]));
  }, async set(values) {Object.assign(data, structuredClone(values));}, async remove(keys) {for(const key of Array.isArray(keys)?keys:[keys])delete data[key];}};
}
const local = storage({'textSamples:ai-product-job-agent':[{id:'old',text:'原方向样本',status:'saved'}]});
const session = storage({pages:[{text:'旧版待保存文本'}]});
const context = vm.createContext({console, document:{getElementById:id => nodes.get(id), createElement:node},
  chrome:{runtime:{id:'a'.repeat(32)},storage:{local,session}},crypto:webcrypto,
  confirm:() => true,prompt:() => 'Agent 开发',setTimeout,clearTimeout,AbortController,TextDecoder});
vm.runInContext(fs.readFileSync('browser_companion/notebook_store.js','utf8'), context);
vm.runInContext(fs.readFileSync('browser_companion/weekly.js','utf8'), context);
vm.runInContext(fs.readFileSync('browser_companion/panel.js','utf8'), context);
async function settle() {for (let i=0;i<20;i++) await new Promise(resolve => setImmediate(resolve));}
(async () => {
  await settle();
  assert.equal(local.data.activeDirection, 'ai-product-job-agent');
  assert.equal(session.data['pages:ai-product-job-agent'][0].text, '旧版待保存文本');
  await nodes.get('direction-new').onclick();
  const id = local.data.activeDirection;
  assert.match(id, /^direction-/);
  assert.equal(nodes.get('pages').children.length, 0);
  local.data['codexChat:'+id] = [{role:'user',content:'只属于Agent方向的对话'}];
  nodes.get('direction-target').value = 'Agent 工程师';
  await nodes.get('direction-save').onclick();
  assert.equal(local.data.preparationDirections.find(d=>d.id===id).target,'Agent 工程师');
  await vm.runInContext('api("save", {page:{text:"Agent 样本"}})', context);
  assert.equal(local.data['textSamples:'+id][0].text,'Agent 样本');
  nodes.get('direction-project').value = '工具调用助手';
  nodes.get('direction-plan').value = '七天计划';
  nodes.get('direction-progress').value = '第一天完成';
  await nodes.get('direction-plan-save').onclick();
  nodes.get('workspace').value = 'ai-product-job-agent';
  await nodes.get('workspace').onchange();
  assert.equal(nodes.get('direction-project').value,'');
  assert.equal(nodes.get('chat-history').children.length,0);
  const old = await vm.runInContext('api("list")',context);
  assert.equal(old.jobs.length,1); assert.equal(old.jobs[0].text,'原方向样本');
  nodes.get('workspace').value = id;
  await nodes.get('workspace').onchange();
  assert.equal(nodes.get('direction-project').value,'工具调用助手');
  assert.equal(nodes.get('direction-progress').value,'第一天完成');
  assert.equal(nodes.get('chat-history').children.length,1);
  const generated = {project:'游戏指标问答 Agent',assumptions:'每日建议60分钟，待本人确认',tasks:Array.from({length:7},(_,i)=>({day:i+1,title:'任务'+(i+1),action:'构建最小功能',artifact:'可检查成果',acceptance:'人工核验结果',minutes:60}))};
  context.planReply = '这是七天草案。<week_plan>'+JSON.stringify(generated)+'</week_plan>';
  await vm.runInContext('savePendingWeeklyPlan(parseWeeklyPlan(planReply).plan)',context);
  let record = local.data.preparationDirections.find(d=>d.id===id);
  assert.equal(record.pendingWeeklyPlan.status,'proposed');
  assert.equal(record.weeklyPlan,undefined);
  assert.equal(record.project,'工具调用助手');
  // Rejecting preserves the existing project and plan; asks for revision.
  await nodes.get('weekly-revise').onclick();
  record = local.data.preparationDirections.find(d=>d.id===id);
  assert.equal(record.pendingWeeklyPlan.status,'rejected');
  assert.equal(record.project,'工具调用助手');
  assert.match(nodes.get('chat-input').value,/不接受/);
  await vm.runInContext('savePendingWeeklyPlan(parseWeeklyPlan(planReply).plan)',context);
  await nodes.get('weekly-accept').onclick();
  record = local.data.preparationDirections.find(d=>d.id===id);
  assert.equal(record.pendingWeeklyPlan,null);
  assert.equal(record.weeklyPlan.tasks.length,7);
  assert.equal(record.weeklyPlan.status,'accepted');
  assert.equal(record.project,'游戏指标问答 Agent');
  assert.match(nodes.get('direction-plan').value,/第7天/);
  assert.equal(record.weeklyPlanHistory[0].project,'工具调用助手');
  context.acceptedPlanId = record.weeklyPlan.id;
  await vm.runInContext('markWeeklyTask(acceptedPlanId,1,true)',context);
  let notebook = await vm.runInContext('LearningNotebook.all()',context);
  assert.equal(notebook.entries.length,1);
  assert.equal(notebook.entries[0].kind,'task');
  assert.match(notebook.entries[0].date,/^\d{4}-\d{2}-\d{2}$/);
  await vm.runInContext('markWeeklyTask(acceptedPlanId,1,false)',context);
  notebook = await vm.runInContext('LearningNotebook.all()',context);
  assert.equal(notebook.entries.length,0);

  nodes.get('workspace').value='ai-product-job-agent'; await nodes.get('workspace').onchange();
  assert.equal(nodes.get('weekly-active').children.length,1);
  assert.equal(local.data.preparationDirections.find(d=>d.id==='ai-product-job-agent').weeklyPlan,undefined);
  context.badPlanReply='<week_plan>{"project":"bad","tasks":[]}</week_plan>';
  assert.equal(vm.runInContext('parseWeeklyPlan(badPlanReply).plan',context),undefined);
  nodes.get('workspace').value=id; await nodes.get('workspace').onchange();
  await vm.runInContext('markWeeklyTask(acceptedPlanId,1,true)',context);
  local.data.globalPersonalBackground={summary:'保留背景'};
  local.data.learningNotebookEntries=[{id:'note',direction:id,title:'保留知识',content:'知识内容'}];
  local.data['learningCourses:'+id]=[{title:'课程'}];
  session.data['pages:'+id]=[{text:'临时文本'}];
  context.confirm=()=>false;
  await nodes.get('direction-delete').onclick();
  assert.equal(local.data.preparationDirections.length,2);
  context.confirm=()=>true;
  await nodes.get('direction-delete').onclick();
  assert.equal(local.data.activeDirection,'ai-product-job-agent');
  for(const prefix of ['textSamples:','codexChat:','learningCourses:'])assert.equal(local.data[prefix+id],undefined);
  assert.equal(session.data['pages:'+id],undefined);
  assert.equal(local.data.globalPersonalBackground.summary,'保留背景');
  notebook=await vm.runInContext('LearningNotebook.all()',context);
  assert.equal(notebook.entries.length,2);
  assert.equal(notebook.entries.find(item=>item.kind==='task').automatic,false);
  assert.equal(notebook.entries.find(item=>item.kind==='task').direction_name,'Agent 开发');
  await nodes.get('direction-delete').onclick();
  assert.equal(local.data.preparationDirections.length,0);
  assert.equal(local.data.activeDirection,null);
  assert.equal(nodes.get('direction-delete').disabled,true);
  await vm.runInContext('initializeDirections()',context);
  assert.equal(local.data.preparationDirections.length,0);
  await assert.rejects(vm.runInContext('api("save",{page:{text:"不能保存到已删除方向"}})',context));
  await nodes.get('direction-new').onclick();
  assert.equal(local.data.preparationDirections.length,1);
  assert.equal(nodes.get('direction-delete').disabled,false);
  console.log('PASS: direction isolation, deletion/cancellation, retained background/notebook, empty state and recreation');
})().catch(error=>{console.error(error);process.exitCode=1;});
