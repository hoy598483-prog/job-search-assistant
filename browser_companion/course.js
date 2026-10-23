const $=id=>document.getElementById(id),el=(tag,text)=>{const node=document.createElement(tag);node.textContent=text;return node;};
const params=new URLSearchParams(location.search),directionId=params.get("direction"),planId=params.get("plan"),day=Number(params.get("day")),client=new LocalCodexClient();
let direction=null,plan=null,task=null,course=null,busy=false,ready=false,controller=null;
const loginButton=el("button","启动官方登录");$("course-connect").after(loginButton);
loginButton.onclick=async()=>{try{if(busy || !confirm("允许启动本机Codex官方登录？完成后请再次点击连接检查。"))return;await client.connect();const result=await client.action("provider_login",{approved:true});$("course-connection").textContent=result.notice;}catch(error){$("course-connection").textContent=error.message;}};
function render(){
  if(!course)return;document.title=course.title+" · 每日课程";document.body.dataset.selectionDocumentKey="course:"+course.id;
  $("course-title").textContent=course.title;$("lesson-goal").textContent=course.goal;$("course-prerequisite").textContent=course.prerequisite_check;
  $("course-sections").replaceChildren();
  course.sections.forEach((section,index)=>{
    const card=el("section","");card.className="lesson-section";card.id="lesson-section-"+index;
    const answer=document.createElement("textarea");answer.maxLength=4000;answer.placeholder="先写下你的理解；提交给旁边的小助教讨论。";
    const ask=el("button","请助教检查我的回答");ask.onclick=()=>{
      if(!answer.value.trim()){$("course-status").textContent="请先写下自己的回答";return;}
      document.dispatchEvent(new CustomEvent("learning-question",{detail:{quote:section.question,paragraph:section.explanation+"\n例子："+section.example,elementId:card.id,question:`检查题：${section.question}\n我的回答：${answer.value}\n请指出正确和不足之处，先问一个能帮助我修正的问题，不要自动宣称掌握。`}}));
    };
    const example=el("pre",section.example);example.className="lesson-example";
    card.append(el("h2",`${index+1}. ${section.title}`),el("pre",section.explanation),el("h3","看一个例子"),example,el("h3","检查一下理解"),el("p",section.question),answer,ask);$("course-sections").append(card);
  });
  $("course-exercise").textContent=course.exercise;$("course-acceptance").textContent=course.acceptance;$("course-limitations").textContent=course.limitations;
  $("course-resources").replaceChildren();for(const resource of course.resources){const card=el("div","");card.className="card";const link=el("a",resource.title);link.href=resource.url;link.target="_blank";link.rel="noopener noreferrer";card.append(link,el("p",resource.note));$("course-resources").append(card);}
  $("course-adopt").disabled=course.status==="accepted";
  $("course-status").textContent=course.status==="accepted"?"已采用课程。学习和问答不会自动标记当天任务完成。":"课程草案，审阅后可采用；计划和进度尚未改变。";
}
$("course-connect").onclick=async()=>{try{if(!confirm("允许连接本机Codex并检查登录？此步骤不发送个人资料。"))return;const status=await client.connect();ready=status.authenticated===true;$("course-connection").textContent=status.notice;}catch(error){$("course-connection").textContent=error.message;}};
$("course-generate").onclick=async()=>{
  if(busy)return;
  try{
    if(!task)throw new Error("请从已接受的一周计划选择某一天");if(!ready)throw new Error("请先连接Codex");
    const allow_web=$("course-web").checked;
    if(!confirm(`把当天任务、已确认个人背景和当前方向目标交给Codex生成课程？${allow_web?"同时允许网络搜索课程资料，检索词可能包含学习目标。":"本次不联网。"}不会发送原始简历或自动修改计划。`))return;
    busy=true;controller=new AbortController();const timer=setTimeout(()=>controller.abort(),125000);$("course-generate").disabled=true;$("course-stop").disabled=false;$("course-adopt").disabled=true;
    const stored=await chrome.storage.local.get("globalPersonalBackground");
    try{
      $("course-stream").textContent="";
      const reply=await client.stream({mode:"course",allow_web,messages:[{role:"user",content:JSON.stringify({已接受的项目:plan.project,当天任务:task,目标岗位:direction.target,本人确认背景:stored.globalPersonalBackground?.summary || "未提供，请不要假设技能",教学偏好:"从我的基础开始讲解，例子之后只问一个理解检查问题，再给项目练习"})}],samples:[]},event=>{if(event.type==="delta")$("course-stream").textContent+=event.text;if(event.type==="status")$("course-status").textContent=event.text;},controller.signal);
      const parsed=LearningCourses.parse(reply);
      course={...parsed,id:crypto.randomUUID(),direction:directionId,planId,day,status:"draft",created_at:new Date().toISOString(),web_requested:allow_web};
      await LearningCourses.save(directionId,course);$("course-stream").textContent="";render();
    }finally{clearTimeout(timer);busy=false;controller=null;$("course-generate").disabled=false;$("course-stop").disabled=true;$("course-adopt").disabled=!course || course.status==="accepted";}
  }catch(error){$("course-status").textContent=error.name==="AbortError"?"已停止，未完成课程不保存。":error.message;}
};
$("course-stop").onclick=()=>controller?.abort();
$("course-adopt").onclick=async()=>{try{if(busy || !course)return;if(!confirm("采用这节课程？只保存课程版本，不标记任务完成。"))return;course={...course,status:"accepted",accepted_at:new Date().toISOString()};await LearningCourses.save(directionId,course);render();}catch(error){$("course-status").textContent=error.message;}};
window.addEventListener("beforeunload",()=>{controller?.abort();client.disconnect();});
(async()=>{
  const stored=await chrome.storage.local.get("preparationDirections");direction=stored.preparationDirections?.find(item=>item.id===directionId);
  plan=[direction?.weeklyPlan,...(direction?.weeklyPlanHistory || [])].find(item=>item?.id===planId);task=plan?.tasks?.find(item=>item.day===day);
  if(!task){$("course-status").textContent="找不到已接受的当天计划，请返回工作台选择。";$("course-generate").disabled=true;return;}
  $("course-task").textContent=`${direction.name} · ${plan.project} · 第${day}天：${task.title}`;
  const courses=await LearningCourses.list(directionId);course=courses.filter(item=>item.planId===planId && item.day===day).at(-1) || null;
  if(course)render();else $("course-status").textContent="尚未生成本节课程，连接Codex后开始。";
})().catch(error=>{$("course-status").textContent=error.message;});
