const $=id=>document.getElementById(id),el=(tag,text)=>{const node=document.createElement(tag);node.textContent=text;return node;};
const client=new LocalCodexClient(),params=new URLSearchParams(location.search);
const loginButton=el("button","启动官方登录");$("qa-connect").after(loginButton);
loginButton.onclick=async()=>{try{if(busy || !confirm("允许启动本机Codex官方登录？完成后请再次点击连接检查。"))return;await client.connect();const result=await client.action("provider_login",{approved:true});$("qa-connection").textContent=result.notice;}catch(error){$("qa-connection").textContent=error.message;}};
let selection=null,messages=[],busy=false,controller=null,activeTab=null,ready=false,selectionRevision=0;
function render(){
  $("qa-messages").replaceChildren();for(const message of messages){const card=el("div","");card.className="card";card.append(el("strong",message.role==="user"?"你":"Codex"),el("pre",message.content));$("qa-messages").append(card);}
}
async function setSelection(value){
  const revision=++selectionRevision;
  if(busy){controller?.abort();$("qa-status").textContent="选区变化，已停止上一条回复。";}
  if(value?.error){$("qa-status").textContent=value.error;return;}
  selection=SelectionQA.clean(value);const stored=await SelectionQA.load(selection);
  if(revision!==selectionRevision)return;
  messages=stored.messages;
  $("qa-summary").value=stored.summary;$("qa-title").textContent=selection.title;$("qa-quote").textContent=selection.quote;
  $("qa-context").textContent=`原文位置：${selection.documentKey}\n课程/方向目标：${selection.goal || "未提供"}\n附近段落：${selection.paragraph || "未提供"}`;
  $("qa-input").value=selection.initialQuestion || "";render();
}
async function loadActiveTab(){
  const [tab]=await chrome.tabs.query({active:true,currentWindow:true});activeTab=tab?.id;
  if(activeTab){const stored=await chrome.storage.session.get("qaPending:"+activeTab);if(stored["qaPending:"+activeTab])await setSelection(stored["qaPending:"+activeTab]);else {controller?.abort();selection=null;messages=[];$("qa-quote").textContent="";$("qa-context").textContent="";$("qa-title").textContent="当前页面尚未选择知识点。选中文字后使用右键菜单。";render();}}
}
$("qa-connect").onclick=async()=>{
  try{if(!confirm("允许本机Codex连接并检查登录？此步骤不发送选区正文。"))return;const status=await client.connect();ready=status.authenticated===true;$("qa-connection").textContent=status.notice;}
  catch(error){ready=false;$("qa-connection").textContent=error.message;}
};
async function send(){
  if(busy)return;if(!selection)throw new Error("请先选择要讨论的原文");
  if(!ready)throw new Error("请先连接Codex；未登录时可到工作台启动官方登录");
  const question=$("qa-input").value.trim();if(!question)throw new Error("请输入问题");
  const captured=selection,prior=[...messages];
  const stored=await chrome.storage.local.get("globalPersonalBackground");
  const background=$("qa-background").checked?stored.globalPersonalBackground?.summary || "未提供":"本次不带入个人背景";
  if(!confirm("发送当前选区、附近段落、课程目标、这段问答的最近记录和所勾选的背景摘要给Codex？不会发送主聊天或整份简历。"))return;
  if(captured!==selection)throw new Error("选区已变化，请重新提问");
  busy=true;controller=new AbortController();$("qa-send").disabled=true;$("qa-stop").disabled=false;
  const timer=setTimeout(()=>controller.abort(),125000);
  const next=[...prior.slice(-18),{role:"user",content:question}];
  render();const card=el("div","");card.className="card";const output=el("pre","");card.append(el("strong","Codex · 生成中"),output);$("qa-messages").append(card);
  try{
    const request=next.map(item=>({...item}));request[request.length-1].content=JSON.stringify({用户问题:question,当前目标:captured.goal,本人已确认背景:background});
    const reply=await client.stream({mode:"selection_qa",messages:request,samples:[`选区：${captured.quote}\n附近原文：${captured.paragraph}`]},event=>{
      if(event.type==="delta")output.textContent+=event.text;
      if(event.type==="status")$("qa-status").textContent=event.text;
    },controller.signal);
    const history=[...next,{role:"assistant",content:reply}];
    await SelectionQA.save(captured,history,captured===selection?$("qa-summary").value:"");
    if(captured===selection){messages=history;render();$("qa-input").value="";$("qa-status").textContent="独立问答已保存，主课程和主聊天未变化。";}
  }catch(error){$("qa-status").textContent=error.name==="AbortError"?"已停止，未完成回复不保存。":error.message;}
  finally{clearTimeout(timer);busy=false;controller=null;$("qa-send").disabled=false;$("qa-stop").disabled=true;}
}
$("qa-send").onclick=()=>send().catch(error=>{$("qa-status").textContent=error.message;});
for(const button of document.querySelectorAll("[data-question]"))button.onclick=()=>{$("qa-input").value=button.dataset.question;$("qa-input").focus();};
$("qa-stop").onclick=()=>controller?.abort();
$("qa-close").onclick=async()=>{controller?.abort();if(params.has("embed"))parent.postMessage({type:"selection-qa-close"},location.origin);else {
  try{if(!chrome.sidePanel.close)throw new Error("请用Chrome侧栏右上角关闭按钮收起");const current=await chrome.windows.getCurrent();await chrome.sidePanel.close({windowId:current.id});}catch(error){$("qa-status").textContent=error.message;}
}};
$("qa-return").onclick=async()=>{
  try{
    if(!selection)throw new Error("没有原文位置");
    if(params.has("embed")){parent.postMessage({type:"selection-qa-return",anchor:selection.anchor},location.origin);return;}
    if(!selection.tabId || !selection.anchor)throw new Error("原文定位不可用，请返回原标签页");
    await chrome.tabs.update(selection.tabId,{active:true});
    const results=await chrome.scripting.executeScript({target:{tabId:selection.tabId,frameIds:[selection.frameId || 0]},args:[selection.anchor],func:id=>{
      const anchor=globalThis.__jobCompanionQaAnchors?.[id];if(!anchor)return false;
      const selection=window.getSelection();selection.removeAllRanges();selection.addRange(anchor.range);anchor.range.startContainer.parentElement?.scrollIntoView({block:"center"});return true;
    }});
    if(!results[0]?.result)throw new Error("原页面已变化，无法恢复旧位置");
  }catch(error){$("qa-status").textContent=error.message;}
};
$("qa-note").onclick=async()=>{
  try{
    if(busy)throw new Error("请等待回复结束");if(!selection)throw new Error("没有当前选区");
    const summary=$("qa-summary").value.trim();if(!summary)throw new Error("请先填写自己的理解或仍有的疑问");
    if(!confirm("确认把原文选区和你编辑的理解收藏到笔记本？不会标记为已掌握，也不会复制到主聊天。"))return;
    await LearningNotebook.save({date:LearningNotebook.localDate(),direction:selection.direction,title:selection.quote.slice(0,100),kind:"knowledge",origin:"selection_qa",content:`原文：${selection.quote}\n\n我的理解 / 疑问：\n${summary}`});
    await SelectionQA.save(selection,messages,summary);$("qa-status").textContent="已收藏到今天的笔记本。";
  }catch(error){$("qa-status").textContent=error.message;}
};
$("qa-reset").onclick=async()=>{
  if(busy || !selection)return;if(!confirm("清空当前知识点问答？不会删除笔记本中的收藏。"))return;
  try{await chrome.storage.local.remove(await SelectionQA.key(selection));messages=[];$("qa-summary").value="";render();}catch(error){$("qa-status").textContent=error.message;}
};
chrome.storage.onChanged.addListener((changes,area)=>{if(area==="session" && activeTab && changes["qaPending:"+activeTab]?.newValue)setSelection(changes["qaPending:"+activeTab].newValue).catch(error=>{$("qa-status").textContent=error.message;});});
chrome.tabs.onActivated?.addListener(()=>{if(!params.has("embed"))loadActiveTab().catch(()=>{});});
window.addEventListener("beforeunload",()=>{controller?.abort();client.disconnect();});
(async()=>{
  if(params.has("request")){const key="qaRequest:"+params.get("request"),stored=await chrome.storage.session.get(key);if(stored[key]){await setSelection(stored[key]);await chrome.storage.session.remove(key);}else $("qa-status").textContent="选区请求已失效，请重新选择原文。";}
  else await loadActiveTab();
})().catch(error=>{$("qa-status").textContent=error.message;});
