
window.Engbers = window.Engbers || {};
Engbers.modules = Engbers.modules || {};
Engbers.registerModule=function(m){Engbers.modules[m.id]=m;};
Engbers.escape=function(s){return String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));};
Engbers.setStatus=function(s){const e=document.getElementById("statusText");if(e)e.textContent=s;};
Engbers.ribbonMap={
 projekt:[
  ["Projekt", [["Projektstammdaten","action","project-data"],["Projektlasten","module","loads"],["Neues Projekt","action","new-project"]]],
  ["Datei", [["Projekt exportieren","action","export-project"],["PDF öffnen","module","documents"],["Nach Update suchen","action","check-update"]]]
 ],
 holzbau:[["Holzbau", [["Holzstütze · folgt","disabled",""],["Holzbalken · folgt","disabled",""],["Auflagerpressung · folgt","disabled",""]]]],
 stahlbau:[["Stahlbau", [["Querschnittsbibliothek","module","steel_library"],["Stahlträger · folgt","disabled",""],["Fußplatte · folgt","disabled",""],["Schweißnähte · folgt","disabled",""],["Schrauben · folgt","disabled",""]]]],
 massivbau:[["Massivbau", [["Fundament","module","foundation"],["Durchstanzen · folgt","disabled",""],["Lasteinleitung · folgt","disabled",""]]]],
 geotechnik:[["Baugruben / Verbau", [["Trägerbohlwand","module","retaining_wall"],["Spundwand · folgt","disabled",""],["Unterfangung · folgt","disabled",""]]],
              ["Geotechnik", [["Fundament / Grundbruch · folgt","disabled",""],["Setzung · folgt","disabled",""]]]],
 verbindungen:[["Verbindungen", [["Eigene Verbindungsnachweise · folgen","disabled",""]]]],
 hersteller:[["Simpson Strong-Tie", [["CMR / CMS Stützenfuß","module","cmr_cms"],["E20/3 Winkelverbinder","sst","E203"],["AG922 Winkelverbinder","sst","AG922"],["ABR9020 Winkelverbinder","sst","ABR9020"],["AJ99416 Winkelverbinder","sst","AJ"],["HTT5 Zuganker","sst","HTT"],["BSNN80/150 Balkenschuh","sst","BSNN"]]],
             ["Weitere Hersteller", [["Herstellerbibliothek wird erweitert","disabled",""]]]],
 dokumente:[["Dokumente", [["PDF öffnen","module","documents"],["Projektstammdaten","action","project-data"]]]],
 ausgabe:[["Ausgabe", [["Aktive Position PDF","action","print"],["Sammelausgabe · vorbereitet","action","print-project"]]]]
};
Engbers.activeModuleId=Engbers.activeModuleId||"";
Engbers.activePositionId=Engbers.activePositionId||"";
Engbers.moduleRibbon={retaining_wall:"geotechnik",foundation:"massivbau",steel_library:"stahlbau",loads:"projekt",documents:"dokumente",cmr_cms:"hersteller"};
Engbers.moduleLabels={retaining_wall:"Trägerbohlwand",foundation:"Fundament",steel_library:"Querschnittsbibliothek",loads:"Projektlasten",documents:"Dokumente",cmr_cms:"CMR / CMS Stützenfuß"};
Engbers.syncNavigationState=function(){
  const tree=document.getElementById("projectTree");
  if(!tree)return;
  tree.querySelectorAll(".nav-active,.nav-position-active").forEach(el=>{
    el.classList.remove("nav-active","nav-position-active");
    el.removeAttribute("aria-current");
  });
  if(Engbers.activeModuleId){
    tree.querySelectorAll(`[data-module="${Engbers.activeModuleId}"]`).forEach(el=>{el.classList.add("nav-active");el.setAttribute("aria-current","page");});
    const label=Engbers.moduleLabels[Engbers.activeModuleId];
    if(label){
      tree.querySelectorAll("button,a,[role=button],div,span").forEach(el=>{
        if(el.closest(".nav-active"))return;
        const own=(el.childElementCount===0||el.matches("button,a,[role=button]"));
        if(own&&String(el.textContent||"").trim()===label){el.classList.add("nav-active");el.setAttribute("aria-current","page");}
      });
    }
  }
  if(Engbers.activePositionId){
    tree.querySelectorAll(`[data-position="${Engbers.activePositionId}"]`).forEach(el=>{el.classList.add("nav-position-active");el.setAttribute("aria-current","page");});
  }
};
Engbers.renderRibbon=function(key){
  const box=document.getElementById("ribbon");box.innerHTML="";
  (Engbers.ribbonMap[key]||[]).forEach(([title,items])=>{
    const g=document.createElement("div");g.className="ribbon-group";
    items.forEach(([label,type,id])=>{
      const b=document.createElement("button");b.textContent=label;
      if(type==="disabled"){b.disabled=true;}
      else if(type==="sst"){b.dataset.sst=id;b.onclick=()=>Engbers.openSimpson(id);}
      else if(type==="module"){b.dataset.module=id;b.onclick=()=>Engbers.openModule(id);}
      else{b.dataset.action=id;b.onclick=()=>Engbers.action(id);}
      if(type==="module"&&id===Engbers.activeModuleId)b.classList.add("active-module");
      g.appendChild(b);
    });
    const t=document.createElement("span");t.className="ribbon-group-title";t.textContent=title;g.appendChild(t);box.appendChild(g);
  });
};
Engbers.setActiveModuleChrome=function(id){
  Engbers.activeModuleId=id||"";
  const key=Engbers.moduleRibbon[id];
  if(key){
    document.querySelectorAll("#ribbonTabs button").forEach(x=>x.classList.toggle("active",x.dataset.ribbon===key));
    Engbers.renderRibbon(key);
  }else{
    document.querySelectorAll("#ribbon [data-module]").forEach(x=>x.classList.toggle("active-module",x.dataset.module===id));
  }
  Engbers.syncNavigationState();
  requestAnimationFrame(()=>Engbers.syncNavigationState());
};

Engbers.searchCatalog=[
 {type:"module",title:"CMR / CMS Stützenfuß",maker:"Simpson Strong-Tie",material:"Holzbau Stahl Holz Stützenfuß Verbindung",module:"cmr_cms",keywords:"cmr cms stützenfuss stützenfuß pfostenträger post base simpson"},
 {type:"sst",title:"E20/3 Winkelverbinder",maker:"Simpson Strong-Tie",material:"Holz Holz Beton Winkel Verbindung",key:"E203",keywords:"e20 winkel winkelverbinder simpson"},
 {type:"sst",title:"AG922 Winkelverbinder",maker:"Simpson Strong-Tie",material:"Holz Beton Winkel Verbindung",key:"AG922",keywords:"ag922 winkel winkelverbinder simpson"},
 {type:"sst",title:"ABR9020 Winkelverbinder",maker:"Simpson Strong-Tie",material:"Holz Winkel Verbindung",key:"ABR9020",keywords:"abr9020 winkel simpson"},
 {type:"sst",title:"AJ99416 Winkelverbinder",maker:"Simpson Strong-Tie",material:"Holz Winkel Verbindung",key:"AJ",keywords:"aj aj99416 winkel simpson"},
 {type:"sst",title:"HTT5 Zuganker",maker:"Simpson Strong-Tie",material:"Holz Beton Zuganker Verbindung",key:"HTT",keywords:"htt htt5 zuganker hold down simpson"},
 {type:"sst",title:"BSNN80/150 Balkenschuh",maker:"Simpson Strong-Tie",material:"Holz Beton Balkenschuh Verbindung",key:"BSNN",keywords:"bsnn balkenschuh simpson"},
 {type:"module",title:"Fundament",maker:"Engbers",material:"Massivbau Beton Stahlbeton Gründung",module:"foundation",keywords:"fundament gründung beton"},
 {type:"module",title:"Stahlquerschnittsbibliothek",maker:"Engbers",material:"Stahlbau Profile HEA HEB HEM IPE IPN UPN",module:"steel_library",keywords:"stahl profil profile querschnitt hea heb hem ipe ipn upn bibliothek"},
 {type:"module",title:"Trägerbohlwand",maker:"Engbers",material:"Geotechnik Verbau Baugrube Stahl HEB Holzbohlen",module:"retaining_wall",keywords:"trägerbohlwand traegerbohlwand verbau baugrube geotechnik heb holzbohlen erddruck"},
 {type:"module",title:"Projektlasten",maker:"Engbers",material:"Lastfluss Einwirkungen",module:"loads",keywords:"lasten lastfluss g q schnee wind"},
 {type:"module",title:"Dokumente / PDF",maker:"Engbers",material:"Dokument PDF",module:"documents",keywords:"pdf dokument unterlage"}
];
Engbers.normalizeSearch=function(s){return String(s||"").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g,"").replace(/ß/g,"ss");};
Engbers.searchAll=function(q){
  const term=Engbers.normalizeSearch(q).trim(); if(!term)return [];
  const words=term.split(/\s+/).filter(Boolean), hits=[];
  Engbers.projects.forEach(p=>{
    const pd=Object.values(p.data||{}).join(" ");
    const hay=Engbers.normalizeSearch(`${p.no} ${p.name} ${pd} projekt bauvorhaben bauherr architekt`);
    if(words.every(w=>hay.includes(w)))hits.push({type:"project",title:(p.no?p.no+" · ":"")+p.name,meta:"Projekt",projectId:p.id,score:1});
    Object.values(p.positions||{}).forEach(pos=>{
      const hayp=Engbers.normalizeSearch(`${pos.pos} ${pos.title} ${pos.moduleId} ${pos.preNote||""} ${pos.postNote||""} position`);
      if(words.every(w=>hayp.includes(w)))hits.push({type:"position",title:`${pos.pos||"—"} · ${pos.title||pos.moduleId}`,meta:`Position · ${(p.no?p.no+" · ":"")+p.name}`,projectId:p.id,positionId:pos.id,score:2});
    });
  });
  Engbers.searchCatalog.forEach(x=>{
    const hay=Engbers.normalizeSearch(`${x.title} ${x.maker} ${x.material} ${x.key||""} ${x.keywords||""} modul programm hersteller`);
    if(words.every(w=>hay.includes(w)))hits.push({...x,meta:`Programm · ${x.maker}${x.material?" · "+x.material:""}`,score:3});
  });
  return hits.sort((a,b)=>b.score-a.score || a.title.localeCompare(b.title)).slice(0,24);
};
Engbers.renderSearch=function(){
  const input=document.getElementById("globalSearch"),box=document.getElementById("searchResults"); if(!input||!box)return;
  const hits=Engbers.searchAll(input.value); box.innerHTML="";
  if(!input.value.trim()){box.classList.remove("open");return;}
  if(!hits.length){box.innerHTML='<div class="search-hit"><div class="search-hit-title">Keine Treffer</div><div class="search-hit-meta">Anderen Suchbegriff versuchen</div></div>';box.classList.add("open");return;}
  hits.forEach((x,i)=>{
    const d=document.createElement("div");d.className="search-hit";d.dataset.searchIndex=i;
    d.innerHTML=`<div class="search-hit-title">${Engbers.escape(x.title)}</div><div class="search-hit-meta">${Engbers.escape(x.meta||"")}</div>`;
    d.onclick=()=>Engbers.openSearchHit(x);box.appendChild(d);
  });
  box.classList.add("open");box._hits=hits;
};
Engbers.openSearchHit=function(x){
  if(x.projectId){Engbers.activeProjectId=x.projectId;Engbers.refreshProjectSelect();Engbers.renderProjectTree();}
  if(x.type==="project")Engbers.openProjectData();
  else if(x.type==="position")Engbers.openPosition(x.positionId);
  else if(x.type==="sst")Engbers.openSimpson(x.key);
  else if(x.type==="module")Engbers.openModule(x.module);
  document.getElementById("searchResults")?.classList.remove("open");
  const input=document.getElementById("globalSearch");if(input)input.value="";
  Engbers.setStatus("Suchtreffer geöffnet: "+x.title);
};

Engbers.action=function(a){
  if(a==="new-project")Engbers.newProject();
  else if(a==="project-data")Engbers.openProjectData();
  else if(a==="export-project")Engbers.exportProject();
  else if(a==="print")Engbers.printCurrent();
  else if(a==="print-project")Engbers.printProjectInfo();
  else if(a==="check-update")Engbers.checkForUpdates?.();
};
Engbers.openModule=function(id){
  Engbers.activePositionId="";
  Engbers.setActiveModuleChrome(id);
  if(id==="loads")return Engbers.openLoads();
  if(id==="documents")return Engbers.openDocuments();
  if(id==="foundation")return Engbers.openFoundation();
  if(id==="cmr_cms")return Engbers.openCMRCMS();
  if(id==="retaining_wall")return Engbers.openRetainingWall();
  Engbers.modules[id]?.open?.();
};
Engbers.openPosition=function(id){
  const p=Engbers.activeProject(),pos=p?.positions?.[id];if(!pos)return;
  Engbers.activePositionId=id;
  Engbers.setActiveModuleChrome(pos.moduleId);
  Engbers.syncNavigationState();
  if(pos.moduleId==="cmr_cms")return Engbers.openCMRCMS(id);
  if(pos.moduleId==="retaining_wall")return Engbers.openRetainingWall(id);
  if(pos.moduleId?.startsWith("sst:"))Engbers.openSimpson(pos.key,id);
};
Engbers.init=function(){
  Engbers.projects=Engbers.storage.getProjects()||[];
  Engbers.ensureProject();Engbers.refreshProjectSelect();Engbers.renderProjectTree();Engbers.renderRibbon("projekt");Engbers.openProjectData();
  const tree=document.getElementById("projectTree");
  if(tree&&window.MutationObserver){
    new MutationObserver(()=>Engbers.syncNavigationState()).observe(tree,{childList:true,subtree:true});
  }
  Engbers.syncNavigationState();
  document.getElementById("projectSelect").onchange=e=>{Engbers.activeProjectId=e.target.value;Engbers.renderProjectTree();Engbers.openProjectData();};
  document.getElementById("projectImport").onchange=e=>e.target.files[0]&&Engbers.importProjectFile(e.target.files[0]);
  const search=document.getElementById("globalSearch");
  if(search){
    search.addEventListener("input",Engbers.renderSearch);
    search.addEventListener("keydown",e=>{
      if(e.key==="Escape"){document.getElementById("searchResults").classList.remove("open");search.blur();}
      if(e.key==="Enter"){
        const hits=Engbers.searchAll(search.value);if(hits[0]){e.preventDefault();Engbers.openSearchHit(hits[0]);}
      }
    });
  }
  document.addEventListener("click",e=>{if(!e.target.closest(".global-search"))document.getElementById("searchResults")?.classList.remove("open");});
  document.getElementById("ribbonTabs").onclick=e=>{
    const b=e.target.closest("button[data-ribbon]");if(!b)return;
    document.querySelectorAll("#ribbonTabs button").forEach(x=>x.classList.remove("active"));b.classList.add("active");Engbers.renderRibbon(b.dataset.ribbon);
  };
  document.body.addEventListener("click",e=>{
    const a=e.target.closest("[data-action]");if(a && !a.closest("#ribbon"))Engbers.action(a.dataset.action);
    const m=e.target.closest("[data-module]");if(m && !m.closest("#ribbon"))Engbers.openModule(m.dataset.module);
    const pi=e.target.closest("[data-position]");if(pi)Engbers.openPosition(pi.dataset.position);
    const si=e.target.closest("[data-sst]");if(si)Engbers.openSimpson(si.dataset.sst);
    if(e.target.closest("[data-projectdata]"))Engbers.openProjectData();
  });
  Engbers.setStatus("Desktop-Oberfläche 1.7.74 geladen");
  Engbers.startUpdateHeartbeat?.();
  if(new URLSearchParams(location.search).get("selftest")==="1"){
    const results=[];
    try{
      Engbers.openModule("cmr_cms");
      results.push(["cmr-open",!!document.querySelector("[data-active-module=cmr]")]);
      results.push(["pre-note",!!document.getElementById("cmrPre")]);
      results.push(["post-note",!!document.getElementById("cmrPost")]);
      results.push(["calc-status",!!document.getElementById("cmrStatus")?.textContent]);
      Engbers.openSimpson("HTT");
      results.push(["htt-open",!!document.querySelector("[data-key=HTT]")]);
      results.push(["search-cmr",Engbers.searchAll("simpson stützenfuß").some(x=>x.module==="cmr_cms")]);
      results.push(["search-project",Engbers.searchAll("26-022").some(x=>x.type==="project")]);
      Engbers.renderProjectTree();
      results.push(["simpson-folder",document.getElementById("projectTree").textContent.includes("Simpson Strong-Tie")]);
      Engbers.openModule("retaining_wall");
      results.push(["retaining-open",!!document.querySelector("[data-active-module=retaining_wall]")]);
      results.push(["retaining-graphic",!!document.getElementById("rwGraphic")?.querySelector("svg")]);
      results.push(["search-retaining",Engbers.searchAll("trägerbohlwand").some(x=>x.module==="retaining_wall")]);
    }catch(e){results.push(["exception",false,String(e)]);}
    const ok=results.every(r=>r[1]);
    document.body.setAttribute("data-selftest",ok?"OK":"FAIL");
    document.body.setAttribute("data-selftest-detail",JSON.stringify(results));
  }
};
document.addEventListener("DOMContentLoaded",Engbers.init);
