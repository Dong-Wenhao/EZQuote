"use strict";
(() => {
  if (document.getElementById("waq-open-panel")) return;
  const pageSession = crypto.randomUUID();
  let language = "zh", lastSelection = "", selectedWrapper = null, timer;
  let binding = {main: null, header: null, title: "", token: ""};
  const labels = {
    zh: {open:"报价工作台",quote:"生成报价",hint:"点击消息旁的「生成报价」，或先选中文字",empty:"请点击一条文字消息旁的「生成报价」，或先选中询价文字。",tooLong:"请只选择本次询价，最多 12000 字符。",failed:"请从 Chrome 工具栏打开报价工作台，再粘贴询价。",filled:"已填入回复，请核对后手动发送。"},
    en: {open:"Quote Desk",quote:"Prepare quote",hint:"Use Prepare quote next to a message, or select its text",empty:"Choose Prepare quote next to a text message, or select inquiry text first.",tooLong:"Select one inquiry, up to 12,000 characters.",failed:"Open Quote Desk from the Chrome toolbar and paste the inquiry.",filled:"Reply inserted. Review it before sending."},
    ms: {open:"Meja sebut harga",quote:"Sediakan sebut harga",hint:"Klik Sediakan sebut harga di sebelah mesej, atau pilih teks",empty:"Klik Sediakan sebut harga di sebelah mesej teks, atau pilih teks pertanyaan dahulu.",tooLong:"Pilih satu pertanyaan, maksimum 12,000 aksara.",failed:"Buka Meja Sebut Harga dari bar alat Chrome dan tampal pertanyaan.",filled:"Balasan dimasukkan. Semak sebelum menghantar."}
  };
  const text = key => (labels[language] || labels.zh)[key];
  function toast(message) {
    let element = document.getElementById("waq-toast");
    if (!element) {element=document.createElement("div");element.id="waq-toast";element.setAttribute("role","status");document.documentElement.append(element);}
    element.textContent=message;element.hidden=false;
    clearTimeout(element.waqTimer);element.waqTimer=setTimeout(()=>element.hidden=true,6500);
  }
  function chatContext() {
    const main=document.querySelector("#main"),header=main?.querySelector("header");
    const name=header?.querySelector('[data-testid="conversation-info-header-chat-title"], span[dir="auto"][title], [data-testid="conversation-info-header"] [title]');
    const title=(name?.getAttribute("title") || name?.textContent || "").trim().slice(0,160);
    if(main!==binding.main || header!==binding.header || title!==binding.title){
      binding={main,header,title,token:crypto.randomUUID()};
    }
    return main && header && title ? {main,chat_title:title,chat_token:binding.token,page_session:pageSession} : null;
  }
  function makeSource(wrapper) {
    const context=chatContext();
    if(!context || !wrapper || !context.main.contains(wrapper))return null;
    if(!wrapper.dataset.waqAnchor)wrapper.dataset.waqAnchor=crypto.randomUUID();
    return {kind:"whatsapp",page_session:pageSession,chat_token:context.chat_token,chat_title:context.chat_title,
      message_id:wrapper.getAttribute("data-id")||"",anchor:wrapper.dataset.waqAnchor};
  }
  function messageText(wrapper) {
    const parts=[...wrapper.querySelectorAll(".selectable-text.copyable-text, [data-testid='msg-text']")]
      .filter(e=>!e.closest('[data-testid="quoted-message"], [data-testid="quoted-message-preview"]'));
    return parts.filter(e=>!parts.some(other=>other!==e && other.contains(e)))
      .map(e=>(e.innerText || e.textContent || "").trim()).filter(Boolean).join("\n");
  }
  function openPanel(inquiry,wrapper) {
    if(inquiry.length>12000){toast(text("tooLong"));return;}
    const source=makeSource(wrapper);
    chrome.runtime.sendMessage({type:"WAQ_OPEN_PANEL",text:inquiry,source}, response=>{
      const error=chrome.runtime.lastError?.message || response?.error;
      if(error)toast(text("failed")+" "+error);
    });
  }
  document.addEventListener("selectionchange",()=>{
    const selection=window.getSelection(),value=selection?.toString().trim()||"";
    if(value){
      lastSelection=value;
      const anchor=selection.anchorNode?.nodeType===Node.ELEMENT_NODE?selection.anchorNode:selection.anchorNode?.parentElement;
      selectedWrapper=anchor?.closest("[data-id], .message-in, .message-out")||null;
    }
  });
  const button=document.createElement("button");
  button.id="waq-open-panel";button.type="button";
  function refreshLabels(){
    button.textContent=text("open");button.title=text("hint");button.setAttribute("aria-label",text("open"));
    document.querySelectorAll(".waq-message-action").forEach(e=>{e.textContent=text("quote");e.title=text("quote");});
  }
  refreshLabels();
  button.addEventListener("click",()=>{
    openPanel(lastSelection,selectedWrapper);
    if(!lastSelection)toast(text("empty"));
    lastSelection="";selectedWrapper=null;
  });
  document.documentElement.append(button);
  function decorateMessages() {
    const context=chatContext();if(!context)return;
    context.main.querySelectorAll(".message-in").forEach(message=>{
      const wrapper=message.closest("[data-id]")||message;
      if(wrapper.querySelector(":scope > .waq-message-action") || !messageText(wrapper))return;
      const action=document.createElement("button");action.type="button";action.className="waq-message-action";
      action.textContent=text("quote");action.title=text("quote");
      action.addEventListener("click",event=>{
        event.preventDefault();event.stopPropagation();
        if(!wrapper.isConnected)return;
        openPanel(messageText(wrapper),wrapper);
      });
      wrapper.classList.add("waq-message");wrapper.append(action);
    });
  }
  function fillDraft(message) {
    const source=message.source,context=chatContext();
    if(!source || !context || source.page_session!==pageSession || source.chat_title!==context.chat_title ||
      (!source.message_id && source.chat_token!==context.chat_token))
      return {ok:false,code:"chat_changed"};
    // A source message must still be present. Identical contact names are not proof of identity.
    const anchor=[...context.main.querySelectorAll("[data-id], [data-waq-anchor]")].find(e=>
      source.message_id ? e.getAttribute("data-id")===source.message_id : e.dataset.waqAnchor===source.anchor);
    if(!anchor)return {ok:false,code:"source_not_visible"};
    const composer=context.main.querySelector('footer [contenteditable="true"][role="textbox"], footer [contenteditable="true"][data-lexical-editor]');
    if(!composer)return {ok:false,code:"composer_missing"};
    if((composer.innerText||composer.textContent||"").replace(/\u200b/g,"").trim())return {ok:false,code:"draft_exists"};
    if(typeof message.text!=="string" || !message.text.trim() || message.text.length>12000)return {ok:false,code:"invalid_text"};
    composer.focus();
    const range=document.createRange(),selection=window.getSelection();range.selectNodeContents(composer);selection.removeAllRanges();selection.addRange(range);
    document.execCommand("insertText",false,message.text);
    if(!(composer.innerText||composer.textContent||"").trim())return {ok:false,code:"insert_failed"};
    composer.dispatchEvent(new InputEvent("input",{bubbles:true,inputType:"insertText",data:message.text}));
    toast(text("filled"));
    return {ok:true};
  }
  chrome.runtime.onMessage?.addListener((message,sender,respond)=>{
    if(sender.id!==chrome.runtime.id)return false;
    if(message?.type==="WAQ_CONTEXT"){
      const selection=window.getSelection(),anchor=selection?.anchorNode?.parentElement;
      respond({source:makeSource(anchor?.closest("[data-id], .message-in, .message-out"))});return false;
    }
    if(message?.type!=="WAQ_INSERT_DRAFT")return false;
    respond(fillDraft(message));return false;
  });
  const observer=new MutationObserver(()=>{
    clearTimeout(timer);timer=setTimeout(decorateMessages,120);
  });
  observer.observe(document.body,{childList:true,subtree:true});
  decorateMessages();
  chrome.storage?.local.get("lang").then(result=>{language=result.lang||"zh";refreshLabels();}).catch(()=>{});
  chrome.storage?.onChanged.addListener((changes,area)=>{
    if(area==="local" && changes.lang){language=changes.lang.newValue||"zh";refreshLabels();}
  });
})();
