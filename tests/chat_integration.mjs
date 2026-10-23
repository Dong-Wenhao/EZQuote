// Real local backend + actual extension scripts. Chrome APIs and the WhatsApp DOM are fixtures.
import {chromium} from "playwright";
import {spawn} from "node:child_process";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import vm from "node:vm";
import assert from "node:assert/strict";
const root=path.resolve(import.meta.dirname,"..");
const out=process.env.QA_OUTPUT||path.join(os.tmpdir(),"quote-chat-qa");
await fs.mkdir(out,{recursive:true});
const data=await fs.mkdtemp(path.join(os.tmpdir(),"quote-chat-data-"));
const python=process.env.TEST_PYTHON||process.env.CODEX_PRIMARY_RUNTIME_PYTHON||"python";
const server=spawn(python,["-m","uvicorn","backend.app:app","--host","127.0.0.1","--port","8765"],{cwd:root,env:{...process.env,WA_QUOTE_DATA:data},stdio:["ignore","pipe","pipe"]});
let logs="",browser,panel,chat;server.stdout.on("data",b=>logs+=b);server.stderr.on("data",b=>logs+=b);
const steps=[],errors=[],store={},handlers={},messages=[],pages=[];
const extensionId="abcdefghijklmnopabcdefghijklmnop",base="http://127.0.0.1:8765";
const clone=value=>value===undefined?undefined:structuredClone(value);
async function writeStorage(value){
  const changes={};for(const [key,item] of Object.entries(value)){changes[key]={oldValue:clone(store[key]),newValue:clone(item)};store[key]=clone(item);}
  await Promise.all(pages.filter(p=>!p.isClosed()).map(p=>p.evaluate(changes=>{
    for(const listener of window.__storageListeners||[])listener(changes,"local");
  },changes).catch(()=>{})));
}
const chrome={
  runtime:{id:extensionId,getURL:p=>"chrome-extension://"+extensionId+"/"+p,onInstalled:{addListener:f=>handlers.install=f},onMessage:{addListener:f=>handlers.message=f}},
  sidePanel:{setPanelBehavior:async()=>{},open:async()=>{}},
  storage:{local:{get:async key=>({[key]:clone(store[key])}),set:writeStorage}},
  contextMenus:{removeAll:f=>f(),create:()=>{},onClicked:{addListener:f=>handlers.menu=f}},
  alarms:{create:()=>{},onAlarm:{addListener:f=>handlers.alarm=f}},
  action:{setBadgeText:async()=>{},setBadgeBackgroundColor:async()=>{}},
  permissions:{contains:async()=>false},
  notifications:{onClicked:{addListener:f=>handlers.notification=f}},
  tabs:{sendMessage:async(id,message)=>{
    assert.equal(id,5);messages.push(clone(message));
    return chat.evaluate(({message,id})=>new Promise(resolve=>window.__contentListener(message,{id},resolve)),{message,id:extensionId});
  }}
};
const context={chrome,URL,Date,crypto:globalThis.crypto,console,AbortSignal,fetch};
vm.createContext(context);
vm.runInContext(await fs.readFile(path.join(root,"extension/background.js"),"utf8"),context);
handlers.install();
function backgroundMessage(message,sender){
  return new Promise(resolve=>handlers.message(message,sender,resolve));
}
async function api(endpoint,token,body){
  const r=await fetch(base+"/api"+endpoint,{method:body===undefined?"GET":"POST",
    headers:{...(token?{Authorization:"Bearer "+token}:{}),"Content-Type":"application/json"},
    ...(body===undefined?{}:{body:JSON.stringify(body)})});
  const value=await r.json();assert(r.ok,JSON.stringify(value));return value;
}
try{
  let ready=false;
  for(let i=0;i<100;i++){try{if((await fetch(base+"/api/health")).ok){ready=true;break;}}catch{}await new Promise(r=>setTimeout(r,100));}
  assert(ready,logs);
  const boss=await api("/setup",null,{shop_name:"Synthetic Shop",boss_password:"boss-chat-test",staff_password:"staff-chat-test"});
  const staff=await api("/login",null,{username:"staff",password:"staff-chat-test"});
  await api("/catalog/import",boss.token,{filename:"products.xlsx",content_b64:(await fs.readFile(path.join(root,"samples/products.xlsx"))).toString("base64")});
  store.auth=staff;store.lang="zh";
  browser=await chromium.launch({executablePath:process.env.BROWSER_EXECUTABLE,headless:true,args:["--no-sandbox","--disable-dev-shm-usage"]});
  const browserContext=await browser.newContext({viewport:{width:430,height:1000}});
  chat=await browserContext.newPage();panel=await browserContext.newPage();pages.push(chat,panel);
  for(const page of pages){
    page.on("pageerror",e=>errors.push(e.message));
    await page.exposeFunction("bridgeGet",async key=>({[key]:clone(store[key])}));
    await page.exposeFunction("bridgeSet",writeStorage);
    await page.exposeFunction("bridgeMessage",message=>backgroundMessage(message,page===chat?
      {id:extensionId,url:"https://web.whatsapp.com/",tab:{id:5,windowId:1}}:
      {id:extensionId,url:"chrome-extension://"+extensionId+"/panel.html"}));
    await page.addInitScript(({extensionId,isChat})=>{
      window.__storageListeners=[];
      const runtime={id:extensionId,sendMessage:(message,callback)=>{
        const promise=window.bridgeMessage(message);
        if(callback){promise.then(callback);return;}
        return promise;
      },onMessage:{addListener:listener=>window.__contentListener=listener}};
      window.chrome={runtime,storage:{local:{get:key=>window.bridgeGet(key),set:value=>window.bridgeSet(value)},
        onChanged:{addListener:listener=>window.__storageListeners.push(listener)}},
        action:{setBadgeText:async()=>{}},permissions:{request:async()=>true}};
    },{extensionId,isChat:page===chat});
  }
  const fixture='<!doctype html><html><head><meta charset="utf-8"></head><body><div id="main"><header><span dir="auto" title="Synthetic Customer A">Synthetic Customer A</span></header><div class="message-in" data-id="false_synthetic-a@c.us_MISSING"><span class="selectable-text copyable-text">A牌水泥20袋，多少钱？</span></div><div class="message-in" data-id="false_synthetic-a@c.us_READY"><span class="selectable-text copyable-text">A牌50kg水泥20袋，多少钱？</span></div><footer><div id="composer" contenteditable="true" role="textbox" data-lexical-editor="true"></div><button id="send" onclick="window.__sendCount++">Send</button></footer></div><script>window.__sendCount=0</script></body></html>';
  await chat.route("https://web.whatsapp.com/**",route=>route.fulfill({contentType:"text/html; charset=utf-8",body:fixture}));
  await chat.goto("https://web.whatsapp.com/");
  await chat.addStyleTag({content:await fs.readFile(path.join(root,"extension/content.css"),"utf8")});
  await chat.evaluate(await fs.readFile(path.join(root,"extension/content.js"),"utf8"));
  await panel.goto(base);
  await panel.locator("#workspace").waitFor({state:"visible"});
  await chat.locator(".message-in").first().hover();
  await chat.locator(".waq-message-action").first().click();
  await panel.locator("#clarificationBox").waitFor({state:"visible"});
  assert.equal(await panel.locator("#customer").inputValue(),"Synthetic Customer A");
  assert.equal(await panel.locator("#sourceEditor").getAttribute("open"),null);
  assert.equal((await api("/quotes",staff.token)).length,0);
  await panel.locator("#fillQuestion").click();
  assert((await chat.locator("#composer").innerText()).includes("规格"));
  assert.equal(await chat.evaluate(()=>window.__sendCount),0);
  await chat.locator("#composer").fill("");
  steps.push("Message action captures customer and original, auto-parses missing spec, inserts clarification without sending");
  await chat.locator(".message-in").nth(1).hover();
  await chat.locator(".waq-message-action").nth(1).click();
  await panel.locator("#captureQueue").waitFor({state:"visible"});
  assert((await panel.locator("#inquiryText").inputValue()).includes("A牌水泥20袋"));
  await panel.locator("#acceptCapture").click();
  await panel.waitForFunction(()=>document.getElementById("estimatedTotal").textContent==="RM370.00");
  await panel.locator("#lines input").fill("21");
  await panel.reload();await panel.locator("#resumeDraft").click();
  await panel.locator("#lineCard").waitFor({state:"visible"});
  assert.equal(await panel.locator("#lines input").inputValue(),"21");
  assert.equal(await panel.locator("#estimatedTotal").innerText(),"RM388.50");
  steps.push("Incoming capture preserves unsaved work; explicit replacement and edited quantities survive reopening");
  await panel.locator("#lines input").fill("20");
  await panel.locator("#confirmProducts").click();await panel.locator("#quoteReviewCard").waitFor({state:"visible"});await panel.locator("#sourceConfirmed").check();
  await panel.locator("#saveSubmit").click();
  await panel.waitForFunction(()=>document.getElementById("quoteStatus").textContent==="待老板批准");
  let records=await api("/quotes",staff.token);assert.equal(records.length,1);
  const id=records[0].id;
  let quote=await api("/quotes/"+id,staff.token);
  assert.equal(quote.source.chat_title,"Synthetic Customer A");
  assert.equal(quote.total,"370.00");
  steps.push("Combined save and submit preserves the source on the real backend");
  await api("/quotes/"+id+"/approve",boss.token,{expected_revision:1});
  await panel.waitForFunction(()=>document.getElementById("quoteStatus").textContent==="已批准",{},{timeout:15000});
  await panel.locator("#replyLanguage").selectOption("ms");
  await panel.locator("#fillReply").click();
  await panel.waitForFunction(()=>document.getElementById("notice").textContent.includes("已填入聊天输入框"));
  const draft=await chat.locator("#composer").innerText();
  assert(draft.includes("RM370.00"));
  quote=await api("/quotes/"+id,staff.token);
  assert.equal(draft.trim(),quote.approval.replies.ms.trim());
  assert(quote.activity.some(e=>e.action==="REPLY_INSERTED"));
  assert(!quote.activity.some(e=>e.action.includes("SENT")));
  assert.equal(await chat.evaluate(()=>window.__sendCount),0);
  await panel.locator("#fillReply").click();
  await panel.waitForFunction(()=>document.getElementById("notice").textContent.includes("已有内容"));
  assert.equal(await chat.locator("#composer").innerText(),draft);
  steps.push("Boss approval updates sidebar; approved Malay reply inserts once, logs draft only, and preserves existing composer text");
  await chat.locator("#composer").fill("");
  await chat.locator("header span").evaluate(e=>{e.title="Synthetic Customer B";e.textContent="Synthetic Customer B";});
  await panel.locator("#fillReply").click();
  await panel.waitForFunction(()=>document.getElementById("notice").textContent.includes("当前聊天已切换"));
  assert.equal((await chat.locator("#composer").innerText()).trim(),"");
  await chat.locator("header span").evaluate(e=>{e.title="Synthetic Customer A";e.textContent="Synthetic Customer A";});
  await panel.locator("#fillReply").click();
  await panel.waitForFunction(()=>document.getElementById("notice").textContent.includes("已填入聊天输入框"));
  assert((await chat.locator("#composer").innerText()).includes("RM370.00"));
  steps.push("Wrong chat is blocked; returning to the original visible message permits insertion");
  await panel.locator("#uiLang").selectOption("ms");
  await chat.waitForFunction(()=>document.querySelector(".waq-message-action").textContent==="Sediakan sebut harga");
  await panel.locator("#uiLang").selectOption("zh");
  assert.equal(await panel.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await panel.evaluate(()=>scrollTo(0,0));await panel.screenshot({path:path.join(out,"chat-approved-sidebar.png"),fullPage:true});
  await panel.locator("#newGlobal").click();
  await chat.locator(".message-in").nth(1).hover();
  await chat.locator(".waq-message-action").nth(1).click();
  await panel.waitForFunction(()=>document.getElementById("estimatedTotal").textContent==="RM370.00"&&!document.getElementById("lineCard").hidden);
  await panel.evaluate(()=>scrollTo(0,0));await panel.screenshot({path:path.join(out,"chat-ready-sidebar.png"),fullPage:true});
  steps.push("Chat action language follows sidebar language; 430px sidebar stays within viewport");
  assert.deepEqual(errors,[]);
  const report={passed:true,browser:browser.version(),steps,errors,nativeChromeAPIs:false,realWhatsAppAccount:false};
  await fs.writeFile(path.join(out,"chat-report.json"),JSON.stringify(report,null,2));
  console.log(JSON.stringify(report,null,2));
}finally{
  if(browser)await browser.close();
  server.kill("SIGTERM");
}
