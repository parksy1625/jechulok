(()=>{try{const k="jechulok_analytics_optout",s=localStorage;if(s.getItem(k)!=="1"&&navigator.doNotTrack!=="1"&&location.hostname.endsWith(".vercel.app")){const a=document.createElement("script");a.defer=true;a.src="/_vercel/insights/script.js";document.head.append(a)}const names={single:"사진 규격",batch:"일괄 변환",pdf:"사진 PDF"},ids={"single-download":"single","batch-zip":"batch","pdf-download":"pdf"},store="jechulok_local_tools_v1";const read=()=>{try{return JSON.parse(s.getItem(store)||"{}")}catch(e){return{}}};const draw=()=>{const el=document.getElementById("my-usage");if(el){const a=Object.entries(read()).filter(([id,n])=>names[id]&&n>0).sort((a,b)=>b[1]-a[1]).slice(0,3);el.textContent=a.length?a.map(([id,n])=>names[id]+" "+n+"회").join(" · "):"아직 내 기기에 저장된 다운로드 기록이 없습니다."}};document.addEventListener("click",e=>{const b=e.target.closest?.("#single-download,#batch-zip,#pdf-download");if(!b||b.disabled||b.hidden||b.tagName==="A"&&!b.getAttribute("href"))return;const id=ids[b.id];if(!id)return;const u=read();u[id]=(u[id]||0)+1;s.setItem(store,JSON.stringify(u));draw()});document.querySelectorAll(".copy-page-url").forEach(b=>b.addEventListener("click",async()=>{const el=b.parentElement.querySelector(".copy-result");try{await navigator.clipboard.writeText(location.href);el.textContent="주소 복사 완료"}catch(e){el.textContent="주소창에서 복사해 주세요"}}));const o=document.getElementById("analytics-optout");if(o){o.checked=s.getItem(k)==="1";o.addEventListener("change",()=>{o.checked?s.setItem(k,"1"):s.removeItem(k);document.getElementById("optout-status").textContent="다음 방문부터 설정이 적용됩니다."})}draw()}catch(e){}})();
;(()=>{if(document.querySelector('script[data-jok-diag]'))return;const s=document.createElement('script');s.src='/diagnostics.js';s.dataset.jokDiag='1';s.defer=true;document.head.append(s)})();
/* v3.7 user experience */

;(()=>{'use strict';const $=id=>document.getElementById(id);
const output=$('single-preview'),original=$('single-thumb'),result=$('single-result');
if(output&&original&&result){
const view=document.createElement('section');view.className='v37-compare';view.hidden=true;
view.innerHTML='<div class="v37-head"><strong>원본과 변환 결과 비교</strong><small>자르기·크기 변경 시 위치가 달라질 수 있습니다.</small></div><div class="v37-frame"><img class="v37-after" alt="완성된 이미지"><img class="v37-before" alt="원본 이미지"><span class="v37-separator" aria-hidden="true"></span></div><label class="v37-slider">비교 위치 <input type="range" min="0" max="100" value="50" step="1" aria-label="원본과 결과 비교 위치"><output>50%</output></label>';
const checker=result.querySelector('.checker');(checker||result).after(view);
const a=view.querySelector('.v37-after'),b=view.querySelector('.v37-before'),r=view.querySelector('input'),n=view.querySelector('output'),line=view.querySelector('.v37-separator');
const move=()=>{const x=+r.value;b.style.clipPath='inset(0 '+(100-x)+'% 0 0)';line.style.left=x+'%';n.textContent=x+'%'};r.addEventListener('input',move);move();
const show=()=>{const ok=!result.hidden&&!!original.getAttribute('src')&&!!output.getAttribute('src');view.hidden=!ok;if(ok){if(a.src!==output.src)a.src=output.src;if(b.src!==original.src)b.src=original.src}};
const watch=new MutationObserver(show);for(const el of [output,original,result])watch.observe(el,{attributes:true,attributeFilter:['src','hidden']});show();}
const solutions=[
[/HEIC|HEIF|heic2any|디코더/i,'HEIC 디코더를 불러오지 못했을 수 있습니다. 인터넷 연결이나 브라우저 버전을 확인하세요.'],
[/AVIF|이미지.*지원|디코딩/i,'이미지 형식 지원을 확인하고, 최신 브라우저에서 다시 시도하세요.'],
[/용량|KB|MB|너무 작|초과/i,'최대 용량을 높이거나 JPG/WebP를 선택하고 출력 픽셀 크기를 줄여 보세요.'],
[/픽셀|해상도|8192|3000만/i,'원하는 가로·세로 크기와 원본 이미지 크기를 확인하세요.'],
[/암호|encrypted|password|서명/i,'암호화된 PDF나 서명된 문서는 편집이 제한될 수 있습니다. 원본 문서를 확인하세요.'],
[/PDF.*라이브러리|CDN|네트워크|연결 실패/i,'라이브러리 로딩이 막혔을 수 있습니다. 인터넷 연결과 콘텐츠 차단 설정을 확인하세요.'],
[/메모리|memory|out of/i,'파일을 나누어 처리하고 불필요한 브라우저 탭을 닫아 주세요.']];
for(const id of ['single-status','batch-status','pdf-status','wb-status']){
const target=$(id);if(!target)continue;const info=document.createElement('p');info.className='v37-help';info.hidden=true;target.after(info);
const update=()=>{const isError=target.classList.contains('error'),message=target.textContent||'';if(!isError||!message.trim()){info.hidden=true;return}const match=solutions.find(item=>item[0].test(message));info.textContent='해결 방법: '+(match?match[1]:'파일과 설정을 다시 확인해 주세요. 진단 도구에서 브라우저 지원 여부를 확인할 수 있습니다.');const a=document.createElement('a');a.href='/diagnostics/';a.textContent=' 브라우저 진단 →';info.append(a);info.hidden=false};new MutationObserver(update).observe(target,{childList:true,characterData:true,subtree:true,attributes:true,attributeFilter:['class']});update();}
const run=$('wb-run');if(run){const ctrl=document.createElement('div');ctrl.className='v37-work';ctrl.innerHTML='<div class="v37-bar" role="progressbar" aria-label="PDF 작업 진행 상태"><span></span></div><button type="button" class="btn btn-soft v37-stop" hidden>PDF 작업 취소</button><small class="v37-work-label" aria-live="polite"></small>';run.after(ctrl);
const stop=ctrl.querySelector('button'),bar=ctrl.querySelector('.v37-bar'),fill=bar.querySelector('span'),label=ctrl.querySelector('small'),status=$('wb-status');
const update=()=>{const busy=run.disabled;stop.hidden=!busy;bar.hidden=!busy;if(!busy){label.textContent='';fill.style.width='0%';stop.disabled=false;return}const message=status?.textContent||'PDF 처리 중';label.textContent=message;const m=message.match(/(\d+)\s*\/\s*(\d+)/);if(m&&+m[2]>0){bar.classList.remove('v37-indeterminate');fill.style.width=Math.min(100,Math.round(+m[1]/+m[2]*100))+'%'}else{bar.classList.add('v37-indeterminate');fill.style.width='32%'}};
stop.onclick=()=>{if(window.__pdfwork?.cancel?.()){stop.disabled=true;label.textContent='중단 요청됨 · 현재 단계 완료 후 취소합니다.'}};
const mo=new MutationObserver(update);mo.observe(run,{attributes:true,attributeFilter:['disabled']});if(status)mo.observe(status,{subtree:true,childList:true,characterData:true});update();}
for(const span of document.querySelectorAll('footer span'))if(span.textContent.includes('© 2026 제출OK · v3.'))span.textContent='© 2026 제출OK · v3.7';
const foot=document.querySelector('footer .footer-row');if(foot&&!foot.querySelector('a[href="/diagnostics/"]')){const a=document.createElement('a');a.href='/diagnostics/';a.textContent='오류 해결 · 기기 진단';foot.append(a);}
})();
