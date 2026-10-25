const $ = id => document.getElementById(id);
let pages = [];
let nativePort = null;
let serviceToken = null;
let servicePort = null;
let authorizedProvider = null;
let connecting = null;
let codexReady = false;
let directions = [{id:"ai-product-job-agent", name:"AI 产品求职", target:"", background:"", project:"", plan:"", progress:""}];
let directionReady = false;
const currentDirection = () => directions.find(direction => direction.id === $("workspace").value);
const captureKey = () => "pages:" + $("workspace").value;
$('extension').textContent = `扩展 ID：${chrome.runtime.id}。首次安装 Native Host 后，重新加载扩展即可自动连接`;
async function establishConnection() {
  try {
    codexReady = false;
    $("chat-send").disabled = true;
    $("chat-projects").disabled = true;
    serviceToken = null;
    servicePort = null;
    const result = await new Promise((resolve, reject) => {
      if (nativePort) { nativePort.disconnect(); nativePort = null; }
      const port = chrome.runtime.connectNative("com.local.job_companion");
      nativePort = port;
      const timeout = setTimeout(() => { port.disconnect(); reject(new Error("Native Host 超时")); }, 5000);
      port.onMessage.addListener(message => { clearTimeout(timeout); message.error ? reject(new Error(message.error)) : resolve(message); });
      port.onDisconnect.addListener(() => { if (chrome.runtime.lastError) { clearTimeout(timeout); reject(new Error(chrome.runtime.lastError.message)); } });
      port.postMessage({action: "handshake", extension_id: chrome.runtime.id});
    });
    if (!result || !result.token) throw new Error("本机服务拒绝握手");
    serviceToken = result.token;
    servicePort = result.port;
    $("token").value = "已自动连接";
    $("notice").textContent = "本机桥接已连接；模型登录尚未验证";
    return true;
  } catch (error) {
    console.warn("Native Messaging handshake failed", error);
    $("token").value = "";
    $("token").placeholder = "Native Host 未连接";
    $("notice").textContent = `无法自动连接：${error?.message || "请检查 Native Host 注册"}`;
    return false;
  }
}
$("notice").textContent = "文本可直接保存到本机浏览器，无需连接服务";
$("provider").onchange = async () => {
  authorizedProvider = null;
  const provider = $("provider").value;
  if (provider === "mock") return;
  if (provider === "claude") {
    $("notice").textContent = "Claude Code 连接尚未实现；当前可连接 Codex。文本仍可本地保存。";
    $("provider").value = "mock";
    return;
  }
  const label = provider === "codex" ? "本机 Codex CLI（使用已有官方登录）" : "本机 API 后端（可能另行计费）";
  if (!confirm(`允许此工作台连接${label}？\n仅在点击分析并再次确认后发送选中文本。不会读取你的登录凭据，也不会自动投递。`)) {
    $("provider").value = "mock";
    return;
  }
  connecting = establishConnection();
  const connected = await connecting;
  connecting = null;
  if (connected) {
    authorizedProvider = provider;
    if (provider === "codex") {
      try { await checkCodexLogin(); }
      catch (error) { $("notice").textContent = error.message; }
    }
    else $("notice").textContent = "本机桥接已连接；API 可用性尚未验证";
  } else {
    $("provider").value = "mock";
  }
};
$("forget-token").onclick = async () => { serviceToken = null; $("token").value = ""; await establishConnection(); };
const el = (tag, text) => { const node = document.createElement(tag); node.textContent = text; return node; };
async function checkCodexLogin() {
  $("provider-status").textContent = "正在检查 Codex 官方 CLI 登录…";
  try {
    const status = await api("provider_status");
    codexReady = status.authenticated === true;
    $("chat-send").disabled = !codexReady;
    $("chat-projects").disabled = !codexReady;
    $("provider-status").textContent = status.notice;
    $("notice").textContent = status.notice;
  } catch (error) {
    $("provider-status").textContent = `无法验证 Codex 登录：${error.message}`;
    throw error;
  }
}
bind("provider-check", async () => {
  if (!nativePort && !await establishConnection()) throw new Error("请先连接本机桥接");
  await checkCodexLogin();
});
bind("provider-login", async () => {
  if (!confirm("允许启动本机 Codex 官方登录？登录由官方 CLI 和浏览器完成，扩展不接收你的密码。")) return;
  if (!nativePort && !await establishConnection()) throw new Error("请先连接本机桥接");
  const result = await api("provider_login", {approved:true});
  $("provider-status").textContent = result.notice;
});
async function api(action, data = {}, retried = false) {
  if (!currentDirection() && !["provider_status", "provider_login"].includes(action)) throw new Error("请先新建或选择准备方向");
  if (["save", "list", "status", "delete"].includes(action)) {
    const workspace = $("workspace").value;
    const key = "textSamples:" + workspace;
    const stored = await chrome.storage.local.get(key);
    let jobs = stored[key] || [];
    if (action === "list") return {jobs};
    if (action === "save") {
      const text = data.page.text;
      if (typeof text !== "string" || !text.trim()) throw new Error("请先输入文本");
      const existing = jobs.find(job => job.text === text);
      if (!existing) jobs.push({id: crypto.randomUUID(), text, source_url: (String(data.page.url || "").startsWith("https://") || String(data.page.url || "").startsWith("http://")) ? data.page.url.slice(0, 4096) : null, source_title: String(data.page.title || "").slice(0, 300), captured_at: String(data.page.captured_at || "").slice(0, 80), saved_at: new Date().toISOString(), status: "saved"});
    } else if (action === "delete") {
      jobs = jobs.filter(job => job.id !== data.id);
    } else {
      const job = jobs.find(job => job.id === data.id);
      if (job) job.status = data.status;
    }
    await chrome.storage.local.set({[key]: jobs});
    return {notice: "文本已保存到本机浏览器"};
  }
  if (connecting) await connecting;
  if (!serviceToken || serviceToken === "已自动连接") throw new Error("本机服务尚未连接");
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), ["analyze", "chat", "resume_analyze"].includes(action) ? 150000 : 20000);
  let response, result;
  try {
    response = await fetch(`http://127.0.0.1:${servicePort}/action`, {signal: controller.signal, method: "POST", headers: {"Content-Type": "application/json", Authorization: "Bearer " + serviceToken}, body: JSON.stringify({action, workspace: $("workspace").value || "learning-assistant", direction:currentDirection(), ...data})});
    result = await response.json();
  } catch (error) {
    throw new Error(error.name === "AbortError" ? "本机服务响应超时，请检查连接；文本收藏仍可使用。" : `本机请求失败：${error.message}`);
  } finally { clearTimeout(timeout); }
  if (!response.ok) {
    if (response.status === 403) {
      serviceToken = null;
      servicePort = null;
      if (!retried && await establishConnection()) {
        return api(action, data, true);
      }
      throw new Error(`本机服务拒绝连接：${result.error || "身份验证失败"}。自动重连未恢复，请检查 Native Host 注册。`);
    }
    throw new Error(result.error || "本机服务失败");
  }
  return result;
}
function bind(id, fn) {
  $(id).onclick = async () => {
    $(id).disabled = true; $("workspace").disabled = true; $("notice").textContent = "处理中…";
    try { await fn(); $("notice").textContent = "完成"; }
    catch(error) { $("notice").textContent = error.message; }
    finally {
      $(id).disabled = ["chat-send","chat-projects"].includes(id) ? !codexReady || chatBusy : false;
      $("workspace").disabled = chatBusy || !directions.length;
      $("direction-delete").disabled = chatBusy || !currentDirection();
      if(["weekly-accept","weekly-revise"].includes(id))renderWeeklyPlans();
    }
  };
}
function link(url, title) {
  const a = el("a", title); a.href = url; a.target = "_blank"; a.rel = "noopener noreferrer"; return a;
}
async function refresh() {
  if (!currentDirection()) { pages=[]; $("pages").replaceChildren(); return; }
  const captured = await chrome.storage.session.get(captureKey());
  pages = captured[captureKey()] || [];
  $("pages").replaceChildren();
  pages.forEach((page, index) => {
    const card = el("div", ""); card.className = "card";
    const selected = document.createElement("input"); selected.type = "checkbox"; selected.checked = true; selected.id = `selected-${index}`;
    const title = el("label", ""); title.append(selected, el("span", page.title));
    const text = document.createElement("textarea"); text.value = page.text; text.oninput = () => { page.text = text.value; };
    const save = el("button", "保存当前原文"); save.onclick = async () => {
      if (!confirm("将当前文本样本保存到此工作分区？")) return;
      try { $("notice").textContent = (await api("save", {page, approved:true})).notice; } catch(e) { $("notice").textContent = e.message; }
    };
    card.append(title, el("p", "文本样本"), text, save); $("pages").append(card);
  });
}
bind("refresh", refresh);
bind("clear", async () => { await chrome.storage.session.remove(captureKey()); pages=[]; $("results").replaceChildren(); await refresh(); });
bind("analyze", async () => {
  const selected = pages.filter((p,i) => $(`selected-${i}`).checked);
  if (!selected.length) throw new Error("请至少选择一页");
  const provider = $("provider").value;
  if (provider !== "mock" && !confirm(`将 ${selected.length} 页当前文本发送给 ${provider}？API 模式可能另行计费。`)) return;
  const result = await api("analyze", {pages:selected, provider, approved:provider !== "mock"});
  $("results").replaceChildren();
  for (const item of result.results) {
    const card = el("div", ""); card.className="card"; card.append(el("h3","文本分析结果"),el("p",`Provider: ${item.provider} · 文本样本 · 语义待审阅`));
    if(item.notice) card.append(el("p",item.notice));
    for(const row of item.items) card.append(el("p",`${row.kind} / ${row.relation}：${row.summary}`),el("blockquote",row.quote));
    if(!item.items.length) card.append(el("p","没有提取到可展示要求；请检查原文或选择模型分析。"));
    $("results").append(card);
  }
});
bind("saved", async () => {
  const result=await api("list"); $("jobs").replaceChildren();
  for(const job of result.jobs) {
    const card=el("div",""); card.className="card"; card.append(el("h3", "已收藏文本"));
    const status=document.createElement("select");
    for(const value of ["saved","considering","applied_manually","interview","offer","rejected","archived"]) {const option=el("option",value);option.value=value;status.append(option);} status.value=job.status;
    const save=el("button","记录状态");save.onclick=async()=>{if(!confirm("仅记录你已完成的操作，不会代为投递。确认保存？"))return;try{await api("status",{id:job.id,status:status.value,approved:true});$("notice").textContent="已记录";}catch(e){$("notice").textContent=e.message;}};
    const original = el("pre", job.text); original.style.whiteSpace = "pre-wrap";
    const remove = el("button", "删除文本");
    remove.onclick = async () => {
      if (!confirm("删除这个文本样本？")) return;
      try { await api("delete", {id:job.id}); card.remove(); $("notice").textContent="已删除"; }
      catch(e) { $("notice").textContent=e.message; }
    };
    card.append(original,status,save,remove);$("jobs").append(card);
  }
});
function renderTraining(state) {
  $("training").replaceChildren();
  const plan=state.plans.find(p=>p.id===state.active_plan_id);
  if(!plan){$("training").append(el("p","尚未采用训练计划。"));return;}
  for(const task of plan.report.tasks){
    const card=el("div","");card.className="card";
    card.append(el("h3",`第 ${task.day} 天 · ${task.title}`),el("p",`${task.action}（${task.minutes} 分钟）`),el("p",task.scope),el("p",`产出：${task.artifact}`),el("p",`验收：${task.acceptance}`));
    for(const entry of state.submissions.filter(s=>s.plan_id===plan.id&&s.task_index===task.day-1))card.append(el("p",`成果：${entry.text} · ${entry.status === "awaiting_review" ? "待审阅" : entry.status}`));
    $("training").append(card);
  }
  $("training").append(el("small",`保留 ${state.plans.length} 个计划版本。请在当前聊天中提交证据供审阅，浏览器不能自行批准成果。`));
}
bind("train",async()=>{
  $("options").replaceChildren(el("p", "正在获取项目候选…"));
  let result;
  try {
    result = await api("training");
    if (!Array.isArray(result.options)) throw new Error("服务未返回项目候选，请更新本机服务");
  } catch (error) {
    $("options").replaceChildren(el("p", error.message));
    throw error;
  }
  $("options").replaceChildren(el("p",result.notice));
  for(const option of result.options){
    const card=el("div","");card.className="card";
    card.append(el("h3",option.title),el("p",option.reason),el("p",`产出：${option.deliverable} · 难度：${option.difficulty}`));
    const choose=el("button","选择并生成计划草案"); choose.onclick=async()=>{
      const minutes=Number($("minutes").value);
      if(!confirm(`选择“${option.title}”，生成每天 ${minutes} 分钟的七天计划草案？此时还不会采用。`))return;
      try { const draft=await api("propose",{project_id:option.id,minutes,approved:true});
        const adopt=el("button","确认采用这个计划"); adopt.onclick=async()=>{if(!confirm("确认采用此计划？采用后才会成为当前计划。"))return;await api("adopt",{plan_id:draft.plan.id,approved:true});renderTraining(await api("progress"));};
        card.append(el("p",draft.notice),adopt); $("notice").textContent="计划草案已生成，请审阅后选择是否采用。";
      } catch(e){$("notice").textContent=e.message;}
    }; card.append(choose);$("options").append(card);
  }
});
bind("progress",async()=>{renderTraining(await api("progress"));});
bind("submit",async()=>{if(!confirm("保存成果并提交审阅？不会自动标记通过。"))return;await api("submit",{day:Number($("day").value),text:$("submission").value,approved:true});renderTraining(await api("progress"));});

let chatMessages = [];
let chatSamples = [];
let chatBusy = false;
let chatController = null;
const cancelChat = el("button", "停止生成");
cancelChat.disabled = true;
cancelChat.onclick = () => chatController?.abort();
$("chat-send").after(cancelChat);
const chatKey = () => "codexChat:" + $("workspace").value;
function renderChat() {
  $("chat-history").replaceChildren();
  for (const message of chatMessages) {
    const card = el("div", ""); card.className = "card";
    card.append(el("strong", message.role === "user" ? "你" : "Codex"), el("pre", message.content));
    $("chat-history").append(card);
  }
}
async function loadChatContext() {
  const {jobs} = await api("list");
  chatSamples = jobs;
  $("chat-context").replaceChildren(el("small", `${jobs.length} 份本地样本，勾选后才会发送（每次最多十份）。`));
  jobs.forEach((sample, index) => {
    const label = el("label", "");
    const checkbox = document.createElement("input"); checkbox.type = "checkbox";
    checkbox.id = `chat-sample-${index}`;
    label.append(checkbox, el("span", `样本 ${index + 1} · ${sample.text.slice(0, 100)}`));
    $("chat-context").append(label);
  });
}
bind("connect-codex", async () => {
  if (!confirm("允许连接本机 Codex 并检查登录？此步骤不发送样本文本。")) return;
  $("provider").value = "codex";
  if (!await establishConnection()) throw new Error("本机桥接连接失败，请查看上方连接状态");
  await checkCodexLogin();
  $("chat-status").textContent = codexReady ? "Codex 已登录，可以发送消息；模型调用尚未验证。" : "请启动官方登录，然后重新检查。";
});
async function sendChat(projects = false) {
  if (!currentDirection()) throw new Error("请先新建准备方向");
  if (chatBusy) return;
  if(!projects && /^(接受|接受计划|接受这个计划|确认采用|确认采用计划|确认采用这个计划)[。！!\s]*$/.test($("chat-input").value.trim()) && currentDirection().pendingWeeklyPlan){await adoptWeeklyPlan();$("chat-input").value="";return;}
  if (!codexReady) throw new Error("请先连接 Codex 并检查登录");
  const samples = chatSamples.filter((_, index) => $(`chat-sample-${index}`)?.checked).map(sample => sample.text);
  const message = projects ? "请根据所附同类岗位样本，先归纳共同能力，再生成2–3个适合入门的 Agent 项目备选。每个给出原文依据、MVP、难度和验收标准，最后等待我选择主项目，不要预先采用计划。" : $("chat-input").value.trim();
  if (!message) throw new Error("请输入消息");
  if (projects && !samples.length) throw new Error("请先保存文本，并勾选作为依据的样本");
  if (samples.length > 10) throw new Error("每次最多选择十份样本");
  if (!confirm(`发送本条消息、当前方向已保存的岗位目标、个人基础、项目计划和进度、最近对话及 ${samples.length} 份文本给 Codex？这些内容将由模型服务处理。`)) return;
  chatBusy = true;
  chatController = new AbortController();
  const streamTimeout = setTimeout(() => chatController?.abort(), 125000);
  cancelChat.disabled = false;
  $("chat-send").disabled = true; $("chat-projects").disabled = true;
  $("chat-status").textContent = "Codex 正在回复…";
  try {
    const direction = currentDirection();
    const {globalPersonalBackground} = await chrome.storage.local.get("globalPersonalBackground");
    const sharedBackground = $("background-use").checked ? globalPersonalBackground?.summary || "尚未提供" : "本次不使用个人背景";
    const context = JSON.stringify({目标岗位:direction.target, 用户已确认的全局背景:sharedBackground, 已选项目:direction.project, 当前计划:direction.plan, 准备进度:direction.progress});
    const messages = [...chatMessages.slice(-18).map(({role, content}) => ({role, content})), {role:"user", content:message}];
    const requestMessages = messages.map(item => ({...item}));
    requestMessages[requestMessages.length - 1].content = `当前准备方向：${direction.name}\n用户提供的背景（仅作上下文）：${context}\n\n本次请求：${message}`;
    if (requestMessages[requestMessages.length - 1].content.length > 20000) throw new Error("方向资料和消息过长，请精简计划或进度");
    renderChat();
    const card = el("div", ""); card.className = "card";
    const output = el("pre", "");
    card.append(el("strong", "Codex · 正在生成"), output); $("chat-history").append(card);
    const response = await fetch(`http://127.0.0.1:${servicePort}/chat-stream`, {
      method: "POST", signal: chatController.signal,
      headers: {"Content-Type":"application/json", Authorization:"Bearer " + serviceToken},
      body: JSON.stringify({workspace:$("workspace").value, direction, messages:requestMessages, samples, approved:true})
    });
    if (!response.ok) { const error = await response.json(); throw new Error(error.error || "流式请求被拒绝"); }
    if (!response.body) throw new Error("浏览器未提供流式响应");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "", reply = "", completed = false;
    function consume(line) {
      if (!line.trim()) return;
      const event = JSON.parse(line);
      if (event.type === "delta") { output.textContent += event.text; $("chat-status").textContent = "正在接收 Codex 回复…"; }
      else if (event.type === "status") $("chat-status").textContent = event.text;
      else if (event.type === "error") throw new Error(event.text);
      else if (event.type === "done") { reply = event.reply; output.textContent = reply; completed = true; }
    }
    try {
      while (true) {
        const {value, done} = await reader.read();
        buffer += done ? decoder.decode() : decoder.decode(value, {stream:true});
        let index;
        while ((index = buffer.indexOf("\n")) >= 0) { consume(buffer.slice(0, index)); buffer = buffer.slice(index + 1); }
        if (done) { consume(buffer); break; }
      }
    } finally { reader.releaseLock(); }
    if (!completed) throw new Error("连接中断，当前回复未完成，未写入对话历史");
    const parsed=parseWeeklyPlan(reply);
    if(parsed.plan)await savePendingWeeklyPlan(parsed.plan);
    chatMessages = [...messages, {role:"assistant", content:parsed.text}];
    await chrome.storage.local.set({[chatKey()]: chatMessages});
    renderChat(); $("chat-input").value = "";
    $("chat-status").textContent = parsed.error || (parsed.plan?"七天计划草案已生成，等待接受或修改。":"Codex 调用成功；项目建议尚未采用。");
  } catch (error) {
    const message = error.name === "AbortError" ? "已停止生成或达到超时限制；未完成回复不写入历史。" : error.message;
    $("chat-status").textContent = message;
    throw new Error(message);
  } finally {
    clearTimeout(streamTimeout); chatController = null; cancelChat.disabled = true;
    chatBusy = false; $("chat-send").disabled = !codexReady; $("chat-projects").disabled = !codexReady;
  }
}
bind("chat-context-refresh", loadChatContext);
bind("chat-send", () => sendChat());
bind("chat-projects", () => sendChat(true));
bind("chat-clear", async () => {
  if (chatBusy) throw new Error("请等待当前回复结束");
  if (!confirm("清空本分区的本地对话？不会删除文本样本。")) return;
  chatMessages = []; await chrome.storage.local.remove(chatKey()); renderChat();
});
async function restoreChat() {
  const stored = await chrome.storage.local.get(chatKey());
  chatMessages = stored[chatKey()] || []; renderChat(); await loadChatContext();
}
function renderDirections(id) {
  $("workspace").replaceChildren();
  for (const direction of directions) { const option = el("option", direction.name); option.value = direction.id; $("workspace").append(option); }
  $("workspace").value = id || "";
  $("workspace").disabled = !directions.length;
  const direction = currentDirection();
  $("direction-delete").disabled = !direction;
  for (const field of ["name", "target", "project", "plan", "progress"]) $("direction-" + field).value = direction?.[field] || "";
}
async function showDirection() {
  $("jobs").replaceChildren(); $("results").replaceChildren(); $("options").replaceChildren(); $("training").replaceChildren();
  $("chat-input").value = ""; $("submission").value = "";
  if (!currentDirection()) {
    pages=[]; chatMessages=[]; chatSamples=[]; renderChat(); $("pages").replaceChildren(); $("chat-context").replaceChildren();
    renderWeeklyPlans();
    $("direction-status").textContent="尚无准备方向，请点击“新建准备方向”。个人背景和学习笔记仍可使用。";
    return;
  }
  await refresh(); await restoreChat();
  renderWeeklyPlans();
  $("direction-status").textContent = `当前方向：${currentDirection().name}。样本、对话、计划与进度分别保存。`;
}
$("workspace").onchange = async () => {
  if (chatBusy) return;
  try { renderDirections($("workspace").value); await chrome.storage.local.set({activeDirection:$("workspace").value}); await showDirection(); }
  catch(error) { $("direction-status").textContent = error.message; }
};
bind("direction-new", async () => {
  if (!directionReady || chatBusy) throw new Error("请等待当前操作结束");
  const name = prompt("新准备方向的名称（例如：Agent 开发工程师）");
  if (!name?.trim()) return;
  if (name.trim().length > 80) throw new Error("方向名称最多80字");
  const direction = {id:"direction-" + crypto.randomUUID(), name:name.trim(), target:"", background:"", project:"", plan:"", progress:""};
  const stored = await chrome.storage.local.get("preparationDirections");
  directions = stored.preparationDirections || directions;
  directions.push(direction);
  await chrome.storage.local.set({preparationDirections:directions, activeDirection:direction.id});
  renderDirections(direction.id); await showDirection();
});
bind("direction-delete", async () => {
  if (!directionReady || chatBusy) throw new Error("请等待当前回复或操作结束");
  const selected = currentDirection();
  if (!selected) throw new Error("没有可删除的方向");
  if (!confirm(`删除“${selected.name}”？\n将清除本浏览器中该方向的文本样本、主对话、课程、计划和进度。\n个人背景、学习笔记及已完成任务的归档会保留。此操作不可撤销。`)) return;
  const stored = await chrome.storage.local.get(["preparationDirections", "learningNotebookEntries"]);
  const records = stored.preparationDirections || [];
  const record = records.find(item=>item.id===selected.id);
  if (!record) throw new Error("此方向已被删除，请刷新工作台");
  const notes = stored.learningNotebookEntries || [];
  const archives = LearningNotebook.completedEntries([record]).filter(item=>!notes.some(note=>note.id===item.id))
    .map(item=>({...item, automatic:false, direction_name:record.name, origin:"deleted_direction_archive"}));
  directions = records.filter(item=>item.id!==record.id);
  // Save notebook snapshots before removing the plan that supplies derived entries.
  await chrome.storage.local.set({learningNotebookEntries:[...notes.map(note=>note.direction===record.id?{...note,direction_name:record.name}:note),...archives], preparationDirections:directions, activeDirection:directions[0]?.id || null});
  await chrome.storage.local.remove(["textSamples:", "codexChat:", "learningCourses:"].map(prefix=>prefix+record.id));
  await chrome.storage.session.remove("pages:"+record.id);
  renderDirections(directions[0]?.id); await showDirection();
});
async function saveDirection(fields) {
  if (chatBusy) throw new Error("请等待当前回复结束再修改方向资料");
  if (!currentDirection()) throw new Error("请先新建准备方向");
  const direction = {...currentDirection()};
  for (const field of fields) direction[field] = $("direction-" + field).value.trim();
  if (!direction.name) throw new Error("请填写方向名称");
  // Read latest registry so editing this direction preserves other tabs' directions.
  const stored = await chrome.storage.local.get("preparationDirections");
  directions = stored.preparationDirections || directions;
  if (!directions.some(item => item.id === direction.id)) throw new Error("此方向已被删除，请刷新工作台");
  directions = directions.map(item => item.id === direction.id ? direction : item);
  await chrome.storage.local.set({preparationDirections:directions});
  renderDirections(direction.id);
  $("direction-status").textContent = "当前方向信息已保存";
}
bind("direction-save", () => saveDirection(["name", "target"]));
bind("direction-plan-save", () => saveDirection(["project", "plan", "progress"]));
async function initializeDirections() {
  const stored = await chrome.storage.local.get(["preparationDirections", "activeDirection"]);
  directions = Array.isArray(stored.preparationDirections) ? stored.preparationDirections : directions;
  const id = directions.some(item => item.id === stored.activeDirection) ? stored.activeDirection : directions[0]?.id || null;
  await chrome.storage.local.set({preparationDirections:directions, activeDirection:id});
  const legacy = await chrome.storage.session.get(["pages", "pages:ai-product-job-agent"]);
  if (directions.some(item=>item.id==="ai-product-job-agent") && legacy.pages && !legacy["pages:ai-product-job-agent"]) {
    await chrome.storage.session.set({"pages:ai-product-job-agent":legacy.pages});
    await chrome.storage.session.remove("pages");
  }
  renderDirections(id); await showDirection(); directionReady = true;
}
initializeDirections().catch(error => { $("direction-status").textContent = error.message; });


$("background-open").onclick = () => chrome.tabs.create({url:chrome.runtime.getURL("background.html")});
async function showBackgroundSummary() {
  const {globalPersonalBackground} = await chrome.storage.local.get("globalPersonalBackground");
  $("background-summary-status").textContent = globalPersonalBackground
    ? "已保存本人确认的背景，所有方向可共用。"
    : "尚无已确认背景，请打开个人背景页面建立。";
}
chrome.storage.onChanged?.addListener((changes, area) => {
  if (area === "local" && changes.globalPersonalBackground) showBackgroundSummary();
});
showBackgroundSummary().catch(error => { $("background-summary-status").textContent = error.message; });
initializeWeeklyPlans();
$("notebook-open").onclick=()=>chrome.tabs.create({url:chrome.runtime.getURL("notebook.html")});
bind("notebook-collect",async()=>{
  const selection=window.getSelection()?.toString().trim();
  const content=selection || [...chatMessages].reverse().find(message=>message.role==="assistant")?.content;
  if(!content)throw new Error("请选中文字或先获取一条Codex回复");
  if(!selection && !confirm("未选中文字，将收藏最新Codex回复为待整理的知识笔记，不代表已掌握。确认保存？"))return;
  const title=prompt("这条知识笔记的标题：");if(!title?.trim())return;
  await LearningNotebook.save({date:LearningNotebook.localDate(),direction:$("workspace").value,kind:"knowledge",title,content,origin:"chat_collection"});
  $("chat-status").textContent="已收藏到今天的学习笔记本。";
});
bind("notebook-archive",async()=>{
  const direction=currentDirection(),content=$("direction-plan").value.trim();
  if(!content)throw new Error("请先填写或导入计划");
  if(!confirm("确认此计划已由本人完成？将按今天日期收集计划及进度快照，不代表自动验收通过。"))return;
  await LearningNotebook.save({date:LearningNotebook.localDate(),direction:direction.id,kind:"plan",title:`已完成计划 · ${$("direction-project").value || direction.name}`,content:content+"\n\n成果与进度：\n"+$("direction-progress").value,origin:"user_archived_plan"});
});
