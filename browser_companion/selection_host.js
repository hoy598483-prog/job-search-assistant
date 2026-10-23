/* An in-page selection panel for our own extension documents. */
(() => {
  let current=null,frame=null;
  const anchors=new Map(),button=document.createElement("button");
  button.className="selection-question-button";button.textContent="询问这个知识点";button.hidden=true;button.type="button";
  document.body.append(button);
  function capture(event){
    if(event.target===button || event.target.closest?.("iframe,input,textarea,button"))return;
    const selection=window.getSelection();const quote=selection?.toString().trim();
    if(!quote || !selection.rangeCount){button.hidden=true;return;}
    const range=selection.getRangeAt(0).cloneRange(),node=range.commonAncestorContainer;
    const element=node.nodeType===1?node:node.parentElement;
    const container=element?.closest(".lesson-section,.card,p,li,blockquote,pre,section") || element;
    const text=container?.innerText || quote,index=text.indexOf(quote);
    const paragraph=index>=0?text.slice(Math.max(0,index-900),index+quote.length+900):text.slice(0,3000);
    const rect=range.getBoundingClientRect(),id=crypto.randomUUID();
    current={id,quote,paragraph,title:document.title,documentKey:document.body.dataset.selectionDocumentKey || location.href.split("#")[0],anchor:id};
    anchors.set(id,{range,x:scrollX,y:scrollY});if(anchors.size>30)anchors.delete(anchors.keys().next().value);
    button.hidden=false;button.style.left=Math.min(Math.max(8,event.clientX || rect.left),innerWidth-190)+"px";
    button.style.top=Math.min(Math.max(8,event.clientY || rect.bottom+8),innerHeight-50)+"px";
  }
  document.addEventListener("mouseup",capture);
  document.addEventListener("contextmenu",event=>{
    capture(event);if(current && !button.hidden && window.getSelection()?.toString().trim())event.preventDefault();
  });
  document.addEventListener("keydown",event=>{if(event.key==="Escape")button.hidden=true;});
  async function openCurrent(){
    try{
      if(!current)return;
      const stored=await chrome.storage.local.get(["activeDirection","preparationDirections"]);
      const params=new URLSearchParams(location.search);
      const direction=params.get("direction") || document.getElementById("workspace")?.value || stored.activeDirection || "";
      const request=SelectionQA.clean({...current,direction,goal:document.querySelector("[data-course-goal]")?.textContent || stored.preparationDirections?.find(item=>item.id===direction)?.target || ""});
      await chrome.storage.session.set({["qaRequest:"+request.id]:request});
      if(!frame){frame=document.createElement("iframe");frame.className="selection-qa-frame";frame.title="独立知识点问答";document.body.append(frame);}
      frame.src=chrome.runtime.getURL("qa.html")+"?embed=1&request="+encodeURIComponent(request.id);
      frame.hidden=false;document.body.classList.add("selection-qa-open");button.hidden=true;
      const anchor=anchors.get(request.anchor);requestAnimationFrame(()=>anchor?.range.startContainer.parentElement?.scrollIntoView({block:"nearest"}));
    }catch(error){button.textContent="无法打开问答，请重试";console.warn(error.message);}
  }
  button.onclick=openCurrent;
  document.addEventListener("learning-question",event=>{
    const detail=event.detail;if(!detail || typeof detail.quote!=="string")return;
    const id=crypto.randomUUID(),element=document.getElementById(detail.elementId);
    if(element){const range=document.createRange();range.selectNodeContents(element);anchors.set(id,{range,x:scrollX,y:scrollY});}
    current={id,quote:detail.quote,paragraph:detail.paragraph,title:document.title,documentKey:document.body.dataset.selectionDocumentKey || location.href.split("#")[0],anchor:element?id:null,initialQuestion:detail.question};
    openCurrent();
  });
  window.addEventListener("message",event=>{
    if(!frame || event.source!==frame.contentWindow || event.origin!==location.origin)return;
    if(event.data?.type==="selection-qa-close"){frame.hidden=true;document.body.classList.remove("selection-qa-open");}
    if(event.data?.type==="selection-qa-return"){
      const anchor=anchors.get(event.data.anchor);if(!anchor)return;
      try{const selection=window.getSelection();selection.removeAllRanges();selection.addRange(anchor.range);const element=anchor.range.startContainer.parentElement;element?.scrollIntoView({block:"center",behavior:"smooth"});}
      catch{scrollTo(anchor.x,anchor.y);}
    }
  });
})();
