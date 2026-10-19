import { readFile, stat } from 'node:fs/promises';
import { createHash } from 'node:crypto';
const list=JSON.parse(await readFile('vendor-lock.json','utf8'));
const failures=[];
for(const item of list){
  try{
    const b=await readFile('dist/vendor/'+item.name);
    const sha=createHash('sha256').update(b).digest('hex');
    if(b.length!==item.size||sha!==item.sha)throw Error('SHA256/size mismatch');
    console.log('PASS',item.name,b.length);
  }catch(e){failures.push(item.name+': '+e.message)}
}
for(const path of ['index.html','pdf-merge/index.html','pdf-split/index.html','smart-submit/index.html','heic-to-jpg/index.html','avif-to-jpg/index.html','app.js','pdf-workbench.js','pdf-on-demand.js']){
  try{
    const b=await readFile('dist/'+path,'utf8');
    if(!b||b.length<500)throw Error('missing or truncated');
    if(path.endsWith('.html')&&!b.includes('v4.0'))throw Error('version not updated');
    console.log('PASS',path,b.length);
  }catch(e){failures.push(path+': '+e.message)}
}
if(failures.length)throw Error('Verification failed:\n'+failures.join('\n'));
console.log('15 static checks passed');
