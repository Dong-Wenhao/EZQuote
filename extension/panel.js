"use strict";
(() => {
const $ = id => document.getElementById(id);
const EXTENSION = Boolean(globalThis.chrome?.runtime?.id);
document.body.classList.toggle("is-extension",EXTENSION);
$("openFullWorkspace").hidden=!EXTENSION;
const API = EXTENSION ? "http://127.0.0.1:8765/api" : location.origin + "/api";
const state = {auth:null,lang:"zh",catalog:{id:0,products:[]},quote:null,lines:[],dirty:false,view:"home",step:0,editing:true,quotes:[],recordFilter:"all",settingsTab:"business",needsReparse:false,upload:null,preview:null,notificationIds:null,requestKey:crypto.randomUUID(),captureId:null,lastCaptureId:null,source:null,pendingCapture:null,desktopEnabled:false,webNotified:new Set(),parseMeta:null,connectionStatus:{}};
let workspaceSequence=0;
const context=()=>workspaceSequence;
const sameQuote=(sequence,q)=>sequence===workspaceSequence&&state.quote?.id===q.id&&state.quote?.revision===q.revision;
const originalLabels = {};
document.querySelectorAll("[data-t]").forEach(el => { originalLabels[el.dataset.t] ??= el.textContent; });
document.querySelectorAll("[data-placeholder]").forEach(el => { originalLabels[el.dataset.placeholder] = el.placeholder; });
const t = key => window.QUOTE_I18N[state.lang]?.[key] || originalLabels[key] || window.QUOTE_I18N.en[key] || key;
const money = value => "RM" + Number(value || 0).toLocaleString("en-MY",{minimumFractionDigits:2,maximumFractionDigits:2});
const node = (tag,text,className) => { const e=document.createElement(tag); if(text!==undefined)e.textContent=text;if(className)e.className=className;return e; };
function notify(message,error=false) { $("noticeMessage").textContent=message;$("notice").classList.toggle("error",error);$("notice").hidden=false; }
function hideNotice(){ $("notice").hidden=true; }
$("dismissNotice").addEventListener("click",hideNotice);
async function localGet(key) {
  if(EXTENSION)return (await chrome.storage.local.get(key))[key];
  try{return JSON.parse(sessionStorage.getItem("qd_"+key));}catch{return null;}
}
async function localSet(key,value) {
  if(EXTENSION)return chrome.storage.local.set({[key]:value});
  sessionStorage.setItem("qd_"+key,JSON.stringify(value));
}
function friendlyError(error,status) {
  if(error&&typeof error==="object"&&error.code)return t(error.code);
  if(typeof error==="string"&&error.startsWith("Insufficient or unknown inventory"))return t("reviewStockHelp")+" "+error;
  if(typeof error==="string" && window.QUOTE_I18N[state.lang]?.[error])return t(error);
  if(status===409 && String(error).includes("changed"))return t("refreshConflict");
  if(status===401)return String(error).includes("Incorrect") ? t("loginFailed") : t("sessionExpired");
  return typeof error==="string" ? error : JSON.stringify(error);
}
async function api(path,options={}) {
  const headers = {...options.headers};
  const auth=state.auth?.token;if(auth)headers.Authorization="Bearer "+auth;
  if(options.body!==undefined){headers["Content-Type"]="application/json";options.body=JSON.stringify(options.body);}
  let response;
  try{response=await fetch(API+path,{...options,headers,signal:AbortSignal.timeout(path==="/inquiries/parse"?60000:30000)});}
  catch{throw new Error(t("offline"));}
  if(!response.ok){
    const body=await response.json().catch(()=>({detail:t("requestFailed")}));
    if(response.status===401 && path!=="/login"&&state.auth?.token===auth){workspaceSequence++;state.auth=null;showPane("login");await localSet("auth",null);}
    throw new Error(friendlyError(body.detail,response.status));
  }
  if(options.blob)return response.blob();
  return response.json();
}
async function run(button,work) {
  hideNotice();const previous=button.disabled;button.disabled=true;button.setAttribute("aria-busy","true");
  try{await work();}catch(error){notify(error.message||t("requestFailed"),true);}
  finally{button.disabled=previous;button.removeAttribute("aria-busy");}
}
function onClick(id,work){$(id).addEventListener("click",()=>run($(id),work));}
function showPane(id){for(const pane of ["offline","setup","login","workspace"])$(pane).hidden=pane!==id;document.body.classList.toggle("has-workspace",id==="workspace");}
function updateFlow(step){
  const changed=state.step!==step;
  state.step=step;
  const saved=Boolean(state.quote&&!state.editing);
  ["inquiryCard","lineCard","quoteReviewCard"].forEach((id,index)=>$(id).hidden=saved||index!==step);
  $("quoteCard").hidden=!saved;
  $("flowCustomer").textContent=saved?state.quote.customer:$("customer").value;
  document.querySelectorAll("#flowProgress li").forEach((item,index)=>{
    item.classList.toggle("active",index===step);item.classList.toggle("done",index<step);
    if(index===step)item.setAttribute("aria-current","step");else item.removeAttribute("aria-current");
  });
  if(changed&&state.view==="inquiry")requestAnimationFrame(()=>{
    const card=$(saved?"quoteCard":["inquiryCard","lineCard","quoteReviewCard"][step]);
    if(card){card.tabIndex=-1;card.focus({preventScroll:true});}
    window.scrollTo({top:Math.max(0,$("view-inquiry").getBoundingClientRect().top+window.scrollY-14),behavior:"auto"});
  });
}
function renderCapture(){
  $("inquiryCount").textContent=$("inquiryText").value.length.toLocaleString("en")+" / 12,000";
  document.body.classList.toggle("has-chat-source",Boolean(state.source));
  $("captureSummary").hidden=!state.source;
  if(state.source){$("capturedCustomer").textContent=$("customer").value||state.source.chat_title;$("capturedText").textContent=$("inquiryText").value;}
  $("fillQuestion").hidden=!(EXTENSION && state.source && !$("clarificationBox").hidden);
}
function renderParseMethod(){
  const meta=state.parseMeta;
  $("parseMethod").textContent=!meta?"":meta.method==="requirements_rules"?t("cpLocalRequirements"):meta.ai_state==="used"?t("aiUsed")+" · "+meta.ai_model:
    meta.ai_state==="fallback"?t("aiFallback")+" ("+meta.warning_code+")":t("rulesUsed");
}
function renderPhone(){
  const q=state.quote;$("phoneNotice").hidden=q?.status!=="PENDING_APPROVAL";
  if(!q)return;
  const job=q.mobile_notification;
  $("phoneStatus").textContent=job?t("phone_"+job.status):t(state.connectionStatus.phone_ready?"phoneNotQueued":"phoneNotEnabled");
  $("phoneError").textContent=job?.error?t("phoneErrorCode")+" "+job.error:"";
  $("notifyPhone").disabled=!state.connectionStatus.phone_ready||["PENDING","SENDING","WAITING_GATEWAY"].includes(job?.status);
}
async function extensionMessage(type,data={}){
  let response;
  try{response=await chrome.runtime.sendMessage({type,...data});}catch{throw new Error(t("tab_missing"));}
  if(!response?.ok)throw new Error(t(response?.error||"insert_failed"));
  return response;
}
function setView(view){
  if(["business","catalog","shop","connections"].includes(view)){state.settingsTab=view;view="settings";}
  if(view==="settings"&&state.auth?.user.role!=="boss")view="home";
  state.view=view;document.querySelectorAll(".view").forEach(v=>v.hidden=v.id!=="view-"+view);
  document.querySelectorAll("nav [data-view]").forEach(b=>{const active=b.dataset.view===view;b.classList.toggle("active",active);if(active)b.setAttribute("aria-current","page");else b.removeAttribute("aria-current");});
  $("workspaceTitle").textContent=t("viewTitle_"+view);
  if(view==="settings")setSettings(state.settingsTab);
  if(view==="home")renderHome();
}
function setSettings(tab){
  state.settingsTab=tab;
  document.querySelectorAll(".settings-pane").forEach(e=>e.hidden=e.id!=="view-"+tab);
  document.querySelectorAll("[data-settings]").forEach(e=>{e.classList.toggle("active",e.dataset.settings===tab);e.setAttribute("aria-pressed",String(e.dataset.settings===tab));});
}
function matchesFilter(q,filter){
  if(filter==="pending")return q.status==="PENDING_APPROVAL";
  if(filter==="ready")return ["COMPLETED","EXPORT_PENDING"].includes(q.status)&&(q.outcome||"open")==="open";
  if(filter==="closed")return ["won","lost"].includes(q.outcome);
  return true;
}
function quoteEntries(container,quotes,emptyKey="noQuotes"){
  container.replaceChildren();
  if(!quotes.length){const empty=node("div",undefined,"empty");empty.append(node("strong",t(emptyKey)),node("p",t("emptyWorkHelp")));container.append(empty);return;}
  quotes.forEach(q=>{
    const button=node("button",undefined,"quote-entry");button.type="button";
    const left=node("div"),right=node("div"),status=t(q.outcome==="won"?"cpWon":q.outcome==="lost"?"cpLost":q.status);
    left.append(node("strong",q.customer),node("small",q.id+" · "+t("revision")+" "+q.revision));
    right.append(node("strong",money(q.total)),node("span",status,"status "+(q.status==="REJECTED"||q.outcome==="lost"?"rejected":q.status==="PENDING_APPROVAL"?"pending":["COMPLETED","EXPORT_PENDING"].includes(q.status)?"done":"")));
    button.append(left,right);button.addEventListener("click",()=>run(button,()=>loadQuote(q.id)));container.append(button);
  });
}
function renderRecords(){
  quoteEntries($("quoteList"),state.quotes.filter(q=>matchesFilter(q,state.recordFilter)),"noFilteredQuotes");
  document.querySelectorAll("[data-record-filter]").forEach(e=>{e.classList.toggle("active",e.dataset.recordFilter===state.recordFilter);e.setAttribute("aria-pressed",String(e.dataset.recordFilter===state.recordFilter));});
}
function renderHome(){
  const boss=state.auth?.user.role==="boss",pending=state.quotes.filter(q=>matchesFilter(q,"pending"));
  $("homeTitle").textContent=t(boss?"bossHomeTitle":"staffHomeTitle");$("homeSubtitle").textContent=t(boss?"bossHomeHelp":"staffHomeHelp");
  $("homeListTitle").textContent=t(boss&&pending.length?"pendingForYou":"recentQuotes");
  $("homePending").textContent=pending.length;$("homeReady").textContent=state.quotes.filter(q=>matchesFilter(q,"ready")).length;$("homeAll").textContent=state.quotes.length;
  $("homeSetup").hidden=Boolean(state.catalog.products.length);
  $("homeSetupHelp").textContent=t(boss?"bossSetupHelp":"staffSetupHelp");
  $("resumeDraft").hidden=!(state.editing&&($("inquiryText").value.trim()||state.lines.length));
  quoteEntries($("homeList"),(boss&&pending.length?pending:state.quotes).slice(0,4));
}
function renderReview(){
  $("reviewSummary").replaceChildren();
  $("reviewSummary").append(node("strong",$("customer").value));
  state.lines.forEach(l=>{const p=state.catalog.products.find(p=>p.sku===l.sku);if(p)$("reviewSummary").append(node("p",(p["name_"+state.lang]||p.name_en||p.name_zh)+" · "+p.spec+" · "+l.quantity+" "+p.unit));});
  const fields=copilot.draftFields();
  if(fields.pricing_enabled)$("reviewSummary").append(node("p",fields.fulfilment==="pickup"?t("cpPickup"):t("cpDelivery")+" · "+fields.delivery_area,"muted"));
  const original=node("details");original.append(node("summary",t("inquiryOriginal")),node("p",$("inquiryText").value,"prewrap muted small"));$("reviewSummary").append(original);
  $("legacyReviewTotal").hidden=Boolean(fields.pricing_enabled);$("legacyReviewAmount").textContent=$("estimatedTotal").textContent;
}
function startNewInquiry(){if(state.editing&&state.dirty&&!window.confirm(t("discardWork")))return;newInquiry();$("customer").focus();}
function applyLanguage(){
  document.documentElement.lang=state.lang==="zh"?"zh-CN":state.lang;
  document.querySelectorAll("[data-t]").forEach(el=>el.textContent=t(el.dataset.t));
  document.querySelectorAll("[data-placeholder]").forEach(el=>el.placeholder=t(el.dataset.placeholder));
  document.querySelectorAll("[data-title]").forEach(el=>{el.title=t(el.dataset.title);el.setAttribute("aria-label",t(el.dataset.title));});
  $("uiLang").value=state.lang;
  $("connectionText").textContent=t($("connectionDot").classList.contains("online")?"online":"offline");
  $("workspaceTitle").textContent=t("viewTitle_"+state.view);
  if(state.auth)$("userLabel").textContent=t(state.auth.user.role)+" · "+state.auth.user.username;
  renderCatalog();renderLines(false);if(state.quote&&!state.editing)renderQuote(state.quote);
  $("inboxHint").textContent=t(state.auth?.user.role==="boss"?"pendingHint":"staffHint");
  const canNotify=state.auth?.user.role==="boss" && (EXTENSION || "Notification" in window);
  $("notifyDesktop").hidden=!canNotify;$("desktopHelp").hidden=!canNotify;renderCapture();renderParseMethod();renderPhone();
  if(state.credentialFlags){
    $("aiKeyState").textContent=t(state.credentialFlags.ai?"credentialSaved":"credentialMissing");
    $("waTokenState").textContent=t(state.credentialFlags.wa?"credentialSaved":"credentialMissing");
  }
  copilot.language();
  renderHome();renderRecords();if(state.editing&&state.step===2){try{renderReview();}catch{updateFlow(1);}}
}
async function connect(){
  try{
    const health=await api("/health");$("connectionDot").classList.add("online");$("connectionText").textContent=t("online");
    if(health.version!=="1.6.1")throw new Error(t("restartNewService"));
    if(!health.configured){showPane("setup");return;}
    if(!state.auth){showPane("login");return;}
    state.auth.user=await api("/me");await enterWorkspace();
  }catch(error){$("connectionDot").classList.remove("online");$("connectionText").textContent=t("offline");showPane("offline");notify(error.message,true);}
}
async function enterWorkspace(){
  state.catalog=await api("/catalog");
  const shop=await api("/shop");
  document.querySelector(".brand p").textContent=shop.name;
  for(const [field,id] of Object.entries({name:"shopName",address:"shopAddress",phone:"shopPhone",terms:"shopTerms"}))$(id).value=shop[field]||"";
  document.querySelectorAll(".boss-only").forEach(e=>e.hidden=state.auth.user.role!=="boss");
  state.connectionStatus=await api("/integrations/status");
  await copilot.loadBusiness(true);
  if(state.auth.user.role==="boss")await loadConnections();
  state.notificationIds=null;applyLanguage();await refreshRecords();showPane("workspace");await pollInbox();
  setView("home");
  if(!state.catalog.products.length){renderHome();return;}
  const input=await localGet("draftInput");
  if(input && !state.quote){
    const restored=copilot.restore(input);
    state.editing=true;state.needsReparse=Boolean(input.needsReparse||restored?.needsReparse);
    $("customer").value=input.customer||"";$("inquiryText").value=input.text||"";$("notes").value=input.notes||"";
    state.source=input.source||null;state.captureId=input.captureId||null;
    state.parseMeta=input.parseMeta||null;renderParseMethod();
    if(input.quoteId){
      try{state.quote=await api("/quotes/"+encodeURIComponent(input.quoteId));state.quote.revision=input.revision;}
      catch{notify(t("resumeFailed"),true);return;}
    }
    if(input.lines?.length){state.lines=input.lines;state.dirty=true;$("quoteLanguage").value=input.language||"zh";renderLines();updateFlow(state.needsReparse?0:input.step===2?2:1);if(!state.needsReparse&&input.step===2){if(await copilot.review(true))renderReview();else updateFlow(1);}}
    else{state.dirty=Boolean(input.text);updateFlow(0);}
    $("clarificationBox").hidden=!input.needsInfo;$("clarification").textContent=input.clarification||"";
    renderCapture();$("sourceEditor").open=!state.source;
  }
  if(EXTENSION){
    const inquiry=await localGet("inquiry");
    if(inquiry?.text && inquiry.captureId!==state.lastCaptureId){await receiveInquiry(inquiry);return;}
  }
  renderHome();
  if(new URLSearchParams(location.search).has("inbox"))setView("records");
}
function newInquiry(){
  workspaceSequence++;
  state.editing=true;state.needsReparse=false;
  document.querySelector(".demo-details").open=false;
  state.quote=null;state.lines=[];state.dirty=false;state.requestKey=crypto.randomUUID();state.source=null;state.captureId=null;state.pendingCapture=null;state.parseMeta=null;renderParseMethod();
  $("inquiryCard").hidden=false;$("lineCard").hidden=true;$("quoteCard").hidden=true;$("clarificationBox").hidden=true;
  $("customer").value="";$("inquiryText").value="";$("notes").value="";$("sourceConfirmed").checked=false;$("captureInfo").textContent="";
  $("captureQueue").hidden=true;$("sourceEditor").open=true;$("quoteOptions").open=false;renderCapture();updateFlow(0);
  setView("inquiry");hideNotice();localSet("draftInput",null);localSet("activeQuote",null);
  copilot.reset();
}
async function receiveInquiry(inquiry,force=false){
  if(inquiry.captureId===state.lastCaptureId && !force)return;
  if(state.dirty && !force){
    state.pendingCapture=inquiry;$("queuedText").textContent=(inquiry.context?.chat_title||"WhatsApp")+" · "+inquiry.text;
    $("captureQueue").hidden=false;return;
  }
  newInquiry();state.captureId=inquiry.captureId;state.lastCaptureId=inquiry.captureId;state.source=inquiry.context||null;
  $("inquiryText").value=inquiry.text;$("customer").value=state.source?.chat_title||"";
  await localSet("lastCaptureId",inquiry.captureId);
  $("captureInfo").textContent=t("captured")+" "+new Date(inquiry.capturedAt).toLocaleTimeString();
  $("sourceEditor").open=!state.source;renderCapture();notify(t("captured"));persistInput();
  if(state.catalog.products.length)await run($("parse"),parseInquiry);
}
function persistInput(){localSet("draftInput",{customer:$("customer").value,text:$("inquiryText").value,notes:$("notes").value,
  source:state.source,captureId:state.captureId,lines:state.lines,language:$("quoteLanguage").value,
  parseMeta:state.parseMeta,copilot:copilot.persist(),step:state.step,needsReparse:state.needsReparse,
  needsInfo:!$("clarificationBox").hidden,clarification:$("clarification").textContent,quoteId:state.quote?.id||null,revision:state.quote?.revision||null});}
function draftInputKey(){
  const cp=copilot.persist();return JSON.stringify([$("customer").value,$("inquiryText").value,$("notes").value,$("quoteLanguage").value,
    state.lines.map(i=>[i.sku,i.quantity,i.source_id||null]),state.source,cp.smart,cp.area,cp.fulfilment,$("sourceConfirmed").checked]);
}
function productLabel(p){return p.brand+" · "+(p["name_"+state.lang]||p.name_en||p.name_zh)+" · "+p.spec+" ["+p.sku+"]";}
function lineIsValid(line){
  const p=state.catalog.products.find(p=>p.sku===line.sku),q=Number(line.quantity);
  return Boolean(p && Number.isFinite(q) && q>0 && q<=1000000 && (p.unit==="kg" || Number.isInteger(q)) && /^\d+(\.\d{1,3})?$/.test(line.quantity));
}
function renderLines(invalidate=true){
  const container=$("lines");container.replaceChildren();
  state.lines.forEach((line,index)=>{
    const block=node("div",undefined,"line-item");
    if(line.source_text)block.append(node("p",line.source_text,"line-source"));
    const evidence=node("details",undefined,"source-evidence");
    if(line.source_text){evidence.append(node("summary",t("reviewSource")),node("p",line.source_text,"prewrap small"));block.append(evidence);}
    if(line.quantity_mentions?.length){
      const original=line.quantity_mentions.map(q=>q.raw).join(" / ");
      const number=node("p",t("reviewOriginalNumber")+" "+original+" → "+(line.quantity||t("reviewChoose")),"quantity-evidence small");
      // Keep the evidence one click away; ambiguous or changed quantities stay visible.
      if(line.source_text&&line.quantity_mentions.length===1&&!line.quantity_mentions[0].error&&line.quantity_mentions[0].value===line.quantity)evidence.append(number);
      else block.append(number);
    }
    copilot.renderMatch(line,block);
    const select=document.createElement("select");select.setAttribute("aria-label",t("selectProduct")+" "+(index+1));
    const empty=node("option",t("selectProduct"));empty.value="";select.append(empty);
    const candidates=(line.candidates?.length?line.candidates:state.catalog.products);
    const all=[...candidates,...state.catalog.products.filter(p=>!candidates.some(c=>c.sku===p.sku))];
    all.forEach(p=>{const option=node("option",productLabel(p));option.value=p.sku;select.append(option);});select.value=line.sku||"";
    select.addEventListener("change",()=>{line.sku=select.value;state.dirty=true;renderLines();persistInput();});
    const choice=node("details",undefined,"product-choice");choice.append(node("summary",t("changeProduct")),select);if(!line.sku)choice.open=true;block.append(choice);
    const grid=node("div",undefined,"line-grid"),label=node("label"),caption=node("span",t("quantity")),quantity=document.createElement("input");
    quantity.type="number";quantity.min="0.001";quantity.max="1000000";quantity.step="any";quantity.value=line.quantity||"";quantity.setAttribute("aria-label",t("quantity")+" "+(index+1));
    quantity.addEventListener("input",()=>{line.quantity=quantity.value;state.dirty=true;updateTotal();persistInput();});
    label.append(caption,quantity);grid.append(label);
    const product=state.catalog.products.find(p=>p.sku===line.sku);
    grid.append(node("div",product?money(product.unit_price)+" / "+product.unit:"—","line-price"));block.append(grid);
    if(!line.sku && line.questions?.length)block.append(node("p",line.questions.join(" "),"line-error"));
    const remove=node("button",t("remove"),"text-button");remove.type="button";remove.addEventListener("click",()=>{state.lines.splice(index,1);state.dirty=true;renderLines();persistInput();});block.append(remove);container.append(block);
  });updateTotal(invalidate);
}
function updateTotal(invalidate=true){
  const total=state.lines.reduce((sum,line)=>{const p=state.catalog.products.find(p=>p.sku===line.sku);return sum+(p&&lineIsValid(line)?Math.round(Number(p.unit_price)*Number(line.quantity)*100)/100:0);},0);
  $("estimatedTotal").textContent=money(total);
  if(invalidate)copilot.invalidate();
}
function renderCatalog(){
  const cat=state.catalog;
  $("catalogInfo").textContent=cat.id?t("catalogVersion")+" "+cat.id+" · "+cat.products.length+" "+t("products"):t("noCatalog");
  $("catalogList").replaceChildren();
  cat.products.forEach(p=>{const row=node("div",undefined,"catalog-entry"),description=node("div",productLabel(p));description.append(node("small",p.unit));row.append(description,node("strong",money(p.unit_price)));$("catalogList").append(row);});
}
function renderQuote(q){
  const changed=state.quote?.id!==q.id||state.quote?.revision!==q.revision;
  state.editing=false;
  if(changed){$("cpEditDetails").open=false;$("rejectDetails").open=false;$("cpOutcomeBox").open=false;$("rejectReason").value="";}
  $("quoteCard").classList.toggle("has-pricing",Boolean(q.pricing));
  state.quote=q;state.source=q.source||null;localSet("activeQuote",q.id);$("quoteCard").hidden=false;$("quoteNumber").textContent=q.id+" · "+t("revision")+" "+q.revision;
  updateFlow(q.status==="COMPLETED"?3:2);
  $("quoteCustomer").textContent=q.customer;$("quoteStatus").textContent=t(q.status);
  $("quoteNextHint").textContent=t(q.approval?"approvedNext":q.status==="PENDING_APPROVAL"?(state.auth?.user.role==="boss"?"bossNext":"staffNext"):q.status==="REJECTED"?"returnedNext":"draftNext");
  $("reviewUpgrade").hidden=!q.review_required;
  $("quoteStatus").className="status "+(q.status==="PENDING_APPROVAL"?"pending":q.status==="REJECTED"?"rejected":q.status==="COMPLETED"?"done":"");
  $("quoteSummary").replaceChildren();
  q.items.forEach(i=>{const row=node("div",undefined,"summary-line"),left=node("div");left.append(node("p",i.brand+" "+(i["name_"+state.lang]||i.name_en||i.name_zh)+" "+i.spec),node("small",i.quantity+" "+i.unit+" × "+money(i.unit_price)));row.append(left,node("strong",money(i.line_total)));$("quoteSummary").append(row);});
  if(q.pricing?.requirement){const r=q.pricing.requirement;$("quoteSummary").append(node("p",r.fulfilment==="pickup"?t("cpPickup"):t("cpDelivery")+" · "+r.area,"muted small"));}
  $("quoteTotal").textContent=money(q.total);$("savedOriginal").textContent=q.inquiry+(q.notes?"\n\n"+q.notes:"");
  $("draftActions").hidden=q.status!=="DRAFT";
  $("submit").disabled=Boolean(q.review_required);$("approve").disabled=Boolean(q.review_required);
  $("bossActions").hidden=q.status!=="PENDING_APPROVAL"||state.auth?.user.role!=="boss";
  $("pendingInfo").hidden=q.status!=="PENDING_APPROVAL";
  $("approvedArea").hidden=!q.approval;
  $("replyTarget").hidden=!q.source;$("replyTargetName").textContent=q.source?.chat_title||"";
  $("fillReply").hidden=!(EXTENSION && q.source && q.status==="COMPLETED");
  if(q.approval){
    $("approvalInfo").textContent=t("approvedBy")+" "+q.approval.approved_by+" · "+new Date(q.approval.approved_at).toLocaleString();
    $("exportWarning").hidden=q.approval.export_status==="COMPLETED";
    $("replyLanguage").value=q.language;updateReply();
  }
  $("activityLog").replaceChildren();
  [...q.activity].reverse().forEach(e=>{const row=node("div",t(e.action),"event");row.append(node("small",e.actor+" · r"+e.revision+" · "+new Date(e.at).toLocaleString()));if(e.details.reason)row.append(node("p",e.details.reason));$("activityLog").append(row);});
  renderPhone();
  copilot.renderQuote(q);
  const audit=(q.review?.resolutions||[]).filter(p=>p.resolution.reason!=="Concrete selection verified by server");$("reviewAudit").hidden=!audit.length;$("reviewAuditLog").replaceChildren();
  for(const entry of audit){
    let value=entry.resolution.value;
    if(value&&typeof value==="object")value=value.action==="remove"?t("choice_remove"):value.sku+" × "+value.quantity;
    else if(["include","exclude","ignore","pickup","delivery"].includes(value))value=t("choice_"+value);
    const row=node("p",t("issue_"+entry.code),"small");row.append(node("span"," · "+value),node("br"),node("span",entry.resolution.reason,"muted"));$("reviewAuditLog").append(row);
  }
}
function updateReply(){if(state.quote?.approval)$("replyText").value=state.quote.approval.replies[$("replyLanguage").value]||"";}
async function loadQuote(id){
  if(state.editing&&state.dirty&&!window.confirm(t("discardWork")))return;
  const sequence=++workspaceSequence,q=await api("/quotes/"+encodeURIComponent(id));if(sequence!==workspaceSequence)return;
  state.dirty=false;state.lines=[];localSet("draftInput",null);
  $("inquiryCard").hidden=true;$("lineCard").hidden=true;setView("inquiry");renderQuote(q);
}
async function refreshRecords(){
  if(!state.auth)return;
  const auth=state.auth.token,quotes=await api("/quotes");if(state.auth?.token!==auth)return;
  const order={PENDING_APPROVAL:0,EXPORT_PENDING:1,REJECTED:2,DRAFT:3,COMPLETED:4};
  if(state.auth.user.role==="boss")quotes.sort((a,b)=>order[a.status]-order[b.status]||b.updated_at.localeCompare(a.updated_at));
  state.quotes=quotes;renderRecords();renderHome();
}
async function pollInbox(){
  if(!state.auth || $("workspace").hidden)return;
  try{
    state.connectionStatus=await api("/integrations/status");renderPhone();
    await copilot.sync();
    const entries=await api("/notifications"),ids=new Set(entries.map(e=>e.id));
    const hasNew=entries.some(e=>!state.notificationIds?.has(e.id));
    if(state.notificationIds && hasNew)notify(t("newPending"));
    if(state.auth.user.role==="boss" && hasNew){
      if(EXTENSION)chrome.runtime.sendMessage({type:"WAQ_NOTIFY_INBOX"}).catch(()=>{});
      else if(state.desktopEnabled && window.Notification?.permission==="granted"){
        for(const entry of entries){
          if(state.webNotified.has(entry.id))continue;
          try{
            const notification=new Notification("Quote Desk · "+t("newPending"),{body:entry.message,icon:"/assets/icon128.png",tag:"waq-"+entry.id});
            notification.onclick=()=>{window.focus();run($("refreshRecords"),()=>loadQuote(entry.quote_id));notification.close();};
            state.webNotified.add(entry.id);
          }catch{}
        }
      }
    }
    state.notificationIds=ids;$("inboxCount").hidden=!entries.length;$("inboxCount").textContent=entries.length;
    if(EXTENSION){await chrome.action.setBadgeText({text:entries.length?String(entries.length):""});}
    if(["records","home"].includes(state.view))await refreshRecords();
    if(state.quote?.status==="PENDING_APPROVAL"&&!state.editing&&!state.dirty){
      const current=state.quote,sequence=context(),q=await api("/quotes/"+current.id);
      if(!sameQuote(sequence,current)||state.editing||state.dirty)return;
      if(q.status!==state.quote.status||q.revision!==state.quote.revision){renderQuote(q);notify(t(q.status));}
      else if(JSON.stringify(q.mobile_notification)!==JSON.stringify(state.quote.mobile_notification)){state.quote=q;renderPhone();}
    }
  }catch{ /* Keep work intact while the server is unavailable. */ }
}
async function download(path,filename){
  const blob=await api(path,{blob:true}),url=URL.createObjectURL(blob),link=node("a");
  link.href=url;link.download=filename;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);
}
async function copyText(text){
  try{await navigator.clipboard.writeText(text);}
  catch{
    const area=document.createElement("textarea");area.value=text;area.style.position="fixed";area.style.opacity="0";document.body.append(area);area.select();
    const ok=document.execCommand("copy");area.remove();if(!ok)throw new Error(t("copyFailed"));
  }
}
async function uploadData(){
  const file=$("catalogFile").files[0];if(!file)throw new Error(t("chooseFile"));
  if(file.size>5*1024*1024)throw new Error("Excel file exceeds 5 MB");
  const bytes=new Uint8Array(await file.arrayBuffer());let binary="";
  for(let i=0;i<bytes.length;i+=32768)binary+=String.fromCharCode(...bytes.subarray(i,i+32768));
  const mapping={};document.querySelectorAll("[data-map]").forEach(e=>mapping[e.dataset.map]=e.value);
  return {filename:file.name,content_b64:btoa(binary),mapping,sheet_name:$("importSheet").value||null};
}
function invalidatePreview(){state.preview=null;$("commitCatalog").hidden=true;$("importPreview").replaceChildren();}
function renderMapping(data){
  $("sheetLabel").hidden=data.sheets.length<2;$("importSheet").replaceChildren();
  data.sheets.forEach(name=>{const option=node("option",name);option.value=name;$("importSheet").append(option);});$("importSheet").value=data.sheet;
  $("columnMapping").replaceChildren();
  for(const field of ["sku","name_zh","name_en","name_ms","brand","spec","unit","unit_price","aliases"]){
    const row=node("label",undefined,"mapping-row");row.append(node("span",field));
    const select=document.createElement("select");select.dataset.map=field;const empty=node("option",t("notMapped"));empty.value="";select.append(empty);
    data.headers.forEach(header=>{const option=node("option",header);option.value=header;select.append(option);});select.value=data.mapping[field]||"";
    select.addEventListener("change",()=>{invalidatePreview();notify(t("catalogPreviewStale"));});row.append(select);$("columnMapping").append(row);
  }
}
const copilot=window.createQuoteCopilot({$,state,api,t,node,money,notify,run,setView,refreshRecords,renderQuote,renderLines,renderCatalog,persistInput,newInquiry,download,context,sameQuote});
onClick("reconnect",connect);
$("setupForm").addEventListener("submit",e=>{e.preventDefault();run($("setupForm").querySelector("button"),async()=>{
  state.auth=await api("/setup",{method:"POST",body:{shop_name:$("setupShop").value,boss_password:$("setupBoss").value,staff_password:$("setupStaff").value}});
  $("setupBoss").value="";$("setupStaff").value="";await localSet("auth",state.auth);await enterWorkspace();
});});
$("loginForm").addEventListener("submit",e=>{e.preventDefault();run($("loginForm").querySelector("button"),async()=>{
  state.auth=await api("/login",{method:"POST",body:{username:$("loginUser").value,password:$("loginPassword").value}});
  $("loginPassword").value="";await localSet("auth",state.auth);await enterWorkspace();
});});
onClick("logout",async()=>{try{await api("/logout",{method:"POST"});}finally{state.auth=null;state.quote=null;state.notificationIds=null;newInquiry();await localSet("auth",null);if(EXTENSION)await chrome.action.setBadgeText({text:""});showPane("login");}});
$("uiLang").addEventListener("change",async()=>{state.lang=$("uiLang").value;await localSet("lang",state.lang);applyLanguage();if(state.auth)await refreshRecords();$("connectionText").textContent=t($("connectionDot").classList.contains("online")?"online":"offline");});
document.querySelectorAll("[data-view]").forEach(button=>button.addEventListener("click",()=>{setView(button.dataset.view);if(["records","home"].includes(state.view))run(button,refreshRecords);}));
document.querySelectorAll("[data-settings]").forEach(button=>button.addEventListener("click",()=>setSettings(button.dataset.settings)));
document.querySelectorAll("[data-record-filter]").forEach(button=>button.addEventListener("click",()=>{state.recordFilter=button.dataset.recordFilter;renderRecords();}));
document.querySelectorAll("[data-filter-jump]").forEach(button=>button.addEventListener("click",()=>{state.recordFilter=button.dataset.filterJump;setView("records");renderRecords();}));
$("newInquiry").addEventListener("click",startNewInquiry);$("newGlobal").addEventListener("click",startNewInquiry);$("startQuote").addEventListener("click",startNewInquiry);
$("sidebarNewQuote").addEventListener("click",startNewInquiry);
$("resumeDraft").addEventListener("click",()=>{setView("inquiry");updateFlow(state.step);});
$("backHome").addEventListener("click",()=>{setView("home");});
$("homeAllRecords").addEventListener("click",()=>{state.recordFilter="all";setView("records");renderRecords();});
$("homeConfigure").addEventListener("click",()=>setView("business"));
$("backToInquiry").addEventListener("click",()=>{updateFlow(0);persistInput();});
$("backToProducts").addEventListener("click",()=>{updateFlow(1);persistInput();});
onClick("confirmProducts",async()=>{
  if(state.needsReparse)throw new Error(t("reparseNeeded"));
  if(!state.lines.length||!state.lines.every(lineIsValid))throw new Error(t("fixLines"));
  if(!$("customer").value.trim())throw new Error(t("chooseCustomer"));
  if(!await copilot.review())throw new Error(t("reviewBlocking"));renderReview();updateFlow(2);persistInput();
});
$("reviewEditUpgrade").addEventListener("click",()=>$("editQuote").click());
for(const id of ["customer","inquiryText","notes"])$(id).addEventListener("input",()=>{
  state.dirty=true;if(id!=="notes")$("sourceConfirmed").checked=false;if(id==="inquiryText"){state.needsReparse=true;copilot.invalidate();}persistInput();renderCapture();
});
$("quoteLanguage").addEventListener("change",()=>{state.dirty=true;persistInput();});
onClick("acceptCapture",async()=>{if(state.pendingCapture)await receiveInquiry(state.pendingCapture,true);});
onClick("keepCapture",async()=>{
  if(state.pendingCapture){state.lastCaptureId=state.pendingCapture.captureId;await localSet("lastCaptureId",state.lastCaptureId);}
  state.pendingCapture=null;$("captureQueue").hidden=true;
});
const samples={zh:"A牌50kg水泥20袋，多少钱？",en:"How much for 20 bags of Brand A cement 50kg?",ms:"Berapa harga 20 beg simen Brand A 50kg?",missing:"A牌水泥20袋，多少钱？"};
document.querySelectorAll("[data-sample]").forEach(button=>button.addEventListener("click",()=>{
  if(state.dirty&&!window.confirm(t("discardWork")))return;
  newInquiry();$("inquiryText").value=samples[button.dataset.sample];$("customer").value="Demo 01";state.dirty=true;$("captureInfo").textContent=t("manualSource");persistInput();
}));
async function parseInquiry(){
  const text=$("inquiryText").value.trim();if(!text)throw new Error(t("enterInquiry"));if(!state.catalog.products.length)throw new Error(t("noProducts"));
  if(!$("customer").value.trim())throw new Error(t("chooseCustomer"));
  const captureId=state.captureId,sequence=context();
  const parsed=await api("/inquiries/parse",{method:"POST",body:{text,...copilot.parseBody()}});
  if(sequence!==workspaceSequence||text!==$("inquiryText").value.trim() || captureId!==state.captureId)return;
  state.lines=parsed.items;state.dirty=true;state.needsReparse=false;$("quoteLanguage").value=parsed.language;
  state.parseMeta={method:parsed.method,ai_state:parsed.ai_state,ai_model:parsed.ai_model,warning_code:parsed.warning_code};renderParseMethod();
  $("lineCard").hidden=false;$("clarificationBox").hidden=parsed.status==="READY";$("clarification").textContent=parsed.clarification;
  if(state.quote)$("quoteCard").hidden=true;renderLines();renderCapture();updateFlow(1);persistInput();
  await copilot.afterParse(parsed);persistInput();
}
onClick("parse",parseInquiry);
onClick("copyQuestion",async()=>{await copyText($("clarification").textContent);notify(t("copied"));});
onClick("fillQuestion",async()=>{await extensionMessage("WAQ_FILL_QUESTION",{captureId:state.captureId,text:$("clarification").textContent});notify(t("replyInserted"));});
$("addLine").addEventListener("click",()=>{state.lines.push({sku:"",quantity:"",source_text:"",candidates:[]});state.dirty=true;renderLines();persistInput();});
async function saveDraft(submitAfter=false){
  const sequence=context();
  if(state.needsReparse)throw new Error(t("reparseNeeded"));
  if(!$("customer").value.trim())throw new Error(t("chooseCustomer"));
  if(!$("sourceConfirmed").checked)throw new Error(t("confirmSourceFirst"));
  if(!state.lines.length||!state.lines.every(lineIsValid))throw new Error(t("fixLines"));
  if(!await copilot.review())throw new Error(t("reviewBlocking"));
  if(sequence!==workspaceSequence)return;
  if(!$("sourceConfirmed").checked)throw new Error(t("confirmSourceFirst"));
  const body={customer:$("customer").value.trim(),inquiry:$("inquiryText").value.trim(),language:$("quoteLanguage").value,
    items:state.lines.map(i=>({sku:i.sku,quantity:i.quantity})),notes:$("notes").value,source_confirmed:true,request_key:state.requestKey,source:state.source,...copilot.draftFields()};
  if(state.quote)body.expected_revision=state.quote.revision;
  const inputKey=draftInputKey();
  let quote=await api(state.quote?"/quotes/"+state.quote.id:"/quotes",{method:state.quote?"PUT":"POST",body});
  if(submitAfter)quote=await api("/quotes/"+quote.id+"/submit",{method:"POST",body:{expected_revision:quote.revision}});
  if(sequence===workspaceSequence){
    if(inputKey===draftInputKey()){state.dirty=false;$("inquiryCard").hidden=true;$("lineCard").hidden=true;renderQuote(quote);localSet("draftInput",null);notify(t(submitAfter?"submitted":"saved"));}
    else{state.quote=quote;state.editing=true;state.dirty=true;copilot.invalidate();persistInput();notify(t(submitAfter?"submitted":"saved")+" "+t("draftChangesKept"));}
  }
  await refreshRecords();
}
onClick("saveDraft",()=>saveDraft(false));
onClick("saveSubmit",()=>saveDraft(true));
onClick("submit",async()=>{
  if(state.dirty)throw new Error(t("saveChangesFirst"));
  const q=state.quote,sequence=context(),result=await api("/quotes/"+q.id+"/submit",{method:"POST",body:{expected_revision:q.revision}});
  if(sameQuote(sequence,q)){renderQuote(result);notify(t("submitted"));}await refreshRecords();
});
onClick("copyMobileLink",async()=>{
  const link=await api("/quotes/"+state.quote.id+"/mobile-link",{method:"POST",body:{expected_revision:state.quote.revision}});
  await copyText(link.url);notify(t("mobileLinkCopied"));
});
onClick("notifyPhone",async()=>{
  const confirmResend=["ACCEPTED","UNKNOWN"].includes(state.quote.mobile_notification?.status);
  if(confirmResend&&!window.confirm(t("confirmResend")))return;
  const q=state.quote,sequence=context(),result=await api("/quotes/"+q.id+"/phone-notification",{method:"POST",
    body:{expected_revision:q.revision,confirm_resend:confirmResend}});
  if(sameQuote(sequence,q)){renderQuote(result);notify(t("phoneQueued"));}
});
onClick("approve",async()=>{
  const q=state.quote,sequence=context(),result=await api("/quotes/"+q.id+"/approve",{method:"POST",body:{expected_revision:q.revision,...copilot.decisionBody(q)}});
  if(sameQuote(sequence,q)){renderQuote(result);notify(t("approved"));}await refreshRecords();await pollInbox();
});
onClick("reject",async()=>{
  const reason=$("rejectReason").value.trim();if(!reason)throw new Error(t("needReason"));
  const q=state.quote,sequence=context(),result=await api("/quotes/"+q.id+"/reject",{method:"POST",body:{expected_revision:q.revision,reason}});
  if(sameQuote(sequence,q)){renderQuote(result);$("rejectReason").value="";notify(t("returned"));}await refreshRecords();await pollInbox();
});
onClick("retryExport",async()=>{const q=state.quote,sequence=context(),result=await api("/quotes/"+q.id+"/export",{method:"POST",body:{expected_revision:q.revision}});if(sameQuote(sequence,q))renderQuote(result);});
onClick("downloadPDF",async()=>{
  const q=state.quote;
  await download("/quotes/"+q.id+"/pdf?revision="+q.revision,q.id+"-r"+q.revision+".pdf");
  await api("/quotes/"+q.id+"/activity",{method:"POST",body:{action:"PDF_PREPARED",revision:q.revision}});
});
onClick("downloadLedger",()=>download("/exports/ledger","quotations.xlsx"));
$("replyLanguage").addEventListener("change",updateReply);
onClick("copyReply",async()=>{
  const q=state.quote,sequence=context();await copyText($("replyText").value);await api("/quotes/"+q.id+"/activity",{method:"POST",body:{action:"REPLY_COPIED",revision:q.revision}});if(sameQuote(sequence,q))notify(t("copied"));
});
onClick("fillReply",async()=>{
  const result=await extensionMessage("WAQ_FILL_REPLY",{quoteId:state.quote.id,revision:state.quote.revision,language:$("replyLanguage").value});
  notify(t(result.logged===false?"replyInsertedLogPending":"replyInserted"));
});
onClick("notifyDesktop",async()=>{
  let granted;
  if(EXTENSION)granted=await chrome.permissions.request({permissions:["notifications"]});
  else granted=(await Notification.requestPermission())==="granted";
  if(!granted)throw new Error(t("notificationDenied"));
  state.desktopEnabled=true;await localSet("desktopEnabled",true);state.notificationIds=null;await pollInbox();notify(t("desktopEnabled"));
});
onClick("refreshQuote",async()=>{await loadQuote(state.quote.id);});
onClick("refreshRecords",refreshRecords);
onClick("editQuote",async()=>{
  const q=state.quote,sequence=++workspaceSequence,catalog=await api("/catalog");if(!sameQuote(sequence,q))return;
  state.catalog=catalog;state.dirty=true;state.editing=true;state.needsReparse=false;state.requestKey=crypto.randomUUID();
  state.parseMeta=null;renderParseMethod();
  $("customer").value=q.customer;$("inquiryText").value=q.inquiry;$("notes").value=q.notes;$("quoteLanguage").value=q.language;$("sourceConfirmed").checked=false;
  state.lines=q.items.map((i,index)=>({sku:i.sku,quantity:i.quantity,source_id:q.review?.sources[index]||null,source_text:i.sku,candidates:[]}));$("inquiryCard").hidden=false;$("lineCard").hidden=false;$("quoteCard").hidden=true;$("clarificationBox").hidden=true;
  copilot.edit(q);
  renderLines();renderCapture();$("sourceEditor").open=!state.source;updateFlow(1);persistInput();if(state.catalog.id!==q.catalog_id)notify(t("catalogChanged"));
});
onClick("downloadTemplate",()=>download("/catalog/template","products.xlsx"));
$("catalogFile").addEventListener("change",()=>{invalidatePreview();$("columnMapping").replaceChildren();$("importSheet").replaceChildren();$("sheetLabel").hidden=true;});
$("importSheet").addEventListener("change",()=>{invalidatePreview();$("columnMapping").replaceChildren();notify(t("catalogPreviewStale"));});
onClick("previewCatalog",async()=>{
  const upload=await uploadData(),preview=await api("/catalog/preview",{method:"POST",body:upload});state.upload=upload;state.preview=preview;renderMapping(preview);
  $("importPreview").replaceChildren();
  if(preview.valid){$("importPreview").append(node("p",preview.products.length+" "+t("products")+". "+t("importValid"),"info"));$("commitCatalog").hidden=false;}
  else{$("importPreview").append(node("p",t("importInvalid")+"\n"+preview.errors.map(e=>"Row "+e.row+": "+e.message).join("\n"),"import-errors"));$("commitCatalog").hidden=true;}
});
onClick("commitCatalog",async()=>{
  if(!state.preview?.valid)throw new Error(t("catalogPreviewStale"));
  state.catalog=await api("/catalog/import",{method:"POST",body:state.upload});renderCatalog();invalidatePreview();notify(t("catalogSaved"));setView("inquiry");
  if(EXTENSION){const inquiry=await localGet("inquiry");if(inquiry?.text && inquiry.captureId!==state.lastCaptureId)await receiveInquiry(inquiry);}
});
$("shopForm").addEventListener("submit",event=>{event.preventDefault();run($("shopForm").querySelector("button"),async()=>{
  await api("/shop",{method:"PUT",body:{name:$("shopName").value,address:$("shopAddress").value,phone:$("shopPhone").value,terms:$("shopTerms").value}});notify(t("settingsSaved"));
});});
if(EXTENSION)chrome.storage.onChanged.addListener((changes,area)=>{
  if(area==="local" && changes.inquiry?.newValue?.text && state.auth)receiveInquiry(changes.inquiry.newValue).catch(error=>notify(error.message,true));
});
const connectionFields={ai_enabled:"aiEnabled",ai_model:"aiModel",wa_enabled:"waEnabled",wa_phone_id:"waPhoneId",boss_phone:"bossPhone",
  phone_confirmed:"phoneConfirmed",wa_version:"waVersion",wa_mode:"waMode",wa_template:"waTemplate",wa_template_language:"waTemplateLanguage",
  notification_language:"notificationLanguage",public_url:"publicURL",link_minutes:"linkMinutes"};
function connectionMode(){ $("templateFields").hidden=$("waMode").value!=="template"; }
async function loadConnections(){
  if(state.auth?.user.role!=="boss")return;
  const settings=await api("/integrations");
  for(const [field,id] of Object.entries(connectionFields)){
    if($(id).type==="checkbox")$(id).checked=Boolean(settings[field]);else $(id).value=settings[field];
  }
  $("aiKey").value="";$("waToken").value="";$("clearAIKey").checked=false;$("clearWAToken").checked=false;
  $("aiKeyState").textContent=t(settings.ai_key_saved?"credentialSaved":"credentialMissing");
  $("waTokenState").textContent=t(settings.wa_token_saved?"credentialSaved":"credentialMissing");
  state.credentialFlags={ai:settings.ai_key_saved,wa:settings.wa_token_saved};
  connectionMode();
}
$("waMode").addEventListener("change",connectionMode);
$("bossPhone").addEventListener("input",()=>$("phoneConfirmed").checked=false);
onClick("refreshConnections",loadConnections);
$("connectionsForm").addEventListener("submit",event=>{
  event.preventDefault();run($("saveConnections"),async()=>{
    const body={};
    for(const [field,id] of Object.entries(connectionFields))body[field]=$(id).type==="checkbox"?$(id).checked:$(id).type==="number"?Number($(id).value):$(id).value;
    Object.assign(body,{ai_key:$("aiKey").value,wa_token:$("waToken").value,clear_ai_key:$("clearAIKey").checked,clear_wa_token:$("clearWAToken").checked});
    await api("/integrations",{method:"PUT",body});await loadConnections();state.connectionStatus=await api("/integrations/status");notify(t("connectionsSaved"));
  });
});
setInterval(pollInbox,5000);
(async()=>{
  state.lang=await localGet("lang")||"zh";state.auth=await localGet("auth");state.lastCaptureId=await localGet("lastCaptureId");
  state.desktopEnabled=Boolean(await localGet("desktopEnabled"));applyLanguage();await connect();
})();
})();
