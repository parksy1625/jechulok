
'use strict';
(()=>{
const $=id=>document.getElementById(id);
const formats={'image/jpeg':{ext:'jpg',name:'JPG'},'image/png':{ext:'png',name:'PNG'},'image/webp':{ext:'webp',name:'WebP'}};
const MAX_COUNT=30,MAX_TOTAL=150*1048576,MAX_EACH=40*1048576,MAX_PIXELS=30_000_000;
const size=n=>n>=1048576?(n/1048576).toFixed(2)+'MB':(n/1024).toFixed(1)+'KB';
const validType=f=>{const ext=f.name.toLowerCase().match(/\.([^.]+)$/)?.[1];const map={jpg:'image/jpeg',jpeg:'image/jpeg',png:'image/png',webp:'image/webp'};const mime=map[ext];return mime&&(f.type===''||f.type===mime)?mime:null;};
const safeName=name=>name.replace(/\.[^.]+$/,'').replace(/[\\/:*?"<>|\x00-\x1f]/g,'_').trim().slice(0,75)||'image';
const errString=e=>e instanceof Error?e.message:String(e);
const yieldUI=()=>new Promise(r=>setTimeout(r,0));
const status=(id,message,kind='info')=>{const el=$(id);el.textContent=message;el.className='status '+kind;};
const stage=(id,message)=>$(id).textContent=message;
const show=(id,visible)=>$(id).hidden=!visible;
function bindDrop(dropId,inputId,cb){const zone=$(dropId),input=$(inputId);zone.querySelector('.choose').addEventListener('click',e=>{e.stopPropagation();input.click()});zone.addEventListener('click',e=>{if(e.target!==input)input.click()});zone.addEventListener('keydown',e=>{if(e.target===zone&&(e.key==='Enter'||e.key===' ')){e.preventDefault();input.click()}});for(const name of ['dragenter','dragover'])zone.addEventListener(name,e=>{e.preventDefault();zone.classList.add('drag')});for(const name of ['dragleave','dragend'])zone.addEventListener(name,e=>{e.preventDefault();zone.classList.remove('drag')});zone.addEventListener('drop',e=>{e.preventDefault();zone.classList.remove('drag');cb(Array.from(e.dataTransfer.files||[]))});input.addEventListener('change',()=>{cb(Array.from(input.files||[]));input.value=''})}
async function loadImage(file){const url=URL.createObjectURL(file);try{const image=new Image();image.decoding='async';image.src=url;await image.decode();if(image.naturalWidth<1||image.naturalHeight<1||image.naturalWidth*image.naturalHeight>MAX_PIXELS)throw Error('이미지의 해상도가 3,000만 픽셀 제한을 넘거나 유효하지 않습니다.');return image}finally{URL.revokeObjectURL(url)}}
async function checkFile(file){if(!validType(file))throw Error('JPG·PNG·WebP 파일만 사용할 수 있습니다.');if(file.size>MAX_EACH)throw Error('한 장 최대 크기는 40MB입니다.');return loadImage(file)}
function parseRequirements(text){const s=text.normalize('NFKC').toLowerCase(),p={};let m;const fm=s.match(/\b(jpe?g|png|webp)\b/);if(fm)p.format=fm[1]==='jpg'||fm[1]==='jpeg'?'image/jpeg':'image/'+fm[1];m=s.match(/(?:가로|너비|폭|width)\s*[:=]?\s*(\d{1,5})/);if(m)p.width=+m[1];m=s.match(/(?:세로|높이|height)\s*[:=]?\s*(\d{1,5})/);if(m)p.height=+m[1];m=s.match(/(\d{2,5})\s*(?:px|픽셀)?\s*[x×*]\s*(\d{2,5})/);if(m){p.width=+m[1];p.height=+m[2]}const sizes=Array.from(s.matchAll(/(\d+(?:\.\d+)?)\s*(kib|mib|kb|mb|킬로바이트|메가바이트)\s*(이하|이내|미만|이상|초과|까지)?/g)).filter(x=>!['이상','초과'].includes(x[3]));if(sizes.length){const v=sizes.at(-1);p.max=+v[1]*(v[2][0]==='m'||v[2]==='메가바이트'?1024:1)}return p}
function config(prefix){const format=$(prefix+'-format').value;if(!formats[format])throw Error('지원하지 않는 출력 형식입니다.');const n=(field,limit)=>{const s=$(prefix+'-'+field).value.trim();if(!s)return null;const value=Number(s);if(!Number.isFinite(value)||value<=0||value>limit||(field!=='max'&&!Number.isInteger(value)))throw Error(field==='max'?'파일 용량은 0보다 크고 40960KB 이하여야 합니다.':'이미지 크기는 1~8192 정수 픽셀이어야 합니다.');return value};const width=n('width',8192),height=n('height',8192),max=n('max',40960),fit=$(prefix+'-fit').value;return {format,width,height,maxBytes:max===null?null:Math.floor(max*1024),fit}}
function dimensions(im,c){let w=c.width,h=c.height;if(w===null&&h===null){w=im.naturalWidth;h=im.naturalHeight}else if(w===null)w=Math.max(1,Math.round(im.naturalWidth*h/im.naturalHeight));else if(h===null)h=Math.max(1,Math.round(im.naturalHeight*w/im.naturalWidth));if(w>8192||h>8192||w*h>MAX_PIXELS)throw Error('출력 해상도는 한 변 8192px, 전체 3,000만 픽셀 이하만 지원합니다.');return {w,h}}
function draw(im,w,h,c){const canvas=document.createElement('canvas');canvas.width=w;canvas.height=h;const ctx=canvas.getContext('2d',{alpha:c.format!=='image/jpeg'});if(!ctx)throw Error('Canvas 그래픽 처리가 지원되지 않는 환경입니다.');ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';if(c.format==='image/jpeg'){ctx.fillStyle='#fff';ctx.fillRect(0,0,w,h)}if(c.width!==null&&c.height!==null){if(c.fit==='stretch')ctx.drawImage(im,0,0,w,h);else if(c.fit==='cover'){const sw=Math.min(im.naturalWidth,im.naturalHeight*w/h),sh=Math.min(im.naturalHeight,im.naturalWidth*h/w);ctx.drawImage(im,(im.naturalWidth-sw)/2,(im.naturalHeight-sh)/2,sw,sh,0,0,w,h)}else{const scale=Math.min(w/im.naturalWidth,h/im.naturalHeight),dw=im.naturalWidth*scale,dh=im.naturalHeight*scale;ctx.drawImage(im,(w-dw)/2,(h-dh)/2,dw,dh)}}else ctx.drawImage(im,0,0,w,h);return canvas}
async function makeBlob(canvas,type,q){return new Promise((resolve,reject)=>canvas.toBlob(b=>{if(!b||b.type!==type)reject(Error('이 브라우저에서 해당 출력 형식을 지원하지 않습니다.'));else resolve(b)},type,q))}
async function fitSize(canvas,c){if(c.maxBytes===null)return await makeBlob(canvas,c.format,.92);if(c.format==='image/png'){const b=await makeBlob(canvas,c.format);return b.size<=c.maxBytes?b:null}const high=await makeBlob(canvas,c.format,.94);if(high.size<=c.maxBytes)return high;let lo=.02,hi=.94,best=await makeBlob(canvas,c.format,lo);if(best.size>c.maxBytes)return null;for(let i=0;i<10;i++){const q=(lo+hi)/2,v=await makeBlob(canvas,c.format,q);if(v.size<=c.maxBytes){best=v;lo=q}else hi=q}return best}
async function transform(im,c,cancel=()=>false){let {w,h}=dimensions(im,c);const fixed=c.width!==null||c.height!==null;for(let i=0;i<(fixed?1:15);i++){if(cancel())throw Error('취소한 작업입니다.');const canvas=draw(im,w,h,c);const b=await fitSize(canvas,c);canvas.width=canvas.height=0;if(b){await verify(b,c,w,h);return {blob:b,w,h}}if(fixed)break;w=Math.floor(w*.82);h=Math.floor(h*.82);if(w<1||h<1)break;await yieldUI()}throw Error(fixed?'지정한 픽셀·형식·용량 조건을 함께 만족할 수 없습니다. 크기나 용량을 조정하세요.':'요구된 용량이 너무 작습니다. 용량을 높이거나 출력 형식을 바꿔 주세요.')}
async function verify(blob,c,w,h){if(blob.type!==c.format||c.maxBytes!==null&&blob.size>c.maxBytes)throw Error('파일 형식/용량 검증에 실패했습니다.');const decoded=await loadImage(blob);if(decoded.naturalWidth!==w||decoded.naturalHeight!==h)throw Error('변환된 이미지의 실제 픽셀 크기가 다릅니다.');if(c.width!==null&&w!==c.width||c.height!==null&&h!==c.height)throw Error('요청한 픽셀 크기를 충족하지 못했습니다.');return true}
function downloadBlob(blob,name){const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.style.display='none';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000)}
function selectTool(which){document.querySelectorAll('[data-tool]').forEach(btn=>{const yes=btn.dataset.tool===which;btn.classList.toggle('active',yes);btn.setAttribute('aria-selected',String(yes))});for(const x of ['single','batch','pdf']){const yes=which===x;show('pane-'+x,yes);$('pane-'+x).classList.toggle('active',yes)}try{history.replaceState(null,'',location.pathname+location.search+'#'+which)}catch(e){}}
document.querySelectorAll('[data-tool]').forEach(x=>x.addEventListener('click',()=>selectTool(x.dataset.tool)));
// ----------------- Single image -----------------
let singleFile=null,singleImg=null,singleURL=null,singleOutputURL=null,singleToken=0,singleBusy=false,singleFormatChosen=false;
function clearSingle(){if(singleOutputURL)URL.revokeObjectURL(singleOutputURL);singleOutputURL=null;show('single-result',false);show('single-empty',true);stage('single-stage','작업 대기');$('single-download').removeAttribute('href')}
async function pickSingle(files){const file=files[0];if(!file)return;const token=++singleToken;singleFile=null;singleImg=null;clearSingle();if(singleURL)URL.revokeObjectURL(singleURL);singleURL=null;show('single-chip',false);try{const im=await checkFile(file);if(token!==singleToken)return;singleFile=file;singleImg=im;singleURL=URL.createObjectURL(file);$('single-thumb').src=singleURL;$('single-name').textContent=file.name;$('single-info').textContent=size(file.size)+' · '+im.naturalWidth+' × '+im.naturalHeight+'px';show('single-chip',true);if(!singleFormatChosen)$('single-format').value=validType(file);status('single-status','이미지 준비 완료. 제출 조건을 설정하세요.')}catch(e){status('single-status',errString(e),'error')}}
bindDrop('single-drop','single-input',pickSingle);
$('single-remove').addEventListener('click',()=>{singleToken++;singleFile=null;singleImg=null;if(singleURL)URL.revokeObjectURL(singleURL);singleURL=null;show('single-chip',false);clearSingle();status('single-status','')});
$('parse-btn').addEventListener('click',()=>{const p=parseRequirements($('requirements').value),msg=[];if(p.format){$('single-format').value=p.format;singleFormatChosen=true;msg.push(formats[p.format].name)}for(const key of ['width','height','max'])if(p[key]!==undefined){$('single-'+key).value=p[key];msg.push(key+' '+p[key])}$('parse-msg').textContent=msg.length?'✓ '+msg.join(' · ')+' 조건을 인식했습니다.':'인식한 조건이 없습니다. 직접 입력해 주세요.';singleToken++;clearSingle()});
$('requirements').addEventListener('keydown',e=>{if((e.metaKey||e.ctrlKey)&&e.key==='Enter')$('parse-btn').click()});
const presets={resume:{format:'image/jpeg',max:500,width:300,height:400,fit:'contain'},under100:{format:'image/jpeg',max:100,width:'',height:'',fit:'contain'},under500:{format:'image/jpeg',max:500,width:'',height:'',fit:'contain'},square:{format:'image/png',max:'',width:512,height:512,fit:'cover'},web:{format:'image/webp',max:'',width:1200,height:'',fit:'contain'}};
function applyPreset(p){const v=presets[p];if(!v)return;for(const [k,val]of Object.entries(v))$('single-'+k).value=val;singleFormatChosen=true;singleToken++;clearSingle();$('parse-msg').textContent='빠른 설정을 적용했습니다. 실제 제출처 규정을 확인하세요.'}
document.querySelectorAll('[data-preset]').forEach(x=>x.addEventListener('click',()=>applyPreset(x.dataset.preset)));
for(const key of ['format','max','width','height','fit'])$('single-'+key).addEventListener('change',()=>{singleToken++;clearSingle();if(key==='format')singleFormatChosen=true});
$('single-form').addEventListener('submit',async e=>{e.preventDefault();if(singleBusy)return;if(!singleFile||!singleImg){status('single-status','이미지부터 선택해 주세요.','error');return}let c;try{c=config('single')}catch(e){status('single-status',errString(e),'error');return}const token=++singleToken;singleBusy=true;$('single-run').disabled=true;clearSingle();stage('single-stage','변환 중');status('single-status','브라우저에서 변환하고 실제 결과를 검증하는 중…');try{await yieldUI();const r=await transform(singleImg,c,()=>token!==singleToken);if(token!==singleToken)return;singleOutputURL=URL.createObjectURL(r.blob);$('single-preview').src=singleOutputURL;$('out-format').textContent=formats[c.format].name;$('out-size').textContent=size(r.blob.size);$('out-dim').textContent=r.w+' × '+r.h;$('single-checks').replaceChildren();for(const label of ['형식 '+formats[c.format].name+' 확인','실제 이미지 크기 '+r.w+' × '+r.h+'px 확인',...(c.maxBytes!==null?['파일 용량 '+size(r.blob.size)+' ≤ '+size(c.maxBytes)]:[])]){const row=document.createElement('div');row.textContent=label;$('single-checks').append(row)}$('single-download').href=singleOutputURL;$('single-download').download=safeName(singleFile.name)+'_제출OK.'+formats[c.format].ext;show('single-empty',false);show('single-result',true);stage('single-stage','검증 완료');status('single-status','모든 지정 조건을 충족했습니다. 다운로드할 수 있습니다.','success')}catch(e){if(token===singleToken){stage('single-stage','오류');status('single-status',errString(e),'error')}}finally{singleBusy=false;$('single-run').disabled=false}});
// ----------------- Batch -----------------
let batchFiles=[],batchResults=[],batchBusy=false,batchToken=0,batchURLs=[];
function clearBatchOutputs(){for(const u of batchURLs)URL.revokeObjectURL(u);batchURLs=[];batchResults=[];show('batch-result',false);show('batch-empty',true);$('batch-zip').disabled=true;stage('batch-stage','작업 대기')}
function validateList(added,existing){const candidates=[...existing,...added];if(candidates.length>MAX_COUNT)throw Error('한 번에 최대 '+MAX_COUNT+'장까지만 선택할 수 있습니다.');if(candidates.reduce((a,b)=>a+b.size,0)>MAX_TOTAL)throw Error('전체 파일 크기는 최대 150MB입니다.');for(const f of added){if(!validType(f))throw Error('JPG·PNG·WebP 파일만 지원합니다: '+f.name);if(f.size>MAX_EACH)throw Error('40MB가 넘는 파일이 있습니다: '+f.name)}return candidates}
function setBatchFiles(files){try{batchFiles=validateList(files,batchFiles);batchToken++;clearBatchOutputs();renderBatch();status('batch-status',files.length+'장 추가됨. 총 '+batchFiles.length+'장')}catch(e){status('batch-status',errString(e),'error')}}
bindDrop('batch-drop','batch-input',setBatchFiles);
function fileRow(index,title,subtitle,buttons=[]){const row=document.createElement('div');row.className='file-row';const ix=document.createElement('span');ix.className='file-index';ix.textContent=index;const info=document.createElement('div');info.className='details';const b=document.createElement('b');b.textContent=title;const small=document.createElement('small');small.textContent=subtitle;info.append(b,small);row.append(ix,info);if(buttons.length){const acts=document.createElement('div');acts.className='actions';for(const o of buttons){const button=document.createElement('button');button.type='button';button.textContent=o.label;button.disabled=!!o.disabled;button.setAttribute('aria-label',o.aria||o.label);button.addEventListener('click',o.fn);acts.append(button)}row.append(acts)}return row}
function renderBatch(){const box=$('batch-list');box.replaceChildren();$('batch-count').textContent='선택한 이미지 '+batchFiles.length+'장';if(!batchFiles.length){const t=document.createElement('p');t.className='tiny';t.textContent='아직 선택한 이미지가 없습니다.';box.append(t)}batchFiles.forEach((f,i)=>box.append(fileRow(i+1,f.name,size(f.size),[{label:'×',aria:f.name+' 목록에서 제거',fn:()=>{if(batchBusy)return;batchFiles.splice(i,1);batchToken++;clearBatchOutputs();renderBatch()}}])))}
$('batch-clear').addEventListener('click',()=>{if(batchBusy)return;batchFiles=[];batchToken++;clearBatchOutputs();renderBatch();status('batch-status','')});
for(const k of ['format','max','width','height','fit'])$('batch-'+k).addEventListener('change',()=>{batchToken++;if(!batchBusy)clearBatchOutputs()});
$('batch-cancel').addEventListener('click',()=>{batchToken++;status('batch-status','취소 요청됨. 현재 파일 처리 직후 중단됩니다.','info')});
$('batch-form').addEventListener('submit',async e=>{e.preventDefault();if(batchBusy)return;if(!batchFiles.length){status('batch-status','이미지를 먼저 선택해 주세요.','error');return}let c;try{c=config('batch')}catch(e){status('batch-status',errString(e),'error');return}batchBusy=true;const token=++batchToken,files=[...batchFiles];clearBatchOutputs();show('batch-result',true);show('batch-empty',false);$('batch-run').disabled=true;show('batch-cancel',true);stage('batch-stage','변환 중');$('batch-summary').textContent='준비 중';$('batch-results').replaceChildren();status('batch-status','일괄 변환 중…');let ok=0,fail=0;for(let i=0;i<files.length;i++){if(token!==batchToken)break;const f=files[i];$('batch-summary').textContent=`${i+1}/${files.length} 처리 중 · 성공 ${ok} / 실패 ${fail}`;await yieldUI();try{const im=await checkFile(f);const r=await transform(im,c,()=>token!==batchToken);if(token!==batchToken)break;const name=String(i+1).padStart(2,'0')+'_'+safeName(f.name)+'_제출OK.'+formats[c.format].ext;const url=URL.createObjectURL(r.blob);batchURLs.push(url);batchResults.push({name,blob:r.blob});const row=fileRow(i+1,f.name,`✓ ${size(r.blob.size)} · ${r.w} × ${r.h}px`,[{label:'저장',fn:()=>downloadBlob(r.blob,name)}]);row.classList.add('ok');$('batch-results').append(row);ok++}catch(e){if(token!==batchToken)break;const row=fileRow(i+1,f.name,errString(e));row.classList.add('error');$('batch-results').append(row);fail++}$('batch-progress').style.width=((i+1)/files.length*100)+'%'}const canceled=token!==batchToken;stage('batch-stage',canceled?'작업 중단':'완료');$('batch-summary').textContent=`${canceled?'중단됨 · ':''}성공 ${ok}장 / 실패 ${fail}장 · 총 ${files.length}장`;$('batch-zip').disabled=ok===0;status('batch-status',canceled?'작업을 중단했습니다. 완료된 결과는 다운로드할 수 있습니다.':`변환 완료: ${ok}개 성공 · ${fail}개 실패`,fail?'error':'success');$('batch-run').disabled=false;show('batch-cancel',false);batchBusy=false});
// ZIP STORE (no external libraries; UTF-8 filenames, CRC32)
const crcTable=(()=>{const t=new Uint32Array(256);for(let i=0;i<256;i++){let c=i;for(let j=0;j<8;j++)c=(c&1)?0xedb88320^(c>>>1):c>>>1;t[i]=c>>>0}return t})();
function crc32(bytes){let c=0xffffffff;for(const b of bytes)c=crcTable[(c^b)&255]^(c>>>8);return(c^0xffffffff)>>>0}
function zipFiles(entries){const enc=new TextEncoder(),parts=[],central=[];let offset=0;const push=data=>{parts.push(data);offset+=data.length};function head(len,fill){const buf=new Uint8Array(len),v=new DataView(buf.buffer);fill(v);return buf}for(const e of entries){const filename=enc.encode(e.name),bytes=e.data,crc=crc32(bytes),start=offset;push(head(30,v=>{v.setUint32(0,0x04034b50,true);v.setUint16(4,20,true);v.setUint16(6,0x800,true);v.setUint16(8,0,true);v.setUint32(14,crc,true);v.setUint32(18,bytes.length,true);v.setUint32(22,bytes.length,true);v.setUint16(26,filename.length,true)}));push(filename);push(bytes);central.push({filename,crc,bytes:bytes.length,start})}const startCD=offset;for(const e of central){push(head(46,v=>{v.setUint32(0,0x02014b50,true);v.setUint16(4,20,true);v.setUint16(6,20,true);v.setUint16(8,0x800,true);v.setUint32(16,e.crc,true);v.setUint32(20,e.bytes,true);v.setUint32(24,e.bytes,true);v.setUint16(28,e.filename.length,true);v.setUint32(42,e.start,true)}));push(e.filename)}const lengthCD=offset-startCD;push(head(22,v=>{v.setUint32(0,0x06054b50,true);v.setUint16(8,entries.length,true);v.setUint16(10,entries.length,true);v.setUint32(12,lengthCD,true);v.setUint32(16,startCD,true)}));return new Blob(parts,{type:'application/zip'})}
$('batch-zip').addEventListener('click',async()=>{if(!batchResults.length)return;$('batch-zip').disabled=true;status('batch-status','ZIP 파일을 만드는 중…');try{const entries=[];for(const r of batchResults){entries.push({name:r.name,data:new Uint8Array(await r.blob.arrayBuffer())})}downloadBlob(zipFiles(entries),'제출OK_일괄변환_'+entries.length+'장.zip');status('batch-status',entries.length+'개 파일 ZIP 다운로드 준비 완료.','success')}catch(e){status('batch-status',errString(e),'error')}finally{$('batch-zip').disabled=false}});
// ----------------- Image to PDF -----------------
let pdfFiles=[],pdfBusy=false,pdfURL=null,pdfToken=0;
function clearPDF(){pdfToken++;if(pdfURL)URL.revokeObjectURL(pdfURL);pdfURL=null;show('pdf-result',false);show('pdf-empty',true);stage('pdf-stage','작업 대기')}
function renderPdf(){const el=$('pdf-list');el.replaceChildren();$('pdf-count').textContent='선택한 사진 '+pdfFiles.length+'장';if(!pdfFiles.length){const p=document.createElement('p');p.className='tiny';p.textContent='아직 선택한 파일이 없습니다.';el.append(p)}pdfFiles.forEach((f,i)=>el.append(fileRow(i+1,f.name,size(f.size),[{label:'↑',disabled:i===0||pdfBusy,aria:f.name+' 앞으로',fn:()=>{[pdfFiles[i-1],pdfFiles[i]]=[pdfFiles[i],pdfFiles[i-1]];clearPDF();renderPdf()}},{label:'↓',disabled:i===pdfFiles.length-1||pdfBusy,aria:f.name+' 뒤로',fn:()=>{[pdfFiles[i+1],pdfFiles[i]]=[pdfFiles[i],pdfFiles[i+1]];clearPDF();renderPdf()}},{label:'×',disabled:pdfBusy,aria:f.name+' 목록에서 제거',fn:()=>{pdfFiles.splice(i,1);clearPDF();renderPdf()}}])))}
function addPDF(files){try{pdfFiles=validateList(files,pdfFiles);clearPDF();renderPdf();status('pdf-status',files.length+'장 추가됐습니다.')}catch(e){status('pdf-status',errString(e),'error')}}
bindDrop('pdf-drop','pdf-input',addPDF);$('pdf-clear').addEventListener('click',()=>{if(pdfBusy)return;pdfFiles=[];clearPDF();renderPdf();status('pdf-status','')});
for(const k of ['orientation','margin','name'])$('pdf-'+k).addEventListener('change',clearPDF);
const encoder=new TextEncoder();const encode=s=>encoder.encode(s);
function jpegPDF(pages,width,height,margin){const objs=new Map(),kids=[];objs.set(1,encode('<< /Type /Catalog /Pages 2 0 R >>'));for(let i=0;i<pages.length;i++){const p=pages[i],imageId=3+3*i,contentId=imageId+1,pageId=imageId+2;const imgWidth=p.w,imgHeight=p.h;const scale=Math.min((width-2*margin)/imgWidth,(height-2*margin)/imgHeight),dw=imgWidth*scale,dh=imgHeight*scale,x=(width-dw)/2,y=(height-dh)/2;const stream=encode('q\n'+dw.toFixed(3)+' 0 0 '+dh.toFixed(3)+' '+x.toFixed(3)+' '+y.toFixed(3)+' cm\n/Im1 Do\nQ\n');objs.set(imageId,[encode('<< /Type /XObject /Subtype /Image /Width '+imgWidth+' /Height '+imgHeight+' /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length '+p.bytes.length+' >>\nstream\n'),p.bytes,encode('\nendstream')]);objs.set(contentId,[encode('<< /Length '+stream.length+' >>\nstream\n'),stream,encode('endstream')]);objs.set(pageId,encode('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 '+width+' '+height+'] /Resources << /XObject << /Im1 '+imageId+' 0 R >> >> /Contents '+contentId+' 0 R >>'));kids.push(pageId+' 0 R')}objs.set(2,encode('<< /Type /Pages /Kids ['+kids.join(' ')+'] /Count '+pages.length+' >>'));const max=pages.length*3+2,parts=[encode('%PDF-1.4\n%\xE2\xE3\xCF\xD3\n')],offsets=[0];let position=parts[0].length;const add=b=>{parts.push(b);position+=b.length};for(let i=1;i<=max;i++){offsets[i]=position;add(encode(i+' 0 obj\n'));const o=objs.get(i);if(Array.isArray(o))o.forEach(add);else add(o);add(encode('\nendobj\n'))}const start=position;add(encode('xref\n0 '+(max+1)+'\n0000000000 65535 f \n'));for(let i=1;i<=max;i++)add(encode(String(offsets[i]).padStart(10,'0')+' 00000 n \n'));add(encode('trailer\n<< /Size '+(max+1)+' /Root 1 0 R >>\nstartxref\n'+start+'\n%%EOF'));return new Blob(parts,{type:'application/pdf'})}
$('pdf-form').addEventListener('submit',async e=>{e.preventDefault();if(pdfBusy)return;if(!pdfFiles.length){status('pdf-status','사진을 먼저 선택해 주세요.','error');return}const files=[...pdfFiles],token=++pdfToken,width=$('pdf-orientation').value==='portrait'?595.28:841.89,height=$('pdf-orientation').value==='portrait'?841.89:595.28,margin=Number($('pdf-margin').value);pdfBusy=true;$('pdf-run').disabled=true;stage('pdf-stage','제작 중');status('pdf-status','사진을 순서대로 PDF에 넣고 있습니다…');const pages=[];try{for(let i=0;i<files.length;i++){if(token!==pdfToken)throw Error('작업 조건이 변경됐습니다.');status('pdf-status',`${i+1}/${files.length} 페이지 작성 중…`);await yieldUI();const im=await checkFile(files[i]);const scale=Math.min(1,2200/Math.max(im.naturalWidth,im.naturalHeight));const w=Math.max(1,Math.round(im.naturalWidth*scale)),h=Math.max(1,Math.round(im.naturalHeight*scale));const canvas=document.createElement('canvas');canvas.width=w;canvas.height=h;const ctx=canvas.getContext('2d',{alpha:false});if(!ctx)throw Error('Canvas를 생성할 수 없습니다.');ctx.fillStyle='#fff';ctx.fillRect(0,0,w,h);ctx.drawImage(im,0,0,w,h);const blob=await makeBlob(canvas,'image/jpeg',.87);canvas.width=canvas.height=0;pages.push({w,h,bytes:new Uint8Array(await blob.arrayBuffer())})}if(token!==pdfToken)throw Error('작업 조건이 변경됐습니다.');const doc=jpegPDF(pages,width,height,margin);if(!doc.size)throw Error('PDF 생성 실패');if(pdfURL)URL.revokeObjectURL(pdfURL);pdfURL=URL.createObjectURL(doc);const name=safeName($('pdf-name').value||'제출OK_사진모음')+'.pdf';$('pdf-download').href=pdfURL;$('pdf-download').download=name;$('pdf-result-name').textContent=name;$('pdf-stats').textContent=files.length+'페이지 · A4 '+($('pdf-orientation').value==='portrait'?'세로':'가로')+' · '+size(doc.size);show('pdf-empty',false);show('pdf-result',true);stage('pdf-stage','완성');status('pdf-status','PDF '+files.length+'페이지를 완성했습니다.','success')}catch(e){if(token===pdfToken){stage('pdf-stage','오류');status('pdf-status',errString(e),'error')}}finally{pdfBusy=false;$('pdf-run').disabled=false;renderPdf()}});
window.addEventListener('beforeunload',()=>{if(singleURL)URL.revokeObjectURL(singleURL);if(singleOutputURL)URL.revokeObjectURL(singleOutputURL);if(pdfURL)URL.revokeObjectURL(pdfURL);batchURLs.forEach(u=>URL.revokeObjectURL(u))});
const query=new URLSearchParams(location.search);
const routes={'/image-batch/':{tool:'batch'},'/images-to-pdf/':{tool:'pdf'},'/image-compress/':{tool:'single',preset:'under500'},'/jpg-500kb/':{tool:'single',preset:'under500'},'/photo-300x400/':{tool:'single',preset:'resume'},'/png-to-jpg/':{tool:'single',format:'image/jpeg'}};
const route=routes[location.pathname.endsWith('/')?location.pathname:location.pathname+'/'];
if(route?.preset&&!query.has('preset'))applyPreset(route.preset);
if(route?.format&&!query.has('preset')){$('single-format').value=route.format;singleFormatChosen=true;}
if(query.has('preset'))applyPreset(query.get('preset'));
const selected=query.get('tool')||location.hash.slice(1)||route?.tool;
if(['single','batch','pdf'].includes(selected))selectTool(selected);
document.addEventListener('paste',e=>{if(e.target?.closest?.('input,textarea,[contenteditable="true"]'))return;const item=Array.from(e.clipboardData?.items||[]).find(x=>x.kind==='file'&&/^image\/(png|jpeg|webp)$/.test(x.type));if(!item)return;const b=item.getAsFile();if(!b)return;e.preventDefault();const f=new File([b],'붙여넣은_이미지.'+(item.type==='image/jpeg'?'jpg':item.type.split('/')[1]),{type:item.type});selectTool('single');pickSingle([f]);status('single-status','클립보드 이미지를 불러왔습니다.','success')});
window.__jechulok={parseRequirements,config,zipFiles,jpegPDF,validType};
})();


;(()=>{
'use strict';
const supported=['single','batch','pdf'];
const LIMIT=40*1048576, TOTAL=150*1048576, COUNT=30;
const heicRe=/\.(heic|heif)$/i,avifRe=/\.avif$/i;
const isHeic=f=>heicRe.test(f.name)||/^image\/(heic|heif)$/i.test(f.type);
const isAvif=f=>avifRe.test(f.name)||/^image\/avif$/i.test(f.type);
const state=(kind,msg,bad=false)=>{const e=document.getElementById(kind+'-status');if(e){e.textContent=msg;e.className='status '+(bad?'error':'info')}};
let pending=null,busy=false;
const loadHeic=async()=>{
 if(typeof window.heic2any==='function')return window.heic2any;
 if(!pending)pending=new Promise((resolve,reject)=>{
   const s=document.createElement('script');
   s.src='/vendor/heic2any.min.js';
   s.async=true;s.onload=resolve;s.onerror=()=>{const b=document.createElement('script');b.src='https://cdn.jsdelivr.net/npm/heic2any@0.0.4/dist/heic2any.min.js';b.async=true;b.onload=resolve;b.onerror=()=>reject(Error('HEIC 변환 라이브러리 연결 실패.'));document.head.append(b)};
   document.head.append(s)
 }).catch(e=>{pending=null;throw e});
 await pending;
 if(typeof window.heic2any!=='function')throw Error('이 브라우저에서 HEIC 변환기를 실행할 수 없습니다.');
 return window.heic2any;
};
async function avifJpg(file){
 let bitmap=null,url=null,image=null,canvas=null;
 try{
   let source,width,height;
   if(typeof createImageBitmap==='function'){
     try{bitmap=await createImageBitmap(file);source=bitmap;width=bitmap.width;height=bitmap.height}catch(e){}
   }
   if(!source){url=URL.createObjectURL(file);image=new Image();image.src=url;await image.decode();source=image;width=image.naturalWidth;height=image.naturalHeight}
   if(!width||!height||width*height>30000000)throw Error('이미지 픽셀 제한(3,000만)을 확인하세요.');
   canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;
   const ctx=canvas.getContext('2d',{alpha:false});if(!ctx)throw Error('캔버스를 사용할 수 없습니다.');
   ctx.fillStyle='#ffffff';ctx.fillRect(0,0,width,height);ctx.drawImage(source,0,0,width,height);
   const out=await new Promise((ok,fail)=>canvas.toBlob(b=>b?ok(b):fail(Error('JPG 생성 실패')),'image/jpeg',.92));
   return out;
 }catch(e){throw Error('AVIF 이미지를 열 수 없습니다. 브라우저 지원 또는 원본 파일을 확인하세요. ('+(e.message||e)+')')}
 finally{bitmap?.close?.();if(url)URL.revokeObjectURL(url);if(canvas){canvas.width=0;canvas.height=0}}
}
async function prepare(file){
 if(!isHeic(file)&&!isAvif(file))return file;
 if(file.size>LIMIT)throw Error('한 파일은 최대 40MB입니다.');
 let blob;
 if(isHeic(file)){
    const conv=await loadHeic();
    let result;try{result=await conv({blob:file,toType:'image/jpeg',quality:.92})}catch(e){throw Error('HEIC 파일을 변환하지 못했습니다. 손상·미지원 인코딩 여부를 확인하세요. ('+(e.message||e)+')')}
    blob=Array.isArray(result)?result[0]:result;
 }else blob=await avifJpg(file);
 if(!blob||blob.size<3||blob.size>LIMIT)throw Error('변환된 JPG의 파일 크기가 유효하지 않습니다.');
 const header=new Uint8Array(await blob.slice(0,3).arrayBuffer());
 if(header[0]!==255||header[1]!==216||header[2]!==255)throw Error('변환 결과가 올바른 JPG 파일이 아닙니다.');
 return new File([blob],file.name.replace(/\.[^.]+$/,'')+'.jpg',{type:'image/jpeg',lastModified:file.lastModified});
}
async function dispatch(kind,files,input){
 if(busy){state(kind,'다른 파일의 변환이 끝난 뒤 다시 시도해 주세요.',true);return}
 if(files.length>COUNT||files.some(f=>f.size>LIMIT)||files.reduce((a,f)=>a+f.size,0)>TOTAL){state(kind,'최대 30장, 개별 40MB, 전체 150MB까지만 지원합니다.',true);return}
 busy=true;
 try{
   const completed=[];
   for(let i=0;i<files.length;i++){state(kind,'브라우저에서 사진 준비 중 '+(i+1)+'/'+files.length+' (서버 업로드 없음)');completed.push(await prepare(files[i]))}
   if(typeof DataTransfer!=='function')throw Error('파일 입력 연동 미지원 브라우저입니다. 최신 브라우저를 이용해 주세요.');
   const transfer=new DataTransfer();completed.forEach(file=>transfer.items.add(file));
   const target=input||document.getElementById(kind+'-input');
   target.files=transfer.files;target.dataset.v35Ready='1';target.dispatchEvent(new Event('change',{bubbles:true}));
   if(files.some(f=>isHeic(f)||isAvif(f)))state(kind,'HEIC·AVIF → JPG 변환을 마쳤습니다. 이제 원하는 용량과 픽셀을 설정하세요.');
 }catch(e){state(kind,e.message||String(e),true)}
 finally{busy=false}
}
for(const kind of supported){
 const input=document.getElementById(kind+'-input');if(!input)continue;
 input.accept=(input.accept||'')+',.heic,.heif,.avif,image/heic,image/heif,image/avif';
 const drop=document.getElementById(kind+'-drop');
 if(drop){const sub=drop.querySelector('span:not(.upload-graphic)');if(sub&&kind==='pdf')sub.textContent='JPG · PNG · WebP · HEIC · AVIF 지원'}
 input.addEventListener('change',e=>{
   if(input.dataset.v35Ready==='1'){delete input.dataset.v35Ready;return}
   const list=Array.from(input.files||[]);
   if(!list.some(f=>isHeic(f)||isAvif(f)))return;
   e.stopImmediatePropagation();e.preventDefault();dispatch(kind,list,input);
 },{capture:true});
 if(drop)drop.addEventListener('drop',e=>{
   const list=Array.from(e.dataTransfer?.files||[]);
   if(!list.some(f=>isHeic(f)||isAvif(f)))return;
   e.preventDefault();e.stopImmediatePropagation();drop.classList.remove('drag');dispatch(kind,list,input);
 },true);
}
if(/^\/(heic-to-jpg|avif-to-jpg)\/?$/.test(location.pathname)){
 document.getElementById('tab-single')?.click();
 const fmt=document.getElementById('single-format');
 if(fmt){fmt.value='image/jpeg';fmt.dispatchEvent(new Event('change',{bubbles:true}))}
}
window.__v35images={prepare,isHeic,isAvif};
})();