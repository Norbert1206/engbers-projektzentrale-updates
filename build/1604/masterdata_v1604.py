import json, os, queue, threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
import masterdata_v1600 as _base
import masterdata_v1603 as _reader

FIELDS=_base.FIELDS
GROUPS=[
    ('BAUVORHABEN',[
        ('project_title','Bezeichnung'),('project_street','Straße'),('project_zip','PLZ'),('project_city','Ort')]),
    ('BAUHERR',[
        ('client_name','Name'),('client_street','Straße'),('client_zip','PLZ'),('client_city','Ort'),('client_phone','Telefon'),('client_email','E-Mail')]),
    ('ARCHITEKT',[
        ('architect_name','Name'),('architect_firm','Büro'),('architect_street','Straße'),('architect_zip','PLZ'),('architect_city','Ort'),('architect_phone','Telefon'),('architect_email','E-Mail')]),
    ('TRAGWERKSPLANUNG',[
        ('engineer_name','Name'),('engineer_firm','Büro'),('engineer_street','Straße'),('engineer_zip','PLZ'),('engineer_city','Ort'),('engineer_phone','Telefon'),('engineer_email','E-Mail')]),
]


def _office_to_vars(office, vars):
    if not office:
        return
    mapping={'engineer_name':'name','engineer_firm':'firm','engineer_street':'street','engineer_zip':'zip','engineer_city':'city','engineer_phone':'phone','engineer_email':'email'}
    for dst,src in mapping.items():
        try: vars[dst].set(office[src] or '')
        except Exception: pass


def _editable_card(parent,title,fields,vars,PANEL,INK,MUTED,ACCENT):
    card=tk.Frame(parent,bg=PANEL,bd=1,relief='solid')
    head=tk.Frame(card,bg=PANEL); head.pack(fill='x',padx=14,pady=(10,6))
    tk.Label(head,text=title,bg=PANEL,fg=INK,font=('Segoe UI Semibold',11)).pack(side='left')
    tk.Frame(card,bg=ACCENT,height=2).pack(fill='x',padx=14)
    body=tk.Frame(card,bg=PANEL); body.pack(fill='both',expand=True,padx=14,pady=8)
    body.grid_columnconfigure(1,weight=1)
    for i,(key,label) in enumerate(fields):
        tk.Label(body,text=label,bg=PANEL,fg=MUTED,width=14,anchor='w').grid(row=i,column=0,sticky='w',pady=3)
        v=vars.setdefault(key,tk.StringVar())
        tk.Entry(body,textvariable=v).grid(row=i,column=1,sticky='ew',pady=3,ipady=4)
    return card


def _readonly_card(parent,title,fields,data,PANEL,INK,MUTED,ACCENT):
    card=tk.Frame(parent,bg=PANEL,bd=1,relief='solid')
    head=tk.Frame(card,bg=PANEL); head.pack(fill='x',padx=14,pady=(10,6))
    tk.Label(head,text=title,bg=PANEL,fg=INK,font=('Segoe UI Semibold',11)).pack(side='left')
    tk.Frame(card,bg=ACCENT,height=2).pack(fill='x',padx=14)
    body=tk.Frame(card,bg=PANEL); body.pack(fill='both',expand=True,padx=14,pady=8)
    for key,label in fields:
        row=tk.Frame(body,bg=PANEL); row.pack(fill='x',pady=2)
        tk.Label(row,text=label,width=14,anchor='w',bg=PANEL,fg=MUTED).pack(side='left')
        val=str(data.get(key,'') or '').strip() or '—'
        tk.Label(row,text=val,anchor='w',bg=PANEL,fg=INK,font=('Segoe UI',10),wraplength=430,justify='left').pack(side='left',fill='x',expand=True)
    return card


def _masterdata_row(app):
    db,_,_,_,_,_,_,_=_base._env(app); _base._schema(db)
    con=db()
    try:
        row=con.execute('SELECT * FROM project_masterdata WHERE project_id=?',(app.project_id,)).fetchone()
        office=con.execute('SELECT * FROM office_profile WHERE id=1').fetchone()
    finally:
        con.close()
    d={k:'' for k,_ in FIELDS}
    if row:
        for k in d:
            try:d[k]=row[k] or ''
            except Exception:pass
    r=app.project_row()
    if not d['project_title']: d['project_title']=r['title'] or ''
    if not d['client_name']: d['client_name']=r['client'] or ''
    if not d['architect_name']: d['architect_name']=r['architect'] or ''
    if not any((d['project_street'],d['project_zip'],d['project_city'])):
        addr=str(r['address'] or '').strip()
        if addr: d['project_street']=addr
    if office:
        for dst,src in {'engineer_name':'name','engineer_firm':'firm','engineer_street':'street','engineer_zip':'zip','engineer_city':'city','engineer_phone':'phone','engineer_email':'email'}.items():
            try:d[dst]=office[src] or d[dst]
            except Exception:pass
    try:d['_updated_at']=row['updated_at'] if row else ''
    except Exception:d['_updated_at']=''
    return d


def render_project_masterdata_cards(app,parent):
    """Read-only 2x2 card view on the project record page."""
    db,_,BG,PANEL,INK,MUTED,ACCENT,DARK=_base._env(app)
    data=_masterdata_row(app)
    outer=tk.Frame(parent,bg=BG); outer.pack(fill='x',pady=(0,12))
    top=tk.Frame(outer,bg=BG); top.pack(fill='x',pady=(0,6))
    tk.Label(top,text='PROJEKTSTAMMDATEN',bg=BG,fg=INK,font=('Segoe UI Semibold',11)).pack(side='left')
    if data.get('_updated_at'):
        tk.Label(top,text='gespeicherte zentrale Projektdaten',bg=BG,fg=MUTED).pack(side='left',padx=(12,0))
    grid=tk.Frame(outer,bg=BG); grid.pack(fill='x')
    grid.grid_columnconfigure(0,weight=1,uniform='md'); grid.grid_columnconfigure(1,weight=1,uniform='md')
    for idx,(title,fields) in enumerate(GROUPS):
        card=_readonly_card(grid,title,fields,data,PANEL,INK,MUTED,ACCENT)
        card.grid(row=idx//2,column=idx%2,sticky='nsew',padx=(0,7) if idx%2==0 else (7,0),pady=(0,10))
    return outer


def open_masterdata(app):
    ok,info=_reader.engine_status()
    if not ok:
        messagebox.showerror('CAD-PDF-Reader fehlt','PyMuPDF konnte nicht geladen werden.\n\nDie Stammdatenerkennung wird nicht gestartet.\n\nBitte unter Sicherung / Update erneut nach Updates suchen.\n\nDetails: '+info,parent=app)
        return None
    db,now_iso,BG,PANEL,INK,MUTED,ACCENT,DARK=_base._env(app); _base._schema(db); r=app.project_row()
    w=tk.Toplevel(app); w.title('Projektstammdaten aus Architektenplänen'); w.geometry('1180x860'); w.configure(bg=BG); w.transient(app)
    h=tk.Frame(w,bg=BG); h.pack(fill='x',padx=22,pady=(18,10))
    tk.Label(h,text='PROJEKTSTAMMDATEN AUS ARCHITEKTENPLÄNEN',bg=BG,fg=INK,font=('Segoe UI Semibold',17)).pack(anchor='w')
    status=tk.Label(h,text='CAD-PDF-Reader aktiv · Suche nach Grundrissen / Ansichten / Schnitten …',bg=BG,fg=MUTED); status.pack(anchor='w',pady=(6,0))
    f=tk.Frame(w,bg=PANEL,bd=1,relief='solid'); f.pack(fill='x',padx=22,pady=(0,10)); ct=ttk.Treeview(f,columns=('Datei','Ordner','Bewertung'),show='headings',height=5)
    for c,wi in zip(('Datei','Ordner','Bewertung'),(370,500,240)):ct.heading(c,text=c);ct.column(c,width=wi,anchor='w')
    ct.pack(fill='x',padx=10,pady=10); paths={}

    body=tk.Frame(w,bg=BG); body.pack(fill='both',expand=True,padx=22,pady=(0,10)); body.grid_columnconfigure(0,weight=1,uniform='cards'); body.grid_columnconfigure(1,weight=1,uniform='cards'); body.grid_rowconfigure(0,weight=1); body.grid_rowconfigure(1,weight=1)
    vars={}
    for idx,(title,fields) in enumerate(GROUPS):
        card=_editable_card(body,title,fields,vars,PANEL,INK,MUTED,ACCENT)
        card.grid(row=idx//2,column=idx%2,sticky='nsew',padx=(0,7) if idx%2==0 else (7,0),pady=(0,10))

    con=db(); old=con.execute('SELECT * FROM project_masterdata WHERE project_id=?',(app.project_id,)).fetchone(); office=con.execute('SELECT * FROM office_profile WHERE id=1').fetchone(); con.close()
    if old:
        for k,v in vars.items():
            try:v.set(old[k] or '')
            except Exception:pass
    else:
        vars['project_title'].set(r['title'] or ''); vars['client_name'].set(r['client'] or ''); vars['architect_name'].set(r['architect'] or '')
    _office_to_vars(office,vars)

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
                    p=Path(dp)/fn;k=str(p).casefold()
                    if k in seen:continue
                    seen.add(k);s,why=_reader._score(p,root)
                    if s>=20:cand.append((s,p,root,why))
        cand.sort(key=lambda x:x[0],reverse=True);out=[]
        for s,p,root,why in cand[:12]:
            t=_reader._pdf_text(p);data=_reader._parse(t) if t else {};out.append((s,p,root,why,len(t),data))
        q.put(out)
    def poll():
        try:rows=q.get_nowait()
        except queue.Empty:w.after(120,poll);return
        merged={};sources=[]
        for s,p,root,why,n,data in rows:
            try:folder=str(p.relative_to(root).parent)
            except Exception:folder=str(p.parent)
            recognized=sum(1 for k,v in data.items() if v and not k.startswith('engineer_'))
            iid=ct.insert('','end',values=(p.name,folder,f'{s} P · {why} · {recognized} Stammdatenfeld(er)'));paths[iid]=p;sources.append(p.name)
            for k,v in data.items():
                if k.startswith('engineer_'):continue
                if v and not merged.get(k):merged[k]=v
        for k,v in merged.items():
            if k in vars:vars[k].set(v)
        _office_to_vars(office,vars)
        status.configure(text=f'{len(rows)} priorisierte Architektur-/Projekt-PDF(s) geprüft · bitte Werte kontrollieren');w._pz_sources=sources
    threading.Thread(target=work,name='PZ-Masterdata-Scan',daemon=True).start();w.after(120,poll)
    ct.bind('<Double-1>',lambda e:app.open_external_path(str(paths[ct.selection()[0]])) if ct.selection() else None)

    foot=tk.Frame(w,bg=BG);foot.pack(fill='x',padx=22,pady=(0,16));tk.Label(foot,text='Vorschläge werden erst nach Speichern übernommen. Original-PDFs bleiben unverändert.',bg=BG,fg=MUTED).pack(side='left')
    def save():
        _office_to_vars(office,vars)
        d={k:v.get().strip() for k,v in vars.items()};d['source_files']=json.dumps(getattr(w,'_pz_sources',[]),ensure_ascii=False);d['updated_at']=now_iso();cols=[x[0] for x in FIELDS]+['source_files','updated_at']
        con=db();c=con.cursor();c.execute('INSERT OR IGNORE INTO project_masterdata(project_id) VALUES(?)',(app.project_id,));c.execute('UPDATE project_masterdata SET '+', '.join(x+'=?' for x in cols)+' WHERE project_id=?',tuple(d.get(x,'') for x in cols)+(app.project_id,))
        address=' '.join(x for x in (d['project_street'],(d['project_zip']+' '+d['project_city']).strip()) if x).strip();arch=d['architect_name'] or d['architect_firm'];c.execute('UPDATE projects SET title=?,address=?,client=?,architect=? WHERE id=?',(d['project_title'] or r['title'],address or r['address'],d['client_name'] or r['client'],arch or r['architect'],app.project_id));con.commit();con.close();messagebox.showinfo('Projektstammdaten','Stammdaten gespeichert.\n\nOriginaldateien wurden nicht verändert.',parent=w);w.destroy();app.refresh_project_combo();app.show_project()
    tk.Button(foot,text='STAMMDATEN SPEICHERN',command=save,bg=ACCENT,fg='white',bd=0,padx=16,pady=9).pack(side='right');tk.Button(foot,text='SCHLIESSEN',command=w.destroy,bg='#e7e4dc',fg=INK,bd=0,padx=16,pady=9).pack(side='right',padx=8)
    return w
