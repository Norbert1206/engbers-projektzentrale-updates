from pathlib import Path
import datetime
import py_compile
import re
import shutil

APP=Path(__file__).resolve().parent/'app.py'


def _compile_text(text,name):
    p=APP.with_name(name)
    try:
        p.write_text(text,encoding='utf-8')
        py_compile.compile(str(p),doraise=True)
    finally:
        try:p.unlink()
        except Exception:pass


def _rep(s,old,new,label):
    if old not in s:
        raise RuntimeError('1.4.45: Abschnitt nicht gefunden: '+label)
    return s.replace(old,new,1)


def _patch_sidebar(s):
    old="""                self.statik_pdf_nav=tk.Button(self.sidebar,text='   ↳ Statik PDF',command=lambda:self.navigate('Statik',self.show_statics),anchor='w',bd=0,bg=DARK,fg='#b9b7b0',activebackground=DARK2,activeforeground='white',font=('Segoe UI',9),padx=30,pady=5,cursor='hand2')\n"""
    new="""                # PZ_STATIK_PDF_NAV_V1445: eigener Statik-PDF-Bereich\n                self.statik_pdf_nav=tk.Button(self.sidebar,text='   ↳ Statik PDF',command=lambda:self.navigate('Statik',self.show_statik_pdf),anchor='w',bd=0,bg=DARK,fg='#b9b7b0',activebackground=DARK2,activeforeground='white',font=('Segoe UI',9),padx=30,pady=5,cursor='hand2')\n"""
    if 'PZ_STATIK_PDF_NAV_V1445' not in s:
        s=_rep(s,old,new,'Statik-PDF Navigation')
    return s


def _patch_statik_pdf_view(s):
    if 'def show_statik_pdf(self):' in s and 'PZ_STATIK_PDF_VIEW_V1445' in s:
        return s
    marker='    def show_statics(self):\n'
    if marker not in s:
        raise RuntimeError('1.4.45: show_statics nicht gefunden.')
    block=r'''    def show_statik_pdf(self):
        # PZ_STATIK_PDF_VIEW_V1445: eigener, rein lesender Statik-PDF-Bereich.
        self.clear()
        r=self.project_row()
        self.titleblock(self.content,'Statik PDF',f"{r['number']} · {r['title']} · Originaldateien, keine Kopien")
        self.program_starter_bar(self.content)
        project_root=Path(self.get_project_folder())

        def find_folder():
            try:
                for child in project_root.iterdir():
                    if child.is_dir() and ''.join(ch for ch in child.name.casefold() if ch.isalnum())=='statikpdf':
                        return child
            except Exception:
                pass
            return project_root/'Statik PDF'

        tools=tk.Frame(self.content,bg=BG); tools.pack(fill='x',pady=(0,10))
        info=tk.Label(tools,text='',bg=BG,fg=MUTED,anchor='w'); info.pack(side='left',fill='x',expand=True)
        search_var=tk.StringVar()
        tk.Label(tools,text='Suche:',bg=BG,fg=MUTED).pack(side='left',padx=(8,4))
        search_entry=tk.Entry(tools,textvariable=search_var,width=28); search_entry.pack(side='left')

        pan,body=self.panel(self.content,'Statik PDF · Projektordner'); pan.pack(fill='both',expand=True)
        cols=('Geändert','Unterordner','Größe')
        tree=ttk.Treeview(body,columns=cols,show='tree headings',height=22)
        tree.heading('#0',text='PDF-Datei'); tree.column('#0',width=560,minwidth=260,stretch=True,anchor='w')
        specs=(('Geändert',145,125),('Unterordner',360,160),('Größe',90,70))
        for col,w,m in specs: tree.heading(col,text=col); tree.column(col,width=w,minwidth=m,stretch=(col=='Unterordner'),anchor='w')
        sy=ttk.Scrollbar(body,orient='vertical',command=tree.yview); tree.configure(yscrollcommand=sy.set)
        tree.grid(row=0,column=0,sticky='nsew'); sy.grid(row=0,column=1,sticky='ns'); body.grid_rowconfigure(0,weight=1); body.grid_columnconfigure(0,weight=1)
        paths={}

        def human_size(size):
            try:
                size=float(size)
                for unit in ('B','KB','MB','GB'):
                    if size<1024 or unit=='GB': return f'{size:.0f} {unit}' if unit=='B' else f'{size:.1f} {unit}'
                    size/=1024
            except Exception:return '—'

        def selected_path(event=None):
            iid=''
            if event is not None:
                try:iid=tree.identify_row(event.y)
                except Exception:iid=''
            if not iid:
                sel=tree.selection(); iid=sel[0] if sel else ''
            if iid:
                try:tree.selection_set(iid)
                except Exception:pass
            return paths.get(iid)

        def refresh(*_):
            for iid in tree.get_children(''): tree.delete(iid)
            paths.clear(); folder=find_folder(); q=search_var.get().strip().casefold(); files=[]
            if folder.exists():
                try:
                    for p in folder.rglob('*.pdf'):
                        try:
                            if p.is_file(): files.append(p)
                        except OSError:pass
                except OSError:pass
            def mtime(p):
                try:return p.stat().st_mtime
                except Exception:return 0
            files.sort(key=lambda p:(mtime(p),p.name.casefold()),reverse=True)
            shown=0
            for p in files:
                try:rel=p.relative_to(folder)
                except Exception:rel=Path(p.name)
                hay=(p.name+' '+str(rel.parent)).casefold()
                if q and q not in hay:continue
                try:st=p.stat(); changed=datetime.datetime.fromtimestamp(st.st_mtime).strftime('%d.%m.%Y %H:%M'); size=human_size(st.st_size)
                except OSError:changed='—'; size='—'
                sub=str(rel.parent); sub='—' if sub=='.' else sub
                iid=tree.insert('','end',text=p.name,values=(changed,sub,size)); paths[iid]=p; shown+=1
            info.config(text=(f'{shown} von {len(files)} PDF-Datei(en) · {folder}' if folder.exists() else f'Ordner noch nicht vorhanden · {folder}'))

        def open_selected(event=None):
            p=selected_path(event)
            if p:self.open_external_path(p)
            return 'break'

        def open_folder():
            folder=find_folder()
            if not folder.exists():
                if not messagebox.askyesno('Statik PDF',f'Der Ordner ist noch nicht vorhanden:\n{folder}\n\nJetzt anlegen?'):return
                try:folder.mkdir(parents=True,exist_ok=True)
                except Exception as exc:messagebox.showerror('Statik PDF',str(exc)); return
            self.open_external_path(folder); refresh()

        tk.Button(tools,text='ORDNER ÖFFNEN',command=open_folder,bg=DARK,fg='white',bd=0,padx=13,pady=7).pack(side='right',padx=(6,0))
        tk.Button(tools,text='AKTUALISIEREN',command=refresh,bg='#e7e4dc',fg=INK,bd=0,padx=13,pady=7).pack(side='right',padx=(6,0))
        tree.bind('<Double-1>',open_selected); tree.bind('<Return>',open_selected)
        search_var.trace_add('write',lambda *_:refresh())
        refresh()

'''
    return s.replace(marker,block+marker,1)


def _patch_statik_quickaccess(s):
    if "_statik_pdf_box=ttk.LabelFrame(content,text='STATIK PDF · SCHNELLZUGRIFF')" in s:
        s=s.replace("_statik_pdf_box=ttk.LabelFrame(content,text='STATIK PDF · SCHNELLZUGRIFF')","_statik_pdf_box=ttk.LabelFrame(self.content,text='STATIK PDF · SCHNELLZUGRIFF')",1)
    return s


def _patch_project_explorer(s):
    if 'PZ_PROJECT_EXPLORER_OPEN_V1445' in s:
        return s
    old_recent="""        recent=[]\n        for src in sources:\n            root=src['path']\n            if not root.exists(): continue\n            try:\n                for p in root.rglob('*'):\n                    if p.is_file():\n                        try: recent.append((p,p.stat().st_mtime,src))\n"""
    new_recent="""        recent=[]\n        for src in sources:\n            root=src['path']\n            if not root.exists(): continue\n            try:\n                for p in root.rglob('*'):\n                    try:\n                        _rel_parts=p.relative_to(root).parts\n                        if '.engbers' in _rel_parts or p.name.startswith('.engbers_'): continue\n                    except Exception:pass\n                    if p.is_file():\n                        try: recent.append((p,p.stat().st_mtime,src))\n"""
    s=_rep(s,old_recent,new_recent,'Projekt-Explorer Verwaltungsdaten zuletzt geändert')

    old="""            rt.pack(fill='x'); rt.bind('<Double-1>',lambda e:self.open_external_path(rmap.get(rt.selection()[0])) if rt.selection() else None)\n"""
    new="""            rt.pack(fill='x')\n            def _open_recent(event=None):\n                iid=''\n                if event is not None:\n                    try:iid=rt.identify_row(event.y)\n                    except Exception:iid=''\n                if not iid:\n                    sel=rt.selection(); iid=sel[0] if sel else ''\n                if iid:\n                    try:rt.selection_set(iid)\n                    except Exception:pass\n                    p=rmap.get(iid)\n                    if p:self.open_external_path(p)\n                return 'break'\n            rt.bind('<Double-1>',_open_recent); rt.bind('<Return>',_open_recent)\n"""
    s=_rep(s,old,new,'Projekt-Explorer zuletzt geändert')

    old2="""            for pp in items:\n                try: rel=pp.relative_to(root); st=pp.stat(); changed=datetime.datetime.fromtimestamp(st.st_mtime).strftime('%d.%m.%Y %H:%M'); size='—' if pp.is_dir() else self.human_size(st.st_size); cat,_=self._effective_category(rel)\n"""
    new2="""            for pp in items:\n                # PZ_PROJECT_EXPLORER_OPEN_V1445: interne Verwaltungsdaten ausblenden.\n                if pp.name=='.engbers' or pp.name.startswith('.engbers_'):\n                    continue\n                try: rel=pp.relative_to(root); st=pp.stat(); changed=datetime.datetime.fromtimestamp(st.st_mtime).strftime('%d.%m.%Y %H:%M'); size='—' if pp.is_dir() else self.human_size(st.st_size); cat,_=self._effective_category(rel)\n"""
    s=_rep(s,old2,new2,'Projekt-Explorer .engbers ausblenden')

    old3="""        def on_open(_evt=None):\n            pp,root,iid=selected()\n            if pp and pp.is_dir():\n                kids=tr.get_children(iid)\n                if len(kids)==1 and tr.item(kids[0],'text')=='…': tr.delete(kids[0]); insert_children(iid,root,pp)\n        def on_double(_evt=None):\n            pp,_,_=selected()\n            if pp:self.open_external_path(pp)\n"""
    new3="""        def _select_from_event(_evt=None):\n            if _evt is not None:\n                try:\n                    iid=tr.identify_row(_evt.y)\n                    if iid:\n                        tr.selection_set(iid); tr.focus(iid); refresh(); return iid\n                except Exception:pass\n            sel=tr.selection(); return sel[0] if sel else None\n        def _load_folder(iid,pp,root):\n            if not iid or not pp or not pp.is_dir():return\n            kids=tr.get_children(iid)\n            if len(kids)==1 and tr.item(kids[0],'text')=='…':\n                tr.delete(kids[0]); insert_children(iid,root,pp)\n        def on_open(_evt=None):\n            pp,root,iid=selected(); _load_folder(iid,pp,root)\n        def on_double(_evt=None):\n            iid=_select_from_event(_evt); pp=pathmap.get(iid); root=rootmap.get(iid)\n            if not pp:return 'break'\n            if pp.is_dir():\n                _load_folder(iid,pp,root)\n                try:tr.item(iid,open=not bool(tr.item(iid,'open')))\n                except Exception:pass\n            else:\n                self.open_external_path(pp)\n            return 'break'\n        def open_original():\n            pp,_,_=selected()\n            if pp:self.open_external_path(pp)\n        def show_in_windows_explorer():\n            pp,_,_=selected()\n            if not pp:return\n            try:\n                if os.name=='nt' and pp.is_file():\n                    subprocess.Popen(['explorer','/select,',str(pp)])\n                else:\n                    self.open_external_path(pp if pp.is_dir() else pp.parent)\n            except Exception as exc:\n                messagebox.showerror('Projekt-Explorer',str(exc))\n"""
    s=_rep(s,old3,new3,'Projekt-Explorer Öffnen-Logik')
    s=s.replace("        assign_btn.configure(command=assign); open_btn.configure(command=on_double)\n","        assign_btn.configure(command=assign); open_btn.configure(command=open_original)\n        show_btn=tk.Button(btns,text='IM EXPLORER ZEIGEN',command=show_in_windows_explorer,bg='#e7e4dc',fg=INK,bd=0,padx=10,pady=7); show_btn.pack(side='left')\n",1)
    s=s.replace("        menu=tk.Menu(self,tearoff=0); menu.add_command(label='Fachlich zuordnen…',command=assign); menu.add_command(label='Original öffnen',command=on_double)\n","        menu=tk.Menu(self,tearoff=0); menu.add_command(label='Fachlich zuordnen…',command=assign); menu.add_command(label='Original öffnen',command=open_original); menu.add_command(label='Im Windows-Explorer zeigen',command=show_in_windows_explorer)\n",1)
    s=s.replace("        tr.bind('<<TreeviewOpen>>',on_open); tr.bind('<Double-1>',on_double); tr.bind('<<TreeviewSelect>>',refresh)\n","        tr.bind('<<TreeviewOpen>>',on_open); tr.bind('<Double-1>',on_double); tr.bind('<Return>',on_double); tr.bind('<<TreeviewSelect>>',refresh)\n",1)
    return s


def _patch_metadata_folder(s):
    if 'PZ_METADATA_DIR_V1445' in s:
        return s
    old_plan="""        def _position_manual_plan_store(folder):\n            try:\n                return _position_project_root(folder)/'.engbers_positionsplaene.json'\n            except Exception:\n                return Path(folder)/'.engbers_positionsplaene.json'\n"""
    new_plan=r'''        def _position_metadata_dir(folder):
            # PZ_METADATA_DIR_V1445: Projektzentrale-Metadaten gebündelt in .engbers.
            try:base=_position_project_root(folder)
            except Exception:base=Path(folder)
            meta=base/'.engbers'
            try:
                meta.mkdir(parents=True,exist_ok=True)
                if os.name=='nt':
                    try:subprocess.run(['attrib','+h',str(meta)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
                    except Exception:pass
            except Exception:
                return base
            return meta

        def _position_migrate_store(folder,legacy_name,new_name):
            try:
                base=_position_project_root(folder); meta=_position_metadata_dir(folder)
                legacy=base/legacy_name; target=meta/new_name
                if meta!=base and legacy.exists() and not target.exists():
                    try:legacy.replace(target)
                    except Exception:
                        try:shutil.copy2(legacy,target)
                        except Exception:return legacy
                return target if meta!=base else legacy
            except Exception:
                return Path(folder)/legacy_name

        def _position_manual_plan_store(folder):
            return _position_migrate_store(folder,'.engbers_positionsplaene.json','positionsplaene.json')
'''
    s=_rep(s,old_plan,new_plan,'Positionsplan-Metadaten')
    old_rec="""        def _position_record_store(folder):\n            try:\n                return _position_project_root(folder)/'.engbers_positionsakte.json'\n            except Exception:\n                return Path(folder)/'.engbers_positionsakte.json'\n"""
    new_rec="""        def _position_record_store(folder):\n            return _position_migrate_store(folder,'.engbers_positionsakte.json','positionsakte.json')\n"""
    s=_rep(s,old_rec,new_rec,'Positionsakte-Metadaten')
    return s


def _patch_position_layout(s):
    if 'def _position_layout_1445()' in s:
        return s
    start=s.find('        def _position_layout_1444():\n')
    if start<0:
        raise RuntimeError('1.4.45: Layoutfunktion 1.4.44 nicht gefunden.')
    end=s.find('        # 1.4.35: Bearbeitungsstatus kompakt direkt hinter der Positionsspalte.\n',start)
    if end<0:
        raise RuntimeError('1.4.45: Ende der Layoutfunktion nicht gefunden.')
    block=r'''        def _position_layout_1445():
            # PZ_POSITION_LAYOUT_V1445: echte Spaltennamen, klare Köpfe, kein Scrollen im Einzelprojekt.
            try:
                cols=list(ptr.cget('columns'))
                required=('Pos.','pz_bearbeitung','Bezeichnung','mb-Modul','mb-Kennwert')
                if not all(c in cols for c in required):return
                single=bool(current_project.get('folder'))
                display=required if single else ('mb-Projekt',)+required
                ptr.configure(displaycolumns=tuple(c for c in display if c in cols))
                ptr.heading('#0',text='Gruppe'); ptr.column('#0',width=98,minwidth=82,stretch=False,anchor='w')
                heads={'mb-Projekt':'mb-Projekt','Pos.':'Position','pz_bearbeitung':'Status','Bezeichnung':'Bezeichnung','mb-Modul':'mb-Modul','mb-Kennwert':'Kennwert'}
                for col,text in heads.items():
                    if col in cols:ptr.heading(col,text=text)
                widths={
                    'mb-Projekt':(100,82,False),
                    'Pos.':(74,64,False),
                    'pz_bearbeitung':(88,80,False),
                    'Bezeichnung':(225,150,True),
                    'mb-Modul':(72,62,False),
                    'mb-Kennwert':(58,52,False),
                }
                for col,(w,m,stretch) in widths.items():
                    if col in cols:ptr.column(col,width=w,minwidth=m,stretch=stretch,anchor='w')
                try:ptr.xview_moveto(0)
                except Exception:pass
                try:
                    if single:psx.grid_remove()
                    else:psx.grid()
                except Exception:pass
            except Exception:pass

'''
    s=s[:start]+block+s[end:]
    s=s.replace('_position_layout_1444()','_position_layout_1445()')
    return s


def _patch_global_search_index(s):
    if 'PZ_SEARCH_PROJECT_FILE_V1445' in s:
        return s
    old="""          ('documents',['category','filename','path'],'Dokument'),\n          ('tasks',['title','area','owner','source'],'Aufgabe')]:\n"""
    new="""          ('documents',['category','filename','path'],'Dokument'),\n          ('project_file_index',['filename','rel_path','category'],'Projektdatei'),\n          ('tasks',['title','area','owner','source'],'Aufgabe')]:\n"""
    s=_rep(s,old,new,'Globale Suche Projektdateien')
    marker="""                # PZ_SEARCH_DOCUMENT_OPEN_V1444\n                if area=='Dokument':\n"""
    if marker not in s:
        raise RuntimeError('1.4.45: Dokument-Öffnen der globalen Suche nicht gefunden.')
    insert=r'''                # PZ_SEARCH_PROJECT_FILE_V1445
                if area=='Projektdatei':
                    try:
                        parts=[x.strip() for x in target.split(' · ',1)]
                        filename=parts[0] if parts else target
                        relpath=parts[1] if len(parts)>1 else ''
                        con=db()
                        if relpath:
                            doc=con.execute('SELECT i.project_id,i.rel_path,p.folder_path,p.number,p.title FROM project_file_index i JOIN projects p ON p.id=i.project_id WHERE i.filename=? AND i.rel_path=? ORDER BY CASE WHEN i.project_id=? THEN 0 ELSE 1 END LIMIT 1',(filename,relpath,self.project_id)).fetchone()
                        else:
                            doc=con.execute('SELECT i.project_id,i.rel_path,p.folder_path,p.number,p.title FROM project_file_index i JOIN projects p ON p.id=i.project_id WHERE i.filename=? ORDER BY CASE WHEN i.project_id=? THEN 0 ELSE 1 END LIMIT 1',(filename,self.project_id)).fetchone()
                        con.close()
                        if not doc:
                            messagebox.showwarning('Projektsuche',f'Die Projektdatei konnte nicht aufgelöst werden:\n{target}',parent=w); return 'break'
                        raw_root=str(doc['folder_path'] or '').strip()
                        root=Path(raw_root) if raw_root else PROJECT_ROOT/re.sub(r'[^A-Za-z0-9._-]+','_',f"{doc['number']}_{doc['title']}")
                        path=root/str(doc['rel_path'])
                        if self.open_external_path(path):w.destroy()
                        return 'break'
                    except Exception as exc:
                        messagebox.showwarning('Projektsuche',f'Projektdatei konnte nicht geöffnet werden:\n{exc}',parent=w); return 'break'

'''
    s=s.replace(marker,insert+marker,1)
    return s


def main():
    if not APP.exists():raise RuntimeError(f'Installation nicht gefunden: {APP}')
    original=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.45"' in original:return 0
    if 'APP_VERSION = "1.4.44"' not in original:
        raise RuntimeError('Update 1.4.45 erwartet exakt Projektzentrale 1.4.44. Es wurde nichts verändert.')

    s=original
    for fn in (_patch_sidebar,_patch_statik_pdf_view,_patch_statik_quickaccess,_patch_project_explorer,_patch_metadata_folder,_patch_position_layout,_patch_global_search_index):
        s=fn(s)
    required=('PZ_STATIK_PDF_NAV_V1445','PZ_STATIK_PDF_VIEW_V1445','PZ_PROJECT_EXPLORER_OPEN_V1445','PZ_METADATA_DIR_V1445','PZ_POSITION_LAYOUT_V1445','PZ_SEARCH_PROJECT_FILE_V1445')
    missing=[x for x in required if x not in s]
    if missing:raise RuntimeError('1.4.45 unvollständig: '+', '.join(missing))

    _compile_text(s,'app.py.1445.features.check')
    s=s.replace('APP_VERSION = "1.4.44"','APP_VERSION = "1.4.45"',1)
    _compile_text(s,'app.py.1445.final.check')
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(APP,APP.with_name(f'app.py.vor_1445_{stamp}.bak'))
    tmp=APP.with_name('app.py.1445.tmp'); tmp.write_text(s,encoding='utf-8'); tmp.replace(APP)
    try:
        APP.with_name('patch_1445_report.txt').write_text(
            'Ausgangsversion: 1.4.44\n'
            'Projekt-Explorer: exakte Doppelklick-Zeile, Datei öffnen, Windows-Explorer, Enter\n'
            'Statik PDF: eigener Unterbereich mit Suche, Liste, Ordner öffnen\n'
            'Statik Schnellzugriff: Parent-Fehler korrigiert\n'
            'Positionsakte: Spaltenköpfe/Breiten, Einzelprojekt ohne Horizontalleiste\n'
            'Metadaten: Migration nach .engbers\\positionsakte.json / positionsplaene.json\n'
            'Globale Suche: indexierte Projektdateien such- und öffnbar\n',encoding='utf-8')
    except Exception:pass
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        try:(Path(__file__).resolve().parent/'patch_1445_error.txt').write_text(str(exc),encoding='utf-8')
        except Exception:pass
        raise SystemExit(1)
