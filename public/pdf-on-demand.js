'use strict';
/* 제출OK v3.8: load the PDF editor only on explicit use. All document bytes stay in the browser. */
(()=>{
  const tab=document.getElementById('tab-pdfwork'),panel=document.getElementById('pane-pdfwork'),status=document.getElementById('wb-status');
  if(!tab||!panel)return;
  const pdfRoute=/^\/(?:pdf-merge|pdf-split|pdf-compress|smart-submit)\/?$/.test(location.pathname);
  const requested=pdfRoute||new URLSearchParams(location.search).get('tool')==='pdfwork'||location.hash==='#pdfwork';
  let wanted=requested,loading=null,ready=false;
  const msg=(message,kind='info')=>{if(status){status.className='status '+kind;status.textContent=message}};
  const reveal=()=>{
    document.querySelectorAll('[data-tool]').forEach(b=>{b.classList.remove('active');b.setAttribute('aria-selected','false')});
    ['single','batch','pdf'].forEach(k=>{const p=document.getElementById('pane-'+k);if(p){p.hidden=true;p.classList.remove('active')}});
    panel.hidden=false;panel.classList.add('active');
    tab.classList.add('active');tab.setAttribute('aria-selected','true');
  };
  const loadScript=(src,check)=>new Promise((resolve,reject)=>{
    if(check())return resolve();
    const s=document.createElement('script');s.src=src;s.async=true;
    let done=false;
    const complete=(err)=>{
      if(done)return;done=true;clearTimeout(timer);
      s.onload=null;s.onerror=null;
      if(err){s.remove();reject(err)}else if(check())resolve();else reject(Error('PDF 라이브러리가 초기화되지 않았습니다.'));
    };
    const timer=setTimeout(()=>complete(Error('PDF 라이브러리 로딩 시간 초과')),20000);
    s.onload=()=>complete();
    s.onerror=()=>complete(Error('네트워크에서 PDF 라이브러리를 받지 못했습니다.'));
    document.head.appendChild(s);
  });
  async function requirePdfLib(){
    if(window.PDFLib?.PDFDocument)return;
    const mirrors=[
      '/vendor/pdf-lib.min.js',
      'https://cdnjs.cloudflare.com/ajax/libs/pdf-lib/1.17.1/pdf-lib.min.js',
      'https://cdn.jsdelivr.net/npm/pdf-lib@1.17.1/dist/pdf-lib.min.js'
    ];
    let last;
    for(const src of mirrors){
      try{await loadScript(src,()=>!!window.PDFLib?.PDFDocument);return}
      catch(e){last=e;if(window.PDFLib?.PDFDocument)return}
    }
    throw last||Error('PDF 편집 라이브러리를 불러오지 못했습니다.');
  }
  async function ensure(){
    if(ready&&window.__pdfwork?.activate)return;
    if(loading)return loading;
    tab.setAttribute('aria-busy','true');
    msg('PDF 편집기를 불러오는 중… 파일은 서버로 전송하지 않습니다.');
    loading=(async()=>{
      await requirePdfLib();
      await loadScript('/pdf-workbench.js',()=>!!window.__pdfwork?.activate);
      ready=true;
      msg('PDF 편집기가 준비됐습니다. 파일을 추가하세요.','success');
    })().catch(e=>{
      loading=null;
      msg((e.message||'PDF 편집기를 불러오지 못했습니다.')+' PDF 탭을 다시 누르면 재시도합니다.','error');
      tab.title='PDF 로딩 실패 — 다시 선택하여 재시도';
      throw e;
    }).finally(()=>tab.removeAttribute('aria-busy'));
    return loading;
  }
  function enter(){
    wanted=true;reveal();
    ensure().then(()=>{if(wanted)window.__pdfwork.activate()}).catch(()=>{});
  }
  tab.addEventListener('click',enter,{capture:true});
  document.querySelectorAll('[data-tool]').forEach(b=>b.addEventListener('click',()=>{wanted=false},{capture:true}));
  if(requested)enter();
  window.__jechulokPdfLoader={load:ensure,isReady:()=>ready};
})();