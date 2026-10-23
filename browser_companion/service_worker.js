const MENU_ID="job-companion-explain-selection";
chrome.runtime.onInstalled.addListener(()=>{
  chrome.contextMenus.removeAll(()=>chrome.contextMenus.create({id:MENU_ID,title:"用 Codex 解释这段内容",contexts:["selection"],documentUrlPatterns:["http://*/*","https://*/*"]}));
});
chrome.contextMenus.onClicked.addListener((info,tab)=>{
  if(info.menuItemId!==MENU_ID || !info.selectionText || !tab?.id)return;
  // Invoke directly in the user gesture; never delay open behind a network request.
  const opening=chrome.sidePanel.open({tabId:tab.id});
  capture(info,tab).catch(error=>chrome.storage.session.set({["qaPending:"+tab.id]:{error:error.message}}));
  opening.catch(()=>{});
});
async function capture(info,tab){
  const id=crypto.randomUUID();let paragraph="",anchor=null;
  try{
    const results=await chrome.scripting.executeScript({target:{tabId:tab.id,frameIds:[info.frameId || 0]},args:[id],func:requestId=>{
      const selection=window.getSelection();if(!selection?.rangeCount)return {};
      const range=selection.getRangeAt(0).cloneRange();
      const element=range.commonAncestorContainer.nodeType===1?range.commonAncestorContainer:range.commonAncestorContainer.parentElement;
      const container=element?.closest("p,li,blockquote,pre,section,article") || element;
      globalThis.__jobCompanionQaAnchors ||= {};
      globalThis.__jobCompanionQaAnchors[requestId]={range,x:scrollX,y:scrollY};
      const keys=Object.keys(globalThis.__jobCompanionQaAnchors);if(keys.length>30)delete globalThis.__jobCompanionQaAnchors[keys[0]];
      return {paragraph:container?.innerText?.slice(0,3000) || "",anchor:requestId};
    }});
    paragraph=results[0]?.result?.paragraph || "";anchor=results[0]?.result?.anchor || null;
  }catch{/* Selection text remains usable when the page disallows script access. */}
  const stored=await chrome.storage.local.get(["activeDirection","preparationDirections"]);
  let documentKey="external-page";try{const url=new URL(info.pageUrl);documentKey=url.origin+url.pathname;}catch{}
  const selection={id,quote:info.selectionText.slice(0,6000),paragraph,anchor,documentKey,title:"网页选区",direction:stored.activeDirection || "",goal:stored.preparationDirections?.find(item=>item.id===stored.activeDirection)?.target || "",tabId:tab.id,frameId:info.frameId || 0};
  await chrome.storage.session.set({["qaPending:"+tab.id]:selection});
}
chrome.tabs.onRemoved.addListener(tabId=>chrome.storage.session.remove("qaPending:"+tabId));
