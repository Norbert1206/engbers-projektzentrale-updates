from pathlib import Path
import datetime
import py_compile
import shutil

APP = Path(__file__).resolve().parent / 'app.py'


def _compile_text(text, name):
    p = APP.with_name(name)
    try:
        p.write_text(text, encoding='utf-8')
        py_compile.compile(str(p), doraise=True)
    finally:
        try:
            p.unlink()
        except Exception:
            pass


def _replace_once(s, old, new, label):
    if old not in s:
        raise RuntimeError('1.4.49: Abschnitt nicht gefunden: ' + label)
    return s.replace(old, new, 1)


def _patch_statik_pdf_tree(s):
    start = s.find('    def show_statik_pdf(self):\n')
    end = s.find('    def show_statics(self):\n', start)
    if start < 0 or end < 0:
        raise RuntimeError('1.4.49: Statik-PDF-Bereich konnte nicht gefunden werden.')
    block = r'''    def show_statik_pdf(self):
        # PZ_STATIK_PDF_TREE_V1449: Explorer-artige Ordnerstruktur für Statik-PDF.
        self.clear()
        try:
            self.header.configure(text='Statik PDF')
            for _n,_b in self.nav_buttons.items():
                _b.configure(bg=DARK2 if _n=='Statik' else DARK)
        except Exception:
            pass
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
        tk.Button(tools,text='← ZURÜCK ZUR STATIK',command=lambda:self.navigate('Statik',self.show_statics),bg='#e7e4dc',fg=INK,bd=0,padx=12,pady=7).pack(side='left',padx=(0,10))
        info=tk.Label(tools,text='',bg=BG,fg=MUTED,anchor='w'); info.pack(side='left',fill='x',expand=True)
        search_var=tk.StringVar()
        tk.Label(tools,text='Suche:',bg=BG,fg=MUTED).pack(side='left',padx=(8,4))
        search_entry=tk.Entry(tools,textvariable=search_var,width=24); search_entry.pack(side='left')

        pan,body=self.panel(self.content,'Statik PDF · Ordnerstruktur'); pan.pack(fill='both',expand=True)
        cols=('Typ','Geändert','Größe')
        tree=ttk.Treeview(body,columns=cols,show='tree headings',height=22)
        tree.heading('#0',text='Ordner / PDF-Datei'); tree.column('#0',width=760,minwidth=320,stretch=True,anchor='w')
        for col,w,m in (('Typ',90,70),('Geändert',145,125),('Größe',90,70)):
            tree.heading(col,text=col); tree.column(col,width=w,minwidth=m,stretch=False,anchor='w')
        sy=ttk.Scrollbar(body,orient='vertical',command=tree.yview); tree.configure(yscrollcommand=sy.set)
        tree.grid(row=0,column=0,sticky='nsew'); sy.grid(row=0,column=1,sticky='ns')
        body.grid_rowconfigure(0,weight=1); body.grid_columnconfigure(0,weight=1)
        pathmap={}

        def human_size(size):
            try:
                size=float(size)
                for unit in ('B','KB','MB','GB'):
                    if size<1024 or unit=='GB':
                        return f'{size:.0f} {unit}' if unit=='B' else f'{size:.1f} {unit}'
                    size/=1024
            except Exception:
                return '—'

        def changed_text(p):
            try:return datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime('%d.%m.%Y %H:%M')
            except Exception:return '—'

        def selected_path(event=None):
            iid=''
            if event is not None:
                try:iid=tree.identify_row(event.y)
                except Exception:iid=''
            if not iid:
                sel=tree.selection(); iid=sel[0] if sel else ''
            if iid:
                try:tree.selection_set(iid); tree.focus(iid)
                except Exception:pass
            return pathmap.get(iid),iid

        def expand_branch(iid):
            try:tree.item(iid,open=True)
            except Exception:pass
            for child in tree.get_children(iid):
                p=pathmap.get(child)
                if p is not None and p.is_dir():expand_branch(child)

        def expand_all():
            for iid in tree.get_children(''):expand_branch(iid)

        def collapse_all():
            def close(iid):
                for child in tree.get_children(iid):close(child)
                try:tree.item(iid,open=False)
                except Exception:pass
            for iid in tree.get_children(''):close(iid)

        def refresh(*_):
            for iid in tree.get_children(''):tree.delete(iid)
            pathmap.clear(); folder=find_folder(); q=search_var.get().strip().casefold()
            all_pdfs=[]
            if folder.exists():
                try:
                    all_pdfs=[p for p in folder.rglob('*.pdf') if p.is_file()]
                except Exception:all_pdfs=[]
            all_pdfs.sort(key=lambda p:str(p.relative_to(folder)).casefold() if folder.exists() else p.name.casefold())
            matched=[]
            for p in all_pdfs:
                try:rel=p.relative_to(folder)
                except Exception:rel=Path(p.name)
                hay=(p.name+' '+str(rel)).casefold()
                if not q or q in hay:matched.append(p)

            needed={folder} if folder.exists() else set()
            by_parent={}
            for p in matched:
                by_parent.setdefault(p.parent,[]).append(p)
                d=p.parent
                while folder.exists() and d!=folder:
                    needed.add(d); d=d.parent
                if folder.exists():needed.add(folder)
            child_dirs={}
            for d in needed:
                if d!=folder:child_dirs.setdefault(d.parent,[]).append(d)
            for vals in child_dirs.values():vals.sort(key=lambda p:p.name.casefold())
            for vals in by_parent.values():vals.sort(key=lambda p:p.name.casefold())

            def add_dir(parent_iid,d):
                iid=tree.insert(parent_iid,'end',text=d.name,values=('Ordner',changed_text(d),'—'),open=bool(q))
                pathmap[iid]=d
                for cd in child_dirs.get(d,[]):add_dir(iid,cd)
                for p in by_parent.get(d,[]):
                    try:size=human_size(p.stat().st_size)
                    except Exception:size='—'
                    fid=tree.insert(iid,'end',text=p.name,values=('PDF',changed_text(p),size))
                    pathmap[fid]=p

            if folder.exists():
                for d in child_dirs.get(folder,[]):add_dir('',d)
                for p in by_parent.get(folder,[]):
                    try:size=human_size(p.stat().st_size)
                    except Exception:size='—'
                    fid=tree.insert('','end',text=p.name,values=('PDF',changed_text(p),size)); pathmap[fid]=p
            info.config(text=(f'{len(matched)} von {len(all_pdfs)} PDF-Datei(en) · {folder}' if folder.exists() else f'Ordner noch nicht vorhanden · {folder}'))
            if q:expand_all()

        def open_selected(event=None):
            p,iid=selected_path(event)
            if not p:return 'break'
            if p.is_dir():
                try:tree.item(iid,open=not bool(tree.item(iid,'open')))
                except Exception:pass
            else:self.open_external_path(p)
            return 'break'

        def show_in_explorer():
            p,_=selected_path()
            if not p:return
            try:
                if os.name=='nt' and p.is_file():subprocess.Popen(['explorer','/select,',str(p)])
                else:self.open_external_path(p if p.is_dir() else p.parent)
            except Exception as exc:messagebox.showerror('Statik PDF',str(exc))

        def copy_path():
            p,_=selected_path()
            if not p:return
            try:self.clipboard_clear(); self.clipboard_append(str(p)); self.update_idletasks()
            except Exception:pass

        def open_folder():
            folder=find_folder()
            if not folder.exists():
                if not messagebox.askyesno('Statik PDF',f'Der Ordner ist noch nicht vorhanden:\n{folder}\n\nJetzt anlegen?'):return
                try:folder.mkdir(parents=True,exist_ok=True)
                except Exception as exc:messagebox.showerror('Statik PDF',str(exc)); return
            self.open_external_path(folder); refresh()

        tk.Button(tools,text='ORDNER ÖFFNEN',command=open_folder,bg=DARK,fg='white',bd=0,padx=13,pady=7).pack(side='right',padx=(6,0))
        tk.Button(tools,text='AKTUALISIEREN',command=refresh,bg='#e7e4dc',fg=INK,bd=0,padx=13,pady=7).pack(side='right',padx=(6,0))
        tk.Button(tools,text='ZUKLAPPEN',command=collapse_all,bg='#e7e4dc',fg=INK,bd=0,padx=10,pady=7).pack(side='right',padx=(6,0))
        tk.Button(tools,text='AUFKLAPPEN',command=expand_all,bg='#e7e4dc',fg=INK,bd=0,padx=10,pady=7).pack(side='right',padx=(6,0))

        menu=tk.Menu(self,tearoff=0)
        menu.add_command(label='Öffnen',command=open_selected)
        menu.add_command(label='Im Windows-Explorer zeigen',command=show_in_explorer)
        menu.add_command(label='Pfad kopieren',command=copy_path)
        def popup(e):
            iid=tree.identify_row(e.y)
            if iid:
                tree.selection_set(iid); tree.focus(iid); menu.tk_popup(e.x_root,e.y_root)
        tree.bind('<Button-3>',popup)
        tree.bind('<Double-1>',open_selected); tree.bind('<Return>',open_selected)
        tree.bind('<Control-c>',lambda _e:(copy_path(),'break')[1])
        search_var.trace_add('write',lambda *_:refresh())
        search_entry.bind('<Escape>',lambda _e:search_var.set(''))
        refresh()

'''
    return s[:start] + block + s[end:]


def _patch_project_explorer(s):
    if 'PZ_PROJECT_EXPLORER_CONTEXT_V1449' in s:
        return s
    marker = "        categories=('Baugrund / Bodengutachten','Statik','Prüfstatik','Pläne / CAD','Wärmeschutz','Schallschutz','DGNB/QNG','Bauleitung','Kommunikation','Bescheinigungen','Dokumente','Fotos / Bilder','Sonstiges')\n"
    if marker not in s:
        raise RuntimeError('1.4.49: Projekt-Explorer Kontextstelle nicht gefunden.')
    insert = r'''        # PZ_PROJECT_EXPLORER_CONTEXT_V1449: Pfadkopie, Auf-/Zuklappen und F5.
        def copy_selected_path():
            pp,_,_=selected()
            if not pp:return
            try:self.clipboard_clear(); self.clipboard_append(str(pp)); self.update_idletasks()
            except Exception:pass
        def expand_all_project_tree():
            def walk(iid):
                pp=pathmap.get(iid); root=rootmap.get(iid)
                if pp is not None and pp.is_dir():
                    _load_folder(iid,pp,root)
                    try:tr.item(iid,open=True)
                    except Exception:pass
                for child in tr.get_children(iid):walk(child)
            for iid in tr.get_children(''):walk(iid)
        def collapse_all_project_tree():
            def walk(iid):
                for child in tr.get_children(iid):walk(child)
                try:tr.item(iid,open=False)
                except Exception:pass
            for iid in tr.get_children(''):walk(iid)
        extra_btns=tk.Frame(right,bg=PANEL); extra_btns.pack(fill='x',padx=12,pady=(0,8))
        tk.Button(extra_btns,text='PFAD KOPIEREN',command=copy_selected_path,bg='#e7e4dc',fg=INK,bd=0,padx=9,pady=6).pack(side='left')
        tk.Button(extra_btns,text='AUFKLAPPEN',command=expand_all_project_tree,bg='#e7e4dc',fg=INK,bd=0,padx=9,pady=6).pack(side='left',padx=(6,0))
        tk.Button(extra_btns,text='ZUKLAPPEN',command=collapse_all_project_tree,bg='#e7e4dc',fg=INK,bd=0,padx=9,pady=6).pack(side='left',padx=(6,0))
'''
    s=s.replace(marker,insert+marker,1)
    old_menu="        menu=tk.Menu(self,tearoff=0); menu.add_command(label='Fachlich zuordnen…',command=assign); menu.add_command(label='Original öffnen',command=open_original); menu.add_command(label='Im Windows-Explorer zeigen',command=show_in_windows_explorer)\n"
    new_menu="        menu=tk.Menu(self,tearoff=0); menu.add_command(label='Fachlich zuordnen…',command=assign); menu.add_command(label='Original öffnen',command=open_original); menu.add_command(label='Im Windows-Explorer zeigen',command=show_in_windows_explorer); menu.add_separator(); menu.add_command(label='Pfad kopieren',command=copy_selected_path)\n"
    s=_replace_once(s,old_menu,new_menu,'Projekt-Explorer Kontextmenü')
    old_bind="        tr.bind('<<TreeviewOpen>>',on_open); tr.bind('<Double-1>',on_double); tr.bind('<Return>',on_double); tr.bind('<<TreeviewSelect>>',refresh)\n"
    new_bind="        tr.bind('<<TreeviewOpen>>',on_open); tr.bind('<Double-1>',on_double); tr.bind('<Return>',on_double); tr.bind('<<TreeviewSelect>>',refresh); tr.bind('<Control-c>',lambda _e:(copy_selected_path(),'break')[1]); tr.bind('<F5>',lambda _e:self.show_project_explorer())\n"
    s=_replace_once(s,old_bind,new_bind,'Projekt-Explorer Tastatur')
    return s


def _patch_position_layout(s):
    if 'def _position_layout_1449()' in s:
        return s
    start=s.find('        def _position_layout_1445():\n')
    end=s.find('        # 1.4.35: Bearbeitungsstatus kompakt direkt hinter der Positionsspalte.\n',start)
    if start<0 or end<0:
        raise RuntimeError('1.4.49: Positionslayout 1.4.45 nicht gefunden.')
    block=r'''        def _position_layout_1449():
            # PZ_POSITION_LAYOUT_V1449: kompakt in Gesamt- und Einzelakte, ohne horizontales Scrollen.
            try:
                cols=list(ptr.cget('columns'))
                required=('Pos.','pz_bearbeitung','Bezeichnung','mb-Modul','mb-Kennwert')
                if not all(c in cols for c in required):return
                single=bool(current_project.get('folder'))
                display=required if single else ('mb-Projekt',)+required
                ptr.configure(displaycolumns=tuple(c for c in display if c in cols))
                ptr.heading('#0',text='Gruppe'); ptr.column('#0',width=78,minwidth=68,stretch=False,anchor='w')
                heads={'mb-Projekt':'mb-Projekt','Pos.':'Position','pz_bearbeitung':'Status','Bezeichnung':'Bezeichnung','mb-Modul':'mb-Modul','mb-Kennwert':'Kennwert'}
                widths={'mb-Projekt':(86,74,False),'Pos.':(68,60,False),'pz_bearbeitung':(76,70,False),'Bezeichnung':(170,115,True),'mb-Modul':(66,58,False),'mb-Kennwert':(50,46,False)}
                for col,text in heads.items():
                    if col in cols:ptr.heading(col,text=text)
                for col,(w,m,stretch) in widths.items():
                    if col in cols:ptr.column(col,width=w,minwidth=m,stretch=stretch,anchor='w')
                try:ptr.xview_moveto(0); psx.grid_remove()
                except Exception:pass
            except Exception:pass

'''
    s=s[:start]+block+s[end:]
    s=s.replace('_position_layout_1445()','_position_layout_1449()')
    return s


def _patch_position_context(s):
    if 'PZ_POSITION_CONTEXT_V1449' in s:
        return s
    marker="        ptr.bind('<<TreeviewSelect>>',position_selected)\n"
    if marker not in s:
        raise RuntimeError('1.4.49: Positionsauswahl-Bindung nicht gefunden.')
    block=r'''        # PZ_POSITION_CONTEXT_V1449: häufige Aktionen direkt per Rechtsklick.
        def _position_context_data():
            sel=ptr.selection()
            if not sel:return None,None,None
            row=item_rows.get(sel[0])
            if not row:return None,None,None
            folder=row.get('_folder') or current_project.get('folder')
            if not folder:return row,None,str(row.get('pos') or '')
            return row,Path(folder),str(row.get('pos') or '')
        def _ctx_mb_open():
            row,folder,pos=_position_context_data()
            if row and folder:_mb_open_project_application(folder,_mb_application_for_position(folder,row),pos)
        def _ctx_status():
            row,folder,pos=_position_context_data()
            if folder and pos:_position_set_status(folder,pos,detail_text)
        def _ctx_note():
            row,folder,pos=_position_context_data()
            if folder and pos:_position_edit_note(folder,pos,detail_text)
        def _ctx_link():
            row,folder,pos=_position_context_data()
            if folder and pos:_position_link_file(folder,pos)
        def _ctx_unlink():
            row,folder,pos=_position_context_data()
            if folder and pos:_position_unlink_file(folder,pos)
        def _ctx_plan():
            row,folder,pos=_position_context_data()
            if folder and pos:_position_assign_plan(folder,pos)
        def _ctx_plan_remove():
            row,folder,pos=_position_context_data()
            if folder and pos:_position_remove_manual_plan(folder,pos)
        _pos_menu=tk.Menu(self,tearoff=0)
        _pos_menu.add_command(label='mb öffnen',command=_ctx_mb_open)
        _pos_menu.add_separator()
        _pos_menu.add_command(label='Status ändern …',command=_ctx_status)
        _pos_menu.add_command(label='Notiz bearbeiten …',command=_ctx_note)
        _pos_menu.add_separator()
        _pos_menu.add_command(label='Datei mit Position verknüpfen …',command=_ctx_link)
        _pos_menu.add_command(label='Dateiverknüpfung entfernen …',command=_ctx_unlink)
        _pos_menu.add_command(label='Positionsplan zuordnen …',command=_ctx_plan)
        _pos_menu.add_command(label='Positionsplan-Zuordnung entfernen …',command=_ctx_plan_remove)
        def _position_popup(e):
            iid=ptr.identify_row(e.y)
            if iid:
                try:ptr.selection_set(iid); ptr.focus(iid); position_selected()
                except Exception:pass
                _pos_menu.tk_popup(e.x_root,e.y_root)
            return 'break'
        ptr.bind('<Button-3>',_position_popup)
'''
    return s.replace(marker,block+marker,1)


def _patch_remember_mb(s):
    if 'PZ_REMEMBER_MB_PROJECT_V1449' in s:
        return s
    old="""                iid=sel[0]; target=item_paths.get(iid)\n                if item_names.get(iid)=='ALLE mb-PROJEKTE': load_all_positions()\n                elif target: load_positions(target,item_names.get(iid,target.name))\n"""
    new="""                iid=sel[0]; target=item_paths.get(iid)\n                # PZ_REMEMBER_MB_PROJECT_V1449\n                try:self._pz_last_mb_project=(self.project_id,item_names.get(iid))\n                except Exception:pass\n                if item_names.get(iid)=='ALLE mb-PROJEKTE': load_all_positions()\n                elif target: load_positions(target,item_names.get(iid,target.name))\n"""
    s=_replace_once(s,old,new,'mb-Projekt Auswahl merken')
    old2="""            first=tr.get_children()\n            if first:\n                tr.selection_set(first[0]); tr.focus(first[0]); load_all_positions()\n"""
    new2="""            first=tr.get_children()\n            if first:\n                _chosen=first[0]\n                try:\n                    _last=getattr(self,'_pz_last_mb_project',None)\n                    if _last and _last[0]==self.project_id:\n                        for _iid in first:\n                            if item_names.get(_iid)==_last[1]:\n                                _chosen=_iid; break\n                except Exception:pass\n                tr.selection_set(_chosen); tr.focus(_chosen); select_mb_project()\n"""
    return _replace_once(s,old2,new2,'mb-Projekt Auswahl wiederherstellen')


def _patch_search_keep_view(s):
    if 'PZ_SEARCH_KEEP_VIEW_V1449' in s:
        return s
    old="""                active=None\n                for label,button in self.nav_buttons.items():\n                    try:\n                        if str(button.cget('bg')).lower()==str(DARK2).lower():\n                            active=label\n                            break\n                    except Exception:\n                        pass\n\n                self.project_id=pid\n"""
    new="""                active=None\n                for label,button in self.nav_buttons.items():\n                    try:\n                        if str(button.cget('bg')).lower()==str(DARK2).lower():\n                            active=label\n                            break\n                    except Exception:\n                        pass\n                # PZ_SEARCH_KEEP_VIEW_V1449\n                try:active_view=str(self.header.cget('text') or '')\n                except Exception:active_view=''\n\n                self.project_id=pid\n"""
    s=_replace_once(s,old,new,'Globale Suche aktuelle Ansicht')
    old2="""                def finish_switch():\n                    if active and active in self.nav_buttons:\n"""
    new2="""                def finish_switch():\n                    if active_view=='Statik PDF' and hasattr(self,'show_statik_pdf'):\n                        self.show_statik_pdf(); return\n                    if active and active in self.nav_buttons:\n"""
    return _replace_once(s,old2,new2,'Globale Suche Ansicht wieder öffnen')


def transform(s):
    for fn in (_patch_statik_pdf_tree,_patch_project_explorer,_patch_position_layout,_patch_position_context,_patch_remember_mb,_patch_search_keep_view):
        s=fn(s)
    required=('PZ_STATIK_PDF_TREE_V1449','PZ_PROJECT_EXPLORER_CONTEXT_V1449','PZ_POSITION_LAYOUT_V1449','PZ_POSITION_CONTEXT_V1449','PZ_REMEMBER_MB_PROJECT_V1449','PZ_SEARCH_KEEP_VIEW_V1449')
    missing=[x for x in required if x not in s]
    if missing:raise RuntimeError('1.4.49 unvollständig: '+', '.join(missing))
    return s


def main():
    if not APP.exists():raise RuntimeError(f'Installation nicht gefunden: {APP}')
    original=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.49"' in original:return 0
    if 'APP_VERSION = "1.4.48"' not in original:
        raise RuntimeError('Update 1.4.49 erwartet exakt Projektzentrale 1.4.48. Es wurde nichts verändert.')
    s=transform(original)
    _compile_text(s,'app.py.1449.features.check')
    s=s.replace('APP_VERSION = "1.4.48"','APP_VERSION = "1.4.49"',1)
    _compile_text(s,'app.py.1449.final.check')
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(APP,APP.with_name(f'app.py.vor_1449_{stamp}.bak'))
    tmp=APP.with_name('app.py.1449.tmp'); tmp.write_text(s,encoding='utf-8'); tmp.replace(APP)
    try:
        APP.with_name('patch_1449_report.txt').write_text(
            'Ausgangsversion: 1.4.48\n'
            'Statik PDF: Explorer-Baum mit echten Ordnern, Suche, Auf-/Zuklappen, Kontextmenü\n'
            'Projekt-Explorer: Pfad kopieren, Auf-/Zuklappen, F5\n'
            'Positionsakte: Gesamt- und Einzelakte ohne horizontales Scrollen\n'
            'Positionsakte: Rechtsklick mit Status/Notiz/Datei/Positionsplan/mb öffnen\n'
            'Statik: zuletzt gewähltes mb-Projekt wird pro Sitzung gemerkt\n'
            'Globale Suche: Statik-PDF-Ansicht bleibt beim Projektwechsel erhalten\n',encoding='utf-8')
    except Exception:pass
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        try:(Path(__file__).resolve().parent/'patch_1449_error.txt').write_text(str(exc),encoding='utf-8')
        except Exception:pass
        raise SystemExit(1)
