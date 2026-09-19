from pathlib import Path
import py_compile, sys

ROOT=Path(sys.argv[1]).resolve()
APP=ROOT/"app.py"
POST=ROOT/"post_update.py"

def one(text, old, new, label):
    c=text.count(old)
    if c != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {c}")
    return text.replace(old,new,1)

app=APP.read_text(encoding="utf-8")
app=one(app,'APP_VERSION = "1.8.39"','APP_VERSION = "1.8.40"',"app version")

start=app.index("    def show_idea_statica(self):\n")
end=app.index("    def show_statics(self):\n",start)

method=r'''    def show_idea_statica(self):
        # PZ_IDEA_STATICA_V1840_EXPAND_FILES_SHARE
        self.clear()
        try:
            self.header.configure(text='IDEA StatiCa')
            for _n,_b in self.nav_buttons.items():
                _b.configure(bg=DARK2 if _n=='Statik' else DARK)
        except Exception:
            pass

        r=self.project_row()
        project_root=Path(self.get_project_folder(r))
        self.titleblock(
            self.content,
            'IDEA StatiCa',
            f"{r['number']} · {r['title']} · Anschluss aufklappen, Dateien auswählen und bei Bedarf freigeben"
        )

        def child_ci(parent,*names):
            if not parent or not parent.exists():
                return None
            wanted={str(n).casefold() for n in names}
            try:
                for p in parent.iterdir():
                    if p.is_dir() and p.name.casefold() in wanted:
                        return p
            except OSError:
                pass
            return None

        statik_root=child_ci(project_root,'Statik','02_Statik')
        if statik_root is None:
            statik_root=project_root/'02_Statik'
            statik_root.mkdir(parents=True,exist_ok=True)

        idea_candidates=[]
        try:
            for p in statik_root.iterdir():
                if not p.is_dir():
                    continue
                key=p.name.casefold().replace(' ','').replace('-','').replace('_','')
                if key in ('ideastatic','ideastatica'):
                    try:
                        score=sum(1 for _ in p.rglob('*'))
                    except Exception:
                        score=0
                    idea_candidates.append((score,p))
        except OSError:
            pass

        if idea_candidates:
            idea_candidates.sort(key=lambda x:(x[0],str(x[1]).casefold()),reverse=True)
            idea_root=idea_candidates[0][1]
        else:
            idea_root=statik_root/'IDEA StatiCa'
            idea_root.mkdir(parents=True,exist_ok=True)

        def open_path(path):
            if not path:
                return
            p=Path(path)
            try:
                if os.name=='nt':
                    os.startfile(str(p))
                elif sys.platform=='darwin':
                    os.system(f'open "{p}"')
                else:
                    os.system(f'xdg-open "{p}" >/dev/null 2>&1 &')
            except Exception as exc:
                messagebox.showerror('IDEA StatiCa',str(exc))

        def idea_kind(p):
            name=p.name.casefold()
            ext=p.suffix.casefold()
            if name.endswith('.ideacon'):
                return 'IDEA'
            if name.endswith('.ideacon.archiv'):
                return 'Archiv'
            if name.endswith('.ideacon.backup'):
                return 'Backup'
            if ext=='.ifc':
                return 'IFC 3D'
            if ext=='.pdf':
                return 'PDF'
            if ext in ('.docx','.doc'):
                return 'Word'
            return ext[1:].upper() if ext else 'Datei'

        def all_project_files():
            try:
                files=[p for p in idea_root.rglob('*') if p.is_file()]
                files.sort(key=lambda p:str(p).casefold())
                return files
            except OSError:
                return []

        def group_connections(files):
            active=[p for p in files if idea_kind(p)=='IDEA']
            groups=[]
            used=set()
            for p in active:
                token=p.name[:-len('.ideaCon')] if p.name.casefold().endswith('.ideacon') else p.stem
                low=token.casefold()
                related=[q for q in files if low and low in q.name.casefold()]
                bim=p.parent/'BIM'
                if bim.exists():
                    for q in files:
                        try:
                            if q.is_relative_to(bim) and q not in related:
                                related.append(q)
                        except Exception:
                            pass
                related.sort(key=lambda q:(
                    {'PDF':0,'Word':1,'IFC 3D':2,'IDEA':3,'Archiv':4,'Backup':5}.get(idea_kind(q),9),
                    q.name.casefold()
                ))
                for q in related:
                    used.add(q)
                groups.append({'name':token,'idea':p,'files':related,'folder':p.parent})
            loose=[p for p in files if p not in used]
            return groups,loose

        def file_size_text(path):
            try:
                n=float(path.stat().st_size)
            except OSError:
                return '—'
            for unit in ('B','KB','MB','GB'):
                if n<1024.0 or unit=='GB':
                    return f'{n:.0f} {unit}' if unit=='B' else f'{n:.1f} {unit}'
                n/=1024.0
            return '—'

        def changed_text(path):
            try:
                return datetime.datetime.fromtimestamp(path.stat().st_mtime).strftime('%d.%m.%Y %H:%M')
            except OSError:
                return '—'

        tools=tk.Frame(self.content,bg=BG)
        tools.pack(fill='x',pady=(0,12))
        tk.Button(
            tools,text='IDEA STATICA STARTEN',
            command=lambda:self.launch_configured_program('idea','IDEA StatiCa'),
            bg=ACCENT,fg='white',bd=0,padx=15,pady=8
        ).pack(side='left')
        tk.Button(
            tools,text='IDEA-ORDNER ÖFFNEN',
            command=lambda:open_path(idea_root),
            bg=DARK,fg='white',bd=0,padx=15,pady=8
        ).pack(side='left',padx=(8,0))

        def new_connection():
            w=tk.Toplevel(self)
            w.title('Neuer IDEA-Anschluss')
            w.geometry('520x220')
            w.configure(bg=BG)
            w.transient(self)
            w.grab_set()
            tk.Label(w,text='NEUER IDEA-ANSCHLUSS',bg=BG,fg=INK,font=('Segoe UI Semibold',13)).pack(anchor='w',padx=22,pady=(20,4))
            tk.Label(w,text='Positionsnummer oder kurze Bezeichnung, z. B. E.01.AN2',bg=BG,fg=MUTED,font=('Segoe UI',9)).pack(anchor='w',padx=22,pady=(0,10))
            e=tk.Entry(w,font=('Segoe UI',11))
            e.pack(fill='x',padx=22)
            e.focus_set()
            def create(_evt=None):
                raw=e.get().strip()
                if not raw:
                    return
                safe=re.sub(r'[<>:"/\\|?*]+','_',raw).strip(' .')
                if not safe:
                    return
                target=idea_root/safe
                try:
                    target.mkdir(parents=True,exist_ok=False)
                    (target/'BIM').mkdir(parents=True,exist_ok=True)
                except FileExistsError:
                    messagebox.showinfo('IDEA StatiCa','Dieser Anschlussordner ist bereits vorhanden.',parent=w)
                    return
                except Exception as exc:
                    messagebox.showerror('IDEA StatiCa',str(exc),parent=w)
                    return
                w.destroy()
                refresh()
                open_path(target)
            bar=tk.Frame(w,bg=BG); bar.pack(fill='x',padx=22,pady=20)
            tk.Button(bar,text='ANLEGEN',command=create,bg=ACCENT,fg='white',bd=0,padx=18,pady=8).pack(side='right')
            tk.Button(bar,text='ABBRECHEN',command=w.destroy,bg=DARK,fg='white',bd=0,padx=18,pady=8).pack(side='right',padx=(0,8))
            e.bind('<Return>',create)

        tk.Button(
            tools,text='NEUER ANSCHLUSS',
            command=new_connection,
            bg='#e7e4dc',fg=INK,bd=0,padx=15,pady=8
        ).pack(side='left',padx=(8,0))

        pan,body=self.panel(self.content,'IDEA StatiCa · Anschlüsse und Dateien')
        pan.pack(fill='both',expand=True,pady=(0,12))

        info=tk.Label(body,text=f'Ablage: {idea_root}',bg=PANEL,fg=MUTED,anchor='w',font=('Segoe UI',9))
        info.pack(fill='x',pady=(0,8))

        split=tk.Frame(body,bg=PANEL)
        split.pack(fill='both',expand=True)
        left=tk.Frame(split,bg=PANEL)
        left.pack(side='left',fill='both',expand=True)
        right=tk.Frame(split,bg='#f3f1ec',width=330)
        right.pack(side='right',fill='y',padx=(12,0))
        right.pack_propagate(False)

        cols=('Typ','Geändert','Größe')
        tree=ttk.Treeview(left,columns=cols,show='tree headings',height=14,selectmode='extended')
        tree.heading('#0',text='Anschluss / Datei')
        tree.column('#0',width=420,anchor='w')
        for c,wid in (('Typ',130),('Geändert',145),('Größe',85)):
            tree.heading(c,text=c)
            tree.column(c,width=wid,anchor='w')
        sy=ttk.Scrollbar(left,orient='vertical',command=tree.yview)
        tree.configure(yscrollcommand=sy.set)
        tree.pack(side='left',fill='both',expand=True)
        sy.pack(side='right',fill='y')

        tk.Label(right,text='AUSWAHL',bg='#f3f1ec',fg=INK,font=('Segoe UI Semibold',10),anchor='w').pack(fill='x',padx=14,pady=(14,8))
        preview=tk.Label(
            right,
            text='Anschluss oder Datei auswählen.',
            bg='#f3f1ec',fg=MUTED,justify='left',anchor='nw',wraplength=290
        )
        preview.pack(fill='both',expand=True,padx=14,pady=(0,10))

        group_by_parent={}
        path_by_iid={}

        def selected_iids():
            return list(tree.selection())

        def selected_files():
            out=[]
            for iid in selected_iids():
                p=path_by_iid.get(iid)
                if p and Path(p).is_file():
                    out.append(Path(p))
            return out

        def selected_group():
            sel=selected_iids()
            if not sel:
                return None
            iid=sel[0]
            if iid in group_by_parent:
                return group_by_parent[iid]
            parent=tree.parent(iid)
            return group_by_parent.get(parent)

        def first_of(g,kind):
            if not g:
                return None
            for p in g.get('files',[]):
                if idea_kind(p)==kind:
                    return p
            return None

        def update_preview(_evt=None):
            sel=selected_iids()
            if not sel:
                preview.configure(text='Anschluss oder Datei auswählen.')
                return
            if len(sel)>1:
                files=selected_files()
                preview.configure(text=f'{len(sel)} Einträge ausgewählt.\n\n{len(files)} Datei(en) können direkt in den Freigabekorb gelegt werden.')
                return
            iid=sel[0]
            p=path_by_iid.get(iid)
            if p:
                g=selected_group()
                rel=''
                try:
                    rel=str(Path(p).relative_to(idea_root))
                except Exception:
                    rel=Path(p).name
                preview.configure(
                    text=f'{Path(p).name}\n\nTyp: {idea_kind(Path(p))}\nGröße: {file_size_text(Path(p))}\nGeändert: {changed_text(Path(p))}\n\n{rel}\n\nDoppelklick öffnet diese Datei.'
                )
                return
            g=group_by_parent.get(iid)
            if g:
                kinds=[idea_kind(p) for p in g['files']]
                preview.configure(
                    text=(
                        f"{g['name']}\n\n"
                        f"IDEA-Datei: {'vorhanden' if 'IDEA' in kinds else 'fehlt'}\n"
                        f"IFC-Modell: {'vorhanden' if 'IFC 3D' in kinds else 'fehlt'}\n"
                        f"Berechnungs-PDF: {'vorhanden' if 'PDF' in kinds else 'fehlt'}\n"
                        f"Word-Nachweis: {'vorhanden' if 'Word' in kinds else 'fehlt'}\n"
                        f"Archiv / Backup: {sum(1 for k in kinds if k in ('Archiv','Backup'))} Datei(en)\n\n"
                        "Mit dem Pfeil links kannst du den Anschluss auf- und zuklappen."
                    )
                )

        def activate_selected(_evt=None):
            sel=selected_iids()
            if not sel:
                return
            iid=sel[0]
            p=path_by_iid.get(iid)
            if p:
                open_path(p)
                return
            if iid in group_by_parent:
                tree.item(iid,open=not bool(tree.item(iid,'open')))

        def open_idea():
            g=selected_group()
            if g and g.get('idea'):
                open_path(g['idea'])

        def open_connection_folder():
            g=selected_group()
            if g:
                open_path(g.get('folder') or idea_root)

        def add_selected_to_share_basket():
            files=selected_files()
            if not files:
                messagebox.showwarning(
                    'Freigabekorb',
                    'Bitte unter dem Anschluss eine oder mehrere Dateien auswählen.\n\nZum Beispiel das Berechnungsprotokoll als PDF.',
                    parent=self
                )
                return
            try:
                from share_basket_v1821 import add_items
                added,total=add_items(self.project_id,files,project_root,source='IDEA StatiCa')
                messagebox.showinfo(
                    'Freigabekorb',
                    f'{added} Datei(en) hinzugefügt.\n\nIm Korb: {total}',
                    parent=self
                )
            except Exception as exc:
                messagebox.showerror('Freigabekorb',str(exc),parent=self)

        def open_share_basket():
            try:
                from share_basket_v1821 import open_basket_dialog
                open_basket_dialog(
                    self,self.project_id,str(r['number'] or ''),str(r['title'] or ''),
                    db_path=DB_PATH
                )
            except Exception as exc:
                messagebox.showerror('Freigabekorb',str(exc),parent=self)

        def refresh():
            for iid in tree.get_children():
                tree.delete(iid)
            group_by_parent.clear()
            path_by_iid.clear()
            files=all_project_files()
            groups,loose=group_connections(files)
            for idx,g in enumerate(groups):
                parent=tree.insert(
                    '','end',
                    text=g['name'],
                    values=('IDEA-Anschluss',changed_text(g.get('idea') or g['files'][0]),''),
                    open=(idx==0)
                )
                group_by_parent[parent]=g
                for p in g['files']:
                    iid=tree.insert(
                        parent,'end',
                        text=p.name,
                        values=(idea_kind(p),changed_text(p),file_size_text(p))
                    )
                    path_by_iid[iid]=p
            if loose:
                parent=tree.insert('','end',text='Weitere Dateien',values=('Nicht zugeordnet','',''),open=False)
                for p in loose:
                    iid=tree.insert(parent,'end',text=p.name,values=(idea_kind(p),changed_text(p),file_size_text(p)))
                    path_by_iid[iid]=p
            info.configure(
                text=f'Ablage: {idea_root}   ·   {len(groups)} Anschluss/Anschlüsse erkannt'
                + (f'   ·   {len(loose)} weitere Datei(en)' if loose else '')
            )
            first=tree.get_children()
            if first:
                tree.selection_set(first[0]); tree.focus(first[0]); update_preview()
            else:
                preview.configure(
                    text='Noch kein IDEA-Anschluss erkannt.\n\nDie Projektzentrale erkennt echte *.ideaCon-Dateien automatisch und ordnet IFC, PDF, Word, Archiv und Backup anhand der Anschlussbezeichnung zu.'
                )

        tree.bind('<<TreeviewSelect>>',update_preview)
        tree.bind('<Double-1>',activate_selected)
        tree.bind('<Return>',activate_selected)

        menu=tk.Menu(self,tearoff=0)
        menu.add_command(label='Öffnen / Anschluss aufklappen',command=activate_selected)
        menu.add_separator()
        menu.add_command(label='Zur Projektfreigabe hinzufügen',command=add_selected_to_share_basket)
        menu.add_command(label='Freigabekorb öffnen',command=open_share_basket)
        def popup(e):
            iid=tree.identify_row(e.y)
            if iid:
                if iid not in tree.selection():
                    tree.selection_set(iid)
                tree.focus(iid)
                menu.tk_popup(e.x_root,e.y_root)
        tree.bind('<Button-3>',popup)

        actions=tk.Frame(body,bg=PANEL)
        actions.pack(fill='x',pady=(10,0))
        tk.Button(actions,text='IN IDEA ÖFFNEN',command=open_idea,bg=ACCENT,fg='white',bd=0,padx=13,pady=7).pack(side='left')
        tk.Button(actions,text='DATEI ÖFFNEN',command=activate_selected,bg=DARK,fg='white',bd=0,padx=13,pady=7).pack(side='left',padx=(8,0))
        tk.Button(actions,text='ZUR FREIGABE',command=add_selected_to_share_basket,bg=ACCENT,fg='white',bd=0,padx=13,pady=7).pack(side='left',padx=(8,0))
        tk.Button(actions,text='FREIGABEKORB',command=open_share_basket,bg=DARK,fg='white',bd=0,padx=13,pady=7).pack(side='left',padx=(8,0))
        tk.Button(actions,text='ANSCHLUSS-ORDNER',command=open_connection_folder,bg='#e7e4dc',fg=INK,bd=0,padx=13,pady=7).pack(side='left',padx=(8,0))
        tk.Button(actions,text='AKTUALISIEREN',command=refresh,bg='#e7e4dc',fg=INK,bd=0,padx=13,pady=7).pack(side='left',padx=(8,0))

        note=tk.Label(
            self.content,
            text='1.8.40 · Anschluss aufklappen: PDF, Word, IFC, IDEA, Archiv und Backup sind einzeln sichtbar und auswählbar. Ausgewählte Dateien können direkt in den bestehenden Freigabekorb gelegt werden.',
            bg=BG,fg=MUTED,anchor='w',justify='left',wraplength=1100,font=('Segoe UI',9)
        )
        note.pack(fill='x',pady=(0,4))

        refresh()

'''

app=app[:start]+method+app[end:]
APP.write_text(app,encoding="utf-8")

post=POST.read_text(encoding="utf-8")
post=post.replace("update_1839_install.log","update_1840_install.log")
post=post.replace("update_1839_error.txt","update_1840_error.txt")
post=one(post,'APP_VERSION = "1.8.39"','APP_VERSION = "1.8.40"',"post version")
post=post.replace("OK: Update 1.8.39 erfolgreich installiert.","OK: Update 1.8.40 erfolgreich installiert.")
POST.write_text(post,encoding="utf-8")

for p in (APP,POST):
    py_compile.compile(str(p),doraise=True)

a=APP.read_text(encoding="utf-8")
for marker in (
    "PZ_IDEA_STATICA_V1840_EXPAND_FILES_SHARE",
    "show='tree headings'",
    "ZUR FREIGABE",
    "source='IDEA StatiCa'",
    "open_basket_dialog",
    "Mit dem Pfeil links kannst du den Anschluss auf- und zuklappen."
):
    assert marker in a, marker
print("OK 1.8.40 expandable IDEA files + share basket")
