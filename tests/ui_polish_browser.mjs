// Actual local backend, synthetic shop and browser; no external providers.
import {chromium} from "playwright";
import {spawn} from "node:child_process";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import assert from "node:assert/strict";
const root=path.resolve(import.meta.dirname,".."),base="http://127.0.0.1:8765";
const output=process.env.QA_OUTPUT||path.join(os.tmpdir(),"quote-ui-polish");await fs.mkdir(output,{recursive:true});
const data=await fs.mkdtemp(path.join(os.tmpdir(),"quote-ui-polish-data-"));
const service=spawn(process.env.TEST_PYTHON||process.env.CODEX_PRIMARY_RUNTIME_PYTHON||"python",["-m","uvicorn","backend.app:app","--host","127.0.0.1","--port","8765"],{cwd:root,env:{...process.env,WA_QUOTE_DATA:data},stdio:["ignore","pipe","pipe"]});
let logs="",browser,staff,release=()=>{};const steps=[],errors=[];
service.stdout.on("data",b=>logs+=b);service.stderr.on("data",b=>logs+=b);
const text="Hi boss, I need 20 bags cement for plastering. Prefer fast setting. Deliver to Shah Alam. How much?";
async function call(endpoint,token,body){const r=await fetch(base+"/api"+endpoint,{method:body?"POST":"GET",headers:{"Content-Type":"application/json",...(token?{Authorization:"Bearer "+token}:{})},body:body?JSON.stringify(body):undefined});const value=await r.json();assert(r.ok,JSON.stringify(value));return value;}
try{
 let ready=false;for(let i=0;i<100;i++){try{if((await fetch(base+"/api/health")).ok){ready=true;break;}}catch{}await new Promise(r=>setTimeout(r,100));}assert(ready,logs);
 const boss=await call("/setup",null,{shop_name:"Blue Ridge Building Supplies",boss_password:"polish-boss-123",staff_password:"polish-staff-123"});
 await call("/business/import",boss.token,{filename:"business_demo.xlsx",content_b64:(await fs.readFile(path.join(root,"samples/business_demo.xlsx"))).toString("base64")});
 browser=await chromium.launch({executablePath:process.env.BROWSER_EXECUTABLE,headless:true,args:["--no-sandbox","--disable-dev-shm-usage"]});
 staff=await browser.newPage({viewport:{width:430,height:920}});staff.on("pageerror",e=>errors.push(e.message));staff.on("dialog",d=>d.accept());
 await staff.goto(base);await staff.locator("#loginPassword").fill("polish-staff-123");await staff.locator("#loginForm button").click();await staff.locator("#workspace").waitFor({state:"visible"});
 await staff.setViewportSize({width:1440,height:1000});
 assert.equal(await staff.locator(".app-sidebar").evaluate(e=>getComputedStyle(e).position),"fixed");
 assert.equal(await staff.locator("body").evaluate(e=>getComputedStyle(e).backgroundColor),"rgb(244, 248, 246)");
 assert.equal(await staff.locator("#sidebarNewQuote").evaluate(e=>getComputedStyle(e).backgroundColor),"rgb(16, 133, 97)");
 assert.equal(await staff.locator(".main-nav button:visible").count(),2);
 await staff.locator("#sidebarNewQuote").click();assert(await staff.locator("#inquiryCard").isVisible());
 await staff.locator('[data-view="home"]').click();assert.equal(await staff.locator('.main-nav [aria-current="page"]').getAttribute("data-view"),"home");
 steps.push("The real emerald theme loads, desktop navigation is fixed, staff sees two permitted sections and the sidebar shortcut opens the actual quotation flow");
 for(const language of ["zh","en","ms"]){
  await staff.locator("#uiLang").selectOption(language);
  for(const width of [320,430,768,900,1160,1440]){
   await staff.setViewportSize({width,height:1000});
   assert(await staff.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${language} home at ${width}`);
   assert.equal(await staff.locator(".app-sidebar").evaluate(e=>getComputedStyle(e).position),width>=900?"fixed":"static");
   assert.equal(await staff.locator("#sidebarNewQuote").isVisible(),width>=900);
  }
 }
 await staff.locator("#uiLang").selectOption("zh");await staff.evaluate(()=>window.scrollTo(0,0));
 await staff.screenshot({path:path.join(output,"home-emerald-1440.png"),fullPage:true});
 await staff.setViewportSize({width:320,height:920});await staff.locator("#uiLang").selectOption("ms");await staff.screenshot({path:path.join(output,"home-ms-320.png"),fullPage:true});
 await staff.locator("#uiLang").selectOption("zh");await staff.setViewportSize({width:430,height:920});
 steps.push("Chinese, English and Malay switch between desktop rail and compact navigation at six widths from 320 to 1440px without overflow");
 await staff.screenshot({path:path.join(output,"home-430.png"),fullPage:true});
 await staff.locator("#startQuote").click();
 const hints={zh:"40 条商品明细",en:"40 product lines",ms:"40 baris produk"};
 for(const lang of ["zh","en","ms"]){
  await staff.locator("#uiLang").selectOption(lang);assert((await staff.locator("#inquiryHint").textContent()).includes(hints[lang]));
  await staff.locator("#inquiryText").fill(text);assert.equal(await staff.locator("#inquiryCount").textContent(),text.length+" / 12,000");
  assert(!(await staff.locator("#dismissNotice").getAttribute("aria-label")).includes("dismissNotice"));
 }
 steps.push("Input guidance, live character count and dismiss-button labels support Chinese, English and Malay");

 await staff.locator("#uiLang").selectOption("zh");await staff.locator("#customer").fill("Demo 01");
 const gate=new Promise(resolve=>release=resolve);let held=false;
 await staff.route("**/api/requirements/review",async route=>{if(!held){held=true;await gate;}await route.continue();});
 await staff.locator("#parse").click();
 await staff.waitForFunction(()=>document.getElementById("cpReviewState").dataset.state==="checking");
 assert.equal(await staff.locator("#cpPreviewBox").getAttribute("aria-busy"),"true");
 await staff.screenshot({path:path.join(output,"checking-430.png"),fullPage:true});release();
 await staff.waitForFunction(()=>document.getElementById("cpReviewState").dataset.state==="ready");
 assert.equal(await staff.locator("#cpPreviewBox").getAttribute("aria-busy"),"false");
 assert.equal(await staff.locator("#lines .source-evidence").getAttribute("open"),null);
 await staff.locator("#lines .source-evidence > summary").click();assert(await staff.locator("#lines .quantity-evidence").isVisible());
 await staff.locator("#lines .source-evidence > summary").click();
 await staff.screenshot({path:path.join(output,"product-430.png"),fullPage:true});
 await staff.locator("#confirmProducts").click();await staff.locator("#quoteReviewCard").waitFor({state:"visible"});
 assert((await staff.locator("#cpPreview").textContent()).includes("471.20"));
 steps.push("Delayed server review shows a checking state, then ready; original numeric evidence remains accessible and the actual recommendation stays RM471.20");

 for(const lang of ["zh","en","ms"]){await staff.locator("#uiLang").selectOption(lang);for(const width of [320,430,1160]){
  await staff.setViewportSize({width,height:920});assert(await staff.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${lang} ${width}`);
  const tiles=await staff.locator("#cpPreview .price-tile").all();assert.equal(tiles.length,2);
  for(const tile of tiles){assert(await tile.evaluate(e=>e.scrollWidth<=e.clientWidth),`${lang} price clipping at ${width}`);}
 }}
 await staff.locator("#uiLang").selectOption("zh");await staff.setViewportSize({width:430,height:920});await staff.screenshot({path:path.join(output,"pricing-430.png"),fullPage:true});
 await staff.setViewportSize({width:1160,height:1000});await staff.evaluate(()=>window.scrollTo(0,0));await staff.screenshot({path:path.join(output,"pricing-desktop.png"),fullPage:true});
 steps.push("The original and recommended amounts fit three languages at 320, 430 and 1160px without horizontal overflow or clipped price tiles");

 await staff.locator("#backToProducts").click();await staff.locator("#backToInquiry").click();
 const long='cement and '.repeat(999)+'cement 1 bag. Deliver to Shah Alam.';
 await staff.locator("#inquiryText").fill(long);const words={zh:"分批",en:"batches",ms:"kumpulan"};
 for(const lang of ["zh","en","ms"]){
  await staff.locator("#uiLang").selectOption(lang);await staff.locator("#parse").click();await staff.locator("#notice.error").waitFor({state:"visible"});
  assert((await staff.locator("#noticeMessage").textContent()).includes(words[lang]));assert(await staff.locator("#inquiryCard").isVisible());
  await staff.locator("#dismissNotice").focus();await staff.keyboard.press("Enter");assert(!(await staff.locator("#notice").isVisible()));
  assert.equal(await staff.locator("#inquiryText").inputValue(),long);
 }
 await staff.locator("#uiLang").selectOption("zh");await staff.setViewportSize({width:320,height:920});await staff.locator("#parse").click();await staff.locator("#notice.error").waitFor({state:"visible"});
 assert(await staff.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await staff.screenshot({path:path.join(output,"batch-error-320.png"),fullPage:true});
 const auth=await staff.evaluate(()=>JSON.parse(sessionStorage.getItem("qd_auth")));
 assert.deepEqual(await call("/quotes",auth.token),[]);assert((await call("/health")).ok);
 await staff.locator("#inquiryText").fill(text);await staff.locator("#parse").click();await staff.waitForFunction(()=>document.getElementById("cpReviewState").dataset.state==="ready");
 steps.push("A 1,000-product inquiry has localized batch guidance, preserves its original text, creates no quote and recovers after editing; dismiss works by keyboard");
 await staff.locator("#logout").click();await staff.locator("#login").waitFor({state:"visible"});assert(!(await staff.locator(".app-sidebar").isVisible()));assert(!(await staff.locator("body").evaluate(e=>e.classList.contains("has-workspace"))));
 assert.deepEqual(errors,[]);const report={passed:true,browser:browser.version(),steps,errors,externalAPIs:"not called",realWhatsAppAccount:false};
 await fs.writeFile(path.join(output,"ui-polish-report.json"),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
}catch(error){release();if(staff)await staff.screenshot({path:path.join(output,"failure.png"),fullPage:true}).catch(()=>{});await fs.writeFile(path.join(output,"backend.log"),logs);console.error(logs.slice(-2000));throw error;}
finally{release();if(browser)await browser.close();service.kill("SIGTERM");}
