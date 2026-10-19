import { chromium } from 'playwright';
import { readFile } from 'node:fs/promises';

const BASE=(process.env.BASE_URL||'http://127.0.0.1:4173').replace(/\/$/,'');
const browser=await chromium.launch({headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
const ctx=await browser.newContext({acceptDownloads:true,viewport:{width:1280,height:900}});
const page=await ctx.newPage();
page.setDefaultTimeout(20000);
const results=[];
async function run(name,fn){
  try{const detail=await fn();console.log('PASS',name,detail||'');results.push({name,pass:true});}
  catch(e){console.error('FAIL',name,e.message);results.push({name,pass:false});}
}
let png,p2,p3,p4;
try{
  await run('No PDF library downloaded on image homepage',async()=>{
    const requests=[];const capture=r=>requests.push(r.url());
    page.on('request',capture);await page.goto(BASE+'/',{waitUntil:'domcontentloaded'});
    await page.waitForTimeout(500);page.off('request',capture);
    if(requests.some(u=>/vendor\/pdf-lib|min\.js.*pdf/.test(u)))throw Error('Eager PDF library load');
  });
  await run('Create real browser-generated PNG fixture',async()=>{
    const base64=await page.evaluate(()=>{
      const c=document.createElement('canvas');c.width=440;c.height=280;
      const x=c.getContext('2d');x.fillStyle='#3159ad';x.fillRect(0,0,440,280);
      x.fillStyle='#ffcc6b';x.fillRect(40,50,260,160);
      return c.toDataURL('image/png').split(',')[1];
    });
    png=Buffer.from(base64,'base64');if(png.length<300)throw Error('Bad PNG');
    return png.length+' bytes';
  });
  if(png){
    await run('PNG to JPG with real 300x200 dimensions',async()=>{
      await page.locator('#single-input').setInputFiles({name:'fixture.png',mimeType:'image/png',buffer:png});
      await page.locator('#single-chip').waitFor({state:'visible'});
      await page.locator('#single-format').selectOption('image/jpeg');
      await page.locator('#single-width').fill('300');await page.locator('#single-height').fill('200');
      await page.locator('#single-run').click();await page.locator('#single-download').waitFor({state:'visible',timeout:30000});
      const r=await page.evaluate(async()=>{
        const v=new Uint8Array(await(await fetch(document.querySelector('#single-download').href)).arrayBuffer());
        return {head:[...v.slice(0,3)].join(','),size:v.length,dim:document.querySelector('#out-dim').textContent};
      });
      if(r.head!=='255,216,255'||!r.dim.includes('300 × 200'))throw Error(JSON.stringify(r));
    });
    await run('Batch conversion of two images',async()=>{
      await page.locator('#tab-batch').click();
      await page.locator('#batch-input').setInputFiles([
        {name:'one.png',mimeType:'image/png',buffer:png},
        {name:'two.png',mimeType:'image/png',buffer:png}
      ]);
      await page.locator('#batch-run').click();
      await page.waitForFunction(()=>document.querySelector('#batch-stage')?.textContent.includes('완료'),null,{timeout:45000});
      if(!(await page.locator('#batch-summary').innerText()).includes('성공 2'))throw Error('Expected 2 successes');
    });
    await run('Image to actual PDF with valid header',async()=>{
      await page.locator('#tab-pdf').click();
      await page.locator('#pdf-input').setInputFiles({name:'sample.png',mimeType:'image/png',buffer:png});
      await page.locator('#pdf-run').click();
      await page.locator('#pdf-download').waitFor({state:'visible',timeout:30000});
      const b=await page.evaluate(async()=>{
        const v=new Uint8Array(await(await fetch(document.querySelector('#pdf-download').href)).arrayBuffer());
        return String.fromCharCode(...v.slice(0,5));
      });
      if(b!=='%PDF-')throw Error('Invalid PDF header');
    });
  }
  await run('PDF editor loads first-party pdf-lib only',async()=>{
    await page.goto(BASE+'/pdf-merge/',{waitUntil:'domcontentloaded'});
    await page.waitForFunction(()=>!!window.PDFLib?.PDFDocument&&!!window.__pdfwork,null,{timeout:30000});
    const list=await page.evaluate(()=>performance.getEntriesByType('resource').map(x=>x.name).filter(s=>s.includes('pdf-lib.min.js')));
    if(list.length!==1||!list[0].includes('/vendor/pdf-lib.min.js'))throw Error(JSON.stringify(list));
  });
  await run('Generate 2-, 3-, and 4-page real PDFs',async()=>{
    const raw=await page.evaluate(async()=>{
      const files=[];for(const n of [2,3,4]){
        const d=await PDFLib.PDFDocument.create();for(let i=0;i<n;i++)d.addPage([300,200]);
        files.push([...new Uint8Array(await d.save())]);
      }return files;
    });
    [p2,p3,p4]=raw.map(a=>Buffer.from(a));
  });
  if(p2&&p3&&p4){
    await run('Merge PDFs into exactly five pages',async()=>{
      await page.locator('#wb-input').setInputFiles([
        {name:'two.pdf',mimeType:'application/pdf',buffer:p2},
        {name:'three.pdf',mimeType:'application/pdf',buffer:p3}
      ]);
      await page.locator('#wb-run').click();await page.locator('#wb-download').waitFor({state:'visible',timeout:60000});
      const count=await page.evaluate(async()=>{
        const b=await(await fetch(document.querySelector('#wb-download').href)).arrayBuffer();
        return(await PDFLib.PDFDocument.load(b)).getPageCount();
      });
      if(count!==5)throw Error('Result has '+count+' pages');
    });
    await run('Extract PDF pages 1 and 3',async()=>{
      await page.goto(BASE+'/pdf-split/',{waitUntil:'domcontentloaded'});
      await page.waitForFunction(()=>!!window.__pdfwork,null,{timeout:30000});
      await page.locator('#wb-input').setInputFiles({name:'four.pdf',mimeType:'application/pdf',buffer:p4});
      await page.locator('#wb-pages').fill('1,3');
      await page.locator('#wb-run').click();await page.locator('#wb-download').waitFor({state:'visible',timeout:60000});
      const n=await page.evaluate(async()=>{
        const a=await(await fetch(document.querySelector('#wb-download').href)).arrayBuffer();
        return(await PDFLib.PDFDocument.load(a)).getPageCount();
      });
      if(n!==2)throw Error('Expected 2 pages, got '+n);
    });
    await run('PDF thumbnail renders with local worker',async()=>{
      await page.locator('.wb-preview-button').first().click();
      await page.waitForFunction(()=>!!window.pdfjsLib,null,{timeout:30000});
      await page.locator('.v33-page-tile canvas').first().waitFor({state:'attached',timeout:30000});
      const src=await page.evaluate(()=>window.pdfjsLib.GlobalWorkerOptions.workerSrc);
      if(src!=='/vendor/pdf.worker.min.js')throw Error(src);
    });
  }
  await run('Verify four hosted libraries with length',async()=>{
    const manifest=await(await page.request.get(BASE+'/vendor/manifest.json')).json();
    if(manifest.dependencies?.length!==4)throw Error('Manifest missing');
    for(const x of manifest.dependencies){
      const resp=await page.request.get(BASE+'/vendor/'+x.name);
      if(!resp.ok()||(await resp.body()).length!==x.size)throw Error('Missing or damaged '+x.name);
    }
  });
  for(const [name,env,type] of [['HEIC','HEIC_FIXTURE','image/heic'],['AVIF','AVIF_FIXTURE','image/avif']]){
    if(!process.env[env])continue;
    await run(name+' actual image conversion',async()=>{
      const blob=await readFile(process.env[env]);
      await page.goto(BASE+'/'+name.toLowerCase()+'-to-jpg/',{waitUntil:'domcontentloaded'});
      await page.locator('#single-input').setInputFiles({name:'test.'+name.toLowerCase(),mimeType:type,buffer:blob});
      await page.locator('#single-chip').waitFor({state:'visible',timeout:30000});
      await page.locator('#single-run').click();await page.locator('#single-download').waitFor({state:'visible',timeout:30000});
      const b=await page.evaluate(async()=>{
        const x=new Uint8Array(await(await fetch(document.querySelector('#single-download').href)).arrayBuffer());
        return [...x.slice(0,3)].join(',');
      });
      if(b!=='255,216,255')throw Error('Invalid JPG output');
    });
  }
}finally{await browser.close()}
const passed=results.filter(r=>r.pass).length;
console.log('RESULTS',passed+'/'+results.length,'passed');
if(passed!==results.length)process.exitCode=1;
