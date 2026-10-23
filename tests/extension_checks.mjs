import fs from "node:fs/promises";
import vm from "node:vm";
import assert from "node:assert/strict";
const root=new URL("../",import.meta.url);
const manifest=JSON.parse(await fs.readFile(new URL("extension/manifest.json",root),"utf8"));
assert.equal(manifest.manifest_version,3);
assert.deepEqual(manifest.host_permissions,["http://127.0.0.1:8765/*"]);
assert.deepEqual(manifest.content_scripts[0].matches,["https://web.whatsapp.com/*"]);
for(const file of ["background.js","content.js","panel.js","copilot.js","i18n.js"]){
  const script=await fs.readFile(new URL("extension/"+file,root),"utf8");
  new vm.Script(script,{filename:file});
}
const html=await fs.readFile(new URL("extension/panel.html",root),"utf8");
const language={window:{}};
vm.createContext(language);vm.runInContext(await fs.readFile(new URL("extension/i18n.js",root),"utf8"),language);
for(const match of html.matchAll(/data-(?:t|placeholder)="([^"]+)"/g)){
  for(const lang of ["en","ms"])assert(language.window.QUOTE_I18N[lang][match[1]],"Missing "+lang+" label "+match[1]);
}
const storage={},events=[],handlers={},badges=[];
const chrome={
  sidePanel:{setPanelBehavior:async()=>{},open:async value=>{events.push("open");}},
  storage:{local:{set:async value=>{events.push("store");Object.assign(storage,value);},get:async key=>({[key]:storage[key]})}},
  runtime:{id:"abcdefghijklmnopabcdefghijklmnop",getURL:p=>"chrome-extension://abcdefghijklmnopabcdefghijklmnop/"+p,onInstalled:{addListener:f=>handlers.install=f},onMessage:{addListener:f=>handlers.message=f}},
  contextMenus:{removeAll:f=>f(),create:()=>{},onClicked:{addListener:f=>handlers.menu=f}},
  alarms:{create:()=>{},onAlarm:{addListener:f=>handlers.alarm=f}},
  action:{setBadgeText:async x=>badges.push(x.text),setBadgeBackgroundColor:async()=>{}}
};
const context={chrome,URL,Date,crypto:globalThis.crypto,console,AbortSignal,fetch:async()=>({ok:true,json:async()=>[{id:1},{id:2}]})};
vm.createContext(context);vm.runInContext(await fs.readFile(new URL("extension/background.js",root),"utf8"),context);
handlers.install();
let response;
handlers.message({type:"WAQ_OPEN_PANEL",text:"A牌50kg水泥20袋"},{url:"https://web.whatsapp.com/",tab:{id:5,windowId:1}},r=>response=r);
await new Promise(setImmediate);
assert(response.ok);assert.equal(storage.inquiry.text,"A牌50kg水泥20袋");assert.deepEqual(events,["open","store"]);
const captured=storage.inquiry;
handlers.message({type:"WAQ_OPEN_PANEL",text:"bad"},{url:"https://other.example/",tab:{id:5,windowId:1}},r=>response=r);
assert.equal(response.ok,false);assert.equal(storage.inquiry,captured);
handlers.message({type:"WAQ_OPEN_PANEL",text:"x".repeat(12001)},{url:"https://web.whatsapp.com/",tab:{id:5,windowId:1}},r=>response=r);
assert.equal(response.ok,false);assert.equal(storage.inquiry,captured);
handlers.menu({menuItemId:"waq-use-selected-inquiry",selectionText:"20 bags Brand A cement 50kg",pageUrl:"https://web.whatsapp.com/"},{id:5,windowId:1});
await new Promise(setImmediate);
assert.equal(storage.inquiry.text,"20 bags Brand A cement 50kg");
storage.auth={user:{role:"boss"},token:"synthetic-test-token"};
await handlers.alarm({name:"quote-inbox"});assert.equal(badges.at(-1),"2");
const source={kind:"whatsapp",page_session:"page-fixture",chat_token:"chat-fixture",chat_title:"Synthetic Customer",
  message_id:"false_fixture@c.us_MESSAGE",anchor:"anchor-fixture"};
handlers.message({type:"WAQ_OPEN_PANEL",text:"A牌50kg水泥20袋",source},
  {url:"https://web.whatsapp.com/",tab:{id:5,windowId:1}},r=>response=r);
await new Promise(setImmediate);
assert.equal(storage.inquiry.context.tab_id,5);
const tabCalls=[],activityCalls=[],notifications=[];
let notificationsGranted=false;
chrome.tabs={sendMessage:async(id,message)=>{tabCalls.push({id,message});return {ok:true};},create:async()=>{}};
chrome.permissions={contains:async()=>notificationsGranted};
chrome.notifications={create:async(id,value)=>notifications.push({id,value}),clear:async()=>{}};
const quote={id:"Q-SYNTHETIC",revision:1,status:"COMPLETED",source:storage.inquiry.context,
  approval:{replies:{zh:"已批准 RM370.00",en:"Approved RM370.00",ms:"Diluluskan RM370.00"}}};
context.fetch=async(url,options)=>{
  if(url.endsWith("/notifications"))return {ok:true,json:async()=>[{id:40,quote_id:"Q-SYNTHETIC",revision:1,message:"Synthetic Customer · RM370.00"}]};
  if(url.endsWith("/activity")){activityCalls.push(JSON.parse(options.body));return {ok:true,json:async()=>({ok:true})};}
  return {ok:true,json:async()=>quote};
};
const panelSender={id:chrome.runtime.id,url:chrome.runtime.getURL("panel.html")};
const request=(message,sender=panelSender)=>new Promise(resolve=>handlers.message(message,sender,resolve));
let value=await request({type:"WAQ_FILL_REPLY",quoteId:quote.id,revision:1,language:"en",text:"UNAPPROVED TEXT"});
assert.equal(value.ok,true);assert.equal(tabCalls.at(-1).message.text,"Approved RM370.00");
assert.equal(activityCalls.at(-1).action,"REPLY_INSERTED");
const before=tabCalls.length;
value=await request({type:"WAQ_FILL_REPLY",quoteId:quote.id,revision:1,language:"en"},
  {id:chrome.runtime.id,url:"https://web.whatsapp.com/",tab:{id:5}});
assert.equal(value.error,"untrusted_sender");assert.equal(tabCalls.length,before);
quote.status="PENDING_APPROVAL";
value=await request({type:"WAQ_FILL_REPLY",quoteId:quote.id,revision:1,language:"en"});
assert.equal(value.error,"approval_changed");assert.equal(tabCalls.length,before);
quote.status="COMPLETED";quote.revision=2;
value=await request({type:"WAQ_FILL_REPLY",quoteId:quote.id,revision:1,language:"en"});
assert.equal(value.error,"approval_changed");assert.equal(tabCalls.length,before);
quote.revision=1;
value=await request({type:"WAQ_FILL_QUESTION",captureId:storage.inquiry.captureId,text:"请确认规格。"});
assert.equal(value.ok,true);assert.equal(tabCalls.at(-1).message.text,"请确认规格。");
value=await request({type:"WAQ_FILL_QUESTION",captureId:"missing-capture",text:"请确认规格。"});
assert.equal(value.error,"no_context");
await handlers.alarm({name:"quote-inbox"});assert.equal(notifications.length,0);
notificationsGranted=true;
await handlers.alarm({name:"quote-inbox"});await handlers.alarm({name:"quote-inbox"});
assert.equal(notifications.length,1);
console.log(JSON.stringify({passed:true,checks:["Manifest scope and JavaScript syntax","Complete English and Malay static UI labels","Selection message, storage and panel call order","Wrong origin and oversized message rejected","Context-menu capture","Boss badge notification polling","Source capture and server-approved reply insertion","Untrusted sender, pending approval and stale revision blocked","Clarification uses a captured source","Optional desktop notification permission and duplicate suppression"],nativeChromeAPIs:false},null,2));
