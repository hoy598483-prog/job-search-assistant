/* One explicit native connection per UI; credentials never leave official CLI. */
globalThis.LocalCodexClient = class {
  constructor(){this.port=null;this.token=null;this.servicePort=null;}
  async connect(){
    if(this.port && this.token)return this.action("provider_status");
    const result=await new Promise((resolve,reject)=>{
      const port=chrome.runtime.connectNative("com.local.job_companion");this.port=port;
      const timer=setTimeout(()=>{port.disconnect();reject(new Error("本机桥接连接超时"));},7000);
      port.onMessage.addListener(message=>{clearTimeout(timer);message.error?reject(new Error(message.error)):resolve(message);});
      port.onDisconnect.addListener(()=>{clearTimeout(timer);if(this.port===port){this.token=null;this.port=null;}reject(new Error(chrome.runtime.lastError?.message || "本机连接断开"));});
      port.postMessage({action:"handshake",extension_id:chrome.runtime.id});
    });
    if(!result.token || !Number.isInteger(result.port))throw new Error("本机握手无效");
    this.token=result.token;this.servicePort=result.port;
    return this.action("provider_status");
  }
  context(){return {workspace:"learning-assistant",direction:{name:"学习助教",target:"课程与独立知识点问答"}};}
  async action(action,data={}){
    if(!this.token)throw new Error("请先连接本机Codex");
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),20000);
    try{
      const response=await fetch(`http://127.0.0.1:${this.servicePort}/action`,{signal:controller.signal,method:"POST",headers:{"Content-Type":"application/json",Authorization:"Bearer "+this.token},body:JSON.stringify({...this.context(),action,...data})});
      const result=await response.json();if(!response.ok)throw new Error(result.error || "本机请求失败");return result;
    }finally{clearTimeout(timer);}
  }
  async stream(data,onEvent,signal){
    if(!this.token)throw new Error("请先连接本机Codex");
    const response=await fetch(`http://127.0.0.1:${this.servicePort}/chat-stream`,{signal,method:"POST",headers:{"Content-Type":"application/json",Authorization:"Bearer "+this.token},body:JSON.stringify({...this.context(),...data,approved:true})});
    if(!response.ok){const error=await response.json();throw new Error(error.error || "本机请求被拒绝");}
    if(!response.body)throw new Error("浏览器未提供流式响应");
    const reader=response.body.getReader(),decoder=new TextDecoder();let buffer="",reply=null;
    const consume=line=>{if(!line.trim())return;const event=JSON.parse(line);if(event.type==="error")throw new Error(event.text);if(event.type==="done")reply=event.reply;onEvent(event);};
    try{
      while(true){const {value,done}=await reader.read();buffer+=done?decoder.decode():decoder.decode(value,{stream:true});let index;while((index=buffer.indexOf("\n"))>=0){consume(buffer.slice(0,index));buffer=buffer.slice(index+1);}if(done){consume(buffer);break;}}
    }finally{reader.releaseLock();}
    if(reply===null)throw new Error("连接中断，回复未完成");return reply;
  }
  disconnect(){if(this.port)this.port.disconnect();this.token=null;this.port=null;}
};
