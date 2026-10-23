"use strict";
(() => {
const $=id=>document.getElementById(id);
const dictionaries={
zh:{mobileTitle:"手机报价审批",loading:"正在读取这笔报价…",total:"报价合计",original:"查看客户原文与备注",decisionTitle:"核对后处理",passwordHelp:"输入你在电脑工作台设置的老板密码。",password:"老板密码",reason:"退回原因（批准时可不填）",approve:"批准并生成报价单",return:"退回修改",scope:"这里只处理当前报价版本，客户回复由员工核对后发送。",pdf:"下载这笔报价单",footer:"本链接有时效。手机审批和电脑工作台会同步更新。",pending:"待批准",approved:"已批准",returned:"已退回",processed:"已处理",expires:"链接有效期至",revision:"版本",ready:"请核对商品、数量和金额，再决定批准或退回。",approvedHelp:"老板批准已记录，员工可在电脑工作台继续准备客户回复。",returnedHelp:"退回原因已记录，员工需要修改并重新提交。",processedHelp:"这笔报价已在工作台处理。",exportPending:"批准已记录，PDF 归档待工作台重试。",mobile_invalid_link:"审批链接无效，请从最新通知重新打开。",mobile_expired:"审批链接已过期，请员工生成新的链接。",mobile_changed:"报价已修改，旧链接不能批准，请打开最新版本。",mobile_already_processed:"这条审批链接已经处理过。",mobile_wrong_password:"老板密码不正确，请重试。",mobile_too_many_attempts:"尝试次数较多，请一分钟后再试。",mobile_reason_required:"退回时请填写原因。",mobile_service_offline:"电脑上的报价服务暂未连接，请保持电脑和手机模式运行后重试。",mobile_pdf_pending:"PDF 尚未准备好，请稍后从工作台重试。",network:"连接失败，请确认电脑和手机审批服务正在运行。",passwordRequired:"请填写老板密码。",working:"正在处理…",requestFailed:"处理失败，请刷新或稍后重试。"},
en:{mobileTitle:"Mobile quotation approval",loading:"Loading this quotation…",total:"Quotation total",original:"View inquiry and notes",decisionTitle:"Review and decide",passwordHelp:"Use the boss password set in the desktop workspace.",password:"Boss password",reason:"Reason for return (optional for approval)",approve:"Approve and generate quotation",return:"Return for changes",scope:"This action applies to this revision only. Staff review and send the customer reply.",pdf:"Download this quotation",footer:"This link expires. Mobile decisions update the desktop workspace.",pending:"Awaiting approval",approved:"Approved",returned:"Returned",processed:"Processed",expires:"Link expires",revision:"Revision",ready:"Check products, quantities and amount before approving or returning.",approvedHelp:"Approval recorded. Staff can prepare the customer reply in the desktop workspace.",returnedHelp:"The reason was recorded. Staff need to revise and submit again.",processedHelp:"This quotation has already been handled in the workspace.",exportPending:"Approval recorded. PDF export needs a retry in the workspace.",mobile_invalid_link:"This approval link is invalid. Open the latest notification.",mobile_expired:"This link expired. Ask staff for a new link.",mobile_changed:"The quotation changed. Open the latest revision.",mobile_already_processed:"This approval link has already been used.",mobile_wrong_password:"Incorrect boss password. Try again.",mobile_too_many_attempts:"Too many attempts. Wait one minute.",mobile_reason_required:"Enter a reason for returning this quotation.",mobile_service_offline:"The desktop service is unavailable. Keep the computer and mobile mode running.",mobile_pdf_pending:"The PDF is not ready. Retry the export in the workspace.",network:"Connection failed. Check that the computer and mobile service are running.",passwordRequired:"Enter the boss password.",working:"Working…",requestFailed:"The request failed. Refresh or try again later."},
ms:{mobileTitle:"Kelulusan sebut harga mudah alih",loading:"Memuatkan sebut harga…",total:"Jumlah sebut harga",original:"Lihat pertanyaan dan nota",decisionTitle:"Semak dan buat keputusan",passwordHelp:"Gunakan kata laluan bos yang ditetapkan pada komputer.",password:"Kata laluan bos",reason:"Sebab pemulangan (pilihan untuk kelulusan)",approve:"Luluskan dan jana sebut harga",return:"Pulangkan untuk pindaan",scope:"Tindakan ini hanya untuk versi ini. Staf menyemak dan menghantar balasan pelanggan.",pdf:"Muat turun sebut harga ini",footer:"Pautan ini tamat tempoh. Keputusan dikemas kini pada komputer.",pending:"Menunggu kelulusan",approved:"Diluluskan",returned:"Dipulangkan",processed:"Selesai diproses",expires:"Pautan tamat",revision:"Versi",ready:"Semak produk, kuantiti dan jumlah sebelum membuat keputusan.",approvedHelp:"Kelulusan direkodkan. Staf boleh menyediakan balasan pelanggan pada komputer.",returnedHelp:"Sebab direkodkan. Staf perlu meminda dan menghantar semula.",processedHelp:"Sebut harga ini telah diproses di ruang kerja.",exportPending:"Kelulusan direkodkan. Eksport PDF perlu dicuba semula di ruang kerja.",mobile_invalid_link:"Pautan tidak sah. Buka notifikasi terkini.",mobile_expired:"Pautan tamat tempoh. Minta pautan baharu daripada staf.",mobile_changed:"Sebut harga berubah. Buka versi terkini.",mobile_already_processed:"Pautan ini telah digunakan.",mobile_wrong_password:"Kata laluan bos salah. Cuba lagi.",mobile_too_many_attempts:"Terlalu banyak cubaan. Tunggu satu minit.",mobile_reason_required:"Isi sebab pemulangan.",mobile_service_offline:"Perkhidmatan komputer tidak tersedia. Biarkan komputer dan mod mudah alih berjalan.",mobile_pdf_pending:"PDF belum sedia. Cuba eksport semula di ruang kerja.",network:"Sambungan gagal. Semak komputer dan perkhidmatan mudah alih.",passwordRequired:"Isi kata laluan bos.",working:"Sedang diproses…",requestFailed:"Permintaan gagal. Muat semula atau cuba lagi nanti."}
};
Object.assign(dictionaries.zh,{pricingTitle:"原价与定价建议",acceptPricing:"采用建议值",discountPct:"最终折扣百分比",freightFee:"最终运费 RM",pricingNote:"定价说明（可选）",originalProducts:"商品原价",baseFreight:"基础运费",originalTotal:"原始总额",suggestedDiscount:"建议折扣",suggestedFreight:"建议运费",recommendedTotal:"建议总额 待批准",finalTotal:"最终总额",pricingReasons:"推荐依据"});
Object.assign(dictionaries.en,{pricingTitle:"Original price and recommendation",acceptPricing:"Accept recommendation",discountPct:"Final discount percent",freightFee:"Final delivery fee RM",pricingNote:"Pricing note (optional)",originalProducts:"Original product price",baseFreight:"Base delivery fee",originalTotal:"Original total",suggestedDiscount:"Suggested discount",suggestedFreight:"Suggested delivery fee",recommendedTotal:"Recommended total pending approval",finalTotal:"Final total",pricingReasons:"Recommendation reasons"});
Object.assign(dictionaries.ms,{pricingTitle:"Harga asal dan cadangan",acceptPricing:"Terima cadangan",discountPct:"Peratus diskaun akhir",freightFee:"Fi penghantaran akhir RM",pricingNote:"Nota harga (pilihan)",originalProducts:"Harga produk asal",baseFreight:"Fi penghantaran asas",originalTotal:"Jumlah asal",suggestedDiscount:"Diskaun dicadangkan",suggestedFreight:"Fi penghantaran dicadangkan",recommendedTotal:"Jumlah cadangan menunggu kelulusan",finalTotal:"Jumlah akhir",pricingReasons:"Sebab cadangan"});
Object.assign(dictionaries.zh,{adjustPricing:"调整折扣和运费",acceptPricing:"恢复建议值",approve:"确认并批准"});
Object.assign(dictionaries.en,{adjustPricing:"Adjust discount and delivery",acceptPricing:"Reset to recommendation",approve:"Confirm and approve"});
Object.assign(dictionaries.ms,{adjustPricing:"Ubah diskaun dan penghantaran",acceptPricing:"Tetapkan semula cadangan",approve:"Sahkan dan luluskan"});
Object.assign(dictionaries.zh,{correctionsTitle:"本次人工更正 请先核对",correctionFinal:"确认值",correctionReason:"原因",choice_include:"需要",choice_exclude:"排除",choice_ignore:"不作为条件",choice_remove:"客户取消此商品",choice_pickup:"自提",choice_delivery:"配送",reviewRequired:"这笔报价需要员工在电脑重新核对并保存新版本，之后才能批准。",review_stale:"核对已失效，请员工在电脑重新核对并保存新版本。"});
Object.assign(dictionaries.en,{correctionsTitle:"Review manual corrections",correctionFinal:"Confirmed value",correctionReason:"Reason",choice_include:"Required",choice_exclude:"Excluded",choice_ignore:"Condition removed",choice_remove:"Customer cancelled this item",choice_pickup:"Collection",choice_delivery:"Delivery",reviewRequired:"Ask staff to review this quotation on the computer and save a new revision before approval.",review_stale:"The review is outdated. Ask staff to review and save a new revision on the computer."});
Object.assign(dictionaries.ms,{correctionsTitle:"Semak pembetulan manual",correctionFinal:"Nilai disahkan",correctionReason:"Sebab",choice_include:"Diperlukan",choice_exclude:"Dikecualikan",choice_ignore:"Syarat dibuang",choice_remove:"Pelanggan membatalkan produk ini",choice_pickup:"Ambil sendiri",choice_delivery:"Penghantaran",reviewRequired:"Minta staf menyemak sebut harga di komputer dan menyimpan versi baharu sebelum kelulusan.",review_stale:"Semakan telah lapuk. Minta staf menyemak dan menyimpan versi baharu di komputer."});
Object.assign(dictionaries.zh,{target_fast_setting:"速凝",target_waterproof:"防水",target_low_odour:"低气味",target_plastering:"抹灰",target_masonry:"砌筑",target_concrete:"混凝土",target_indoor:"室内",target_outdoor:"室外"});
Object.assign(dictionaries.en,{target_fast_setting:"Fast setting",target_waterproof:"Waterproof",target_low_odour:"Low odour",target_plastering:"Plastering",target_masonry:"Masonry",target_concrete:"Concrete",target_indoor:"Indoor",target_outdoor:"Outdoor"});
Object.assign(dictionaries.ms,{target_fast_setting:"Cepat kering",target_waterproof:"Kalis air",target_low_odour:"Kurang bau",target_plastering:"Melepa",target_masonry:"Kerja bata",target_concrete:"Konkrit",target_indoor:"Dalaman",target_outdoor:"Luaran"});
let language=sessionStorage.getItem("quote_mobile_language")||(/^zh/.test(navigator.language)?"zh":/^ms/.test(navigator.language)?"ms":"en");
let token=location.hash.slice(1)||sessionStorage.getItem("quote_mobile_token")||"";
if(location.hash){sessionStorage.setItem("quote_mobile_token",token);history.replaceState(null,"",location.pathname+location.search);}
let current=null,busy=false,reviewSequence=0;
let pricingKey="";
const t=key=>(dictionaries[language]||dictionaries.en)[key]||dictionaries.en[key]||key;
const money=value=>"RM"+Number(value).toLocaleString("en-MY",{minimumFractionDigits:2,maximumFractionDigits:2});
function message(value,error=false){$("message").textContent=value;$("message").classList.toggle("error",error);$("message").hidden=!value;}
function applyLanguage(){
  $("language").value=language;document.documentElement.lang=language==="zh"?"zh-CN":language;
  document.querySelectorAll("[data-t]").forEach(e=>e.textContent=t(e.dataset.t));
  if(current)render(current);
}
async function request(operation,body={},blob=false){
  let response;
  try{response=await fetch("/api/mobile/"+operation,{method:"POST",headers:{"Content-Type":"application/json",Authorization:"Bearer "+token},
    body:JSON.stringify(body),signal:AbortSignal.timeout(60000)});}catch{throw new Error(t("network"));}
  if(!response.ok){
    const error=await response.json().catch(()=>({detail:"requestFailed"}));
    const code=typeof error.detail==="string"?error.detail:error.detail?.code||"requestFailed";
    const failure=new Error(t(code));failure.code=code;throw failure;
  }
  return blob?response.blob():response.json();
}
function render(data){
  current=data;const q=data.quote;
  $("review").hidden=false;$("shop").textContent=data.shop;$("state").textContent=t(data.state);
  $("reference").textContent=q.id+" · "+t("revision")+" "+q.revision;$("customer").textContent=q.customer;
  $("amount").textContent=money(q.total);$("expires").textContent=t("expires")+" "+new Date(data.expires*1000).toLocaleString();
  $("original").textContent=q.inquiry+(q.notes?"\n\n"+q.notes:"");$("items").replaceChildren();
  q.items.forEach(item=>{
    const row=document.createElement("div");row.className="item";
    const left=document.createElement("div"),name=document.createElement("p"),detail=document.createElement("small"),amount=document.createElement("strong");
    name.textContent=item.brand+" "+(item["name_"+language]||item.name_en||item.name_zh)+" "+item.spec;
    detail.textContent=item.quantity+" "+item.unit+" × "+money(item.unit_price);amount.textContent=money(item.line_total);
    left.append(name,detail);row.append(left,amount);$("items").append(row);
  });
  renderPricing(q);
  renderCorrections(q);
  $("reviewRequired").hidden=!q.review_required;$("approve").disabled=busy||Boolean(q.review_required);
  $("decisionForm").hidden=!data.can_decide;$("processed").hidden=data.can_decide;$("pdf").hidden=!data.pdf_ready;
  $("processedTitle").textContent=t(data.state);
  $("processedHelp").textContent=t(data.state==="approved"?(data.pdf_ready?"approvedHelp":"exportPending"):data.state==="returned"?"returnedHelp":"processedHelp");
  message(t(data.can_decide?"ready":data.state==="approved"?"approvedHelp":data.state==="returned"?"returnedHelp":"processedHelp"));
}
function pricingTotal(){
  if(!current?.quote.pricing)return;
  const cents=value=>{const s=String(value);if(!/^\d+(\.\d{1,2})?$/.test(s))return null;const [whole,fraction=""]=s.split(".");return BigInt(whole)*100n+BigInt(fraction.padEnd(2,"0"));};
  const product=cents(current.quote.pricing.recommendation.original_product_price),basis=cents($("discountPct").value),fee=cents($("freightFee").value);
  let formatted="—";
  if(product!==null&&basis!==null&&fee!==null&&basis<=10000n){const value=product-(product*basis+5000n)/10000n+fee;formatted="RM"+(value/100n).toLocaleString("en-MY")+"."+(value%100n).toString().padStart(2,"0");}
  $("priceDecisionTotal").textContent=t("finalTotal")+": "+formatted;
}
function renderPricing(q){
  $("pricing").hidden=!q.pricing;$("ownerPricing").hidden=!q.pricing;
  $("totalLabel").textContent=t(q.pricing?(q.pricing.decision?"finalTotal":"recommendedTotal"):"total");
  if(!q.pricing)return;
  const rec=q.pricing.recommendation,dec=q.pricing.decision,container=$("priceDetails");container.replaceChildren();
  const entries=[["originalProducts",money(rec.original_product_price)],["baseFreight",money(rec.base_freight)],["originalTotal",money(rec.original_total)],["suggestedDiscount",rec.suggested_discount_pct+"%"],["suggestedFreight",money(rec.suggested_freight)],["recommendedTotal",money(rec.recommended_total)]];
  if(dec)entries.push(["discountPct",dec.discount_pct+"%"],["freightFee",money(dec.freight)]);
  for(const [key,value]of entries){const row=document.createElement("p"),left=document.createElement("span"),right=document.createElement("strong");row.className="pricing-row";left.textContent=t(key);right.textContent=value;row.append(left,right);container.append(row);}
  const details=document.createElement("details"),summary=document.createElement("summary"),list=document.createElement("ul");summary.textContent=t("pricingReasons");details.append(summary,list);
  for(const reason of rec.reasons[language]||rec.reasons.en){const item=document.createElement("li");item.textContent=reason;list.append(item);}container.append(details);
  const key=q.id+":"+q.revision;
  if(key!==pricingKey){pricingKey=key;$("discountPct").value=rec.suggested_discount_pct;$("freightFee").value=rec.suggested_freight;$("pricingNote").value="";}
  pricingTotal();
}
function renderCorrections(q){
  const corrections=(q.pricing?.requirement?.resolutions||[]).filter(p=>p.resolution.reason!=="Concrete selection verified by server");
  $("requirementCorrections").hidden=!corrections.length;const container=$("correctionsList");container.replaceChildren();
  for(const correction of corrections){
    const row=document.createElement("div");row.className="manual-correction";
    const source=document.createElement("p");source.className="original";source.textContent=correction.source_text;
    let value=correction.resolution.value;
    if(value&&typeof value==="object")value=value.action==="remove"?t("choice_remove"):value.sku+" × "+value.quantity;
    else if(["include","exclude","ignore","pickup","delivery"].includes(value))value=t("choice_"+value);
    const final=document.createElement("p"),reason=document.createElement("p");
    const target=correction.target?(dictionaries[language]["target_"+correction.target]||correction.target):"";
    final.textContent=t("correctionFinal")+": "+(target?target+" · ":"")+value;
    reason.textContent=t("correctionReason")+": "+correction.resolution.reason;
    row.append(source,final,reason);container.append(row);
  }
}
function failure(error){
  if(["mobile_expired","mobile_invalid_link","mobile_changed"].includes(error.code)){$("decisionForm").hidden=true;$("pdf").hidden=true;current=null;}
  if(error.code==="review_stale"&&current){current.quote.review_required=true;$("reviewRequired").hidden=false;$("approve").disabled=true;}
  message(error.message,true);
}
async function load(){
  if(!token){message(t("mobile_invalid_link"),true);return;}
  const sequence=++reviewSequence,requestedToken=token;
  try{const data=await request("review");if(sequence===reviewSequence&&requestedToken===token)render(data);}
  catch(error){if(sequence===reviewSequence&&requestedToken===token)failure(error);}
}
async function decide(decision){
  if(busy || !current?.can_decide)return;
  if(decision==="approve"&&current.quote.review_required){message(t("reviewRequired"),true);return;}
  const password=$("password").value;
  if(!password){message(t("passwordRequired"),true);return;}
  if(decision==="return"&&!$("reason").value.trim()){message(t("mobile_reason_required"),true);return;}
  const requestedToken=token;reviewSequence++;
  busy=true;$("approve").disabled=true;$("return").disabled=true;message(t("working"));
  try{const data=await request("decision",{decision,expected_revision:current.quote.revision,boss_password:password,reason:$("reason").value.trim(),
    ...(decision==="approve"&&current.quote.pricing?{discount_pct:$("discountPct").value,freight:$("freightFee").value,pricing_note:$("pricingNote").value}:{})});if(requestedToken===token)render(data);}
  catch(error){if(requestedToken===token)failure(error);}
  finally{if(requestedToken===token){$("password").value="";busy=false;$("approve").disabled=Boolean(current?.quote.review_required);$("return").disabled=false;}}
}
$("decisionForm").addEventListener("submit",event=>event.preventDefault());
$("acceptPricing").addEventListener("click",()=>{const r=current.quote.pricing.recommendation;$("discountPct").value=r.suggested_discount_pct;$("freightFee").value=r.suggested_freight;$("pricingNote").value="";pricingTotal();});
for(const id of ["discountPct","freightFee"])$(id).addEventListener("input",pricingTotal);
$("approve").addEventListener("click",()=>decide("approve"));$("return").addEventListener("click",()=>decide("return"));
$("language").addEventListener("change",()=>{language=$("language").value;sessionStorage.setItem("quote_mobile_language",language);applyLanguage();});
$("pdf").addEventListener("click",async()=>{
  const requestedToken=token,quoteId=current?.quote.id;
  $("pdf").disabled=true;
  try{const blob=await request("pdf",{},true);if(requestedToken!==token)return;const url=URL.createObjectURL(blob),link=document.createElement("a");link.href=url;link.download=quoteId+".pdf";document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);}
  catch(error){if(requestedToken===token)failure(error);}finally{if(requestedToken===token)$("pdf").disabled=false;}
});
window.addEventListener("hashchange",()=>{
  const next=location.hash.slice(1);if(!next)return;
  sessionStorage.setItem("quote_mobile_token",next);history.replaceState(null,"",location.pathname+location.search);
  token=next;current=null;busy=false;pricingKey="";reviewSequence++;
  $("password").value="";$("reason").value="";$("pricingNote").value="";
  $("review").hidden=true;$("decisionForm").hidden=true;$("pdf").hidden=true;$("pdf").disabled=false;$("return").disabled=false;
  message(t("loading"));load();
});
applyLanguage();load();
setInterval(()=>{if(!busy && current?.can_decide)load();},15000);
})();
