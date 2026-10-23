// Actual workspace, gateway and mobile UI; external OpenAI/Meta responses are synthetic.
import {chromium} from "playwright";
import {spawn} from "node:child_process";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import assert from "node:assert/strict";
const root=path.resolve(import.meta.dirname,".."),base="http://127.0.0.1:8765",mobileBase="http://127.0.0.1:8766";
const out=process.env.QA_OUTPUT||path.join(os.tmpdir(),"quote-mobile-qa");
await fs.mkdir(out,{recursive:true});
const data=await fs.mkdtemp(path.join(os.tmpdir(),"quote-mobile-data-"));
const python=process.env.TEST_PYTHON||process.env.CODEX_PRIMARY_RUNTIME_PYTHON||"python";
const env={...process.env,WA_QUOTE_DATA:data,WA_QUOTE_FIXTURE:"1"};
const servers=[
  spawn(python,["tests/mobile_fixture_server.py"],{cwd:root,env,stdio:["ignore","pipe","pipe"]}),
  spawn(python,["-m","uvicorn","backend.mobile_gateway:app","--host","127.0.0.1","--port","8766"],{cwd:root,env,stdio:["ignore","pipe","pipe"]})
];
let logs="",browser;for(const server of servers){server.stdout.on("data",b=>logs+=b);server.stderr.on("data",b=>logs+=b);}
const steps=[],errors=[];
try{
  for(const address of [base+"/api/health",mobileBase+"/health"]){
    let ready=false;
    for(let i=0;i<100;i++){try{if((await fetch(address)).ok){ready=true;break;}}catch{}await new Promise(r=>setTimeout(r,100));}
    assert(ready,"Server did not start: "+logs);
  }
  browser=await chromium.launch({executablePath:process.env.BROWSER_EXECUTABLE,headless:true,args:["--no-sandbox","--disable-dev-shm-usage"]});
  const bossContext=await browser.newContext({viewport:{width:1100,height:980},acceptDownloads:true});
  const staffContext=await browser.newContext({viewport:{width:430,height:980},acceptDownloads:true});
  const phoneContext=await browser.newContext({viewport:{width:390,height:844},acceptDownloads:true});
  const boss=await bossContext.newPage(),staff=await staffContext.newPage(),phone=await phoneContext.newPage();
  for(const page of [boss,staff,phone])page.on("pageerror",e=>errors.push(e.message));
  await boss.goto(base);
  await boss.locator("#setupShop").fill("Synthetic mobile shop");
  await boss.locator("#setupBoss").fill("boss-mobile-browser");
  await boss.locator("#setupStaff").fill("staff-mobile-browser");
  await boss.locator("#setupForm button").click();
  await boss.locator("#workspace").waitFor({state:"visible"});
  await boss.locator('[data-view="settings"]').click();await boss.locator('[data-settings="catalog"]').click();await boss.locator("#importCard > summary").click();await boss.locator("#catalogFile").setInputFiles(path.join(root,"samples/products.xlsx"));
  await boss.locator("#previewCatalog").click();await boss.locator("#commitCatalog").click();await boss.locator("#view-inquiry").waitFor({state:"visible"});
  await boss.locator('[data-view="settings"]').click();await boss.locator('[data-settings="connections"]').click();
  await boss.locator("#aiEnabled").check();await boss.locator("#aiKey").fill("sk-SYNTHETIC-BROWSER-KEY");
  await boss.locator("#waEnabled").check();await boss.locator("#bossPhone").fill("60100000000");
  await boss.locator("#phoneConfirmed").check();await boss.locator("#waPhoneId").fill("123456789");
  await boss.locator("#waToken").fill("SYNTHETIC-BROWSER-WA-TOKEN");
  await boss.locator("#publicURL").fill("https://approval.example.test");
  await boss.locator("#saveConnections").click();
  await boss.waitForFunction(()=>document.getElementById("notice").textContent.includes("连接设置已保存"));
  assert.equal(await boss.locator("#aiKey").inputValue(),"");assert.equal(await boss.locator("#waToken").inputValue(),"");
  assert((await boss.locator("#aiKeyState").innerText()).includes("已保存"));
  steps.push("Boss configures AI, verified phone recipient and HTTPS origin; credentials clear from the form");
  await staff.goto(base);await staff.locator("#loginUser").selectOption("staff");
  await staff.locator("#loginPassword").fill("staff-mobile-browser");await staff.locator("#loginForm button").click();
  await staff.locator("#workspace").waitFor({state:"visible"});
  assert.equal(await staff.locator('[data-view="settings"]').isVisible(),false);
  await staff.locator("#startQuote").click();await staff.locator("#customer").fill("Synthetic Customer A");
  await staff.locator("#inquiryText").fill("A牌50kg水泥二十袋，还有 Brand A PVC pipe 20mm five pieces");
  await staff.locator("#parse").click();await staff.locator("#lineCard").waitFor({state:"visible"});
  assert.equal(await staff.locator("#lines .line-item").count(),2);
  assert.equal(await staff.locator("#estimatedTotal").innerText(),"RM413.75");
  assert((await staff.locator("#parseMethod").textContent()).includes("AI 理解"));
  await staff.locator("#confirmProducts").click();await staff.locator("#quoteReviewCard").waitFor({state:"visible"});await staff.locator("#sourceConfirmed").check();await staff.locator("#saveSubmit").click();
  await staff.waitForFunction(()=>document.getElementById("quoteStatus").textContent==="待老板批准");
  steps.push("Staff has no settings access; structured extraction separates two products and the catalog computes RM413.75");
  let notifications=[];
  for(let i=0;i<70;i++){
    notifications=await (await fetch(base+"/__fixture/phone")).json();
    if(notifications.length)break;
    await new Promise(r=>setTimeout(r,100));
  }
  assert.equal(notifications.length,1);
  const payload=notifications[0],parameters=payload.template.components[0].parameters;
  assert.equal(payload.to,"60100000000");assert.equal(parameters[2].text,"RM413.75");
  await staff.waitForFunction(()=>document.getElementById("phoneStatus").textContent.includes("接口已受理"),{},{timeout:15000});
  assert(!(await staff.locator("#phoneStatus").textContent()).includes("已送达"));
  steps.push("Background outbox submits one template with the correct amount and scoped link; UI distinguishes acceptance from delivery");
  const token=new URL(parameters[3].text).hash;
  await phone.goto(mobileBase+"/mobile"+token);
  await phone.locator("#language").selectOption("zh");
  await phone.locator("#decisionForm").waitFor({state:"visible"});
  assert.equal(await phone.locator("#amount").innerText(),"RM413.75");
  assert.equal(await phone.locator("#items .item").count(),2);
  assert.equal(new URL(phone.url()).hash,"");
  await phone.locator("#password").fill("wrong-password");await phone.locator("#approve").click();
  await phone.waitForFunction(()=>document.getElementById("message").textContent.includes("密码不正确"));
  assert.equal(await phone.locator("#password").inputValue(),"");
  assert.equal(await staff.locator("#quoteStatus").innerText(),"待老板批准");
  await phone.evaluate(()=>scrollTo(0,0));
  await phone.screenshot({path:path.join(out,"phone-review.png"),fullPage:true});
  steps.push("Separate phone context reviews only this quotation; wrong boss password cannot approve and is cleared");
  await phone.locator("#language").selectOption("ms");
  await phone.locator("#password").fill("boss-mobile-browser");await phone.locator("#approve").click();
  await phone.locator("#pdf").waitFor({state:"visible"});
  assert.equal(await phone.locator("#processedTitle").innerText(),"Diluluskan");
  await staff.waitForFunction(()=>document.getElementById("quoteStatus").textContent==="已批准",{},{timeout:15000});
  const downloadWait=phone.waitForEvent("download");await phone.locator("#pdf").click();
  const download=await downloadWait;await download.saveAs(path.join(out,"mobile-quotation.pdf"));
  assert((await fs.readFile(path.join(out,"mobile-quotation.pdf"))).subarray(0,4).toString()==="%PDF");
  await phone.evaluate(()=>scrollTo(0,0));
  await phone.screenshot({path:path.join(out,"phone-approved-ms.png"),fullPage:true});
  steps.push("Malay mobile approval updates the staff workspace and downloads the actual generated PDF through the gateway");
  await phone.setViewportSize({width:320,height:780});
  await phone.locator("#language").selectOption("en");
  assert.equal(await phone.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await boss.setViewportSize({width:360,height:900});
  await boss.locator("#uiLang").selectOption("en");
  assert.equal(await boss.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await boss.locator("#uiLang").selectOption("ms");
  assert((await boss.locator("#aiKeyState").innerText()).includes("Disimpan"));
  await boss.locator("#uiLang").selectOption("zh");
  await boss.evaluate(()=>scrollTo(0,0));
  await boss.screenshot({path:path.join(out,"connections-360.png"),fullPage:true});
  const blocked=await fetch(mobileBase+"/api/catalog");assert.equal(blocked.status,404);
  steps.push("Mobile and settings layouts fit narrow screens; language labels switch; public gateway has no catalog route");
  assert.deepEqual(errors,[]);
  const report={passed:true,browser:browser.version(),steps,errors,externalAI:"synthetic provider",phoneDelivery:"not attempted",publicTunnel:"not used",actualGatewayHTTP:true};
  await fs.writeFile(path.join(out,"mobile-report.json"),JSON.stringify(report,null,2));
  console.log(JSON.stringify(report,null,2));
}finally{
  if(browser)await browser.close();
  for(const server of servers)server.kill("SIGTERM");
}
