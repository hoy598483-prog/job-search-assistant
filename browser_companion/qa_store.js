globalThis.SelectionQA = (()=>{
  function clean(selection){
    if(!selection || typeof selection.quote!=="string" || !selection.quote.trim())throw new Error("请先选择一段文字");
    return {id:selection.id || crypto.randomUUID(),quote:selection.quote.slice(0,6000),paragraph:String(selection.paragraph || "").slice(0,3000),
      documentKey:String(selection.documentKey || "").slice(0,1500),title:String(selection.title || "知识点问答").slice(0,200),
      goal:String(selection.goal || "").slice(0,1500),initialQuestion:String(selection.initialQuestion || "").slice(0,6000),direction:String(selection.direction || ""),tabId:selection.tabId ?? null,frameId:selection.frameId ?? 0,
      anchor:selection.anchor || null,created_at:new Date().toISOString()};
  }
  async function key(selection){
    const bytes=new TextEncoder().encode(JSON.stringify([selection.direction,selection.documentKey,selection.quote,selection.paragraph]));
    const hash=await crypto.subtle.digest("SHA-256",bytes);return "selectionQA:"+Array.from(new Uint8Array(hash),b=>b.toString(16).padStart(2,"0")).join("");
  }
  async function load(selection){const id=await key(selection),stored=await chrome.storage.local.get(id);return {key:id,messages:stored[id]?.messages || [],summary:stored[id]?.summary || ""};}
  async function save(selection,messages,summary=""){
    const id=await key(selection);
    if(!Array.isArray(messages) || messages.length>20)throw new Error("局部对话最多20条，请开启新的讨论或先整理摘要");
    await chrome.storage.local.set({[id]:{selection,messages,summary,updated_at:new Date().toISOString()}});
  }
  return {clean,key,load,save};
})();
