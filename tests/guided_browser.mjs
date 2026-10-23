// Navigation, audited corrections, draft recovery and record classification.
// Real local HTTP service. No external provider or WhatsApp account is used.
import {chromium} from "playwright";
import {spawn} from "node:child_process";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import assert from "node:assert/strict";
const root=path.resolve(import.meta.dirname,".."),base="http://127.0.0.1:8765";
const output=process.env.QA_OUTPUT||path.join(os.tmpdir(),"quote-guided-qa");await fs.mkdir(output,{recursive:true});
const data=await fs.mkdtemp(path.join(os.tmpdir(),"quote-guided-data-"));
const python=process.env.TEST_PYTHON||process.env.CODEX_PRIMARY_RUNTIME_PYTHON||"python";
const service=spawn(python,["-m","uvicorn","backend.app:app","--host","127.0.0.1","--port","8765"],{cwd:root,env:{...process.env,WA_QUOTE_DATA:data},stdio:["ignore","pipe","pipe"]});
const steps=[],errors=[];let logs="",browser,staff,boss;
service.stdout.on("data",b=>logs+=b);service.stderr.on("data",b=>logs+=b);
const call=async(endpoint,auth,body,method=body?"POST":"GET")=>{const r=await fetch(base+"/api"+endpoint,{method,headers:{"Content-Type":"application/json",...(auth?{Authorization:"Bearer "+auth.token}:{})},...(body?{body:JSON.stringify(body)}:{})});const value=await r.json();assert(r.ok,JSON.stringify(value));return value;};
const text="I need 20 bags cement for plastering. Prefer fast setting. Deliver to Shah Alam.";
try{
 for(let i=0;i<100;i++){try{if((await fetch(base+"/api/health")).ok)break;}catch{}await new Promise(r=>setTimeout(r,100));}
 const owner=await call("/setup",null,{shop_name:"Blue Ridge Building Supplies",boss_password:"guided-boss-pass",staff_password:"guided-staff-pass"});
 const worker=await call("/login",null,{username:"staff",password:"guided-staff-pass"});
 await call("/business/import",owner,{filename:"business_demo.xlsx",content_b64:(await fs.readFile(path.join(root,"samples/business_demo.xlsx"))).toString("base64")});
 browser=await chromium.launch({executablePath:process.env.BROWSER_EXECUTABLE,headless:true,args:["--no-sandbox","--disable-dev-shm-usage"]});
 const bc=await browser.newContext({viewport:{width:1160,height:1000}}),sc=await browser.newContext({viewport:{width:430,height:920}});
 boss=await bc.newPage();staff=await sc.newPage();
 for(const page of [boss,staff])page.on("pageerror",e=>errors.push(e.message));
 async function signIn(page,user,password){await page.goto(base);await page.locator("#loginUser").selectOption(user);await page.locator("#loginPassword").fill(password);await page.locator("#loginForm button").click();await page.locator("#view-home").waitFor({state:"visible"});}
 await signIn(boss,"boss","guided-boss-pass");await signIn(staff,"staff","guided-staff-pass");
 assert.equal(await staff.locator("nav button:visible").count(),2);assert.equal(await boss.locator("nav button:visible").count(),3);
 assert(!(await staff.locator("#cpSmart").isVisible()));assert(!(await staff.locator("#catalogFile").isVisible()));
 assert.equal(await staff.locator("#homePending").textContent(),"0");
 await boss.screenshot({path:path.join(output,"home-desktop.png"),fullPage:true});await staff.screenshot({path:path.join(output,"home-430.png"),fullPage:true});
 steps.push("Role-based home has one prominent new-quote action, accurate empty counts, two staff tabs and three owner tabs");
 await staff.locator("#startQuote").click();await staff.locator("#customer").fill("Draft customer");await staff.locator("#inquiryText").fill(text);await staff.locator("#parse").click();await staff.locator("#lineCard").waitFor({state:"visible"});
 assert(!(await staff.locator("#inquiryCard").isVisible()));assert(!(await staff.locator("#quoteReviewCard").isVisible()));assert(!(await staff.locator("#cpRequirementJSON").isVisible()));
 async function correct(code,reason){await staff.locator("#confirmProducts").click();const issue=staff.locator('[data-issue-code="'+code+'"]');await issue.waitFor({state:"visible"});assert(!(await staff.locator("#quoteReviewCard").isVisible()));await issue.locator("input").fill(reason);await staff.locator("#applyRequirementCorrections").click();await staff.locator("#reviewIssues").waitFor({state:"hidden"});await staff.locator("#confirmProducts").click();await staff.locator("#quoteReviewCard").waitFor({state:"visible"});}
 await staff.locator("#lines input").fill("21");await correct("quantity_changed","Customer confirmed 21 bags");
 assert((await staff.locator("#cpPreview").textContent()).includes("483.00"));assert((await staff.locator("#reviewSummary").textContent()).includes("21"));
 assert(!(await staff.locator("#lineCard").isVisible()));assert.equal(await staff.locator("#cpPreview details[open]").count(),0);
 for(const language of ["en","ms","zh"]){await staff.locator("#uiLang").selectOption(language);assert((await staff.locator("#cpPreview").textContent()).includes("483.00"));assert(await staff.locator("#quoteReviewCard").isVisible());}
 steps.push("Product and price steps show separately; quantity edits affect real prices and language switches preserve the recommendation");
 await staff.locator("#backToProducts").click();assert.equal(await staff.locator("#lines input").inputValue(),"21");await staff.locator("#cpArea").fill("Klang");await correct("area_changed","Customer confirmed Klang delivery");assert((await staff.locator("#reviewSummary").textContent()).includes("Klang"));
 await staff.locator("#sourceConfirmed").check();await staff.reload();await staff.locator("#view-home").waitFor({state:"visible"});await staff.locator("#resumeDraft").click();await staff.locator("#quoteReviewCard").waitFor({state:"visible"});
 assert((await staff.locator("#reviewSummary").textContent()).includes("21"));assert((await staff.locator("#reviewSummary").textContent()).includes("Klang"));assert(!(await staff.locator("#sourceConfirmed").isChecked()));
 steps.push("Back navigation retains products; a reloaded draft resumes the correct step and delivery area and requires source confirmation again");
 await staff.locator("#backToProducts").click();await staff.locator("#backToInquiry").click();await staff.locator("#inquiryText").fill(text.replace("20 bags","25 bags"));
 await staff.locator("#parse").click();await staff.locator("#lineCard").waitFor({state:"visible"});assert.equal(await staff.locator("#lines input").inputValue(),"25");
 staff.once("dialog",d=>d.dismiss());await staff.locator("#newGlobal").click();assert.equal(await staff.locator("#lines input").inputValue(),"25");
 await staff.locator("#backHome").click();assert(await staff.locator("#resumeDraft").isVisible());await staff.locator("#resumeDraft").click();assert(await staff.locator("#lineCard").isVisible());
 staff.once("dialog",d=>d.accept());await staff.locator("#newGlobal").click();assert.equal(await staff.locator("#inquiryText").inputValue(),"");
 steps.push("Changed inquiry is reparsed; cancelling a new-quote request preserves unsaved work and home can resume it");
 async function pending(customer,key){const items=[{sku:"CEM-A-FAST-50",quantity:"20"}],r=await call("/requirements/review",worker,{inquiry:text,items,area:"Shah Alam",fulfilment:"delivery"});assert(r.can_quote);const q=await call("/quotes",worker,{customer,inquiry:text,items,language:"zh",source_confirmed:true,request_key:key,pricing_enabled:true,delivery_area:"Shah Alam",review_id:r.review_id});await call("/quotes/"+q.id+"/submit",worker,{expected_revision:q.revision});return q;}
 const accepted=await pending("Ready for approval","guided-accept-001");
 await boss.locator('[data-view="home"]').click();await boss.waitForFunction(()=>document.getElementById("homePending").textContent==="1");await boss.locator("#homeList .quote-entry").first().click();
 await boss.locator("#quoteCard").waitFor({state:"visible"});assert(!(await boss.locator("#cpDiscount").isVisible()));assert(!(await boss.locator("#rejectReason").isVisible()));assert.equal(await boss.locator("#cpQuotePricing details[open]").count(),0);
 await boss.screenshot({path:path.join(output,"owner-approval-desktop.png"),fullPage:true});await boss.locator("#approve").click();await boss.waitForFunction(()=>document.getElementById("quoteStatus").textContent==="已批准");
 const a=await call("/quotes/"+accepted.id,worker);assert.equal(a.pricing.decision.mode,"accepted");assert.equal(a.total,"471.20");
 steps.push("Owner approves the saved recommendation directly with edit fields, history reasons and return controls collapsed");
 await call("/quotes/"+accepted.id+"/outcome",worker,{expected_revision:1,expected_outcome_version:0,outcome:"won",note:"Synthetic accepted result",actual_delivery_cost:"29"});
 const returned=await pending("Return this quotation","guided-return-001");
 await boss.locator('[data-view="records"]').click();await boss.locator('[data-record-filter="pending"]').click();await boss.locator("#quoteList .quote-entry").first().click();await boss.locator("#rejectDetails > summary").click();await boss.locator("#rejectReason").fill("Please check quantity with customer");await boss.locator("#reject").click();await boss.waitForFunction(()=>document.getElementById("quoteStatus").textContent==="已退回");
 await staff.locator('[data-view="home"]').click();await staff.waitForFunction(()=>document.getElementById("homeAll").textContent==="2");assert.equal(await staff.locator("#homePending").textContent(),"0");assert.equal(await staff.locator("#homeReady").textContent(),"0");
 await staff.locator('[data-filter-jump="all"]').click();await staff.locator('[data-record-filter="closed"]').click();assert.equal(await staff.locator("#quoteList .quote-entry").count(),1);assert((await staff.locator("#quoteList").textContent()).includes("已成交"));
 await staff.locator('[data-record-filter="pending"]').click();assert.equal(await staff.locator("#quoteList .quote-entry").count(),0);
 steps.push("Return reason is saved; home counts and filters use current approval and customer outcomes rather than calling approvals sales");
 await boss.locator('[data-view="settings"]').click();
 for(const tab of ["business","catalog","shop","connections"]){await boss.locator('[data-settings="'+tab+'"]').click();assert(await boss.locator("#view-"+tab).isVisible());assert.equal(await boss.locator(".settings-pane:visible").count(),1);}
 await boss.locator('[data-settings="business"]').click();assert(!(await boss.locator("#aiKey").isVisible()));
 for(const page of [boss,staff])for(const language of ["zh","en","ms"]){await page.locator("#uiLang").selectOption(language);for(const width of [320,430,1160]){await page.setViewportSize({width,height:920});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${language} at ${width}`);}}
 await staff.locator('[data-view="home"]').click();await staff.setViewportSize({width:320,height:900});await staff.screenshot({path:path.join(output,"home-ms-320.png"),fullPage:true});
 await boss.locator("#uiLang").selectOption("zh");await boss.setViewportSize({width:1160,height:1000});await boss.locator('[data-view="home"]').click();await boss.screenshot({path:path.join(output,"home-with-records.png"),fullPage:true});
 steps.push("All administration is grouped in owner settings; three languages fit 320px, 430px and desktop without horizontal overflow");
 assert.deepEqual(errors,[]);const report={passed:true,browser:browser.version(),steps,errors,realWhatsAppAccount:false,externalAPIs:"not called"};await fs.writeFile(path.join(output,"guided-report.json"),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
}catch(error){for(const [name,p]of [["staff",staff],["boss",boss]])if(p)await p.screenshot({path:path.join(output,name+"-failure.png"),fullPage:true}).catch(()=>{});console.error(logs.slice(-1500));throw error;}
finally{if(browser)await browser.close();service.kill("SIGTERM");}
