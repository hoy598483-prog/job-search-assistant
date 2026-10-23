/* Structured plan lifecycle; task completion remains user-reported. */
function parseWeeklyPlan(reply) {
  const start=reply.indexOf("<week_plan>"); if(start<0)return {text:reply};
  const text=reply.slice(0,start).trim(),end=reply.indexOf("</week_plan>",start);
  try {
    if(end<0)throw new Error("计划数据未完整返回");
    const plan=JSON.parse(reply.slice(start+11,end));
    if(typeof plan.project!=="string" || !plan.project.trim() || plan.project.length>200 || typeof plan.assumptions!=="string" || plan.assumptions.length>2000 || !Array.isArray(plan.tasks) || plan.tasks.length!==7)throw new Error("七天计划格式无效");
    const tasks=plan.tasks.map((task,index)=>{
      if(task.day!==index+1 || !Number.isInteger(task.minutes) || task.minutes<15 || task.minutes>240)throw new Error("每日预算或天数无效");
      const result={day:task.day,minutes:task.minutes,done:false};
      for(const key of ["title","action","artifact","acceptance"]){if(typeof task[key]!=="string" || !task[key].trim() || task[key].length>1200)throw new Error("每日任务信息缺失");result[key]=task[key].trim();}
      return result;
    });
    return {text,plan:{id:crypto.randomUUID(),project:plan.project.trim(),assumptions:plan.assumptions,tasks,status:"proposed",created_at:new Date().toISOString()}};
  }catch(error){return {text,error:error.message+"；未导入计划，请重新生成完整七天草案。"};}
}
async function updateDirectionRecord(update) {
  const id=$("workspace").value,stored=await chrome.storage.local.get("preparationDirections");
  const records=stored.preparationDirections || directions,record=records.find(item=>item.id===id);
  if(!record)throw new Error("当前方向不存在");
  const updated=update({...record});directions=records.map(item=>item.id===id?updated:item);
  await chrome.storage.local.set({preparationDirections:directions});
}
function weeklyPlanText(plan){return `${plan.project}\n${plan.assumptions}\n\n`+plan.tasks.map(task=>`第${task.day}天 · ${task.title}（建议${task.minutes}分钟）\n任务：${task.action}\n产出：${task.artifact}\n验收：${task.acceptance}`).join("\n\n");}
async function savePendingWeeklyPlan(plan){await updateDirectionRecord(record=>({...record,pendingWeeklyPlan:plan}));renderWeeklyPlans();}
async function markWeeklyTask(planId,day,done) {
  if(chatBusy)throw new Error("请等待当前回复结束");
  await updateDirectionRecord(record=>{
    if(record.weeklyPlan?.id!==planId)throw new Error("计划已变化，请刷新");
    const now=new Date();
    record.weeklyPlan={...record.weeklyPlan,tasks:record.weeklyPlan.tasks.map(task=>task.day!==day?task:{...task,done,
      completed_at:done?(task.completed_at || now.toISOString()):null,
      completed_on:done?(task.completed_on || LearningNotebook.localDate(now)):null})};
    record.progress=`本人标记完成${record.weeklyPlan.tasks.filter(task=>task.done).length}/7天；未经过自动验收。`;
    return record;
  });
  $("direction-progress").value=currentDirection().progress;renderWeeklyPlans();
}
function renderWeeklyPlans() {
  const record=currentDirection(),pending=record?.pendingWeeklyPlan;
  $("weekly-proposal").replaceChildren();$("weekly-accept").disabled=!pending || pending.status!=="proposed";$("weekly-revise").disabled=!pending;
  $("weekly-proposal").append(el("p",pending?(pending.status==="rejected"?"草案未采用，等待修改。":"待确认的一周计划"):"选定主项目后由Codex生成七天草案。"));
  if(pending)$("weekly-proposal").append(el("pre",weeklyPlanText(pending)));
  $("weekly-active").replaceChildren();
  const plan=record?.weeklyPlan;if(!plan){$("weekly-active").append(el("p","尚无已接受的七天计划。"));return;}
  $("weekly-active").append(el("h3",plan.project),el("p","勾选完成后按当天日期收集到学习笔记本；这代表本人自报完成。"));
  for(const task of plan.tasks){
    const card=el("div","");card.className="card";const label=el("label",""),checkbox=document.createElement("input");checkbox.type="checkbox";checkbox.checked=!!task.done;
    label.append(checkbox,el("span",`第${task.day}天 · ${task.title}（${task.minutes}分钟）· 本人标记完成`));
    checkbox.onchange=async()=>{checkbox.disabled=true;try{await markWeeklyTask(plan.id,task.day,checkbox.checked);}catch(error){checkbox.checked=!checkbox.checked;$("notice").textContent=error.message;}finally{checkbox.disabled=false;}};
    const lesson=el("button","打开当天课程 / 基础讲解与提问");
    lesson.onclick=()=>chrome.tabs.create({url:chrome.runtime.getURL("course.html")+`?direction=${encodeURIComponent(record.id)}&plan=${encodeURIComponent(plan.id)}&day=${task.day}`});
    card.append(label,el("p",`任务：${task.action}`),el("p",`产出：${task.artifact}`),el("p",`验收：${task.acceptance}`),lesson);$("weekly-active").append(card);
  }
}
async function adoptWeeklyPlan() {
  if(chatBusy)throw new Error("请等待当前回复结束");
  const pending=currentDirection()?.pendingWeeklyPlan;if(!pending || pending.status!=="proposed")throw new Error("没有待接受草案");
  await updateDirectionRecord(record=>{
    if(record.pendingWeeklyPlan?.id!==pending.id)throw new Error("草案已更新，请刷新");
    const history=[...(record.weeklyPlanHistory || [])];
    if(record.weeklyPlan)history.push(record.weeklyPlan);else if(record.plan)history.push({project:record.project,plan:record.plan,progress:record.progress,status:"previous_manual_record"});
    return {...record,weeklyPlanHistory:history,weeklyPlan:{...pending,status:"accepted",accepted_at:new Date().toISOString()},pendingWeeklyPlan:null,project:pending.project,plan:weeklyPlanText(pending),progress:"已接受计划，尚未开始。"};
  });
  renderDirections($("workspace").value);renderWeeklyPlans();$("chat-status").textContent="已接受并导入计划。";
}
function initializeWeeklyPlans() {
  bind("weekly-accept",adoptWeeklyPlan);
  bind("weekly-revise",async()=>{
    if(chatBusy)throw new Error("请等待当前回复结束");
    const feedback=prompt("你希望怎样修改计划？");if(!feedback?.trim())return;
    await updateDirectionRecord(record=>({...record,pendingWeeklyPlan:{...record.pendingWeeklyPlan,status:"rejected"}}));renderWeeklyPlans();
    $("chat-input").value=`我不接受当前七天草案，请按以下要求修改并重新给出完整七天计划：${feedback.trim()}`;
    if(codexReady)await sendChat();
  });
}
