const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict'),{webcrypto}=require('node:crypto');
const nodes=new Map();
function node(){return {value:'',textContent:'',children:[],append(...items){this.children.push(...items)},replaceChildren(...items){this.children=items},addEventListener(){},click(){}};}
for(const [,id] of fs.readFileSync('browser_companion/notebook.html','utf8').matchAll(/id="([^"]+)"/g))nodes.set(id,node());
nodes.get('note-kind').value='knowledge';
const data={preparationDirections:[{id:'a',name:'AI产品'}]};
const local={async get(keys){return Object.fromEntries((Array.isArray(keys)?keys:[keys]).map(key=>[key,structuredClone(data[key])]))},async set(values){Object.assign(data,structuredClone(values))}};
const context=vm.createContext({chrome:{storage:{local}},crypto:webcrypto,confirm:()=>true,document:{getElementById:id=>nodes.get(id),createElement:node},setTimeout,URL,Blob});
vm.runInContext(fs.readFileSync('browser_companion/notebook_store.js','utf8'),context);
vm.runInContext(fs.readFileSync('browser_companion/notebook.js','utf8'),context);
(async()=>{
  for(let i=0;i<10;i++)await new Promise(resolve=>setImmediate(resolve));
  nodes.get('note-date').value='2026-10-21';nodes.get('note-direction').value='a';nodes.get('note-title').value='指标口径';nodes.get('note-content').value='DAU时区要一致';
  await nodes.get('note-save').onclick();
  assert.equal(data.learningNotebookEntries.length,1);
  assert.equal(nodes.get('note-list').children[0].textContent,'2026-10-21');
  nodes.get('filter-date').value='2026-10-20';vm.runInContext('render()',context);
  assert.equal(nodes.get('note-list').children.length,0);
  nodes.get('filter-date').value='';vm.runInContext('render()',context);
  const card=nodes.get('note-list').children[1];
  card.children.find(item=>item.textContent==='编辑').onclick();
  nodes.get('note-content').value='补充：去重用户，统一时区';await nodes.get('note-save').onclick();
  assert.equal(data.learningNotebookEntries[0].content,'补充：去重用户，统一时区');
  const updated=nodes.get('note-list').children[1];
  await updated.children.find(item=>item.textContent==='删除').onclick();
  assert.equal(data.learningNotebookEntries.length,0);
  console.log('PASS: notebook page save, date grouping/filtering, edit and delete');
})().catch(error=>{console.error(error);process.exitCode=1});
