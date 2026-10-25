"use strict";
const byId = id => document.getElementById(id);
let csrf = "", overview = null, current = null, draftItems = [], suggestions = [];
function status(message, bad=false){byId("notice").textContent=message;byId("notice").className=bad?"warn":"good";}
function node(tag,text="",cls=""){const e=document.createElement(tag);if(text)e.textContent=text;if(cls)e.className=cls;return e;}
async function api(path,body){
 const config=body===undefined?{method:"GET",credentials:"same-origin"}:
 {method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json","X-Review-CSRF":csrf},body:JSON.stringify(body)};
 const response=await fetch(path,config);const result=await response.json();
 if(!response.ok)throw Error(result.error||"Request failed");return result;
}
function shape(){return {quote:"",summary:"",kind:"unclear",relation:"single"};}
async function refresh(){
 overview=await api("/api/overview");csrf=overview.csrf_token;
 byId("summary").textContent="总数 "+overview.total+" · 人工确认 "+overview.reviewed+" · 未完成 "+overview.unreviewed;
 const list=byId("cases");list.replaceChildren();
 for(const c of overview.cases){
  const b=node("button","","case"+(current&&current.id===c.id?" selected":""));
  b.append(node("strong",c.title||c.id),node("small",(c.company?c.company+" · ":"")+c.status));
  b.onclick=()=>load(c.id).catch(e=>status(e.message,true));list.append(b);
 }
}
function renderItems(){
 const place=byId("items");place.replaceChildren();
 draftItems.forEach((item,index)=>{
  const box=node("div","","item"),quote=node("textarea"),summary=node("input");
  quote.rows=2;quote.value=item.quote;quote.oninput=()=>{item.quote=quote.value;};
  summary.value=item.summary;summary.oninput=()=>{item.summary=summary.value;};
  box.append(node("strong","条目 "+(index+1)),node("label","原文证据 quote"),quote,node("label","摘要 summary"),summary);
  const fields=node("div","","fields");
  for(const field of ["kind","relation"]){
   const options=field==="kind"?["duty","required","preferred","unclear"]:["single","any_of","all_of","unclear"];
   const wrapper=node("div"),sel=node("select");
   for(const value of options){const option=node("option",value);option.value=value;sel.append(option);}
   sel.value=item[field];sel.onchange=()=>{item[field]=sel.value;};
   wrapper.append(node("label",field),sel);fields.append(wrapper);
  }
  const remove=node("button","删除条目","remove");remove.onclick=()=>{draftItems.splice(index,1);renderItems();};
  box.append(fields,remove);place.append(box);
 });
}
function renderSuggestions(){
 const place=byId("suggestions");place.replaceChildren();
 if(!suggestions.length)return;
 place.append(node("p","AI 候选 "+suggestions.length+" 条，请核对引用和遗漏。","hint"));
 const list=node("ol");
 for(const s of suggestions)list.append(node("li","["+s.kind+" / "+s.relation+"] "+s.summary+" —— "+s.quote));
 const adopt=node("button","复制到编辑区（尚未审核）");
 adopt.onclick=()=>{if(!confirm("覆盖当前编辑区？这不是完成人工审核。"))return;
  draftItems=suggestions.map(x=>Object.assign({},x));renderItems();status("已复制建议。请通读全文检查遗漏。");};
 place.append(list,adopt);
}
async function load(id){
 current=await api("/api/case?id="+encodeURIComponent(id));
 draftItems=(current.items||[]).map(x=>Object.assign({},x));suggestions=[];
 byId("source").value=current.source||"";byId("note").value=current.note||"";
 const heading=byId("current");heading.replaceChildren(node("h2",current.title||id),
  node("p",(current.company||"未知公司")+" · "+current.annotation_status+" · "+id));
 const link=byId("source-link");link.removeAttribute("href");
 if(current.url&&/^https?:\/\//.test(current.url))link.href=current.url;
 byId("seed-notes").textContent=current.initial_ai_notes||"";
 renderItems();renderSuggestions();await refresh();
 status(current.source?"可编辑标注或生成新的预标注。":"尚无完整 JD：从来源页复制招聘正文，保存后再调用 Codex。");
}
async function saveSource(){
 if(!current)return;const source=byId("source").value;
 if(!source.trim())throw Error("请输入 JD 正文");
 if(!confirm("保存这份 JD 的原文？更换原文会清除该职位之前的草稿及确认状态。"))return;
 const result=await api("/api/source",{id:current.id,source});await load(current.id);
 status("已保存原文（"+result.length+" 字符）");
}
async function suggest(provider){
 if(!current||!current.source)throw Error("请先保存完整 JD 原文");
 let consent=false;
 if(provider==="codex"){consent=confirm("允许将当前 JD 文本发送给本机登录的 Codex 服务做初步提取？不发送人工标签、简历，不会自动确认。");if(!consent)return;}
 status("正在生成初步建议...");
 const res=await api("/api/suggest",{id:current.id,provider,consent});
 suggestions=res.suggested_items.map(x=>({quote:x.quote,summary:x.summary,kind:x.kind,relation:x.relation}));
 renderSuggestions();status("初步建议已生成，仍需逐条审阅。");
}
async function save(reviewed){
 if(!current)return;
 if(byId("source").value!==current.source)throw Error("JD 正文已变动，请先保存原文");
 let confirmed_complete=false;
 if(reviewed){confirmed_complete=confirm("确认你已通读完整 JD，检查每一项职责、要求、加分项以及是否存在遗漏或错误的 AND/OR，且引用逐字匹配原文？");if(!confirmed_complete)return;}
 const result=await api(reviewed?"/api/review":"/api/save",
   {id:current.id,items:draftItems,note:byId("note").value,confirmed_complete});
 await load(current.id);status(result.status==="reviewed"?"已人工确认 Gold Label。":"草稿已保存，尚未参与评分。");
}
async function exportReviewed(){
 const result=await api("/api/export",{});
 status("已导出 "+result.reviewed+"/"+result.total+" 条至 "+result.path);
}
function bind(id,fn){byId(id).onclick=()=>Promise.resolve(fn()).catch(e=>status(e.message,true));}
bind("save-source",saveSource);
bind("suggest-baseline",()=>suggest("baseline"));
bind("suggest-codex",()=>suggest("codex"));
bind("add",()=>{draftItems.push(shape());renderItems();});
bind("save",()=>save(false));
bind("review",()=>save(true));
bind("export",exportReviewed);
refresh().then(async()=>{if(overview.cases.length)await load(overview.cases[0].id);})
 .catch(e=>status(e.message,true));
