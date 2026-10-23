const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict'),{webcrypto}=require('node:crypto');
const handlers={},calls=[],session={};
const chrome={runtime:{onInstalled:{addListener:fn=>handlers.install=fn}},contextMenus:{removeAll:fn=>fn(),create:menu=>{handlers.menu=menu},onClicked:{addListener:fn=>handlers.click=fn}},sidePanel:{open:async options=>calls.push(['open',options])},
  scripting:{executeScript:async()=>{calls.push(['capture']);return [{result:{paragraph:'附近段落',anchor:'anchor'}}]}},
  storage:{local:{get:async()=>({activeDirection:'a',preparationDirections:[{id:'a',target:'理解指标'}]})},session:{set:async value=>Object.assign(session,value),remove:async key=>delete session[key]}},tabs:{onRemoved:{addListener:fn=>handlers.remove=fn}}};
const context=vm.createContext({chrome,crypto:webcrypto,URL});vm.runInContext(fs.readFileSync('browser_companion/service_worker.js','utf8'),context);
(async()=>{
  handlers.install();assert.equal(handlers.menu.contexts[0],'selection');
  handlers.click({menuItemId:'job-companion-explain-selection',selectionText:'知识点',pageUrl:'https://example.org/docs?secret=removed',frameId:0},{id:2});
  for(let i=0;i<10;i++)await new Promise(resolve=>setImmediate(resolve));
  assert.equal(calls[0][0],'open');assert.equal(session['qaPending:2'].quote,'知识点');
  assert.equal(session['qaPending:2'].documentKey,'https://example.org/docs');assert.equal(session['qaPending:2'].direction,'a');
  console.log('PASS: user-gesture side-panel open, bounded selection capture and no URL query collection');
})().catch(error=>{console.error(error);process.exitCode=1});
