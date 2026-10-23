import fs from "node:fs/promises";
import path from "node:path";
import {fileURLToPath} from "node:url";
import {Workbook, SpreadsheetFile} from "@oai/artifact-tool";

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"..");
const qa=path.resolve(root,"../tmp/business_sample_qa");
await fs.mkdir(qa,{recursive:true});
const previous=JSON.parse(await fs.readFile(path.join(root,"samples/products.json"),"utf8"));
const costs=[14,7,14.5,6.2,45,4.5];
const categories=["cement","cement","cement","pvc_pipe","paint","nails"];
const fields=["sku","name_zh","name_en","name_ms","brand","spec","unit","unit_price","aliases","category","applications","preferences","unit_cost","source"];
const products=previous.map((p,i)=>({...p,unit_price:Number(p.unit_price),category:categories[i],applications:i<3?"plastering|masonry|concrete":i===4?"indoor|outdoor":"",preferences:"",unit_cost:costs[i],source:"Synthetic demo"}));
products.push(
 {sku:"CEM-A-FAST-50",name_zh:"快凝抹灰水泥",name_en:"Fast Cement",name_ms:"Simen Cepat Kering",brand:"Brand A",spec:"50kg",unit:"bag",unit_price:23,aliases:"水泥|cement|simen|快凝水泥",category:"cement",applications:"plastering|masonry",preferences:"fast_setting",unit_cost:18,source:"Synthetic demo"},
 {sku:"CEM-B-FAST-50",name_zh:"快凝水泥",name_en:"Fast Cement",name_ms:"Simen Cepat Kering",brand:"Brand B",spec:"50kg",unit:"bag",unit_price:24,aliases:"水泥|cement|simen",category:"cement",applications:"plastering|masonry",preferences:"fast_setting",unit_cost:18.5,source:"Synthetic demo"},
 {sku:"CEM-C-PRO-50",name_zh:"快凝防水水泥",name_en:"Fast Waterproof Cement",name_ms:"Simen Cepat Kalis Air",brand:"Brand C",spec:"50kg",unit:"bag",unit_price:23.8,aliases:"水泥|cement|simen",category:"cement",applications:"plastering|masonry",preferences:"fast_setting|waterproof",unit_cost:18.4,source:"Synthetic demo"}
);
const stocks=[[120,20,100],[45,10,80],[0,15,100],[60,10,50],[35,10,60],[200,40,150],[85,15,80],[12,15,80],[70,15,100]];
const inventory=products.map((p,i)=>[p.sku,...stocks[i],"Synthetic demo"]);
const history=[];
const wins=[2,3,4,3,3];
for(let i=0;i<8;i++)history.push(["DEMO-FAST-"+String(i+1).padStart(3,"0"),"2026-10-"+String(2+i).padStart(2,"0"),"CEM-A-FAST-50",[18,20,22,20,20,20,25,20][i],"Shah Alam",i<5?wins[i]:3,28,25,i<5?"won":"lost","Synthetic demo"]);
for(let i=0;i<12;i++)history.push(["DEMO-OTHER-"+String(i+1).padStart(3,"0"),"2026-09-"+String(3+i).padStart(2,"0"),products[i%6].sku,10+(i%3)*5,i%2?"Klang":"Petaling Jaya",i%3, i%2?38:34,i%2?40:35,i%4?"won":"lost","Synthetic demo"]);
history.push(["DEMO-OPEN-001","2026-10-10","CEM-A-FAST-50",20,"Shah Alam",3,28,25,"open","Synthetic demo"]);
const delivery=[["Shah Alam","莎阿南|沙阿南|ShahAlam",35,30,"Synthetic demo"],["Petaling Jaya","PJ|八打灵再也",40,34,"Synthetic demo"],["Klang","巴生",45,38,"Synthetic demo"],["Kuala Lumpur","KL|吉隆坡",55,48,"Synthetic demo"]];
const rules=[["min_margin_pct",15,"Synthetic demo"],["max_discount_pct",10,"Synthetic demo"],["max_delivery_subsidy",3,"Synthetic demo"],["minimum_similar_orders",3,"Synthetic demo"],["sales_window_days",90,"Synthetic demo"]];
const tables={Products:[fields,...products.map(p=>fields.map(k=>p[k]??""))],Inventory:[["sku","stock","low_stock","high_stock","source"],...inventory],History:[["order_id","date","sku","quantity","area","discount_pct","delivery_cost","delivery_fee","outcome","source"],...history],Delivery:[["area","aliases","base_fee","cost","source"],...delivery],Rules:[["key","value","source"],...rules]};
const workbook=Workbook.create();
for(const [name,values] of Object.entries(tables)){
 const sheet=workbook.worksheets.add(name);sheet.showGridLines=false;sheet.tabColor="#174A78";
 const rows=values.length,cols=values[0].length;
 sheet.getRangeByIndexes(0,0,rows,cols).values=values;
 const used=sheet.getRangeByIndexes(0,0,rows,cols);used.format.font={name:"Noto Sans SC",size:11,color:"#172E49"};used.format.rowHeight=42;used.format.columnWidth=20;used.format.verticalAlignment="center";used.format.wrapText=true;used.format.borders={preset:"all",style:"thin",color:"#D9D9D9"};
 sheet.getRangeByIndexes(0,0,1,cols).format={fill:"#174A78",font:{name:"Noto Sans SC",size:11,bold:true,color:"#FFFFFF"},rowHeight:36,wrapText:true};
 for(let r=1;r<rows;r++)if(r%2===0)sheet.getRangeByIndexes(r,0,1,cols).format.fill="#F2F6FA";
 sheet.freezePanes.freezeRows(1);sheet.getRange("A:A").format.columnWidth=name==="Rules"?32:25;
 if(name==="Products"){
  sheet.getRange("B:G").format.columnWidth=24;sheet.getRange("I:I").format.columnWidth=32;sheet.getRange("K:L").format.columnWidth=31;
  sheet.getRange(`H2:H${rows}`).setNumberFormat('"RM "#,##0.00');sheet.getRange(`M2:M${rows}`).setNumberFormat('"RM "#,##0.00');
 }
 if(name==="History"){sheet.getRange("C:C").format.columnWidth=25;sheet.getRange("E:E").format.columnWidth=23;sheet.getRange(`G2:H${rows}`).setNumberFormat('"RM "#,##0.00');}
 if(name==="Delivery"){sheet.getRange("B:B").format.columnWidth=36;sheet.getRange(`C2:D${rows}`).setNumberFormat('"RM "#,##0.00');}
 if(name==="Rules")sheet.getRange(`B2:B${rows}`).format.horizontalAlignment="center";
 if(name==="Inventory")sheet.getRange(`B2:D${rows}`).format.horizontalAlignment="center";
 const table=sheet.tables.add(sheet.getRangeByIndexes(0,0,rows,cols),true,name+"Source");table.showFilterButton=true;
}
workbook.recalculate();
const output=await SpreadsheetFile.exportXlsx(workbook);await output.save(path.join(root,"samples/business_demo.xlsx"));
await fs.writeFile(path.join(root,"samples/business_demo.json"),JSON.stringify(tables,null,2));
for(const [name,range,label]of [["Products","A1:I6","products"],["Products","J1:N10","product-metadata"],["Inventory","A1:E10","inventory"],["History","A1:J10","history"],["Delivery","A1:E5","delivery"],["Rules","A1:C6","rules"]]){
 const preview=await workbook.render({sheetName:name,range,scale:1.4,format:"png"});
 await fs.writeFile(path.join(qa,label+".png"),new Uint8Array(await preview.arrayBuffer()));
}
console.log(JSON.stringify({file:path.join(root,"samples/business_demo.xlsx"),products:products.length,history_orders:history.length,sheets:Object.keys(tables)}));
