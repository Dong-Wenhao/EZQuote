"use strict";
window.createQuoteCopilot = ({$,state,api,t,node,money,notify,run,setView,refreshRecords,renderQuote,renderLines,renderCatalog,persistInput,newInquiry,download,context,sameQuote}) => {
  state.business={configured:false,inventory:{},delivery:[],rules:{}};
  let requirement=null,preview=null,upload=null,previewImport=null,ownerEdit=null,lastSync=0,previewSequence=0,pricingStatus="idle";
  const parserVersion="requirements_rules_v5";
  let checked=null,corrections=[],lastIssues=[],resolutionDrafts={},correctionScopes={};
  const enabled=()=>$("cpSmart").checked;
  const fulfilment=()=>$("cpFulfilment").value==="auto"?(requirement?.fulfilment||"delivery"):$("cpFulfilment").value;
  const area=()=>fulfilment()==="pickup"?"":$("cpArea").value.trim();
  const validItems=()=>state.lines.length&&state.lines.every(l=>l.sku&&Number(l.quantity)>0);
  function reviewState(status){
    pricingStatus=status;$("cpReviewState").dataset.state=status;
    $("cpReviewStateText").textContent=t("reviewState_"+status);
    $("cpReviewState").hidden=!enabled();
    $("cpPreviewBox").setAttribute("aria-busy",String(status==="checking"));
  }
  const pairs=(container,entries)=>{const grid=node("dl",undefined,"cp-money-grid");for(const [label,value]of entries){grid.append(node("dt",label),node("dd",value));}container.append(grid);};
  function pricingView(container,pricing){
    container.replaceChildren();if(!pricing)return;
    const r=pricing.recommendation,d=pricing.decision;
    const compare=node("div",undefined,"pricing-comparison");
    for(const [label,value,kind]of [[t("cpOriginalTotal"),r.original_total,""],[t(d?"cpFinalTotal":"cpShortRecommended"),d?d.final_total:r.recommended_total," recommended"]]){
      const tile=node("div",undefined,"price-tile"+kind);tile.append(node("small",label),node("strong",money(value)));compare.append(tile);
    }
    container.append(compare);
    pairs(container,[[t("cpOriginalProducts"),money(r.original_product_price)],
      [t(d?"cpFinalDiscount":"cpSuggestedDiscount"),(d?d.discount_pct:r.suggested_discount_pct)+"% · −"+money(d?d.discount_amount:r.suggested_discount_amount)],
      [t(d?"cpFinalFreight":"cpSuggestedFreight"),money(d?d.freight:r.suggested_freight)]]);
    const reasons=node("details");reasons.append(node("summary",t("cpReasons")));
    pairs(reasons,[[t("cpBaseFreight"),money(r.base_freight)],[t("cpOriginalTotal"),money(r.original_total)],...(d?[[t("cpShortRecommended"),money(r.recommended_total)]]:[])]);
    reasons.append(node("p",t(r.confidence==="low"?"cpLowConfidence":"cpMediumConfidence"),"muted small"));
    const list=node("ul");for(const reason of (r.reasons[state.lang]||r.reasons.en))list.append(node("li",reason));reasons.append(list);container.append(reasons);
    if(d){
      container.append(node("p",t(d.mode==="edited"?"cpEdited":"cpAccepted"),"muted small"));
      if(d.note)container.append(node("p",d.note,"prewrap small"));
    }
  }
  function toggle(){
    $("cpDeliveryInputs").hidden=!enabled();$("cpPreviewBox").hidden=!enabled();
    $("cpReviewState").hidden=!enabled();
    $("cpRequirement").hidden=!enabled()||!requirement;
    $("cpArea").disabled=fulfilment()==="pickup";
  }
  function invalidate(){
    preview=null;checked=null;previewSequence++;$("sourceConfirmed").checked=false;$("cpPreview").replaceChildren();$("cpPreviewHint").textContent=t("cpPreviewNeeded");toggle();
    reviewState("idle");
  }
  function correctionValue(problem){
    const line=state.lines.find(l=>l.source_id===problem.source_id)||state.lines[problem.item_index];
    const product=line&&state.catalog.products.find(p=>p.sku===line.sku);
    if(problem.choices)return resolutionDrafts[problem.id]?.value||null;
    if(problem.code==="missing_product")return resolutionDrafts[problem.id]?.value==="remove"?{action:"remove",source_id:problem.source_id}:null;
    if(problem.code==="extra_product")return line?{sku:line.sku,quantity:String(Number(line.quantity))}:null;
    if(problem.field==="quantity")return line?String(Number(line.quantity)):null;
    if(problem.field==="sku")return line?.sku||null;
    if(problem.field==="specification")return product?.spec||null;
    if(problem.field==="unit")return product?.unit||null;
    if(problem.field==="fulfilment")return fulfilment();
    if(problem.field==="area")return state.business.delivery.find(r=>[r.area,...r.aliases.split("|")].some(a=>a.toLowerCase()===area().toLowerCase()))?.area||area();
    return null;
  }
  function correctionScope(problem){
    const line=state.lines.find(l=>l.source_id===problem.source_id)||state.lines[problem.item_index];
    if(problem.field==="quantity")return String(Number(line?.quantity));
    if(problem.field==="area")return area().toLowerCase();
    if(problem.field==="fulfilment")return fulfilment();
    if(problem.code==="missing_product")return state.lines.some(l=>l.source_id===problem.source_id)?"present":"removed";
    if(problem.code==="extra_product")return JSON.stringify([line?.sku,String(Number(line?.quantity))]);
    return line?.sku||"";
  }
  function showIssues(issues){
    lastIssues=issues||[];const container=$("reviewIssues");container.replaceChildren();container.hidden=!lastIssues.length;
    if(!lastIssues.length)return;
    container.append(node("h3",t("reviewNeedsAction")),node("p",t("reviewActionHelp"),"muted small"));
    for(const problem of lastIssues){
      const box=node("div",undefined,"review-issue"),draft=resolutionDrafts[problem.id]||{reason:"",value:""};resolutionDrafts[problem.id]=draft;
      box.dataset.issueCode=problem.code;
      box.append(node("strong",t("issue_"+problem.code)),node("p",problem.source_text?.slice(0,500)||"","prewrap small"));
      const hard=["multiple_products","multiple_quantities","ambiguous_modifier","uncovered_text"].includes(problem.code)||problem.code==="stock";
      if(!hard){
        if(problem.target)box.append(node("p",t("reviewTarget")+": "+(t("target_"+problem.target)=== "target_"+problem.target?problem.target:t("target_"+problem.target)),"small"));
        if(problem.choices||problem.code==="missing_product"){
          const select=node("select");select.setAttribute("aria-label",t("reviewFinalChoice"));const empty=node("option",t("reviewChoose"));empty.value="";select.append(empty);
          const options=problem.choices||["remove"];
          for(const value of options){const option=node("option",t("choice_"+value));option.value=value;select.append(option);}select.value=draft.value;
          select.addEventListener("change",()=>{draft.value=select.value;
            if(problem.field==="fulfilment"){
              if(["pickup","delivery"].includes(select.value))$("cpFulfilment").value=select.value;
              else if(problem.target==="pickup"&&select.value==="include")$("cpFulfilment").value="pickup";
              else if(problem.target==="pickup"&&select.value==="exclude")$("cpFulfilment").value="delivery";
            }invalidate();persistInput();});box.append(select);
        }else box.append(node("p",t("reviewConfirmCurrent"),"muted small"));
        const label=node("label"),input=node("input");label.append(node("span",t("reviewReason")),input);input.maxLength=500;input.value=draft.reason;input.setAttribute("aria-label",t("reviewReason"));
        input.addEventListener("input",()=>{draft.reason=input.value;persistInput();});box.append(label);
      }else box.append(node("p",t(problem.code==="stock"?"reviewStockHelp":"reviewEditHelp"),"muted small"));
      container.append(box);
    }
    const button=node("button",t("reviewApply"),"secondary full");button.id="applyRequirementCorrections";button.type="button";
    button.addEventListener("click",()=>run(button,async()=>{
      const next=corrections.filter(c=>!lastIssues.some(p=>p.id===c.issue_id));
      for(const problem of lastIssues){const draft=resolutionDrafts[problem.id],value=correctionValue(problem);if(draft?.reason.trim().length>=3&&value!==null){next.push({issue_id:problem.id,value,reason:draft.reason.trim()});correctionScopes[problem.id]={problem,scope:correctionScope(problem)};}}
      corrections=next;invalidate();if(await refreshPricing())notify(t("reviewConfirmed"));persistInput();
    }));container.append(button);
  }
  async function refreshPricing(quiet=false){
    if(!enabled())return true;
    if(!validItems()){reviewState("blocked");if(!quiet)throw new Error(t("fixLines"));return false;}
    const sequence=++previewSequence;
    reviewState("checking");
    try{
      if(!state.business.configured)throw new Error(t("cpImportFirst"));
      if(fulfilment()==="delivery"&&!area())throw new Error(t("cpChooseDelivery"));
      corrections=corrections.filter(c=>{const saved=correctionScopes[c.issue_id];if(saved&&saved.scope!==correctionScope(saved.problem)){delete resolutionDrafts[c.issue_id];delete correctionScopes[c.issue_id];return false;}return true;});
      const payload={items:state.lines.map(l=>({sku:l.sku,quantity:l.quantity,source_id:l.source_id||null})),inquiry:$("inquiryText").value.trim(),area:area(),fulfilment:fulfilment(),quote_id:state.quote?.id||null,expected_revision:state.quote?.revision||0,corrections};
      const reviewed=await api("/requirements/review",{method:"POST",body:payload});
      if(sequence!==previewSequence)throw new Error(t("review_stale"));
      if(!reviewed.can_quote){checked=null;preview=null;showIssues(reviewed.issue_details);$("cpPreview").replaceChildren();persistInput();throw new Error(t("reviewBlocking"));}
      checked=reviewed;showIssues([]);
      const body={items:payload.items.map(({sku,quantity})=>({sku,quantity})),inquiry:payload.inquiry,area:reviewed.facts.area,fulfilment:fulfilment(),quote_id:payload.quote_id,review_id:checked.review_id};
      const result=await api("/pricing/preview",{method:"POST",body});
      if(sequence!==previewSequence)throw new Error(t("review_stale"));
      preview=result;pricingView($("cpPreview"),result);$("cpPreviewHint").textContent="";$("clarificationBox").hidden=true;reviewState("ready");return true;
    }catch(e){if(sequence===previewSequence){$("cpPreviewHint").textContent=e.message;reviewState("blocked");}if(!quiet)throw e;return false;}
  }
  function renderBusiness(){
    const b=state.business;$("cpBusinessStats").replaceChildren();
    if(!b.configured){$("cpBusinessStats").append(node("p",t("cpNoData")));$("cpBusinessRules").textContent="";$("cpInventoryList").replaceChildren();return;}
    for(const [label,value]of [["cpOrders",b.orders],["cpClosedOrders",b.closed_orders],["cpLiveOrders",b.live_orders],["cpConversion",b.conversion_rate===null?"—":(Number(b.conversion_rate)*100).toFixed(1)+"%"]]){
      const block=node("div");block.append(node("strong",String(value)),node("small",t(label)));$("cpBusinessStats").append(block);
    }
    $("cpBusinessRules").textContent=t("cpMinimumMargin")+" "+b.rules.min_margin_pct+"% · "+t("cpMaximumDiscount")+" "+b.rules.max_discount_pct+"% · "+t("cpMaximumSubsidy")+" "+money(b.rules.max_delivery_subsidy);
    $("cpAreas").replaceChildren();for(const r of b.delivery){const option=node("option");option.value=r.area;$("cpAreas").append(option);}
    $("cpInventoryList").replaceChildren();
    for(const [sku,inv]of Object.entries(b.inventory)){
      const product=state.catalog.products.find(p=>p.sku===sku),row=node("div",undefined,"catalog-entry");
      const left=node("div",product?(product["name_"+state.lang]||product.name_en||product.name_zh):sku);left.append(node("small",sku));
      row.append(left,node("strong",t("cpStock")+" "+inv.stock+(product?" "+product.unit:"")));$("cpInventoryList").append(row);
    }
  }
  async function loadBusiness(initial=false){
    const previous=state.business?.id;state.business=await api("/business");lastSync=Date.now();
    if(initial&&state.business.configured)$("cpSmart").checked=true;
    if(previous&&previous!==state.business.id)invalidate();
    renderBusiness();toggle();
  }
  function ownerTotal(){
    const q=state.quote,r=q?.pricing?.recommendation;if(!r)return;
    const cents=value=>{const s=String(value);if(!/^\d+(\.\d{1,2})?$/.test(s))return null;const [whole,fraction=""]=s.split(".");return BigInt(whole)*100n+BigInt(fraction.padEnd(2,"0"));};
    const product=cents(r.original_product_price),basis=cents($("cpDiscount").value),fee=cents($("cpFreight").value);
    let value="—";
    if(product!==null&&basis!==null&&fee!==null&&basis<=10000n){const total=product-(product*basis+5000n)/10000n+fee;value="RM"+(total/100n).toLocaleString("en-MY")+"."+(total%100n).toString().padStart(2,"0");}
    $("cpOwnerTotal").textContent=t("cpFinalTotal")+" · "+value;
    ownerEdit={key:q.id+":"+q.revision,discount:$("cpDiscount").value,freight:$("cpFreight").value,note:$("cpDecisionNote").value};
  }
  function renderSaved(q){
    $("cpQuotePricing").hidden=!q.pricing;$("cpOwnerEdit").hidden=!q.pricing;$("cpOutcomeBox").hidden=!q.pricing;
    $("cpTotalCaption").textContent=q.pricing?t(q.approval?"cpFinalTotal":"cpRecommendedTotal"):t("quoteTotal");
    if(q.pricing){
      pricingView($("cpQuotePricing"),q.pricing);
      const key=q.id+":"+q.revision,r=q.pricing.recommendation;
      if(!ownerEdit||ownerEdit.key!==key)ownerEdit={key,discount:r.suggested_discount_pct,freight:r.suggested_freight,note:""};
      $("cpDiscount").value=ownerEdit.discount;$("cpFreight").value=ownerEdit.freight;$("cpDecisionNote").value=ownerEdit.note;
      ownerTotal();
      $("cpOutcome").value=q.outcome.outcome;$("cpOutcomeNote").value=q.outcome.note||"";$("cpActualCost").value=q.outcome.actual_delivery_cost||"";
      $("cpOutcomeState").textContent=t({open:"cpOpen",won:"cpWon",lost:"cpLost"}[q.outcome.outcome])+(q.outcome.updated_at?" · "+new Date(q.outcome.updated_at).toLocaleString():"");
    }
  }
  async function fileUpload(){
    const file=$("cpBusinessFile").files[0];if(!file)throw new Error(t("chooseFile"));
    if(file.size>5*1024*1024)throw new Error("Excel file exceeds 5 MB");
    const bytes=new Uint8Array(await file.arrayBuffer());let binary="";
    for(let i=0;i<bytes.length;i+=32768)binary+=String.fromCharCode(...bytes.subarray(i,i+32768));
    return {filename:file.name,content_b64:btoa(binary)};
  }
  const click=(id,fn)=>$(id).addEventListener("click",()=>run($(id),fn));
  $("cpSmart").addEventListener("change",()=>{if(enabled()&&!state.business.configured){$("cpSmart").checked=false;notify(t("cpImportFirst"),true);}else if(!enabled()&&state.business.configured){$("cpSmart").checked=true;notify(t("cpPricingRequired"),true);}requirement=null;$("cpRequirementJSON").textContent="";invalidate();state.dirty=true;persistInput();});
  for(const id of ["cpArea","cpFulfilment"])$(id).addEventListener(id==="cpArea"?"input":"change",()=>{invalidate();state.dirty=true;persistInput();});
  click("cpRefreshPricing",()=>refreshPricing());
  click("cpFullSample",async()=>{
    if(!state.business.configured){notify(t("cpImportFirst"),true);if(state.auth?.user.role==="boss")setView("business");return;}
    if(state.dirty&&!window.confirm(t("discardWork")))return;
    newInquiry();$("cpSmart").checked=true;$("inquiryText").value={zh:"我要20袋水泥用于抹灰，偏好速凝，送到莎阿南，多少钱？",en:"Hi boss, I need 20 bags cement for plastering. Prefer fast setting. Deliver to Shah Alam. How much?",ms:"Saya mahu 20 beg simen untuk melepa, mahu cepat kering. Hantar ke Shah Alam. Berapa harga?"}[state.lang];
    $("customer").value="Demo 01";state.dirty=true;toggle();persistInput();
  });
  click("cpAccept",async()=>{const r=state.quote.pricing.recommendation;$("cpDiscount").value=r.suggested_discount_pct;$("cpFreight").value=r.suggested_freight;$("cpDecisionNote").value="";ownerTotal();});
  for(const id of ["cpDiscount","cpFreight","cpDecisionNote"])$(id).addEventListener("input",()=>{ownerTotal();if($("notice").classList.contains("error"))$("notice").hidden=true;});
  click("cpSaveOutcome",async()=>{
    const q=state.quote,sequence=context();const result=await api("/quotes/"+q.id+"/outcome",{method:"POST",body:{expected_revision:q.revision,expected_outcome_version:q.outcome.version,outcome:$("cpOutcome").value,note:$("cpOutcomeNote").value,actual_delivery_cost:$("cpActualCost").value||null}});
    if(sameQuote(sequence,q))renderQuote(result);await loadBusiness();await refreshRecords();if(sameQuote(sequence,q))notify(t(result.ledger_error?"cpLedgerRetry":"cpOutcomeSaved"),Boolean(result.ledger_error));
  });
  click("cpBusinessTemplate",()=>download("/business/template","business_demo.xlsx"));
  click("cpBusinessRefresh",()=>loadBusiness());
  $("cpBusinessFile").addEventListener("change",()=>{upload=previewImport=null;$("cpBusinessImport").hidden=true;$("cpImportSummary").textContent="";});
  click("cpBusinessPreview",async()=>{upload=await fileUpload();previewImport=await api("/business/preview",{method:"POST",body:upload});$("cpImportSummary").textContent="Products "+previewImport.products+" · Inventory "+previewImport.inventory_rows+" · History "+previewImport.history_orders+" · Delivery "+previewImport.delivery_areas;$("cpBusinessImport").hidden=false;});
  click("cpBusinessImport",async()=>{
    if(!previewImport||!upload)throw new Error(t("catalogPreviewStale"));
    state.business=await api("/business/import",{method:"POST",body:upload});state.catalog=await api("/catalog");$("cpBusinessImport").hidden=true;previewImport=null;
    $("cpSmart").checked=true;renderBusiness();toggle();renderCatalog();renderLines();notify(t("cpImported"));
    // The catalog view is rebuilt through the existing language/render path on next tab refresh.
  });
  return {
    loadBusiness, renderQuote:renderSaved, invalidate,review:refreshPricing,
    language(){renderBusiness();if(preview)pricingView($("cpPreview"),preview);if(requirement)$("cpRequirementJSON").textContent=JSON.stringify(requirement,null,2);showIssues(lastIssues);toggle();reviewState(pricingStatus);},
    parseBody(){if(!enabled())return {};if(!state.business.configured)throw new Error(t("cpImportFirst"));return {mode:"requirements",area:area(),fulfilment:$("cpFulfilment").value};},
    async afterParse(parsed){requirement=parsed.requirement||null;corrections=[];resolutionDrafts={};correctionScopes={};checked=null;showIssues(parsed.issue_details||[]);if(requirement){$("cpArea").value=requirement.area||$("cpArea").value;$("cpFulfilment").value=requirement.fulfilment;$("cpRequirementJSON").textContent=JSON.stringify(requirement,null,2);}toggle();reviewState(parsed.status==="READY"?"idle":"blocked");if(parsed.status==="READY"&&enabled())await refreshPricing(true);},
    draftFields(){if(!enabled())return {};if(!state.business.configured)throw new Error(t("cpImportFirst"));if(fulfilment()==="delivery"&&!area())throw new Error(t("cpChooseDelivery"));return {pricing_enabled:true,delivery_area:checked?.facts.area||area(),fulfilment:fulfilment(),review_id:checked?.review_id||null};},
    decisionBody(q){return q.pricing?{discount_pct:$("cpDiscount").value,freight:$("cpFreight").value,pricing_note:$("cpDecisionNote").value}:{};},
    renderMatch(line,block){
      const best=line.best_match,selected=state.catalog.products.find(p=>p.sku===line.sku);
      if(!selected)return;
      const isBest=best?.sku===selected.sku,card=node("div",undefined,"cp-match");
      card.append(node("span",t(isBest?"cpBestMatch":"cpSelected"),"match-badge"),node("strong",selected.brand+" "+(selected["name_"+state.lang]||selected.name_en||selected.name_zh)+" · "+selected.spec));
      const inv=state.business.inventory?.[selected.sku];if(inv)card.append(node("p",t("cpStock")+" "+inv.stock+" "+selected.unit+" · "+money(selected.unit_price)+" / "+selected.unit,"match-stock"));
      const excluded=Object.values(line.constraints||{}).flatMap(c=>c.exclude||[]);
      if(excluded.length)card.append(node("p",t("reviewExcluded")+": "+excluded.map(v=>t("target_"+v)==="target_"+v?v:t("target_"+v)).join(" · "),"small"));
      if(isBest)card.append(node("p",(best.match_reasons[state.lang]||best.match_reasons.en).filter(reason=>!/^库存|^Stock|^Stok/i.test(reason)).join(" · "),"small"));
      if(line.alternatives?.length){const alternatives=node("details");alternatives.append(node("summary",t("cpAlternatives")));
        for(const alternative of line.alternatives.filter(a=>a.sku!==selected.sku)){
          const button=node("button",alternative.brand+" · "+alternative.spec+" · "+money(alternative.unit_price)+" · "+t("cpStock")+" "+(alternative.stock??"—"),"alternative-choice");button.type="button";
          button.addEventListener("click",()=>{line.sku=alternative.sku;state.dirty=true;renderLines();persistInput();});alternatives.append(button);
        }card.append(alternatives);
      }
      block.append(card);
    },
    persist(){return {parserVersion,smart:enabled(),area:$("cpArea").value,fulfilment:$("cpFulfilment").value,requirement,corrections,resolutionDrafts,correctionScopes,lastIssues};},
    restore(input){if(!input?.copilot)return {};const saved=input.copilot,needsReparse=Boolean((saved.smart||state.business.configured)&&input.lines?.length&&saved.parserVersion!==parserVersion);$("cpSmart").checked=Boolean(saved.smart||state.business.configured);$("cpArea").value=saved.area||"";$("cpFulfilment").value=saved.fulfilment||"auto";requirement=needsReparse?null:saved.requirement||null;corrections=needsReparse?[]:saved.corrections||[];resolutionDrafts=needsReparse?{}:saved.resolutionDrafts||{};correctionScopes=needsReparse?{}:saved.correctionScopes||{};showIssues(needsReparse?[]:saved.lastIssues||[]);$("cpRequirementJSON").textContent=requirement?JSON.stringify(requirement,null,2):"";invalidate();return {needsReparse};},
    reset(){requirement=null;ownerEdit=null;corrections=[];resolutionDrafts={};correctionScopes={};showIssues([]);$("cpArea").value="";$("cpFulfilment").value="auto";$("cpSmart").checked=Boolean(state.business.configured);invalidate();},
    edit(q){$("cpSmart").checked=Boolean(q.pricing||state.business.configured);requirement=q.pricing?.requirement||null;corrections=[];resolutionDrafts={};correctionScopes={};showIssues([]);$("cpArea").value=requirement?.area||"";$("cpFulfilment").value=requirement?.fulfilment||"auto";$("cpRequirementJSON").textContent=requirement?JSON.stringify(requirement,null,2):"";invalidate();},
    async sync(){if(Date.now()-lastSync>15000)await loadBusiness();}
  };
};
