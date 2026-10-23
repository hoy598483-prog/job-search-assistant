const $ = id=>document.getElementById(id);
const el = (tag,text)=>{const node=document.createElement(tag);node.textContent=text;return node;};
let editing=null, entries=[], directions=[], filtered=[];
function reset() {editing=null;$("note-title").value="";$("note-content").value="";$("note-date").value=LearningNotebook.localDate();$("note-save").textContent="保存笔记";}
function directionName(id) {return directions.find(direction=>direction.id===id)?.name || entries.find(entry=>entry.direction===id && entry.direction_name)?.direction_name || (id ? "原方向" : "通用知识");}
function render() {
  const query=$("filter-search").value.toLowerCase();
  filtered=entries.filter(entry=>(!$("filter-direction").value || entry.direction===$("filter-direction").value)
    && (!$("filter-date").value || entry.date===$("filter-date").value)
    && (entry.title+entry.content).toLowerCase().includes(query)).sort((a,b)=>(b.date || "").localeCompare(a.date || "") || a.title.localeCompare(b.title));
  $("note-list").replaceChildren();
  let previous;
  for(const entry of filtered) {
    const date=entry.date || "日期未知（旧记录未保存完成时间）";
    if(date!==previous) {$("note-list").append(el("h2",date));previous=date;}
    const card=el("div","");card.className="card";
    card.append(el("h3",entry.title),el("small",`${directionName(entry.direction)} · ${{task:"已完成任务",plan:"已完成计划",knowledge:"知识点 / 心得"}[entry.kind]}`),el("pre",entry.content));
    if(entry.origin==="deleted_direction_archive") card.append(el("small","原准备方向已删除，此处保留已完成任务与计划的归档。"));
    if(entry.automatic) card.append(el("small","来自计划完成记录；若误标完成，请返回工作台取消勾选。"));
    else {
      const edit=el("button","编辑"); edit.onclick=()=>{editing=entry.id;$("note-date").value=entry.date;$("note-title").value=entry.title;$("note-content").value=entry.content;$("note-kind").value=entry.kind;$("note-direction").value=entry.direction;$("note-save").textContent="保存修改";};
      const remove=el("button","删除");remove.onclick=async()=>{if(!confirm("删除这条笔记？"))return;try{await LearningNotebook.remove(entry.id);if(editing===entry.id)reset();await refresh();}catch(error){$("note-status").textContent=error.message;}};
      card.append(edit,remove);
    }
    $("note-list").append(card);
  }
  $("note-status").textContent=`共${filtered.length}条记录。${filtered.length ? "" : "可以先记录一条知识点，或在工作台标记完成任务。"}`;
}
async function refresh() {
  const result=await LearningNotebook.all();entries=result.entries;directions=result.directions;
  for(const id of ["note-direction","filter-direction"]) {
    const value=$(id).value;$(id).replaceChildren();
    const all=el("option",id==="note-direction"?"通用知识（所有方向可回顾）":"全部方向");all.value="";$(id).append(all);
    const archived = [...new Map(entries.filter(entry=>entry.direction && !directions.some(d=>d.id===entry.direction)).map(entry=>[entry.direction,{id:entry.direction,name:(entry.direction_name || "原方向")+"（已删除）"}])).values()];
    for(const direction of [...directions,...archived]) {const option=el("option",direction.name);option.value=direction.id;$(id).append(option);}
    $(id).value=value;
  }
  render();
}
$("note-save").onclick=async()=>{
  $("note-save").disabled=true;
  try {
    if($("note-kind").value==="plan" && !confirm("确认这份计划已由本人完成？此记录不代表自动验收通过。"))return;
    await LearningNotebook.save({id:editing,date:$("note-date").value,direction:$("note-direction").value,kind:$("note-kind").value,title:$("note-title").value,content:$("note-content").value});
    reset();await refresh();
  } catch(error){$("note-status").textContent=error.message;}finally{$("note-save").disabled=false;}
};
$("note-reset").onclick=reset;
$("note-refresh").onclick=()=>refresh().catch(error=>{$("note-status").textContent=error.message;});
for(const id of ["filter-direction","filter-date","filter-search"]) $(id).addEventListener("input",render);
$("note-export").onclick=()=>{
  const text="# 学习笔记本\n\n"+filtered.map(entry=>`## ${entry.date || "日期未知"} · ${entry.title}\n\n方向：${directionName(entry.direction)}\n\n${entry.content}\n`).join("\n");
  const url=URL.createObjectURL(new Blob([text],{type:"text/markdown;charset=utf-8"}));
  const link=el("a","");link.href=url;link.download=`学习笔记-${LearningNotebook.localDate()}.md`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
chrome.storage.onChanged?.addListener((changes,area)=>{if(area==="local" && (changes.learningNotebookEntries || changes.preparationDirections)) refresh().catch(error=>{$("note-status").textContent=error.message;});});
reset();refresh().catch(error=>{$("note-status").textContent=error.message;});
