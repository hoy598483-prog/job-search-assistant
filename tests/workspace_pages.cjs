const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
function node(){return {children:[],attributes:{},dataset:{},hidden:false,textContent:'',append(...children){this.children.push(...children);},prepend(...children){this.children.unshift(...children);},setAttribute(key,value){this.attributes[key]=value;},getAttribute(key){return key==='href'?this.href:this.attributes[key];},removeAttribute(key){delete this.attributes[key];},querySelectorAll(){return this.children;}};}
const html=fs.readFileSync('browser_companion/panel.html','utf8');
const nodes=new Map([...html.matchAll(/id="([^"]+)"/g)].map(match=>[match[1],node()]));
const sections=[...html.matchAll(/data-workspace-page="([^"]+)"/g)].map(match=>{const element=node();element.dataset.workspacePage=match[1];return element;});
const main=node(),body=node(),events={},location={pathname:'/panel.html',hash:''};
body.classList={add(){}};
const context=vm.createContext({location,document:{body,title:'',createElement:()=>node(),createTextNode:text=>text,getElementById:id=>nodes.get(id),querySelector:()=>main,querySelectorAll:()=>sections},window:{addEventListener:(name,handler)=>events[name]=handler,scrollTo(){}}});
vm.runInContext(fs.readFileSync('browser_companion/ui_shell.js','utf8'),context);
function verify(view){
  for(const element of sections)assert.equal(element.hidden,element.dataset.workspacePage!==view);
  const nav=body.children[0].children[1];
  assert.equal(nav.children.filter(link=>link.attributes['aria-current']==='page').length,1);
  assert.equal(nav.children.find(link=>link.attributes['aria-current']==='page').href,'panel.html#'+view);
}
verify('collect');
nodes.get('chat-input').value='未发送的消息';
location.hash='#plan';events.hashchange();verify('plan');
assert.equal(nodes.get('workspace-title').textContent,'Codex 计划');
location.hash='#collect';events.hashchange();verify('collect');
assert.equal(nodes.get('chat-input').value,'未发送的消息');
assert.match(html, /id="chat-section" data-workspace-page="plan" hidden/);
assert.match(html, /id="results" class="grid" data-workspace-page="collect"/);
console.log('PASS: separate collection/planning routes, active navigation and preserved draft');
