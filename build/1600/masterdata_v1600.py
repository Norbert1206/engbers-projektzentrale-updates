from pathlib import Path
import os, re, json, threading, queue
import tkinter as tk
from tkinter import ttk, messagebox

FIELDS=[
 ('project_title','Bauvorhaben · Bezeichnung'),('project_street','Bauvorhaben · Straße'),('project_zip','Bauvorhaben · PLZ'),('project_city','Bauvorhaben · Ort'),
 ('client_name','Bauherr · Name'),('client_street','Bauherr · Straße'),('client_zip','Bauherr · PLZ'),('client_city','Bauherr · Ort'),('client_phone','Bauherr · Telefon'),('client_email','Bauherr · E-Mail'),
 ('architect_name','Architekt · Name'),('architect_firm','Architekt · Büro'),('architect_street','Architekt · Straße'),('architect_zip','Architekt · PLZ'),('architect_city','Architekt · Ort'),('architect_phone','Architekt · Telefon'),('architect_email','Architekt · E-Mail'),
 ('engineer_name','Tragwerksplanung · Name'),('engineer_firm','Tragwerksplanung · Büro'),('engineer_street','Tragwerksplanung · Straße'),('engineer_zip','Tragwerksplanung · PLZ'),('engineer_city','Tragwerksplanung · Ort'),('engineer_phone','Tragwerksplanung · Telefon'),('engineer_email','Tragwerksplanung · E-Mail')]

def _env(app):
    g=app.project_row.__globals__
    return g['db'],g['now_iso'],g.get('BG','#f3f1e9'),g.get('PANEL','#faf9f5'),g.get('INK','#181818'),g.get('MUTED','#77736b'),g.get('ACCENT','#b08b49'),g.get('DARK','#202020')

def _schema(db):
    con=db(); c=con.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS project_masterdata(project_id INTEGER PRIMARY KEY,project_title TEXT DEFAULT '',project_street TEXT DEFAULT '',project_zip TEXT DEFAULT '',project_city TEXT DEFAULT '',client_name TEXT DEFAULT '',client_street TEXT DEFAULT '',client_zip TEXT DEFAULT '',client_city TEXT DEFAULT '',client_phone TEXT DEFAULT '',client_email TEXT DEFAULT '',architect_name TEXT DEFAULT '',architect_firm TEXT DEFAULT '',architect_street TEXT DEFAULT '',architect_zip TEXT DEFAULT '',architect_city TEXT DEFAULT '',architect_phone TEXT DEFAULT '',architect_email TEXT DEFAULT '',engineer_name TEXT DEFAULT '',engineer_firm TEXT DEFAULT '',engineer_street TEXT DEFAULT '',engineer_zip TEXT DEFAULT '',engineer_city TEXT DEFAULT '',engineer_phone TEXT DEFAULT '',engineer_email TEXT DEFAULT '',source_files TEXT DEFAULT '',updated_at TEXT DEFAULT '')''')
    c.execute('''CREATE TABLE IF NOT EXISTS office_profile(id INTEGER PRIMARY KEY CHECK(id=1),name TEXT DEFAULT '',firm TEXT DEFAULT '',street TEXT DEFAULT '',zip TEXT DEFAULT '',city TEXT DEFAULT '',phone TEXT DEFAULT '',email TEXT DEFAULT '')''')
    c.execute("INSERT OR IGNORE INTO office_profile VALUES(1,'Dipl.-Ing. Norbert Engbers','Engbers Ingenieurbau','Kiesbahn 6','49809','Lingen','0591-16246105','info@engbers-ingenieurbau.de')")
    c.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','4')")
    con.commit(); con.close()

def _pdf_text(path,max_pages=6):
    text=''; Reader=None
    try: from pypdf import PdfReader as Reader
    except Exception:
        try: from PyPDF2 import PdfReader as Reader
        except Exception: pass
    if Reader:
        try:
            r=Reader(str(path),strict=False); text='\n'.join((p.extract_text() or '') for p in list(r.pages)[:max_pages])
        except Exception: text=''
    if not text.strip():
        try:
            import fitz
            d=fitz.open(str(path)); parts=[]
            for i in range(min(len(d),max_pages)):
                b=sorted(d[i].get_text('blocks') or [],key=lambda x:(round(float(x[1])/10),float(x[0])))
                parts.append('\n'.join(str(x[4]) for x in b if len(x)>4 and str(x[4]).strip()))
            d.close(); text='\n'.join(parts)
        except Exception: pass
    return text

def _score(p,root):
    try: rel=str(p.relative_to(root)).lower().replace('\\','/')
    except Exception: rel=str(p).lower().replace('\\','/')
    n=p.name.lower(); s=8; why=[]
    for word,pts in [('grundrisse',50),('grundriss',48),('ansichten',46),('ansicht',44),('schnitte',42),('schnitt',40),('ausführungsplan',36),('ausfuehrungsplan',36),('bauantrag',50),('genehmigungsplan',46),('entwurf',25),('werkplan',28),('eingabeplan',30),('lageplan',18)]:
        if word in n: s+=pts; why.append(word)
    if 'architekt' in rel: s+=45; why.append('Architekt-Ordner')
    if 'pläne architekten' in rel or 'plaene architekten' in rel: s+=35; why.append('Architektenpläne')
    elif '/pläne/' in rel or '/plaene/' in rel: s+=16; why.append('Pläne')
    if 'statik pdf' in rel: s-=35
    if 'wärmeschutz' in rel or 'waermeschutz' in rel or 'bescheinigung' in rel: s-=25
    return s,', '.join(why[:4])

def _parse(text):
    lines=[]
    for x in (text or '').replace('\r','\n').replace('\xa0',' ').split('\n'):
        x=re.sub(r'\s+',' ',x).strip(' \t|;')
        if x and x not in lines[-3:]: lines.append(x)
    labels={'client':('bauherr','bauherrschaft','auftraggeber'),'architect':('architekt','architektur','planverfasser','entwurfsverfasser'),'project':('bauvorhaben','baumaßnahme','baumassnahme','bauprojekt'),'location':('bauort','grundstück','grundstueck')}
    all_labels=sum((v for v in labels.values()),())
    def block(k,take=8):
        for i,line in enumerate(lines):
            if any(x in line.casefold() for x in labels[k]):
                out=[]
                if ':' in line and line.split(':',1)[1].strip(): out.append(line.split(':',1)[1].strip())
                for z in lines[i+1:i+1+take]:
                    if out and any(x in z.casefold() for x in all_labels): break
                    out.append(z)
                return out
        return []
    addr=re.compile(r'(?P<street>[A-ZÄÖÜa-zäöüß0-9 .\-/]+?(?:straße|strasse|str\.|weg|allee|platz|ring|damm|gasse|ufer|bahn|stieg|kamp|chaussee)\s*\d+[a-zA-Z]?)(?:\s*[,;]\s*|\s+)(?P<zip>\d{5})\s+(?P<city>[A-ZÄÖÜa-zäöüß .\-]+)',re.I)
    mail=re.compile(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}')
    phone=re.compile(r'(?:tel(?:efon)?\.?|fon|mobil)\s*[:.]?\s*([+0-9][0-9 /()\-]{5,})',re.I)
    def party(vals):
        j=' | '.join(vals); o={'name':'','firm':'','street':'','zip':'','city':'','phone':'','email':''}
        m=mail.search(j); p=phone.search(j); a=addr.search(j.replace('|',' '))
        if m:o['email']=m.group(0)
        if p:o['phone']=p.group(1).strip(' ,;')
        if a:o.update(street=a.group('street').strip(' ,;'),zip=a.group('zip'),city=a.group('city').strip(' ,;'))
        useful=[v for v in vals if len(v)>2 and not re.search(r'\b\d{5}\b',v) and not mail.search(v) and not phone.search(v) and not any(k in v.casefold() for k in ('telefon','tel.','email','e-mail','www.'))]
        if useful:o['name']=useful[0]
        if len(useful)>1 and not re.search(r'\d',useful[1]) and len(useful[1])<80:o['firm']=useful[1]
        return o
    pv,lv=block('project',9),block('location',5); c,a=party(block('client')),party(block('architect'))
    ad=addr.search(' '.join(pv+lv)); title=''
    for v in pv:
        if len(v)>=5 and not re.search(r'\b\d{5}\b',v) and not addr.search(v) and not any(k in v.casefold() for k in ('maßstab','massstab','datum','plannr')): title=v; break
    return {'project_title':title,'project_street':ad.group('street').strip(' ,;') if ad else '','project_zip':ad.group('zip') if ad else '','project_city':ad.group('city').strip(' ,;') if ad else '',
      'client_name':c['name'],'client_street':c['street'],'client_zip':c['zip'],'client_city':c['city'],'client_phone':c['phone'],'client_email':c['email'],
      'architect_name':a['name'],'architect_firm':a['firm'],'architect_street':a['street'],'architect_zip':a['zip'],'architect_city':a['city'],'architect_phone':a['phone'],'architect_email':a['email']}

def open_masterdata(app):
    db,now_iso,BG,PANEL,INK,MUTED,ACCENT,DARK=_env(app); _schema(db); r=app.project_row()
    w=tk.Toplevel(app); w.title('Projektstammdaten aus Architektenplänen'); w.geometry('1080x780'); w.configure(bg=BG); w.transient(app)
    h=tk.Frame(w,bg=BG); h.pack(fill='x',padx=22,pady=(18,10))
    tk.Label(h,text='PROJEKTSTAMMDATEN AUS ARCHITEKTENPLÄNEN',bg=BG,fg=INK,font=('Segoe UI Semibold',17)).pack(anchor='w')
    status=tk.Label(h,text='Suche nach Grundrissen / Ansichten / Schnitten …',bg=BG,fg=MUTED); status.pack(anchor='w',pady=(6,0))
    f=tk.Frame(w,bg=PANEL,bd=1,relief='solid'); f.pack(fill='x',padx=22,pady=(0,10)); ct=ttk.Treeview(f,columns=('Datei','Ordner','Bewertung'),show='headings',height=5)
    for c,wi in zip(('Datei','Ordner','Bewertung'),(360,470,180)):ct.heading(c,text=c);ct.column(c,width=wi,anchor='w')
    ct.pack(fill='x',padx=10,pady=10); paths={}
    body=tk.Frame(w,bg=PANEL,bd=1,relief='solid'); body.pack(fill='both',expand=True,padx=22,pady=(0,10)); vars={}
    left=tk.Frame(body,bg=PANEL); right=tk.Frame(body,bg=PANEL); left.pack(side='left',fill='both',expand=True,padx=(14,7),pady=10); right.pack(side='left',fill='both',expand=True,padx=(7,14),pady=10)
    for i,(key,label) in enumerate(FIELDS):
        par=left if i<(len(FIELDS)+1)//2 else right; row=i if par is left else i-(len(FIELDS)+1)//2
        tk.Label(par,text=label,bg=PANEL,fg=MUTED,width=25,anchor='w').grid(row=row,column=0,sticky='w',pady=3); v=tk.StringVar(); vars[key]=v; tk.Entry(par,textvariable=v).grid(row=row,column=1,sticky='ew',pady=3,ipady=4); par.grid_columnconfigure(1,weight=1)
    con=db(); old=con.execute('SELECT * FROM project_masterdata WHERE project_id=?',(app.project_id,)).fetchone(); office=con.execute('SELECT * FROM office_profile WHERE id=1').fetchone(); con.close()
    if old:
        for k,v in vars.items():
            try:v.set(old[k] or '')
            except Exception:pass
    else:
        vars['project_title'].set(r['title'] or ''); vars['client_name'].set(r['client'] or ''); vars['architect_name'].set(r['architect'] or '')
    for dst,src in {'engineer_name':'name','engineer_firm':'firm','engineer_street':'street','engineer_zip':'zip','engineer_city':'city','engineer_phone':'phone','engineer_email':'email'}.items():
        if office and not vars[dst].get().strip():vars[dst].set(office[src] or '')
    q=queue.Queue()
    def work():
        try:sources=app._project_sources()
        except Exception:sources=[{'path':app.get_project_folder()}]
        cand=[];seen=set()
        for src in sources:
            root=Path(src['path'])
            if not root.exists():continue
            for dp,ds,fs in os.walk(root):
                ds[:]=[d for d in ds if not d.lower().startswith('.engbers') and d.lower() not in ('.git','__pycache__')]
                for fn in fs:
                    if not fn.lower().endswith('.pdf'):continue
                    p=Path(dp)/fn; k=str(p).casefold()
                    if k in seen:continue
                    seen.add(k); s,why=_score(p,root)
                    if s>=20:cand.append((s,p,root,why))
        cand.sort(key=lambda x:x[0],reverse=True); out=[]
        for s,p,root,why in cand[:12]:
            t=_pdf_text(p); out.append((s,p,root,why,len(t),_parse(t) if t else {}))
        q.put(out)
    def poll():
        try:rows=q.get_nowait()
        except queue.Empty:w.after(120,poll);return
        merged={};sources=[]
        for s,p,root,why,n,data in rows:
            try:folder=str(p.relative_to(root).parent)
            except Exception:folder=str(p.parent)
            iid=ct.insert('','end',values=(p.name,folder,f'{s} P · {why} · {n} Zeichen'));paths[iid]=p;sources.append(p.name)
            for k,v in data.items():
                if v and not merged.get(k):merged[k]=v
        for k,v in merged.items():
            if k in vars:vars[k].set(v)
        status.configure(text=f'{len(rows)} priorisierte Architektur-PDF(s) geprüft · bitte Werte kontrollieren');w._pz_sources=sources
    threading.Thread(target=work,name='PZ-Masterdata-Scan',daemon=True).start();w.after(120,poll)
    ct.bind('<Double-1>',lambda e:app.open_external_path(str(paths[ct.selection()[0]])) if ct.selection() else None)
    foot=tk.Frame(w,bg=BG);foot.pack(fill='x',padx=22,pady=(0,16));tk.Label(foot,text='Vorschläge werden erst nach Speichern übernommen. Original-PDFs bleiben unverändert.',bg=BG,fg=MUTED).pack(side='left')
    def save():
        d={k:v.get().strip() for k,v in vars.items()};d['source_files']=json.dumps(getattr(w,'_pz_sources',[]),ensure_ascii=False);d['updated_at']=now_iso();cols=[x[0] for x in FIELDS]+['source_files','updated_at']
        con=db();c=con.cursor();c.execute('INSERT OR IGNORE INTO project_masterdata(project_id) VALUES(?)',(app.project_id,));c.execute('UPDATE project_masterdata SET '+', '.join(x+'=?' for x in cols)+' WHERE project_id=?',tuple(d.get(x,'') for x in cols)+(app.project_id,))
        address=' '.join(x for x in (d['project_street'],(d['project_zip']+' '+d['project_city']).strip()) if x).strip();arch=d['architect_name'] or d['architect_firm'];c.execute('UPDATE projects SET title=?,address=?,client=?,architect=? WHERE id=?',(d['project_title'] or r['title'],address or r['address'],d['client_name'] or r['client'],arch or r['architect'],app.project_id));con.commit();con.close();messagebox.showinfo('Projektstammdaten','Stammdaten gespeichert.\n\nOriginaldateien wurden nicht verändert.',parent=w);w.destroy();app.refresh_project_combo();app.show_project()
    tk.Button(foot,text='STAMMDATEN SPEICHERN',command=save,bg=ACCENT,fg='white',bd=0,padx=16,pady=9).pack(side='right');tk.Button(foot,text='SCHLIESSEN',command=w.destroy,bg='#e7e4dc',fg=INK,bd=0,padx=16,pady=9).pack(side='right',padx=8)
