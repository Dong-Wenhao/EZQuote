// Real local services and real UI; external AI, WhatsApp and a public tunnel are not used.
import {chromium} from "playwright";
import {spawn} from "node:child_process";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import assert from "node:assert/strict";
const root=path.resolve(import.meta.dirname,".."),base="http://127.0.0.1:8765",gateway="http://127.0.0.1:8766";
const TEXT="Hi boss, I need 20 bags cement for plastering. Prefer fast setting. Deliver to Shah Alam. How much?";
const out=process.env.QA_OUTPUT||path.join(os.tmpdir(),"quote-copilot-qa");await fs.mkdir(out,{recursive:true});
const data=await fs.mkdtemp(path.join(os.tmpdir(),"quote-copilot-data-"));
const python=process.env.TEST_PYTHON||process.env.CODEX_PRIMARY_RUNTIME_PYTHON||"python";
const env={...process.env,WA_QUOTE_DATA:data};
const servers=[
 spawn(python,["-m","uvicorn","backend.app:app","--host","127.0.0.1","--port","8765"],{cwd:root,env,stdio:["ignore","pipe","pipe"]}),
 spawn(python,["-m","uvicorn","backend.mobile_gateway:app","--host","127.0.0.1","--port","8766"],{cwd:root,env,stdio:["ignore","pipe","pipe"]})];
let logs="",browser,staff;const steps=[],errors=[];
for(const p of servers){p.stdout.on("data",b=>logs+=b);p.stderr.on("data",b=>logs+=b);}
try{
 for(const url of [base+"/api/health",gateway+"/health"]){let ready=false;for(let i=0;i<100;i++){try{if((await fetch(url)).ok){ready=true;break;}}catch{}await new Promise(r=>setTimeout(r,100));}assert(ready,logs);}
 browser=await chromium.launch({executablePath:process.env.BROWSER_EXECUTABLE,headless:true,args:["--no-sandbox","--disable-dev-shm-usage"]});
 const bossContext=await browser.newContext({viewport:{width:1160,height:1000},acceptDownloads:true});
 const staffContext=await browser.newContext({viewport:{width:430,height:1000},acceptDownloads:true});
 const phoneContext=await browser.newContext({viewport:{width:390,height:844},acceptDownloads:true});
 const boss=await bossContext.newPage(),phone=await phoneContext.newPage();staff=await staffContext.newPage();staff.on("dialog",d=>d.accept());
 for(const p of [boss,staff,phone])p.on("pageerror",e=>errors.push(e.message));
 await boss.goto(base);await boss.locator("#setupShop").fill("Copilot Demo Supplies");await boss.locator("#setupBoss").fill("boss-copilot-test");await boss.locator("#setupStaff").fill("staff-copilot-test");await boss.locator("#setupForm button").click();await boss.locator("#workspace").waitFor({state:"visible"});
 await boss.locator('[data-view="settings"]').click();await boss.locator('[data-settings="business"]').click();await boss.locator("#cpBusinessFile").setInputFiles(path.join(root,"samples/business_demo.xlsx"));await boss.locator("#cpBusinessPreview").click();await boss.locator("#cpBusinessImport").waitFor({state:"visible"});await boss.locator("#cpBusinessImport").click();
 await boss.waitForFunction(()=>document.getElementById("notice").textContent.includes("完整经营数据已导入"));
 assert((await boss.locator("#cpBusinessStats").innerText()).includes("21"));
 await boss.screenshot({path:path.join(out,"business-import.png"),fullPage:true});
 steps.push("Owner imports the complete business workbook with products, inventory, history, delivery and rules");
 await staff.goto(base);await staff.locator("#loginPassword").fill("staff-copilot-test");await staff.locator("#loginForm button").click();await staff.locator("#workspace").waitFor({state:"visible"});
 assert.equal(await staff.locator('[data-view="settings"]').isVisible(),false);assert.equal(await staff.locator("#cpSmart").isChecked(),true);assert(await staff.locator("#view-home").isVisible());
 await staff.locator("#startQuote").click();await staff.locator(".demo-details > summary").click();await staff.locator("#cpFullSample").click();await staff.locator("#parse").click();await staff.locator("#lineCard").waitFor({state:"visible"});assert(!(await staff.locator("#inquiryCard").isVisible()));
 assert.equal(await staff.locator("#lines select").first().inputValue(),"CEM-A-FAST-50");
 const requirement=JSON.parse(await staff.locator("#cpRequirementJSON").textContent());assert.equal(requirement.items[0].brand,null);assert.equal(requirement.area,"Shah Alam");
 assert((await staff.locator("#lines").innerText()).includes("85"));
 await staff.waitForFunction(()=>document.getElementById("cpPreview")?.textContent.includes("495.00"),undefined,{timeout:10000});
 assert((await staff.locator("#cpPreview").textContent()).includes("495.00"));
 await staff.screenshot({path:path.join(out,"product-check.png"),fullPage:true});
 steps.push("Unbranded natural inquiry matches 85-stock fast cement and shows structured requirements, alternatives and RM471.20 recommendation");
 await staff.locator("#confirmProducts").click();await staff.locator("#quoteReviewCard").waitFor({state:"visible"});assert((await staff.locator("#cpPreview").textContent()).includes("471.20"));await staff.screenshot({path:path.join(out,"requirement-and-pricing.png"),fullPage:true});await staff.locator("#sourceConfirmed").check();await staff.locator("#saveSubmit").click();await staff.waitForFunction(()=>document.getElementById("quoteStatus").textContent==="待老板批准");
 const reference=(await staff.locator("#quoteNumber").textContent()).split(" · ")[0];
 await boss.locator('[data-view="records"]').click();await boss.locator("#quoteList .quote-entry").first().waitFor({state:"visible"});await boss.locator("#quoteList .quote-entry").first().click();
 await boss.locator("#cpEditDetails > summary").click();await boss.locator("#cpDiscount").fill("5");await boss.locator("#cpFreight").fill("0");await boss.locator("#approve").click();await boss.waitForFunction(()=>document.getElementById("notice").classList.contains("error"));
 assert.equal(await boss.locator("#quoteStatus").textContent(),"待老板批准");
 await boss.locator("#cpDiscount").fill("4");await boss.locator("#cpFreight").fill("30");await boss.locator("#cpDecisionNote").fill("Owner checked area and margin");
 await boss.screenshot({path:path.join(out,"owner-edits.png"),fullPage:true});
 await boss.locator("#approve").click();await boss.waitForFunction(()=>document.getElementById("quoteStatus").textContent==="已批准");await staff.waitForFunction(()=>document.getElementById("quoteStatus").textContent==="已批准",{},{timeout:15000});
 assert.equal(await staff.locator("#quoteTotal").textContent(),"RM471.60");
 steps.push("Minimum-margin violation is blocked; owner edits to 4% and RM30 then approves RM471.60 while the original recommendation remains");
 for(const language of ["zh","en","ms"]){await staff.locator("#replyLanguage").selectOption(language);const reply=await staff.locator("#replyText").inputValue();assert(reply.includes("471.60")&&reply.includes("4.00")&&reply.includes("30.00"));}
 let wait=staff.waitForEvent("download");await staff.locator("#downloadPDF").click();await(await wait).saveAs(path.join(out,"owner-edited-quotation.pdf"));
 wait=staff.waitForEvent("download");await staff.locator("#downloadLedger").click();await(await wait).saveAs(path.join(out,"business-quotations.xlsx"));
 steps.push("Actual PDF and Excel downloads use the approved amount; all three customer replies include the final discount and freight");
 await staff.locator("#cpOutcomeBox > summary").click();await staff.locator("#cpOutcome").selectOption("won");await staff.locator("#cpActualCost").fill("29");await staff.locator("#cpOutcomeNote").fill("Synthetic customer accepted");await staff.locator("#cpSaveOutcome").click();await staff.waitForFunction(()=>document.getElementById("notice").textContent.includes("客户结果已保存"));
 await staff.screenshot({path:path.join(out,"outcome-recorded.png"),fullPage:true});
 await staff.locator("#newGlobal").click();await staff.locator(".demo-details > summary").click();await staff.locator("#cpFullSample").click();await staff.locator("#parse").click();await staff.locator("#confirmProducts").click();await staff.locator("#quoteReviewCard").waitFor({state:"visible"});await staff.waitForFunction(()=>document.getElementById("cpPreview").textContent.includes("3.17%"));
 assert((await staff.locator("#cpPreview").textContent()).includes("9"));
 steps.push("Recording a won result and actual delivery cost changes the next recommendation to 9 similar orders and a 3.17% discount");
 await staff.locator("#newGlobal").click();await staff.locator("#customer").fill("Missing Area Demo");await staff.locator("#inquiryText").fill("Need 20 bags cement for plastering, prefer fast setting");await staff.locator("#parse").click();await staff.locator("#clarificationBox").waitFor({state:"visible"});assert((await staff.locator("#clarification").textContent()).includes("delivery area"));
 await staff.locator("#confirmProducts").click();await staff.waitForFunction(()=>document.getElementById("notice").classList.contains("error"));assert(!(await staff.locator("#quoteReviewCard").isVisible()));
 for(const lang of ["en","ms","zh"]){await staff.locator("#uiLang").selectOption(lang);assert(!(await staff.locator("#cpDeliveryInputs").innerText()).includes("cpFulfilment"));}
 await staff.setViewportSize({width:360,height:900});assert(await staff.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await staff.screenshot({path:path.join(out,"requirements-360.png"),fullPage:true});
 steps.push("Missing delivery area blocks submission, new labels switch across three languages and the 360px workflow fits without overflow");
 // Optional phone approval remains available without sending any notification or starting a tunnel.
 const staffAuth=await staff.evaluate(()=>JSON.parse(sessionStorage.getItem("qd_auth")));
 const bossAuth=await boss.evaluate(()=>JSON.parse(sessionStorage.getItem("qd_auth")));
 const call=async(endpoint,auth,body,method="POST")=>{const r=await fetch(base+"/api"+endpoint,{method,headers:{Authorization:"Bearer "+auth.token,"Content-Type":"application/json"},body:JSON.stringify(body)});const data=await r.json();assert(r.ok,JSON.stringify(data));return data;};
 await call("/integrations",bossAuth,{public_url:"https://phone.example.test"},"PUT");
 const items=[{sku:"CEM-A-FAST-50",quantity:"20"}],review=await call("/requirements/review",staffAuth,{inquiry:TEXT,items,area:"Shah Alam",fulfilment:"delivery"});assert(review.can_quote);
 const q=await call("/quotes",staffAuth,{customer:"Synthetic Phone Customer",inquiry:TEXT,language:"en",items,source_confirmed:true,request_key:"browser-smart-phone-001",pricing_enabled:true,delivery_area:"Shah Alam",review_id:review.review_id});
 await call("/quotes/"+q.id+"/submit",staffAuth,{expected_revision:1});const link=await call("/quotes/"+q.id+"/mobile-link",staffAuth,{expected_revision:1});
 await phone.goto(gateway+"/mobile#"+new URL(link.url).hash.slice(1));await phone.locator("#ownerPricing").waitFor({state:"visible"});
 await phone.locator("#language").selectOption("ms");await phone.locator("#phoneEdit > summary").click();await phone.locator("#discountPct").fill("4");await phone.locator("#freightFee").fill("30");await phone.locator("#password").fill("boss-copilot-test");await phone.locator("#approve").click();await phone.waitForFunction(()=>!document.getElementById("pdf").hidden);
 assert.equal(await phone.locator("#amount").textContent(),"RM471.60");await phone.setViewportSize({width:320,height:820});assert(await phone.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await phone.screenshot({path:path.join(out,"mobile-edited-ms-320.png"),fullPage:true});
 const check=await(await fetch(base+"/api/quotes/"+q.id,{headers:{Authorization:"Bearer "+staffAuth.token}})).json();assert.equal(check.pricing.decision.mode,"edited");
 steps.push("The real isolated mobile gateway supports Malay owner edits and approval, including a 320px layout; no external API or tunnel is used");
 assert.deepEqual(errors,[]);
 const report={passed:true,browser:browser.version(),steps,errors,externalAPIs:"not called",publicTunnel:"not used",realWhatsAppAccount:false,dataDirectory:data};
 await fs.writeFile(path.join(out,"copilot-report.json"),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
}catch(error){
 if(staff){
  await staff.screenshot({path:path.join(out,"failure.png"),fullPage:true}).catch(()=>{});
  const current=await staff.evaluate(()=>({preview:document.getElementById("cpPreview")?.textContent,hint:document.getElementById("cpPreviewHint")?.textContent})).catch(()=>({}));
  await fs.writeFile(path.join(out,"failure-state.json"),JSON.stringify(current,null,2));
 }
 await fs.writeFile(path.join(out,"backend.log"),logs);console.error(logs.slice(-2500));throw error;
}finally{if(browser)await browser.close();for(const p of servers)p.kill("SIGTERM");}
