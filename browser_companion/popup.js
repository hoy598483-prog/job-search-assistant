async function openPanel() { await chrome.tabs.create({url: chrome.runtime.getURL("panel.html#collect")}); }
document.getElementById("open").onclick = openPanel;
document.getElementById("background").onclick = () => chrome.tabs.create({url:chrome.runtime.getURL("background.html")});
document.getElementById("notebook").onclick = () => chrome.tabs.create({url:chrome.runtime.getURL("notebook.html")});
document.getElementById("capture").onclick = async () => {
  try {
    const state = await chrome.storage.local.get(["activeDirection", "preparationDirections"]);
    const activeDirection = state.activeDirection || "ai-product-job-agent";
    if (Array.isArray(state.preparationDirections) && !state.preparationDirections.some(item=>item.id===activeDirection)) throw new Error("请先打开工作台，新建或选择准备方向");
    const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
    if (!/^https?:\/\//.test(tab.url || "")) throw new Error("只能采集普通 HTTP(S) 页面");
    const [{result}] = await chrome.scripting.executeScript({target: {tabId: tab.id}, func: () => {
      const captured_at = new Date().toISOString();
      const clean = node => { const copy = node.cloneNode(true); copy.querySelectorAll("script,style,form,input,textarea,select,button,[contenteditable],nav,footer,[hidden],[aria-hidden=true]").forEach(n => n.remove()); return copy.textContent.replace(/\s+/g, " ").trim(); };
      const selected = window.getSelection().toString().trim();
      const root = document.querySelector("main,[role=main],article") || document.body;
      const text = (selected || clean(root)).slice(0, 60000);
      return {pages: text ? [{text, captured_at, url: location.href, title: document.title}] : [], mode: selected ? "selection" : "page-text"};
    }});
    if (!result.pages?.length) throw new Error("未找到岗位内容；可先选中招聘文本再采集");
    const key = "pages:" + activeDirection;
    const captured = await chrome.storage.session.get(key);
    const pages = captured[key] || [];
    const next = pages.slice();
    for (const page of result.pages) { const index = next.findIndex(p => p.text === page.text); if (index >= 0) next[index] = page; else if (next.length < 6) next.push(page); }
    await chrome.storage.session.set({[key]: next});
    document.getElementById("message").textContent = result.mode === "selection" ? "已收藏选中的文本" : "已收藏当前页面文本";
    await openPanel();
  } catch (error) { document.getElementById("message").textContent = error.message; }
};
