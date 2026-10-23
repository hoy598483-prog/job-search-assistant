/* Browser-local notebook. No model, service, token or uploaded resume required. */
globalThis.LearningNotebook = (() => {
  const key = "learningNotebookEntries";
  function localDate(value = new Date()) {
    const date = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(date.getTime())) return null;
    return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,"0")}-${String(date.getDate()).padStart(2,"0")}`;
  }
  function validDate(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value || "")) return false;
    const [year,month,day] = value.split("-").map(Number);
    const date = new Date(year,month-1,day);
    return date.getFullYear()===year && date.getMonth()===month-1 && date.getDate()===day;
  }
  async function save(entry) {
    if (!validDate(entry.date)) throw new Error("请选择有效日期");
    if (!entry.title?.trim() || !entry.content?.trim()) throw new Error("请填写标题和内容");
    if (entry.title.length>200 || entry.content.length>20000) throw new Error("标题最多200字，内容最多20000字");
    const stored = await chrome.storage.local.get(key);
    const entries = stored[key] || [];
    const duplicate = !entry.id && entry.origin==="user_archived_plan"
      ? entries.find(item=>item.origin===entry.origin && item.date===entry.date && item.direction===(entry.direction || "") && item.title===entry.title.trim() && item.content===entry.content.trim()) : null;
    const record = {id:entry.id || duplicate?.id || crypto.randomUUID(), date:entry.date,
      title:entry.title.trim(), content:entry.content.trim(),
      direction_name:entry.direction_name || entries.find(item=>item.id===entry.id)?.direction_name || "",
      direction:entry.direction || "", kind:["plan","task"].includes(entry.kind) ? entry.kind : "knowledge",
      created_at:entries.find(item=>item.id===entry.id)?.created_at || new Date().toISOString(),
      updated_at:new Date().toISOString(), origin:entry.origin || "manual"};
    await chrome.storage.local.set({[key]:[...entries.filter(item=>item.id!==record.id),record]});
    return record;
  }
  async function remove(id) {
    const stored = await chrome.storage.local.get(key);
    await chrome.storage.local.set({[key]:(stored[key] || []).filter(item=>item.id!==id)});
  }
  function completedEntries(directions) {
    const result = [], seen = new Set();
    for (const direction of directions) {
      const plans = [...(direction.weeklyPlanHistory || []), direction.weeklyPlan].filter(plan=>plan && Array.isArray(plan.tasks));
      for (const plan of plans) {
        const planId = plan.id || plan.created_at || JSON.stringify(plan.tasks);
        for (const task of plan.tasks.filter(task=>task.done)) {
          const id = `task:${direction.id}:${planId}:${task.day}`;
          if (seen.has(id)) continue; seen.add(id);
          result.push({id, direction:direction.id, kind:"task", automatic:true,
            date:task.completed_on || (task.completed_at ? localDate(task.completed_at) : null),
            title:`${plan.project || direction.project} · 第${task.day}天 · ${task.title}`,
            content:`任务：${task.action || "旧记录未保存"}\n产出：${task.artifact || "旧记录未保存"}\n验收标准：${task.acceptance || "旧记录未保存"}\n完成状态：本人标记完成，未经过自动验收。`});
        }
        if (plan.tasks.length===7 && plan.tasks.every(task=>task.done)) {
          const id=`plan:${direction.id}:${planId}`;
          if (seen.has(id)) continue; seen.add(id);
          const dates=plan.tasks.map(task=>task.completed_on || (task.completed_at ? localDate(task.completed_at) : null));
          result.push({id,direction:direction.id,kind:"plan",automatic:true,
            date:dates.every(Boolean) ? dates.sort().at(-1) : null,
            title:`已完成一周计划 · ${plan.project || direction.project}`,
            content:plan.tasks.map(task=>`第${task.day}天：${task.title}\n任务：${task.action}\n产出：${task.artifact}\n验收：${task.acceptance}`).join("\n\n") + "\n\n完成状态：本人标记全部完成，未经过自动验收。"});
        }
      }
    }
    return result;
  }
  async function all() {
    const stored = await chrome.storage.local.get([key,"preparationDirections"]);
    const directions=stored.preparationDirections || [];
    return {directions, entries:[...(stored[key] || []), ...completedEntries(directions)]};
  }
  return {localDate,validDate,save,remove,completedEntries,all};
})();
