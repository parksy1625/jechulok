'use strict';(()=>{const $=id=>document.getElementById(id);if(!$('wb-run'))return;let docs=[],current=null,busy=false,objectUrl=null,cancelRequested=false;
const ensureActive=()=>{if(cancelRequested)throw Error('사용자가 PDF 작업을 취소했습니다.');};
const BYTES=1048576,show=(id,visible)=>$(id).hidden=!visible,report=(s,t='info')=>{$('wb-status').className='status '+t;$('wb-status').textContent=s},sz=n=>n>=BYTES?(n/BYTES).toFixed(2)+'MB':(n/1024).toFixed(1)+'KB';
const safe=n=>n.replace(/\.[^.]*$/,'').replace(/[\\/:*?"<>|\x00-\x1f]/g,'_').slice(0,60)||'document';
function pdf(){if(!window.PDFLib?.PDFDocument)throw Error('PDF 라이브러리 연결 실패: 인터넷/CDN 차단 설정을 확인해 주세요.');return window.PDFLib.PDFDocument}
function reset(){if(objectUrl)URL.revokeObjectURL(objectUrl);objectUrl=null;show('wb-empty',true);show('wb-result',false);$('wb-stage').textContent='대기'}
function activate(){for(const v of ['single','batch','pdf']){show('pane-'+v,false);$('pane-'+v).classList.remove('active')}show('pane-pdfwork',true);$('pane-pdfwork').classList.add('active');document.querySelectorAll('.tab').forEach(b=>{const active=b.id==='tab-pdfwork';b.classList.toggle('active',active);b.setAttribute('aria-selected',String(active))})}
document.querySelectorAll('[data-tool]').forEach(b=>b.addEventListener('click',()=>{show('pane-pdfwork',false);$('pane-pdfwork').classList.remove('active');$('tab-pdfwork').classList.remove('active')}));
$('tab-pdfwork').addEventListener('click',activate);
const route=location.pathname;if(['/pdf-merge/','/pdf-split/','/pdf-compress/','/smart-submit/'].includes(route)){activate();$('wb-mode').value=route==='/pdf-split/'?'extract':route==='/pdf-compress/'?'compress':route==='/smart-submit/'?'smart':'merge'}
function refresh(){const mode=$('wb-mode').value;show('wb-page-box',mode==='extract'||mode==='remove');show('wb-compress-box',mode==='compress');show('wb-quality-box',mode==='compress'&&$('wb-compress').value==='raster');show('wb-smart-box',mode==='smart')}
$('wb-mode').addEventListener('change',()=>{reset();refresh()});$('wb-compress').addEventListener('change',()=>{reset();refresh()});$('wb-quality').oninput=()=>{$('wb-quality-text').textContent=$('wb-quality').value+'%'};refresh();
function render(){closePagePreview();const area=$('wb-list');area.replaceChildren();$('wb-count').textContent='선택한 PDF '+docs.length+'개';docs.forEach((d,i)=>{const row=document.createElement('div');row.className='file-row';const label=document.createElement('div');label.className='details';const name=document.createElement('b');name.textContent=(i+1)+'. '+d.file.name;const desc=document.createElement('small');desc.textContent=sz(d.file.size)+' · '+d.pages+'페이지';label.append(name,desc);const acts=document.createElement('div');acts.className='actions';for(const [mark,next] of [['↑',i-1],['↓',i+1],['×',-1]]){const b=document.createElement('button');b.textContent=mark;b.disabled=busy||(next!==-1&&(next<0||next>=docs.length));b.addEventListener('click',()=>{if(next===-1)docs.splice(i,1);else [docs[i],docs[next]]=[docs[next],docs[i]];reset();render()});acts.append(b)}row.append(label,acts);area.append(row);addPagePreview(d,row,i,area)})}
$('wb-input').addEventListener('change',async e=>{if(busy)return;try{const additions=Array.from(e.target.files);if(docs.length+additions.length>10)throw Error('최대 10개까지 지원합니다.');if([...docs.map(x=>x.file),...additions].reduce((a,b)=>a+b.size,0)>120*BYTES)throw Error('전체 120MB를 초과합니다.');const list=[];for(const f of additions){if(!/\.pdf$/i.test(f.name)||f.size>50*BYTES||f.size<8)throw Error('PDF 확장자, 파일당 50MB 이내만 지원합니다.');const header=await f.slice(0,1024).text();if(!header.includes('%PDF-'))throw Error('PDF 파일 헤더가 올바르지 않습니다.');const doc=await pdf().load(await f.arrayBuffer(),{updateMetadata:false});list.push({file:f,pages:doc.getPageCount(),order:doc.getPageIndices()})}const pages=[...docs,...list].reduce((a,b)=>a+b.pages,0);if(pages>300)throw Error('총 페이지는 300페이지 이하여야 합니다.');docs.push(...list);render();reset();report('PDF 추가 완료','success')}catch(e){report(String(e.message||e),'error')}finally{e.target.value=''}});
$('wb-clear').onclick=()=>{if(busy)return;docs=[];reset();render()};
function pages(text,count){if(!text.trim())throw Error('페이지 범위를 입력하세요: 1,3-5');const s=new Set();for(const raw of text.split(',')){const match=raw.trim().match(/^(\d+)(?:\s*[-~]\s*(\d+))?$/);if(!match)throw Error('페이지 형식이 잘못됐습니다.');const a=+match[1],b=+(match[2]||match[1]);if(a<1||b>count||a>b)throw Error('페이지 범위가 문서 크기를 벗어납니다.');for(let i=a;i<=b;i++)s.add(i-1)}return [...s].sort((a,b)=>a-b)}
function parse(text){const s=text.normalize('NFKC').toLowerCase(),obj={merge:/합치|병합|묶|하나로/.test(s),removeFirst:0,keep:null,maxBytes:null};let m=s.match(/(?:첫|앞|처음)\s*(\d+)\s*페이지\s*(?:를\s*)?(?:제외|삭제|빼|제거)/);if(m)obj.removeFirst=+m[1];m=s.match(/(\d+)\s*[-~]\s*(\d+)\s*페이지\s*(?:만\s*)?(?:남기|추출|선택)/);if(m)obj.keep=[+m[1],+m[2]];const found=[...s.matchAll(/(\d+(?:\.\d+)?)\s*(mb|mib|메가바이트|kb|kib|킬로바이트)\s*(?:이하|이내|미만|까지)?/g)];if(found.length){const f=found.at(-1);obj.maxBytes=Math.floor(+f[1]*(f[2].startsWith('m')||f[2]==='메가바이트'?BYTES:1024));if(obj.maxBytes<=0||obj.maxBytes>120*BYTES)throw Error('허용 용량 범위를 확인하세요.')}if(obj.removeFirst&&obj.keep)throw Error('페이지 제외와 선택을 동시에 지정할 수 없습니다.');if(!obj.merge&&!obj.removeFirst&&!obj.keep&&obj.maxBytes===null)throw Error('지원하는 제출 조건을 찾지 못했습니다.');return obj}
function plan(){current=parse($('wb-instruction').value);const p=current;$('wb-plan').textContent=[p.merge?'✓ 여러 PDF 병합':'✓ 첫 번째 PDF 사용',p.removeFirst?'✓ 첫 '+p.removeFirst+'페이지 제외':p.keep?'✓ '+p.keep.join('~')+'페이지 추출':'✓ 페이지 유지',p.maxBytes!==null?'✓ '+sz(p.maxBytes)+' 이하 검증':'✓ 용량 제한 없음'].join('\n');return p}
$('wb-parse').onclick=()=>{try{plan();report('계획을 확인했습니다.','success')}catch(e){report(e.message,'error')}};
async function open(f){ensureActive();const d=await pdf().load(await f.arrayBuffer(),{updateMetadata:false});ensureActive();return d}
async function pick(src,ids){const out=await pdf().create();const chosen=await out.copyPages(src,ids);chosen.forEach(p=>out.addPage(p));return out}
async function join(list){const out=await pdf().create();let finished=0;for(const f of list){ensureActive();const d=await open(f.file),ids=f.order&&f.order.length===d.getPageCount()?f.order:d.getPageIndices();for(let i=0;i<ids.length;i+=24){ensureActive();const pieces=await out.copyPages(d,ids.slice(i,i+24));pieces.forEach(x=>out.addPage(x));finished+=pieces.length;report('병합 중 · '+finished+'페이지 처리');await new Promise(resolve=>setTimeout(resolve,0));}}return out}
async function pdfjs(){if(window.pdfjsLib)return window.pdfjsLib;await new Promise((ok,fail)=>{const s=document.createElement('script');s.src='/vendor/pdf.min.js';s.onload=ok;s.onerror=()=>{const b=document.createElement('script');b.src='https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js';b.onload=ok;b.onerror=()=>fail(Error('PDF 압축 라이브러리를 불러오지 못했습니다.'));document.head.append(b)};document.head.append(s)});return window.pdfjsLib}
async function raster(doc){const js=await pdfjs();js.GlobalWorkerOptions.workerSrc='/vendor/pdf.worker.min.js';const task=js.getDocument({data:new Uint8Array(await doc.save()),isEvalSupported:false});const view=await task.promise;try{if(view.numPages>60)throw Error('고압축은 60페이지 이하만 지원합니다.');const out=await pdf().create();for(let i=1;i<=view.numPages;i++){ensureActive();report('이미지 기반 압축 중 '+i+'/'+view.numPages);const page=await view.getPage(i),unit=page.getViewport({scale:1}),scale=Math.min(110/72,Math.sqrt(6000000/(unit.width*unit.height))),v=page.getViewport({scale}),c=document.createElement('canvas');c.width=Math.ceil(v.width);c.height=Math.ceil(v.height);const ctx=c.getContext('2d',{alpha:false});ctx.fillStyle='white';ctx.fillRect(0,0,c.width,c.height);try{await page.render({canvasContext:ctx,viewport:v}).promise;ensureActive();const blob=await new Promise((ok,fail)=>c.toBlob(b=>b?ok(b):fail(Error('페이지 JPG 생성 실패')),'image/jpeg',+$('wb-quality').value/100));const image=await out.embedJpg(await blob.arrayBuffer()),p=out.addPage([unit.width,unit.height]);p.drawImage(image,{x:0,y:0,width:unit.width,height:unit.height})}finally{c.width=c.height=0;page.cleanup()}}return out}finally{await view.destroy()}}
async function go(){if(busy)return;if(!docs.length){report('PDF 파일을 선택하세요.','error');return}busy=true;cancelRequested=false;$('wb-run').disabled=true;reset();$('wb-stage').textContent='처리 중';try{const mode=$('wb-mode').value,p=mode==='smart'?plan():null;if(mode!=='merge'&&mode!=='smart'&&docs.length!==1)throw Error('이 작업은 PDF 1개만 선택하세요.');if(mode==='merge'&&docs.length<2)throw Error('병합할 PDF를 2개 이상 선택하세요.');if(p&&docs.length>1&&!p.merge)throw Error('여러 PDF의 경우 병합 명령을 추가하세요.');let doc=mode==='merge'||p?.merge?await join(docs):await open(docs[0].file),original=docs.reduce((n,d)=>n+d.file.size,0),filename='제출OK_'+mode+'.pdf';ensureActive();if(mode!=='merge'&&!p?.merge&&docs[0]?.order?.some((v,i)=>v!==i))doc=await pick(doc,docs[0].order);if(mode==='extract'||mode==='remove'){const x=pages($('wb-pages').value,doc.getPageCount()),ids=mode==='extract'?x:doc.getPageIndices().filter(i=>!x.includes(i));if(!ids.length)throw Error('남는 페이지가 없습니다.');doc=await pick(doc,ids)}if(p?.removeFirst){if(p.removeFirst>=doc.getPageCount())throw Error('제외 페이지가 문서보다 많습니다.');doc=await pick(doc,doc.getPageIndices().slice(p.removeFirst))}if(p?.keep){const[a,b]=p.keep;if(a<1||a>b||b>doc.getPageCount())throw Error('페이지 범위 오류');doc=await pick(doc,doc.getPageIndices().slice(a-1,b))}if(mode==='split'){const entries=[];if(doc.getPageCount()>100)throw Error('분할은 최대 100페이지까지 지원합니다.');for(let i=0;i<doc.getPageCount();i++){ensureActive();report('분할 중 '+(i+1)+'/'+doc.getPageCount());await new Promise(r=>setTimeout(r,0));ensureActive();const part=await pick(doc,[i]);entries.push({name:safe(docs[0].file.name)+'_'+(i+1)+'.pdf',data:new Uint8Array(await part.save())})}ensureActive();const zip=window.__jechulok.zipFiles(entries);ensureActive();publish(zip,'제출OK_분할.zip',entries.length+'개 PDF 확인 · ZIP 다운로드','application/zip');return}
let bytes=new Uint8Array(await doc.save({useObjectStreams:true})),lossy=mode==='compress'&&$('wb-compress').value==='raster'||!!(p&&p.maxBytes!==null&&bytes.length>p.maxBytes&&$('wb-lossy-allow').checked);
ensureActive();if(lossy){doc=await raster(doc);ensureActive();bytes=new Uint8Array(await doc.save({useObjectStreams:true}))}
if(mode==='compress'&&!lossy&&bytes.length>=original){bytes=new Uint8Array(await docs[0].file.arrayBuffer());report('무손실 압축 효과가 없어 원본을 유지했습니다.')}
if(p && p.maxBytes!==null&&bytes.length>p.maxBytes)throw Error('결과 크기 '+sz(bytes.length)+' > 제출 제한 '+sz(p.maxBytes)+'. 제출 조건 미충족 — 다운로드 완료 처리하지 않았습니다.');
if(new TextDecoder('ascii').decode(bytes.slice(0,5))!=='%PDF-')throw Error('출력 PDF 헤더 오류');
ensureActive();const check=await pdf().load(bytes,{updateMetadata:false});ensureActive();if(check.getPageCount()!==doc.getPageCount())throw Error('페이지 수 검증 실패');
publish(new Blob([bytes],{type:'application/pdf'}),filename,check.getPageCount()+'페이지 검증 · '+sz(bytes.length)+(p?.maxBytes?' · 제한 '+sz(p.maxBytes)+' 충족':''),'application/pdf');
}catch(e){$('wb-stage').textContent=cancelRequested?'취소됨':'조건 미충족';report(String(e.message||e),'error')}finally{busy=false;cancelRequested=false;$('wb-run').disabled=false;render()}}
function publish(blob,name,info,type){reset();objectUrl=URL.createObjectURL(blob);$('wb-download').href=objectUrl;$('wb-download').download=name;$('wb-download').textContent=type==='application/zip'?'ZIP 다운로드 ↓':'검증된 PDF 다운로드 ↓';$('wb-result-name').textContent=name;$('wb-result-info').textContent=info;$('wb-checks').textContent='✓ 결과 파일 '+sz(blob.size);show('wb-result',true);show('wb-empty',false);$('wb-stage').textContent='완료';report('완성되었습니다.','success')}

let activePagePreview=null;
function closePagePreview(){if(!activePagePreview)return;const v=activePagePreview;activePagePreview=null;v.observer?.disconnect();v.cleanup?.();const result=v.doc?.destroy?.()||v.task?.destroy?.();if(result&&typeof result.catch==='function')result.catch(()=>{});}
function addPagePreview(item,row,idx,area){
item.order ||= Array.from({length:item.pages},(_,i)=>i);
const controls=row.querySelector('.actions'),button=document.createElement('button');button.type='button';button.textContent='▤ 미리보기·정렬';button.className='wb-preview-button';button.setAttribute('aria-expanded','false');controls.prepend(button);
const panel=document.createElement('section');panel.className='wb-thumbs';panel.hidden=true;area.append(panel);
button.onclick=async()=>{if(busy)return;if(!panel.hidden){closePagePreview();panel.hidden=true;panel.replaceChildren();button.setAttribute('aria-expanded','false');return}
closePagePreview();document.querySelectorAll('.wb-thumbs').forEach(x=>{x.hidden=true;x.replaceChildren()});document.querySelectorAll('.wb-preview-button').forEach(x=>x.setAttribute('aria-expanded','false'));panel.hidden=false;button.setAttribute('aria-expanded','true');panel.textContent='PDF 페이지를 준비하는 중…';
try{const js=await pdfjs();js.GlobalWorkerOptions.workerSrc='/vendor/pdf.worker.min.js';
const task=js.getDocument({data:new Uint8Array(await item.file.arrayBuffer()),isEvalSupported:false});const session={task,doc:null,observer:null};activePagePreview=session;
const pdfDoc=await task.promise;session.doc=pdfDoc;if(activePagePreview!==session)return;
let queue=Promise.resolve();
function draw(){
session.cleanup?.();session.observer?.disconnect();panel.replaceChildren();
const tip=document.createElement('p');tip.className='v33-page-tip';tip.textContent='휴대폰에서는 ↕ 손잡이를 끌어 순서를 변경하세요. ↑↓ 버튼 또는 키보드로도 이동할 수 있습니다. 화면에 보이는 페이지만 미리보기를 생성합니다.';
const grid=document.createElement('div');grid.className='v33-page-grid';panel.append(tip,grid);
let observer=null;
session.cleanup=()=>{observer?.disconnect();grid.querySelectorAll('canvas').forEach(c=>{c.width=0;c.height=0;c.remove()})};
function queueRender(tile,num){
  if(tile.dataset.rendering==='1'||tile.querySelector('canvas'))return;
  tile.dataset.rendering='1';
  queue=queue.then(async()=>{
    if(activePagePreview!==session||!tile.isConnected||tile.dataset.visible!=='1')return;
    const page=await pdfDoc.getPage(num+1),size=page.getViewport({scale:1});
    const scale=Math.min(.40,150/Math.max(size.width,size.height)),viewport=page.getViewport({scale}),c=document.createElement('canvas');
    c.width=Math.max(1,Math.ceil(viewport.width));c.height=Math.max(1,Math.ceil(viewport.height));
    const ctx=c.getContext('2d',{alpha:false});ctx.fillStyle='white';ctx.fillRect(0,0,c.width,c.height);
    try{
      await page.render({canvasContext:ctx,viewport}).promise;
      if(activePagePreview===session&&tile.isConnected&&tile.dataset.visible==='1')tile.prepend(c);
      else {c.width=0;c.height=0}
    }finally{page.cleanup()}
  }).catch(()=>{if(tile.isConnected&&tile.dataset.visible==='1'){const hint=document.createElement('small');hint.textContent='미리보기 불가';tile.prepend(hint)}})
  .finally(()=>{tile.dataset.rendering='0'});
}
function release(tile){
  tile.dataset.visible='0';
  const c=tile.querySelector('canvas');
  if(c){c.width=0;c.height=0;c.remove()}
}
observer=typeof IntersectionObserver==='function'?new IntersectionObserver(entries=>{
  for(const e of entries){
    if(e.isIntersecting){e.target.dataset.visible='1';queueRender(e.target,Number(e.target.dataset.page))}
    else release(e.target);
  }
},{rootMargin:'100px 0px'}):null;
session.observer=observer;
item.order.forEach((num,pos)=>{
  const tile=document.createElement('div');tile.className='v33-page-tile';tile.draggable=true;tile.dataset.page=String(num);
  tile.dataset.position=String(pos);tile.dataset.visible='0';tile.setAttribute('role','group');
  tile.setAttribute('aria-label','현재 '+(pos+1)+'번째, 원본 '+(num+1)+'페이지');
  const label=document.createElement('small');label.textContent=(pos+1)+'번째 · 원본 '+(num+1)+'쪽';
  const actions=document.createElement('div');actions.className='v33-page-actions';
  const grip=document.createElement('button');grip.type='button';grip.className='v34-touch-grip';
  grip.textContent='↕';grip.title='터치해서 원하는 위치로 이동';grip.setAttribute('aria-label',(pos+1)+'번째 페이지 위치 이동 손잡이');
  actions.append(grip);
  for(const [symbol,to] of [['↑',pos-1],['↓',pos+1]]){
    const b=document.createElement('button');b.type='button';b.textContent=symbol;b.disabled=to<0||to>=item.order.length;
    b.setAttribute('aria-label','페이지 '+(to<pos?'앞':'뒤')+'으로 이동');
    b.onclick=()=>reorder(pos,to);actions.append(b);
  }
  grip.addEventListener('keydown',e=>{
    if(e.key==='ArrowUp'||e.key==='ArrowDown'){e.preventDefault();reorder(pos,pos+(e.key==='ArrowUp'?-1:1))}
  });
  let selected=null;
  const clear=()=>{tile.classList.remove('v34-moving');grid.querySelectorAll('.v34-target').forEach(x=>x.classList.remove('v34-target'));selected=null};
  grip.addEventListener('pointerdown',e=>{
    if(busy||e.button!==0)return;
    e.preventDefault();selected=pos;tile.classList.add('v34-moving');
    try{grip.setPointerCapture(e.pointerId)}catch(err){}
  });
  grip.addEventListener('pointermove',e=>{
    if(selected===null)return;e.preventDefault();
    const hit=document.elementFromPoint(e.clientX,e.clientY)?.closest?.('.v33-page-tile');
    if(hit&&grid.contains(hit)){selected=Number(hit.dataset.position);
      grid.querySelectorAll('.v34-target').forEach(x=>x.classList.remove('v34-target'));hit.classList.add('v34-target')}
    if(e.clientY<55)window.scrollBy(0,-12);else if(e.clientY>window.innerHeight-55)window.scrollBy(0,12);
  });
  grip.addEventListener('pointerup',e=>{if(selected===null)return;e.preventDefault();const dest=selected;clear();reorder(pos,dest)});
  grip.addEventListener('pointercancel',clear);
  tile.addEventListener('dragstart',e=>{
    if(e.target===grip){e.preventDefault();return}
    e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain',String(pos));
  });
  tile.addEventListener('dragover',e=>e.preventDefault());
  tile.addEventListener('drop',e=>{
    e.preventDefault();const from=Number(e.dataTransfer.getData('text/plain'));
    if(Number.isInteger(from)&&from>=0&&from<item.order.length)reorder(from,pos)
  });
  tile.append(label,actions);grid.append(tile);
  if(observer)observer.observe(tile);else if(pos<12){tile.dataset.visible='1';queueRender(tile,num)}
});
}
function reorder(from,to){if(busy||to<0||to>=item.order.length||from===to)return;item.order.splice(to,0,item.order.splice(from,1)[0]);reset();draw();const focusTarget=panel.querySelectorAll('.v34-touch-grip')[to];if(focusTarget&&document.activeElement?.classList?.contains('v34-touch-grip'))focusTarget.focus();report('변경한 페이지 순서가 출력 PDF에 적용됩니다.','success')}
draw();
}catch(e){panel.textContent='미리보기 실패: '+(e.message||e)}}}

$('wb-run').onclick=go;window.__pdfwork={parse,pages,go,activate,cancel:()=>{if(!busy)return false;cancelRequested=true;report('취소 요청을 받았습니다. 현재 단계 완료 후 중단합니다.');return true;}};render();window.addEventListener('beforeunload',reset);
})();