"use strict";
const MENU_ID="waq-use-selected-inquiry",API="http://127.0.0.1:8765/api";
function isWhatsApp(url){try{return new URL(url).origin==="https://web.whatsapp.com";}catch{return false;}}
function isPanel(sender){
  try{const url=new URL(sender.url);return sender.id===chrome.runtime.id && url.origin===new URL(chrome.runtime.getURL("panel.html")).origin && url.pathname==="/panel.html";}
  catch{return false;}
}
function cleanSource(source,tabId){
  if(!source || source.kind!=="whatsapp")return null;
  for(const [key,max] of [["page_session",100],["chat_token",100],["chat_title",160],["anchor",100]]){
    if(typeof source[key]!=="string" || !source[key].trim() || source[key].length>max)return null;
  }
  if(typeof source.message_id!=="string" || source.message_id.length>500)return null;
  return {kind:"whatsapp",tab_id:tabId,page_session:source.page_session,chat_token:source.chat_token,
    chat_title:source.chat_title,message_id:source.message_id,anchor:source.anchor};
}
async function storeInquiry(text,tabId,source=null){
  const inquiry={text:text.trim(),source:"WhatsApp Web",sourceTabId:tabId,
    context:cleanSource(source,tabId),capturedAt:new Date().toISOString(),captureId:crypto.randomUUID()};
  const {captures={}}=await chrome.storage.local.get("captures");
  const recent=Object.fromEntries([...Object.entries(captures),[inquiry.captureId,inquiry]].slice(-20));
  return chrome.storage.local.set({inquiry,captures:recent});
}
async function authenticated(path,options={}){
  const {auth}=await chrome.storage.local.get("auth");
  if(!auth?.token)throw new Error("sign_in");
  const response=await fetch(API+path,{...options,headers:{Authorization:"Bearer "+auth.token,
    ...(options.body?{"Content-Type":"application/json"}:{}),...options.headers},signal:AbortSignal.timeout(15000)});
  if(!response.ok)throw new Error(response.status===401?"sign_in":"request_failed");
  return response.json();
}
async function insertApprovedReply(message){
  const q=await authenticated("/quotes/"+encodeURIComponent(message.quoteId));
  if(q.revision!==message.revision || q.status!=="COMPLETED" || !q.approval)throw new Error("approval_changed");
  if(!q.source)throw new Error("no_context");
  const text=q.approval.replies[message.language];if(!text)throw new Error("invalid_text");
  let result;
  try{result=await chrome.tabs.sendMessage(q.source.tab_id,{type:"WAQ_INSERT_DRAFT",source:q.source,text});}
  catch{throw new Error("tab_missing");}
  if(!result?.ok)throw new Error(result?.code||"insert_failed");
  let logged=true;
  try{await authenticated("/quotes/"+encodeURIComponent(q.id)+"/activity",{method:"POST",body:JSON.stringify({action:"REPLY_INSERTED",revision:q.revision})});}
  catch{logged=false;}
  return {ok:true,logged};
}
async function insertQuestion(message){
  const {captures={}}=await chrome.storage.local.get("captures");
  const inquiry=captures[message.captureId];
  if(!inquiry?.context)throw new Error("no_context");
  if(typeof message.text!=="string" || !message.text.trim() || message.text.length>12000)throw new Error("invalid_text");
  try{
    const result=await chrome.tabs.sendMessage(inquiry.sourceTabId,{type:"WAQ_INSERT_DRAFT",source:inquiry.context,text:message.text});
    if(!result?.ok)throw new Error(result?.code||"insert_failed");
    return {ok:true};
  }catch(error){throw new Error(error.message.includes("Receiving end")?"tab_missing":error.message);}
}
chrome.sidePanel.setPanelBehavior({openPanelOnActionClick:true}).catch(console.error);
chrome.runtime.onInstalled.addListener(()=>{
  chrome.contextMenus.removeAll(()=>chrome.contextMenus.create({id:MENU_ID,title:"用所选文字准备报价",contexts:["selection"],documentUrlPatterns:["https://web.whatsapp.com/*"]}));
  chrome.alarms.create("quote-inbox",{periodInMinutes:1});
});
chrome.contextMenus.onClicked.addListener((info,tab)=>{
  if(info.menuItemId!==MENU_ID || !tab?.id || !isWhatsApp(info.pageUrl) || typeof info.selectionText!=="string" || info.selectionText.length>12000)return;
  const opening=chrome.sidePanel.open({windowId:tab.windowId});
  const capture=(async()=>{
    let context=null;try{context=(await chrome.tabs.sendMessage(tab.id,{type:"WAQ_CONTEXT"}))?.source;}catch{}
    await storeInquiry(info.selectionText,tab.id,context);
  })();
  Promise.all([opening,capture]).catch(console.error);
});
chrome.runtime.onMessage.addListener((message,sender,respond)=>{
  if(message?.type==="WAQ_OPEN_PANEL"){
    if(!sender.tab?.id || !isWhatsApp(sender.url) || typeof message.text!=="string" || message.text.length>12000){
      respond({ok:false,error:"请选择本次询价，最多 12000 字符。"});return false;
    }
    // Keep open() in the original click event, before any asynchronous work.
    const opening=chrome.sidePanel.open({windowId:sender.tab.windowId});
    Promise.all([opening,message.text.trim()?storeInquiry(message.text,sender.tab.id,message.source):Promise.resolve()])
      .then(()=>respond({ok:true})).catch(e=>respond({ok:false,error:e.message}));
    return true;
  }
  if(!["WAQ_FILL_REPLY","WAQ_FILL_QUESTION","WAQ_NOTIFY_INBOX"].includes(message?.type))return false;
  if(!isPanel(sender)){respond({ok:false,error:"untrusted_sender"});return false;}
  const job=message.type==="WAQ_FILL_REPLY"?insertApprovedReply(message):
    message.type==="WAQ_FILL_QUESTION"?insertQuestion(message):pollBossInbox();
  Promise.resolve(job).then(value=>respond(value||{ok:true})).catch(e=>respond({ok:false,error:e.message}));
  return true;
});
let polling=null;
async function pollBossInbox(){
  if(polling)return polling;
  polling=(async()=>{
    const {auth}=await chrome.storage.local.get("auth");
    if(auth?.user?.role!=="boss"){await chrome.action.setBadgeText({text:""});return;}
    const entries=await authenticated("/notifications");
    await chrome.action.setBadgeBackgroundColor({color:"#174f92"});
    await chrome.action.setBadgeText({text:entries.length?String(entries.length):""});
    if(!chrome.permissions || !(await chrome.permissions.contains({permissions:["notifications"]})))return;
    const {notifiedIds=[]}=await chrome.storage.local.get("notifiedIds");
    const seen=new Set(notifiedIds);
    for(const entry of entries){
      const key=entry.quote_id+":"+entry.revision+":"+entry.id;
      if(seen.has(key))continue;
      await chrome.notifications.create("waq-"+entry.id,{type:"basic",iconUrl:chrome.runtime.getURL("icon128.png"),
        title:"Quote Desk · 待审批 / Approval",message:entry.message,contextMessage:entry.quote_id});
      seen.add(key);
    }
    await chrome.storage.local.set({notifiedIds:[...seen].slice(-300)});
  })();
  try{return await polling;}finally{polling=null;}
}
chrome.alarms.onAlarm.addListener(async alarm=>{
  if(alarm.name!=="quote-inbox")return;
  try{await pollBossInbox();}catch{}
});
chrome.notifications?.onClicked.addListener(async id=>{
  if(!id.startsWith("waq-"))return;
  await chrome.tabs.create({url:chrome.runtime.getURL("panel.html")+"?inbox=1"});
  await chrome.notifications.clear(id);
});
