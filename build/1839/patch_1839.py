from pathlib import Path
import py_compile, re, sys

ROOT=Path(sys.argv[1]).resolve()
APP=ROOT/"app.py"
POST=ROOT/"post_update.py"

def one(text, old, new, label):
    c=text.count(old)
    if c != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {c}")
    return text.replace(old,new,1)

app=APP.read_text(encoding="utf-8")
app=one(app,'APP_VERSION = "1.8.38"','APP_VERSION = "1.8.39"',"app version")

# New projects: IDEA root only. Each connection can get its own folder/BIM subfolder later.
app=one(
    app,
    "(root/'02_Statik'/'IDEA StatiCa'/'BIM Anschluss').mkdir(parents=True,exist_ok=True)",
    "(root/'02_Statik'/'IDEA StatiCa').mkdir(parents=True,exist_ok=True)",
    "future IDEA root"
)

start=app.index("    def show_idea_statica(self):\n")
end=app.index("    def show_statics(self):\n",start)

method=r'''    def show_idea_statica(self):
        # PZ_IDEA_STATICA_V1839_REAL_STRUCTURE
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
            f"{r['number']} · {r['title']} · Anschlüsse automatisch aus IDEA-Dateien zusammenfassen"
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

        # Existing user folders such as "Idea Static" are preferred.
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
                return 'IFC'
            if ext=='.pdf':
                return 'PDF'
            if ext in ('.docx','.doc'):
                return 'Word'
            return 'Sonstiges'

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
                # Also keep the BIM subfolder content if this IDEA file is already inside a per-connection folder.
                bim=p.parent/'BIM'
                if bim.exists():
                    for q in files:
                        try:
                            if q.is_relative_to(bim) and q not in related:
                                related.append(q)
                        except Exception:
                            pass
                for q in related:
                    used.add(q)
                groups.append({'name':token,'idea':p,'files':related,'folder':p.parent})
            loose=[p for p in files if p not in used]
            return groups,loose

        def newest_text(files):
            stamps=[]
            for p in files:
                try:
                    stamps.append(p.stat().st_mtime)
                except OSError:
                    pass
            if not stamps:
                return '—'
            return datetime.datetime.fromtimestamp(max(stamps)).strftime('%d.%m.%Y %H:%M')

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

        pan,body=self.panel(self.content,'IDEA StatiCa · Anschlüsse')
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

        cols=('Anschluss','IDEA','IFC','PDF','Word','Archiv','Geändert')
        tree=ttk.Treeview(left,columns=cols,show='headings',height=13)
        widths={'Anschluss':220,'IDEA':65,'IFC':55,'PDF':55,'Word':60,'Archiv':70,'Geändert':145}
        for c in cols:
            tree.heading(c,text=c)
            tree.column(c,width=widths[c],anchor='w')
        sy=ttk.Scrollbar(left,orient='vertical',command=tree.yview)
        tree.configure(yscrollcommand=sy.set)
        tree.pack(side='left',fill='both',expand=True)
        sy.pack(side='right',fill='y')

        tk.Label(right,text='ANSCHLUSS',bg='#f3f1ec',fg=INK,font=('Segoe UI Semibold',10),anchor='w').pack(fill='x',padx=14,pady=(14,8))
        preview=tk.Label(
            right,
            text='Anschluss auswählen.',
            bg='#f3f1ec',fg=MUTED,justify='left',anchor='nw',wraplength=290
        )
        preview.pack(fill='both',expand=True,padx=14,pady=(0,10))

        groups_by_iid={}

        def selected_group():
            sel=tree.selection()
            return groups_by_iid.get(sel[0]) if sel else None

        def first_of(g,kind):
            for p in g.get('files',[]):
                if idea_kind(p)==kind:
                    return p
            return None

        def ifc_summary(ifc):
            if not ifc or not Path(ifc).is_file():
                return ''
            try:
                text=Path(ifc).read_text(encoding='utf-8',errors='ignore')
                beam=text.count('IFCBEAM(')
                plate=text.count('IFCPLATE(')
                mech=text.count('IFCMECHANICALFASTENER(')
                weld=text.count("IFCFASTENER(")
                project=''
                m=re.search(r"IFCPROJECT\\([^\\n]*?'([^']*)'",text,re.I)
                if m:
                    project=m.group(1)
                parts=[]
                if project:
                    parts.append(f'Modell: {project}')
                if beam:
                    parts.append(f'{beam} Profile')
                if plate:
                    parts.append(f'{plate} Platten')
                if mech:
                    parts.append(f'{mech} Schraubenelement/-gruppe')
                if weld:
                    parts.append(f'{weld} Schweißnaht-Elemente')
                return ' · '.join(parts)
            except Exception:
                return 'IFC-Modell erkannt'

        def update_preview(_evt=None):
            g=selected_group()
            if not g:
                return
            ifc=first_of(g,'IFC')
            pdf=first_of(g,'PDF')
            word=first_of(g,'Word')
            archiv=[p for p in g['files'] if idea_kind(p) in ('Archiv','Backup')]
            lines=[
                g['name'],
                '',
                'IDEA-Datei: vorhanden' if g.get('idea') else 'IDEA-Datei: fehlt',
                'IFC-Modell: vorhanden' if ifc else 'IFC-Modell: fehlt',
                'Berechnungs-PDF: vorhanden' if pdf else 'Berechnungs-PDF: fehlt',
                'Word-Nachweis: vorhanden' if word else 'Word-Nachweis: fehlt',
                f'Archiv / Backup: {len(archiv)} Datei(en)',
            ]
            if ifc:
                summary=ifc_summary(ifc)
                if summary:
                    lines.extend(['',summary,'','IFC ist die Grundlage für die geplante drehbare 3D-Vorschau.'])
            preview.configure(text='\\n'.join(lines))

        def open_idea():
            g=selected_group()
            if g and g.get('idea'):
                open_path(g['idea'])

        def open_pdf():
            g=selected_group()
            p=first_of(g,'PDF') if g else None
            if p:
                open_path(p)
            elif g:
                messagebox.showinfo('IDEA StatiCa','Für diesen Anschluss wurde kein PDF gefunden.')

        def open_ifc():
            g=selected_group()
            p=first_of(g,'IFC') if g else None
            if p:
                open_path(p)
            elif g:
                messagebox.showinfo('IDEA StatiCa','Für diesen Anschluss wurde kein IFC-Modell gefunden.')

        def open_connection_folder():
            g=selected_group()
            if g:
                open_path(g.get('folder') or idea_root)

        def refresh():
            for iid in tree.get_children():
                tree.delete(iid)
            groups_by_iid.clear()
            files=all_project_files()
            groups,loose=group_connections(files)
            for g in groups:
                kinds=[idea_kind(p) for p in g['files']]
                vals=(
                    g['name'],
                    '✓',
                    '✓' if 'IFC' in kinds else '—',
                    '✓' if 'PDF' in kinds else '—',
                    '✓' if 'Word' in kinds else '—',
                    str(sum(1 for k in kinds if k in ('Archiv','Backup'))) or '—',
                    newest_text(g['files'])
                )
                iid=tree.insert('','end',values=vals)
                groups_by_iid[iid]=g
            info.configure(
                text=f'Ablage: {idea_root}   ·   {len(groups)} Anschluss/Anschlüsse erkannt'
                + (f'   ·   {len(loose)} weitere Datei(en)' if loose else '')
            )
            first=tree.get_children()
            if first:
                tree.selection_set(first[0]); tree.focus(first[0]); update_preview()
            else:
                preview.configure(
                    text='Noch kein IDEA-Anschluss erkannt.\\n\\nDie Projektzentrale erkennt echte *.ideaCon-Dateien automatisch und ordnet IFC, PDF, Word, Archiv und Backup anhand der Anschlussbezeichnung zu.'
                )

        tree.bind('<<TreeviewSelect>>',update_preview)
        tree.bind('<Double-1>',lambda _e:open_idea())
        tree.bind('<Return>',lambda _e:open_idea())

        actions=tk.Frame(body,bg=PANEL)
        actions.pack(fill='x',pady=(10,0))
        tk.Button(actions,text='IN IDEA ÖFFNEN',command=open_idea,bg=ACCENT,fg='white',bd=0,padx=13,pady=7).pack(side='left')
        tk.Button(actions,text='PDF ÖFFNEN',command=open_pdf,bg=DARK,fg='white',bd=0,padx=13,pady=7).pack(side='left',padx=(8,0))
        tk.Button(actions,text='IFC ÖFFNEN',command=open_ifc,bg=DARK,fg='white',bd=0,padx=13,pady=7).pack(side='left',padx=(8,0))
        tk.Button(actions,text='ANSCHLUSS-ORDNER',command=open_connection_folder,bg='#e7e4dc',fg=INK,bd=0,padx=13,pady=7).pack(side='left',padx=(8,0))
        tk.Button(actions,text='AKTUALISIEREN',command=refresh,bg='#e7e4dc',fg=INK,bd=0,padx=13,pady=7).pack(side='left',padx=(8,0))

        note=tk.Label(
            self.content,
            text='1.8.39 · auf echte IDEA-Dateistruktur abgestimmt: *.ideaCon, .Archiv, .backup, PDF, Word und IFC/BIM werden je Anschluss logisch zusammengefasst. Bestehende Dateien werden nicht verschoben.',
            bg=BG,fg=MUTED,anchor='w',justify='left',wraplength=1100,font=('Segoe UI',9)
        )
        note.pack(fill='x',pady=(0,4))

        refresh()

'''

app=app[:start]+method+app[end:]
APP.write_text(app,encoding="utf-8")

post=POST.read_text(encoding="utf-8")
post=post.replace("update_1838_install.log","update_1839_install.log")
post=post.replace("update_1838_error.txt","update_1839_error.txt")
post=one(post,'APP_VERSION = "1.8.38"','APP_VERSION = "1.8.39"',"post version")
post=post.replace("OK: Update 1.8.38 erfolgreich installiert.","OK: Update 1.8.39 erfolgreich installiert.")
POST.write_text(post,encoding="utf-8")

for p in (APP,POST):
    py_compile.compile(str(p),doraise=True)

check=APP.read_text(encoding="utf-8")
for marker in (
    "PZ_IDEA_STATICA_V1839_REAL_STRUCTURE",
    "endswith('.ideacon')",
    "IDEA-Datei: vorhanden",
    "IFC ist die Grundlage",
    "NEUER ANSCHLUSS",
    "Bestehende Dateien werden nicht verschoben"
):
    if marker not in check:
        raise RuntimeError(marker)
print("OK 1.8.39 real IDEA structure")
