import copy
import os
import re
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import ttk, messagebox

import masterdata_v1604 as _md

W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
Q=lambda n:f'{{{W}}}{n}'


def _txt(el):
    if el is None:
        return ''
    return ''.join((x.text or '') for x in el.iter(Q('t')))


def _ancestor(el, tag, parents):
    q=Q(tag)
    while el is not None and el.tag != q:
        el=parents.get(el)
    return el


def _ctx(ff, parents):
    tc=_ancestor(ff,'tc',parents)
    tr=_ancestor(ff,'tr',parents)
    p=_ancestor(ff,'p',parents)
    cell=_txt(tc)
    if tr is not None:
        row=' | '.join(_txt(c) for c in list(tr) if c.tag==Q('tc'))
    else:
        row=_txt(p)
    return cell,row,p,tc


def _field_index(ff, parents):
    tc=_ancestor(ff,'tc',parents)
    p=_ancestor(ff,'p',parents)
    base=tc if tc is not None else p
    arr=[x for x in base.iter(Q('ffData'))] if base is not None else [ff]
    return arr.index(ff),len(arr)


def _classify(ff, parents):
    # Kontrollkästchen bleiben grundsätzlich unangetastet.
    if ff.find(Q('checkBox')) is not None:
        return None
    cell,row,_,_=_ctx(ff,parents)
    c=cell.casefold()
    r=row.casefold()
    combo=(cell+' '+row).casefold()
    idx,_=_field_index(ff,parents)

    # Bauvorhaben / Bauort.
    if 'genaue bezeichnung' in combo or 'bezeichnung des bauvorhabens' in combo:
        return 'project_title'
    if 'bauort' in combo or 'anschrift des bauvorhabens' in combo or 'objektanschrift' in combo:
        return 'project_address'

    # Beteiligte. Bei Feldern in einer gemeinsamen Zelle entscheidet die Reihenfolge:
    # erstes Formularfeld = Name, zweites Formularfeld = Anschrift.
    if 'bauherrschaft' in c or re.search(r'\bbauherr\b',c):
        return 'client_name' if idx==0 else 'client_address'
    if 'entwurfsverfass' in c or 'planverfasser' in c or 'architekt' in c:
        return 'architect_name' if idx==0 else 'architect_address'
    if ('fachplanerin' in c or 'fachplaner' in c or 'tragwerksplan' in c) and ('name' in c or 'anschrift' in c):
        return 'engineer_name' if idx==0 else 'engineer_address'

    # Kopfbereich saSV / Büro. Die Beschriftung steht häufig in der linken Tabellenzelle,
    # das eigentliche Formularfeld in der rechten Zelle.
    if 'vor- und nachname der/des sasv' in r or 'name der/des sasv' in r:
        return 'engineer_name'
    if 'bürobezeichnung' in r or 'buerobezeichnung' in r:
        return 'engineer_firm'
    if r.strip().startswith('anschrift') and len(r)<100:
        return 'engineer_address'

    # Weitere Kontaktfelder, falls andere Bescheinigungen sie explizit enthalten.
    if 'telefon' in c or 'tel.' in c:
        if 'bauherr' in c: return 'client_phone'
        if 'architekt' in c or 'entwurfsverfass' in c: return 'architect_phone'
        if 'fachplaner' in c or 'sasv' in c: return 'engineer_phone'
    if 'e-mail' in c or 'email' in c:
        if 'bauherr' in c: return 'client_email'
        if 'architekt' in c or 'entwurfsverfass' in c: return 'architect_email'
        if 'fachplaner' in c or 'sasv' in c: return 'engineer_email'
    return None


def _flatten(ff, value, parents):
    fld=parents.get(ff)
    begin=_ancestor(fld,'r',parents)
    p=_ancestor(begin,'p',parents)
    if begin is None or p is None:
        return False
    children=list(p)
    try:
        bi=children.index(begin)
    except ValueError:
        return False
    endi=None
    bookmark_ids=[]
    for i,el in enumerate(children[bi:],bi):
        bs=el.find(Q('bookmarkStart'))
        if bs is not None and bs.get(Q('id')):
            bookmark_ids.append(bs.get(Q('id')))
        fc=el.find('.//'+Q('fldChar'))
        if fc is not None and fc.get(Q('fldCharType'))=='end':
            endi=i
            break
    if endi is None:
        return False

    rpr=begin.find(Q('rPr'))
    rpr=copy.deepcopy(rpr) if rpr is not None else None
    for el in children[bi:endi+1]:
        p.remove(el)
    # Zu entfernten Formularfeldern gehörige Bookmark-Enden nicht als Waisen stehen lassen.
    for el in list(p):
        if el.tag==Q('bookmarkEnd') and el.get(Q('id')) in bookmark_ids:
            p.remove(el)

    run=ET.Element(Q('r'))
    if rpr is not None:
        run.append(rpr)
    t=ET.SubElement(run,Q('t'))
    t.text=str(value)
    p.insert(min(bi,len(p)),run)
    return True


def _address(street, zip_code, city):
    street=str(street or '').strip()
    zip_code=str(zip_code or '').strip()
    city=str(city or '').strip()
    tail=' '.join(x for x in (zip_code,city) if x)
    return ', '.join(x for x in (street,tail) if x)


def _values(data):
    return {
        'engineer_name':str(data.get('engineer_name','') or '').strip(),
        'engineer_firm':str(data.get('engineer_firm','') or '').strip(),
        'engineer_address':_address(data.get('engineer_street'),data.get('engineer_zip'),data.get('engineer_city')),
        'engineer_phone':str(data.get('engineer_phone','') or '').strip(),
        'engineer_email':str(data.get('engineer_email','') or '').strip(),
        'project_title':str(data.get('project_title','') or '').strip(),
        'project_address':_address(data.get('project_street'),data.get('project_zip'),data.get('project_city')),
        'client_name':str(data.get('client_name','') or '').strip(),
        'client_address':_address(data.get('client_street'),data.get('client_zip'),data.get('client_city')),
        'client_phone':str(data.get('client_phone','') or '').strip(),
        'client_email':str(data.get('client_email','') or '').strip(),
        'architect_name':str(data.get('architect_name','') or data.get('architect_firm','') or '').strip(),
        'architect_address':_address(data.get('architect_street'),data.get('architect_zip'),data.get('architect_city')),
        'architect_phone':str(data.get('architect_phone','') or '').strip(),
        'architect_email':str(data.get('architect_email','') or '').strip(),
    }


def inspect_docx(path, data=None):
    vals=_values(data or {})
    try:
        with zipfile.ZipFile(path,'r') as z:
            root=ET.fromstring(z.read('word/document.xml'))
    except Exception as e:
        return {'ok':False,'mapped':0,'text_fields':0,'error':str(e)}
    parents={c:p for p in root.iter() for c in p}
    mapped=0
    text_fields=0
    keys=[]
    for ff in root.iter(Q('ffData')):
        if ff.find(Q('checkBox')) is not None:
            continue
        text_fields+=1
        key=_classify(ff,parents)
        if key and (not vals or vals.get(key)):
            mapped+=1
            keys.append(key)
    return {'ok':True,'mapped':mapped,'text_fields':text_fields,'keys':keys,'error':''}


def fill_docx(src, dst, data):
    vals=_values(data)
    with zipfile.ZipFile(src,'r') as zin:
        root=ET.fromstring(zin.read('word/document.xml'))
        parents={c:p for p in root.iter() for c in p}
        fields=list(root.iter(Q('ffData')))
        plans=[]
        for ff in fields:
            key=_classify(ff,parents)
            if key and vals.get(key):
                plans.append((ff,key,vals[key]))
        if not plans:
            return 0
        for ff,key,value in plans:
            _flatten(ff,value,parents)
        new_xml=ET.tostring(root,encoding='utf-8',xml_declaration=True)
        dst=Path(dst)
        dst.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(dst,'w',zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                content=new_xml if item.filename=='word/document.xml' else zin.read(item.filename)
                zout.writestr(item,content)
    return len(plans)


def _project_sources(app):
    try:
        srcs=app._project_sources()
    except Exception:
        srcs=[{'path':app.get_project_folder()}]
    out=[]
    seen=set()
    for s in srcs:
        p=Path(s.get('path',''))
        if not p.exists():
            continue
        k=str(p).casefold()
        if k in seen:
            continue
        seen.add(k)
        out.append(p)
    return out


def _bescheinigungen_roots(app):
    roots=[]
    seen=set()
    for project_root in _project_sources(app):
        direct=project_root/'Bescheinigungen'
        candidates=[]
        if direct.is_dir():
            candidates.append(direct)
        try:
            for dp,ds,fs in os.walk(project_root):
                ds[:]=[d for d in ds if d.casefold() not in ('.git','__pycache__','ausgefüllt','ausgefuellt') and not d.startswith('.engbers')]
                p=Path(dp)
                if p.name.casefold()=='bescheinigungen':
                    candidates.append(p)
                    ds[:]=[]
        except Exception:
            pass
        for p in candidates:
            k=str(p.resolve()).casefold()
            if k not in seen:
                seen.add(k); roots.append(p)
    return roots


def _documents(app):
    rows=[]
    seen=set()
    for root in _bescheinigungen_roots(app):
        for p in root.rglob('*.docx'):
            if any(part.casefold() in ('ausgefüllt','ausgefuellt') for part in p.parts):
                continue
            if p.name.startswith('~$') or '_ausgefüllt' in p.stem.casefold() or '_ausgefuellt' in p.stem.casefold():
                continue
            k=str(p).casefold()
            if k in seen:
                continue
            seen.add(k)
            try: rel=p.relative_to(root)
            except Exception: rel=Path(p.name)
            rows.append((root,p,rel))
    rows.sort(key=lambda x:(str(x[0]).casefold(),str(x[2]).casefold()))
    return rows


def _output_path(root, src, rel):
    parent=(root/'Ausgefüllt'/rel.parent)
    return parent/(src.stem+'_ausgefüllt'+src.suffix)


def open_wordforms(app):
    data=_md._masterdata_row(app)
    db,_,BG,PANEL,INK,MUTED,ACCENT,DARK=_md._base._env(app)
    w=tk.Toplevel(app)
    w.title('Word-Bescheinigungen ausfüllen')
    w.geometry('1180x760')
    w.configure(bg=BG)
    w.transient(app)

    head=tk.Frame(w,bg=BG); head.pack(fill='x',padx=22,pady=(18,10))
    tk.Label(head,text='WORD-BESCHEINIGUNGEN',bg=BG,fg=INK,font=('Segoe UI Semibold',18)).pack(anchor='w')
    tk.Label(head,text='Quelle: Ordner Bescheinigungen · Ausgabe: Bescheinigungen\\Ausgefüllt · Originaldateien bleiben unverändert',bg=BG,fg=MUTED).pack(anchor='w',pady=(5,0))

    info=tk.Frame(w,bg=PANEL,bd=1,relief='solid'); info.pack(fill='x',padx=22,pady=(0,10))
    summary=[
        ('Bauvorhaben',data.get('project_title','')),
        ('Bauort',_address(data.get('project_street'),data.get('project_zip'),data.get('project_city'))),
        ('Bauherr',data.get('client_name','')),
        ('Architekt',data.get('architect_name','') or data.get('architect_firm','')),
    ]
    for i,(k,v) in enumerate(summary):
        row=tk.Frame(info,bg=PANEL); row.pack(fill='x',padx=14,pady=(8 if i==0 else 2,8 if i==len(summary)-1 else 2))
        tk.Label(row,text=k,width=16,anchor='w',bg=PANEL,fg=MUTED).pack(side='left')
        tk.Label(row,text=v or '—',anchor='w',bg=PANEL,fg=INK,font=('Segoe UI Semibold',10)).pack(side='left',fill='x',expand=True)

    box=tk.Frame(w,bg=PANEL,bd=1,relief='solid'); box.pack(fill='both',expand=True,padx=22,pady=(0,10))
    tree=ttk.Treeview(box,columns=('Datei','Ordner','Felder','Status'),show='headings',selectmode='extended')
    widths=(360,330,170,260)
    for c,wi in zip(('Datei','Ordner','Felder','Status'),widths):
        tree.heading(c,text=c); tree.column(c,width=wi,anchor='w')
    tree.pack(side='left',fill='both',expand=True,padx=(10,0),pady=10)
    sb=ttk.Scrollbar(box,orient='vertical',command=tree.yview); sb.pack(side='right',fill='y',padx=(0,10),pady=10); tree.configure(yscrollcommand=sb.set)

    docs={}
    roots=_bescheinigungen_roots(app)
    for root,src,rel in _documents(app):
        check=inspect_docx(src,data)
        fields=(f"{check['mapped']} automatisch" if check['ok'] else 'Fehler')
        status=('bereit' if check['ok'] and check['mapped'] else ('keine passenden Formularfelder' if check['ok'] else check['error']))
        iid=tree.insert('','end',values=(src.name,str(rel.parent) if str(rel.parent)!='.' else 'Bescheinigungen',fields,status))
        docs[iid]={'root':root,'src':src,'rel':rel,'check':check,'dst':None}

    status_lbl=tk.Label(w,bg=BG,fg=MUTED,anchor='w')
    if roots:
        status_lbl.configure(text=f'{len(docs)} Word-Datei(en) in {len(roots)} Bescheinigungen-Ordner(n) gefunden')
    else:
        status_lbl.configure(text='Kein Ordner Bescheinigungen im aktuellen Projekt gefunden.')
    status_lbl.pack(fill='x',padx=22,pady=(0,8))

    def _fill(ids):
        if not ids:
            messagebox.showinfo('Word-Bescheinigungen','Bitte mindestens eine Word-Datei auswählen.',parent=w)
            return
        made=[]; skipped=[]; failed=[]
        for iid in ids:
            item=docs.get(iid)
            if not item: continue
            if not item['check'].get('mapped'):
                skipped.append(item['src'].name); continue
            dst=_output_path(item['root'],item['src'],item['rel'])
            try:
                n=fill_docx(item['src'],dst,data)
                if n:
                    item['dst']=dst; made.append(dst)
                    vals=list(tree.item(iid,'values')); vals[3]=f'{n} Felder ausgefüllt'; tree.item(iid,values=vals)
                else:
                    skipped.append(item['src'].name)
            except Exception as e:
                failed.append(f'{item["src"].name}: {e}')
                vals=list(tree.item(iid,'values')); vals[3]='Fehler'; tree.item(iid,values=vals)
        status_lbl.configure(text=f'{len(made)} Datei(en) erstellt · Originale unverändert')
        msg=[]
        if made: msg.append(f'{len(made)} ausgefüllte Kopie(n) erstellt.')
        if skipped: msg.append(f'{len(skipped)} Datei(en) ohne passende/gefüllte Felder übersprungen.')
        if failed: msg.append('Fehler:\n'+'\n'.join(failed[:5]))
        if made:
            msg.append('\nAusgabe unter Bescheinigungen\\Ausgefüllt.')
        messagebox.showinfo('Word-Bescheinigungen','\n'.join(msg) or 'Keine Datei geändert.',parent=w)

    def fill_selected():
        _fill(list(tree.selection()))

    def fill_all():
        _fill(list(docs.keys()))

    def open_original(event=None):
        sel=tree.selection()
        if sel:
            app.open_external_path(str(docs[sel[0]]['src']))

    def open_output():
        sel=tree.selection()
        if sel and docs[sel[0]].get('dst') and docs[sel[0]]['dst'].exists():
            app.open_external_path(str(docs[sel[0]]['dst']))
            return
        for item in docs.values():
            if item.get('dst') and item['dst'].exists():
                app.open_external_path(str(item['dst'].parent)); return
        if roots:
            out=roots[0]/'Ausgefüllt'; out.mkdir(parents=True,exist_ok=True); app.open_external_path(str(out))

    tree.bind('<Double-1>',open_original)
    foot=tk.Frame(w,bg=BG); foot.pack(fill='x',padx=22,pady=(0,16))
    tk.Button(foot,text='AUSGABE ÖFFNEN',command=open_output,bg='#e7e4dc',fg=INK,bd=0,padx=14,pady=9).pack(side='left')
    tk.Button(foot,text='SCHLIESSEN',command=w.destroy,bg='#e7e4dc',fg=INK,bd=0,padx=14,pady=9).pack(side='right')
    tk.Button(foot,text='ALLE AUSFÜLLEN',command=fill_all,bg=ACCENT,fg='white',bd=0,padx=16,pady=9).pack(side='right',padx=8)
    tk.Button(foot,text='MARKIERTE AUSFÜLLEN',command=fill_selected,bg=DARK,fg='white',bd=0,padx=16,pady=9).pack(side='right')
    return w
