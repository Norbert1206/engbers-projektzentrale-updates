(function(){
  const E=window.Engbers=window.Engbers||{};
  const esc=s=>String(s??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  function cssLinks(){
    return Array.from(document.querySelectorAll('link[rel="stylesheet"]')).map(l=>`<link rel="stylesheet" href="${esc(l.getAttribute('href'))}">`).join('');
  }
  function cloneHtml(n){ return n ? n.outerHTML : ''; }
  function buildPrintDocument(){
    const q=s=>document.querySelector(s), edge=q('.rw-sheet-edgebrand');
    const groups=[
      [q('.rw-output-head'),q('.rw-project-output-head'),q('#rwOutputHeroMetrics'),q('[data-proof-page="01"]')],
      [q('[data-sheet="02"]')],
      [q('[data-proof-page="03"]')],
      [q('[data-proof-page="04"]')],
      [q('[data-proof-page="05"]')],
      [q('[data-sheet="06"]')],
      [q('[data-proof-page="07"]')],
      [q('[data-proof-page="08"]')]
    ].filter(g=>g.some(Boolean));
    const pages=groups.map((g,i)=>{
      const content=g.filter(Boolean).map(cloneHtml).join('\n');
      const brand=edge?cloneHtml(edge.cloneNode(true)):'';
      return `<section class="eng-pdf-page" data-pdf-page="${i+1}"><div class="eng-pdf-scale"><main class="paper gt-modern-shell pdf-vector-page">${brand}${content}</main></div></section>`;
    }).join('\n');
    return `<!doctype html><html><head><meta charset="utf-8">${cssLinks()}<style>
      @page{size:A4 portrait;margin:0}
      *{-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}
      html,body{margin:0!important;padding:0!important;background:#fff!important}
      body.rw-output-preview{background:#fff!important;overflow:visible!important;width:auto!important;min-width:0!important}
      .eng-pdf-page{position:relative!important;box-sizing:border-box!important;width:210mm!important;height:297mm!important;margin:0!important;padding:5mm 4mm!important;overflow:hidden!important;background:#fff!important;break-after:page!important;page-break-after:always!important}
      .eng-pdf-page:last-child{break-after:auto!important;page-break-after:auto!important}
      .eng-pdf-scale{position:relative!important;width:202mm!important;height:287mm!important;overflow:visible!important}
      body.rw-output-preview main.paper.gt-modern-shell.pdf-vector-page{position:relative!important;box-sizing:border-box!important;width:100%!important;min-width:0!important;max-width:none!important;margin:0!important;padding:0 0 0 9mm!important;background:#fff!important;box-shadow:none!important;transform:none!important;overflow:visible!important}
      body.rw-output-preview main.paper.gt-modern-shell.pdf-vector-page>*{width:100%!important;max-width:100%!important;box-sizing:border-box!important}
      body.rw-output-preview main.paper.gt-modern-shell.pdf-vector-page svg{width:100%!important;max-width:100%!important;height:auto!important;display:block!important}
      body.rw-output-preview main.paper.gt-modern-shell.pdf-vector-page table{max-width:100%!important}
      body.rw-output-preview tr{break-inside:avoid!important;page-break-inside:avoid!important}
      body.rw-output-preview .rw-sheet-edgebrand{display:flex!important;position:absolute!important;left:20px!important;right:auto!important;top:auto!important;bottom:96px!important;writing-mode:horizontal-tb!important;text-orientation:mixed!important;flex-direction:row!important;align-items:center!important;gap:8px!important;width:max-content!important;height:auto!important;transform:rotate(-90deg)!important;transform-origin:left bottom!important;z-index:999!important;visibility:visible!important;opacity:1!important}
      body.rw-output-preview .rw-proof-page,body.rw-output-preview [data-sheet]{box-shadow:none!important}
      .rw-output-exit,.toolbarline,.topbar,.nav,.module-tabs,.eng-devbar,.dochead{display:none!important}
    </style></head><body class="rw-output-preview">${pages}</body></html>`;
  }
  async function ensureOutput(){
    if(document.body.classList.contains('rw-output-preview')) return false;
    const b=document.getElementById('rwOutputPreview');
    if(!b) throw new Error('Ausgabeansicht der aktiven Position wurde nicht gefunden.');
    b.click(); await new Promise(r=>setTimeout(r,160)); return true;
  }
  E.printCurrent=async function(){
    let revert=false;
    try{
      revert=await ensureOutput();
      const html=buildPrintDocument();
      const pageCount=(html.match(/class="eng-pdf-page"/g)||[]).length;
      if(pageCount<3) throw new Error('Fachblätter konnten nicht vollständig zusammengestellt werden.');
      const pos=(document.getElementById('rwPosNo')?.value||'Position').trim();
      const res=await fetch('http://127.0.0.1:18765/pdf',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({filename:`EI_G_001_${pos}.pdf`,html})});
      const data=await res.json(); if(!res.ok||!data.ok) throw new Error(data.error||'PDF-Erzeugung fehlgeschlagen.');
    }catch(e){ alert('PDF-Ausgabe konnte nicht erstellt werden.\n\n'+e.message); }
    finally{ if(revert) document.getElementById('rwOutputPreview')?.click(); }
  };
})();
