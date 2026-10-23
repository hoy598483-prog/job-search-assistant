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

for (const [, id] of fs.readFileSync('browser_companion/background.html', 'utf8').matchAll(/id="([^"]+)"/g)) nodes.set(id, node());
const data = {};
const local = {
  async get(keys) {
    if (typeof keys === 'string') return {[keys]:data[keys]};
    return Object.fromEntries(keys.map(key=>[key,data[key]]));
  },
  async set(values) {Object.assign(data,structuredClone(values));},
  async remove(key) {delete data[key];}
};
const context = vm.createContext({console,document:{getElementById:id=>nodes.get(id),createElement:node},
  chrome:{storage:{local},runtime:{}},confirm:()=>true,setTimeout,clearTimeout,AbortController,URL});
vm.runInContext(fs.readFileSync('browser_companion/background.js','utf8'),context);
(async () => {
  for(let i=0;i<10;i++) await new Promise(resolve=>setImmediate(resolve));
  assert.equal(data.preparationDirections,undefined);
  assert.equal(data.activeDirection,undefined);
  assert.equal(nodes.has('workspace'),false);
  nodes.get('background-source').value='本人原文：会Python';
  vm.runInContext('codexReady=true; api=async(action,request)=>{if(action!=="chat")throw new Error("unexpected action");if(request.samples[0]!=="本人原文：会Python")throw new Error("wrong source");return {reply:"模型草案：会Python"};};',context);
  await nodes.get('background-analyze').onclick();
  assert.equal(data.globalPersonalBackground,undefined);
  assert.equal(data.globalBackgroundDraft,'模型草案：会Python');
  assert.equal(JSON.stringify(data).includes('本人原文：会Python'),false);
  nodes.get('background-draft').value='本人确认：会Python';
  await nodes.get('background-adopt').onclick();
  assert.equal(data.globalPersonalBackground.summary,'本人确认：会Python');
  assert.equal(data.globalPersonalBackground.confirmed,true);
  assert.equal(data.activeDirection,undefined);
  await nodes.get('background-remove').onclick();
  assert.equal(data.globalPersonalBackground,undefined);
  console.log('PASS: independent profile page without direction, analysis draft, explicit adoption and removal');
})().catch(error=>{console.error(error);process.exitCode=1;});
