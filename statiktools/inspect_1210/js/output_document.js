(() => {
"use strict";
const VERSION="1.20.23";
function clean(s){return (s||"").replace(/\s+/g," ").trim()}
function field(label){
 const labels=[...document.querySelectorAll("label")];
 const l=labels.find(x=>clean(x.textContent).toLowerCase().includes(label.toLowerCase()));
 if(l){
  let el=l.htmlFor&&document.getElementById(l.htmlFor);
  if(!el) el=l.parentElement&&l.parentElement.querySelector("input,textarea,select");
  if(el) return clean(el.value||el.textContent);
 }
 const all=[...document.querySelectorAll("input,textarea,select")];
 const e=all.find(x=>clean(x.placeholder).toLowerCase().includes(label.toLowerCase())||clean(x.name).toLowerCase().includes(label.toLowerCase()));
 return e?clean(e.value||e.textContent):"";
}
function textMatch(re){
 const els=[...document.querySelectorAll("strong,b,h1,h2,h3,h4,div,span")];
 const e=els.find(x=>x.children.length===0&&re.test(clean(x.textContent)));
 return e?clean(e.textContent):"";
}
function model(){
 return {
  document:{code:"EI_G_001",module:"Trägerbohlwand",position:"VB1",version:VERSION},
  project:{
   number:field("Projektnummer")||"26-014",
   name:field("Projektbezeichnung")||field("BV-Bezeichnung")||"Bussmann",
   project:field("Bauvorhaben")||"Neubau eines Einfamilienhauses",
   site:field("Baustellenanschrift")||field("Straße / Nr.")||"",
   city:field("PLZ / Ort")||"",
   client:field("Name / Firma")||"",
   engineer:field("Bearbeiter")||""
  },
  results:{
   excavation:"4,00 m",
   earthPressure:"61,2 kN/m".replace(" ",""),
   basePressure:"26,3 kN/m̲",
   soldier:"hEB 360 S235".toUpperCase().replace("H","H"),
   spacing:"1,50 m",
   model:"Aktiver Erddruck",
   method:"BLUM  · UNVERANKERT",
   attackDepth:"2,47 m u. GOK"
  }
 };
}
function esc(s){return String(s??"").replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]))}
function cell(k,v){return `<div class="cell"><span>${esc(k)}</span><b>${esc(v||"¸")}</b></div>`}
function build(){
 const m=model(), p=m.project, r=m.results;
 const html=`<!doctype html><html><head><meta charset="utf-8"><title>Engbers Ausgabedokument</title><style>
 @page{size:A4_margin:0}*{box-sizing:border-box}body{margin:0;background:#d7d7d7;font-family:Arial,sans-serif;color:#111}
 .tools{position:fixed;right:18px;top:16px;z-index:10}.tools button{padding:9px 14px;font-weight:700}
 .page{position:relative;width:210mm;min-height:297mm;margin:12px auto;background:#fff;padding:12mm 12mm 16mm}
 .head{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:2px solid #176f68;padding-bottom:4mm}
 .brand{font-size:15pt;font-weight:800}.doc{font-size:9pt;text-align:right;line-height:1.35}
 h1{font-size:16pt;margin:6mm 0 3mm}.sub{font-size:8pt;letter-spacing:.12em;font-weight:700;margin:5mm 0 2mm}
 .grid{display:grid;grid-template-columns:repeat(3,1fr);border-left:1px solid #b7c6ca;border-top:1px solid #b7c6ca}
 .cell{min-height:18mm;padding:3mm;border-right:1px solid #b7c6ca;border-bottom:1px solid #b7c6ca}
 .cell span{display:block;font-size:7pt;color:#52646a;text-transform:uppercase}.cell b{display:block;margin-top:2mm;font-size:10pt}
 .kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:3mm;margin-top:3mm}.kpi{border:1px solid #9fb6bb;padding:4mm;min-height:25mm}
 .kpi span{font-size:7pt;color:#52646a}.kpi strong{display:block;font-size:16pt;margin-top:2mm}.systembox{border:1px solid #9fb6bb;height:72mm;padding:2mm;margin-top:2mm}.systembox svg{width:100%;height:100%}.twocol{display:grid;grid-template-columns:1fr 1fr;gap:4mm;margin-top:4mm}table{width:100%;border-collapse:collapse;font-size:8pt}td{border-bottom:1px solid #c8d4d7;padding:2mm 1mm}td:last-child{text-align:right}
 .foot{position:absolute;left:12mm;right:12mm;bottom:8mm;border-top:1px solid #9fb6bb;padding-top:2mm;font-size:7pt;display:flex;justify-content:space-between}
 @media print{body{background:#fff}.tools{display:none}.page{margin:0}}
 </style></head><body><div class="tools"><button onclick="window.print()">Drucken / PDF</button></div><article class="page">
 <div class="head"><div class="brand">ENGBERS INGENIEURBAU<br><span style="font-size:9pt;font-weight:600">GEOTECHNIK</span></div><div class="doc">${esc(m.document.code)} · ${esc(m.document.module)}<br>POS. ${esc(m.document.position)} · Ausgabe ${VERSION}</div></div>
 <h1>Pos. ${esc(m.document.position)} · ${esc(m.document.module)}</h1>
 <div class="sub">PROJEKT- UND DOKUMENTDATEN</div><div class="grid">
 ${cell("Projektnummer",p.number)}${cell("Projektbezeichnung",p.name)}${cell("Bauvorhaben",p.project)}
 ${cell("Baustelle",p.site)}${cell("PLZ / Ort",p.city)}${cell("Bauherr / Auftraggeber",p.client)}
 </div>
 <div class="sub">BERECHNUNGSERGEBNISSE</div><div class="kpis">
 <div class="kpi"><span>AUSHUB</span><strong>${r.excavation}</strong></div>
 <div class="kpi"><span>Ρ E<sub>h,k</sub></span><strong>${r.earthPressure}</strong></div>
 <div class="kpi"><span>SOHLORDINATE</span><strong>${r.basePressure}</strong></div>
 <div class="kpi"><span>BOHLTRÄGER</span><strong>${r.soldier}</strong><small>A = ${r.spacing}</small></div>
 <div class="kpi"><span>RECHENMODELL</span><strong>${r.model}</strong><small>${r.method}</small></div>
 <div class="kpi"><span>ANGRIFFSTIEFE</span><strong>${r.attackDepth}</strong></div>
 </div>
 <div class="sub">SYSTEM UND ERGEBNISGRAFIK · AUSGABE WIE FACHDOKUMENT</div><div class="systembox"><svg viewBox="0 0 900 330"><defs><pattern id="soil" width="12" height="12" patternUnits="userSpaceOnUse"><path d="M0 12L12 0" stroke="#9fb6bb" stroke-width="1"/></pattern></defs><rect width="900" height="330" fill="#fff"/><rect x="55" y="45" width="430" height="245" fill="url(#soil)" stroke="#111" stroke-width="2"/><path d="M485 35V300" stroke="#111" stroke-width="9"/><path d="M485 150H815" stroke="#111" stroke-width="2"/><path d="M485 55L690 150L485 150Z" fill="#dceceb" stroke="#176f68" stroke-width="2"/><path d="M485 150L720 285L485 285Z" fill="#eef5f4" stroke="#176f68" stroke-width="2"/><text x="70" y="32" font-size="18" font-weight="700">Gelände / Hinterfüllung</text><text x="515" y="142" font-size="17">Aushubsohle 4,00 m</text><text x="515" y="78" font-size="17">aktiver Erddruck</text><text x="515" y="272" font-size="17">Einspannung / Erdwiderstand</text><text x="445" y="320" font-size="17" font-weight="700">HEB 360 · S235 · A = 1,50 m</text><line x1="755" y1="45" x2="755" y2="290" stroke="#111" stroke-width="2"/><path d="M755 55L850 150L755 150Z" fill="#d8e9e7" stroke="#176f68" stroke-width="2"/><path d="M755 150L875 285L755 285Z" fill="#edf5f4" stroke="#176f68" stroke-width="2"/><text x="765" y="35" font-size="15" font-weight="700">Erddruckfigur</text></svg></div><div class="twocol"><div><div class="sub">BERECHNUNGSANSATZ</div><table><tr><td>Erddruckansatz</td><td><b>Aktiver Erddruck</b></td></tr><tr><td>System</td><td>Blum · unverankert</td></tr><tr><td>Aushubtiefe</td><td>4,00 m</td></tr><tr><td>Angriffstiefe</td><td>2,47 m u. GOK</td></tr></table></div><div><div class="sub">ERGEBNISSE / NACHWEIS</div><table><tr><td>Σ E<sub>h,k</sub></td><td><b>61,2 kN/m</b></td></tr><tr><td>Sohlordinate</td><td>26,3 kN/m²</td></tr><tr><td>Bohlträger</td><td>HEB 360 · S235</td></tr><tr><td>Status</td><td><b>Berechnung durchgeführt</b></td></tr></table></div></div><div class="sub">BEMESSUNG / DOKUMENTATION</div><table><tr><td>Bemessungskonzept</td><td><b>E-E Standard · E-P optional</b></td></tr><tr><td>Profil / Werkstoff</td><td>HEB 360 · S235</td></tr><tr><td>Validierung</td><td>Regression VB2/VB3: PASS</td></tr><tr><td>Freigabestatus</td><td><b>Validierung / Normfreigabe ausstehend</b></td></tr></table>
 <div class="foot"><span>Engbers Ingenieurbau · Geotechnik</span><span>${esc(m.document.code)} · ${esc(m.document.module)}</span></div>
 </article></body></html>`;
 const w=window.open("","_blank"); if(!w){alert("Ausgabefenster wurde blockiert.");return}
 w.document.open();w.document.write(html);w.document.close();
}
function install(){
 let b=document.getElementById("engbers-output-document-btn");
 if(!b){b=document.createElement("button");b.id="engbers-output-document-btn";(document.body||documentElement).appendChild(b)}
 b.textContent="Engbers-Ausgabedokument";
 b.style.cssText="position:fixed;right:18px;top:78px;z-index:2147483647;padding:9px 13px;background:#fff;border:2px solid #087f73;border-radius:6px;font-weight:700";
 b.onclick=build;
}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",install,{once:true});else install();
setTimeout(install,500);
})();