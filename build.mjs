import { cp, mkdir, writeFile, readdir, readFile, stat, rm } from 'node:fs/promises';
import { createHash } from 'node:crypto';

const manifest = JSON.parse(await readFile('vendor-lock.json','utf8'));
const source = await stat('public/index.html').catch(() => null);
if (!source || source.size < 1000) throw Error('Missing committed site files under public/');
await rm('dist',{recursive:true,force:true});
await cp('public','dist',{recursive:true});
await mkdir('dist/vendor',{recursive:true});

async function fetchVerified(item) {
  let last;
  for (const url of item.urls) {
    try {
      const r=await fetch(url,{signal:AbortSignal.timeout(60000)});
      if(!r.ok)throw Error('HTTP '+r.status);
      const bytes=Buffer.from(await r.arrayBuffer());
      const actual=createHash('sha256').update(bytes).digest('hex');
      if(bytes.length!==item.size||actual!==item.sha)throw Error('SHA256/size mismatch');
      await writeFile('dist/vendor/'+item.name,bytes);
      console.log('Verified',item.name,bytes.length);
      return;
    } catch(e){last=e;console.warn('Vendor source failed',item.name,new URL(url).hostname,e.message)}
  }
  throw Error('Verified dependency unavailable: '+item.name+': '+last?.message);
}
await Promise.all(manifest.map(fetchVerified));
await writeFile('dist/vendor/manifest.json',JSON.stringify({version:'4.0.0',dependencies:manifest.map(x=>({name:x.name,size:x.size,sha256:x.sha}))},null,2));
async function relabel(dir){
  for(const entry of await readdir(dir,{withFileTypes:true})){
    const path=dir+'/'+entry.name;
    if(entry.isDirectory())await relabel(path);
    else if(entry.name.endsWith('.html')){
      let src=await readFile(path,'utf8');
      src=src.replace(/© 2026 제출OK · v3\.\d+/g,'© 2026 제출OK · v4.0')
        .replace(/FREE FILE TOOL · V3\.\d+/g,'FREE FILE TOOL · V4.0');
      await writeFile(path,src);
    }
  }
}
await relabel('dist');
console.log('v4.0 site built from Git source with hash-verified dependencies');
