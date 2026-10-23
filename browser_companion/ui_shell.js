/* Shared presentation only: no model, storage or backend requests. */
(() => {
  const page=location.pathname.split("/").pop();
  const entries=[{file:"panel.html",hash:"#collect",title:"数据收集",symbol:"◫",caption:"COLLECT SAMPLES"},
    {file:"panel.html",hash:"#plan",title:"Codex 计划",symbol:"↗",caption:"PLAN WITH CODEX"},
    {file:"background.html",title:"个人背景",symbol:"◎",caption:"YOUR BACKGROUND"},
    {file:"notebook.html",title:"学习笔记本",symbol:"▤",caption:"LEARNING NOTEBOOK"}];
  const active=entries.find(entry=>entry.file===page);if(!active)return;
  document.body.classList.add("app-body");
  const rail=document.createElement("aside");rail.className="app-rail";
  const brand=document.createElement("a");brand.className="app-brand";brand.href="panel.html#collect";
  const mark=document.createElement("span");mark.className="brand-mark";mark.textContent="↗";mark.setAttribute("aria-hidden","true");
  brand.append(mark,document.createTextNode("求职助理"));rail.append(brand);
  const nav=document.createElement("nav");nav.setAttribute("aria-label","主要导航");
  for(const entry of entries){const link=document.createElement("a");link.href=entry.file+(entry.hash || "");if(entry===active)link.setAttribute("aria-current","page");
    const symbol=document.createElement("span");symbol.className="nav-symbol";symbol.textContent=entry.symbol;symbol.setAttribute("aria-hidden","true");link.append(symbol,document.createTextNode(entry.title));nav.append(link);}
  rail.append(nav);const footer=document.createElement("div");footer.className="rail-footer";footer.textContent="本地记录 · 由你确认每一步";rail.append(footer);document.body.prepend(rail);
  const caption=document.createElement("div");caption.className="page-caption";caption.textContent=active.caption;document.querySelector("main").prepend(caption);
  function renderWorkspacePage() {
    if(page!=="panel.html")return;
    const view=location.hash==="#plan"?"plan":"collect";
    for(const element of document.querySelectorAll("[data-workspace-page]"))element.hidden=element.dataset.workspacePage!==view;
    const entry=entries.find(item=>item.hash==="#"+view);
    document.getElementById("workspace-title").textContent=entry.title;
    document.getElementById("workspace-description").textContent=view==="collect"
      ?"收集、分析和保存同类岗位文本。文本收藏无需连接 Codex。"
      :"选择岗位样本，与 Codex 讨论项目，再确认采用一周计划。";
    document.title=entry.title+" · 求职助理";caption.textContent=entry.caption;
    for(const link of nav.querySelectorAll("a")){
      if(link.getAttribute("href")===entry.file+entry.hash)link.setAttribute("aria-current","page");
      else link.removeAttribute("aria-current");
    }
  }
  renderWorkspacePage();
  window.addEventListener("hashchange",()=>{renderWorkspacePage();if(page==="panel.html")window.scrollTo(0,0);});
})();
