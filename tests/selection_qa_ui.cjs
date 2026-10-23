const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict'),{webcrypto}=require('node:crypto');
const nodes=new Map();function node(){return {value:'',textContent:'',children:[],checked:true,append(...items){this.children.push(...items)},replaceChildren(...items){this.children=items},focus(){},after(){}};}
for(const [,id] of fs.readFileSync('browser_companion/qa.html','utf8').matchAll(/id="([^"]+)"/g))nodes.set(id,node());
const data={globalPersonalBackground:{summary:'有数学基础'},'codexChat:a':[{role:'user',content:'主聊天不能被读取'}]},pending={'qaRequest:r1':{id:'r1',quote:'交集',paragraph:'两个集合共有元素',documentKey:'course:1',direction:'a',anchor:'here'}};
const store=data=>({async get(keys){return Object.fromEntries((Array.isArray(keys)?keys:[keys]).map(key=>[key,structuredClone(data[key])]))},async set(values){Object.assign(data,structuredClone(values))},async remove(key){delete data[key]}});
let request=null;const posted=[];
class Client{async connect(){return {authenticated:true,notice:'已登录'}}async stream(body,event){request=body;event({type:'delta',text:'交集解释'});return '交集解释'}disconnect(){}}
const context=vm.createContext({console,chrome:{storage:{local:store(data),session:store(pending),onChanged:{addListener(){}}},tabs:{onActivated:{addListener(){}}}},crypto:webcrypto,TextEncoder,URLSearchParams,location:{search:'?embed=1&request=r1',origin:'chrome-extension://test'},parent:{postMessage:value=>posted.push(value)},window:{addEventListener(){}},document:{getElementById:id=>nodes.get(id),createElement:node,querySelectorAll:()=>[]},LocalCodexClient:Client,confirm:()=>true,setTimeout,clearTimeout,AbortController});
vm.runInContext(fs.readFileSync('browser_companion/notebook_store.js','utf8'),context);vm.runInContext(fs.readFileSync('browser_companion/qa_store.js','utf8'),context);vm.runInContext(fs.readFileSync('browser_companion/qa.js','utf8'),context);
(async()=>{
  for(let i=0;i<20;i++)await new Promise(resolve=>setImmediate(resolve));
  assert.equal(nodes.get('qa-quote').textContent,'交集');
  await nodes.get('qa-connect').onclick();nodes.get('qa-input').value='结合数学解释';await nodes.get('qa-send').onclick();
  assert.equal(request.mode,'selection_qa');assert.equal(request.messages.length,1);assert.equal(JSON.stringify(request).includes('主聊天不能被读取'),false);assert.match(request.messages[0].content,/有数学基础/);
  assert.equal(data['codexChat:a'].length,1);assert.equal(data.learningNotebookEntries,undefined);
  nodes.get('qa-summary').value='交集是共同元素';await nodes.get('qa-note').onclick();assert.equal(data.learningNotebookEntries.length,1);
  await nodes.get('qa-return').onclick();assert.equal(posted[0].type,'selection-qa-return');assert.equal(posted[0].anchor,'here');
  console.log('PASS: QA UI isolated context, explicit note collection and source-return message');
})().catch(error=>{console.error(error);process.exitCode=1});
