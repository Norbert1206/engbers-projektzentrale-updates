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
app=one(app,'APP_VERSION = "1.8.37"','APP_VERSION = "1.8.38"',"app version")

# Add IDEA StatiCa sub-navigation directly below Statik PDF.
needle="                self.statik_pdf_nav.pack(fill='x')"
insert="""                self.statik_pdf_nav.pack(fill='x')
                # PZ_IDEA_STATICA_NAV_V1838
                self.idea_statica_nav=tk.Button(
                    self.sidebar,
                    text='   ↳ IDEA StatiCa',
                    command=self.show_idea_statica,
                    anchor='w',bd=0,bg=DARK,fg='#b9b7b0',
                    activebackground=DARK2,activeforeground='white',
                    font=('Segoe UI',9),padx=30,pady=subnav_pady,cursor='hand2'
                )
                self.idea_statica_nav.pack(fill='x')"""
app=one(app,needle,insert,"IDEA nav")

# Future projects: create the desired IDEA folder structure when Statik is selected.
needle="""                for folder in ['01_Projekt','02_Statik','03_Pruefstatik','04_Waermeschutz','05_DGNB_QNG','06_Schallschutz','07_Bauleitung','08_Kommunikation','09_Dokumente','10_Angebote_Rechnungen','Goodnotes']: (root/folder).mkdir(parents=True,exist_ok=True)
                self.project_id=pid; self.refresh_project_combo(); w.destroy(); self.show_dashboard(); messagebox.showinfo('Projekt angelegt',f'{num} · {title} wurde angelegt. Fachbereiche können später ergänzt oder entfernt werden.')"""
replacement="""                for folder in ['01_Projekt','02_Statik','03_Pruefstatik','04_Waermeschutz','05_DGNB_QNG','06_Schallschutz','07_Bauleitung','08_Kommunikation','09_Dokumente','10_Angebote_Rechnungen','Goodnotes']: (root/folder).mkdir(parents=True,exist_ok=True)
                if 'Statik' in selected:
                    (root/'02_Statik'/'IDEA StatiCa'/'BIM Anschluss').mkdir(parents=True,exist_ok=True)
                self.project_id=pid; self.refresh_project_combo(); w.destroy(); self.show_dashboard(); messagebox.showinfo('Projekt angelegt',f'{num} · {title} wurde angelegt. Fachbereiche können später ergänzt oder entfernt werden.')"""
app=one(app,needle,replacement,"future IDEA folders")

# Remove Allplan/Allmenu from the statics starter bar; user launches Allplan independently.
app=app.replace("            ('ALLPLAN',lambda:self.launch_configured_program('allplan','Allplan'),'#e7e4dc'),\n","")
app=app.replace("            ('ALLMENU',lambda:self.launch_configured_program('allmenu','Allmenu'),'#e7e4dc'),\n","")

# Add IDEA to statics subtitle.
app=one(
    app,
    "self.clear(); self.titleblock(self.content,'Statik','Baugrund · mb AEC Projekte · Positionsakte · Prüfstatik · Pläne · Lastfluss')",
    "self.clear(); self.titleblock(self.content,'Statik','Baugrund · mb AEC Projekte · IDEA StatiCa · Positionsakte · Prüfstatik · Pläne · Lastfluss')",
    "statics subtitle"
)

# Insert the compact IDEA StatiCa project area before show_statics.
marker="    def show_statics(self):\n"
idea_method=r'''    def show_idea_statica(self):
        # PZ_IDEA_STATICA_V1838
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
            f"{r['number']} · {r['title']} · BIM-Anschlüsse projektbezogen ablegen und direkt öffnen"
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
        idea_root=statik_root/'IDEA StatiCa'
        bim_root=idea_root/'BIM Anschluss'
        try:
            bim_root.mkdir(parents=True,exist_ok=True)
        except Exception as exc:
            messagebox.showerror('IDEA StatiCa',f'Der IDEA-StatiCa-Ordner konnte nicht angelegt werden:\n\n{exc}')
            return

        def open_path(path):
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

        tools=tk.Frame(self.content,bg=BG)
        tools.pack(fill='x',pady=(0,12))
        tk.Button(
            tools,text='IDEA STATICA STARTEN',
            command=lambda:self.launch_configured_program('idea','IDEA StatiCa'),
            bg=ACCENT,fg='white',bd=0,padx=15,pady=8
        ).pack(side='left')
        tk.Button(
            tools,text='BIM-ANSCHLUSS ÖFFNEN',
            command=lambda:open_path(bim_root),
            bg=DARK,fg='white',bd=0,padx=15,pady=8
        ).pack(side='left',padx=(8,0))

        pan,body=self.panel(self.content,'BIM Anschluss · Projektdateien')
        pan.pack(fill='both',expand=True,pady=(0,12))

        info=tk.Label(
            body,
            text=f'Ablage: {bim_root}',
            bg=PANEL,fg=MUTED,anchor='w',font=('Segoe UI',9)
        )
        info.pack(fill='x',pady=(0,8))

        split=tk.Frame(body,bg=PANEL)
        split.pack(fill='both',expand=True)
        left=tk.Frame(split,bg=PANEL)
        left.pack(side='left',fill='both',expand=True)
        right=tk.Frame(split,bg='#f3f1ec',width=300)
        right.pack(side='right',fill='y',padx=(12,0))
        right.pack_propagate(False)

        cols=('Datei','Typ','Geändert','Größe')
        tree=ttk.Treeview(left,columns=cols,show='headings',height=13)
        widths={'Datei':380,'Typ':120,'Geändert':145,'Größe':90}
        for c in cols:
            tree.heading(c,text=c)
            tree.column(c,width=widths[c],anchor='w')
        sy=ttk.Scrollbar(left,orient='vertical',command=tree.yview)
        tree.configure(yscrollcommand=sy.set)
        tree.pack(side='left',fill='both',expand=True)
        sy.pack(side='right',fill='y')

        tk.Label(
            right,text='VORSCHAU / 3D',
            bg='#f3f1ec',fg=INK,font=('Segoe UI Semibold',10),anchor='w'
        ).pack(fill='x',padx=14,pady=(14,8))
        preview=tk.Label(
            right,
            text='Datei auswählen.\n\nIFC-Dateien werden erkannt und sind die Grundlage für die spätere drehbare 3D-Vorschau.',
            bg='#f3f1ec',fg=MUTED,justify='left',anchor='nw',wraplength=260
        )
        preview.pack(fill='both',expand=True,padx=14,pady=(0,12))

        item_paths={}
        type_counts={}

        def file_type(p):
            ext=p.suffix.casefold()
            if ext in ('.ideaconn','.idea','.ideaconnection'):
                return 'IDEA Connection'
            if ext=='.ifc':
                return 'IFC 3D'
            if ext=='.pdf':
                return 'PDF'
            if ext in ('.png','.jpg','.jpeg','.bmp','.gif','.tif','.tiff'):
                return 'Bild'
            return ext[1:].upper() if ext else 'Datei'

        def size_text(n):
            n=float(n)
            for unit in ('B','KB','MB','GB'):
                if n<1024.0 or unit=='GB':
                    return f'{n:.0f} {unit}' if unit=='B' else f'{n:.1f} {unit}'
                n/=1024.0
            return ''

        def selected_path():
            sel=tree.selection()
            return item_paths.get(sel[0]) if sel else None

        def refresh():
            for iid in tree.get_children():
                tree.delete(iid)
            item_paths.clear()
            type_counts.clear()
            files=[]
            try:
                files=[p for p in bim_root.rglob('*') if p.is_file()]
                files.sort(key=lambda p:(p.suffix.casefold(),p.name.casefold()))
            except OSError:
                files=[]
            for p in files:
                try:
                    st=p.stat()
                    changed=datetime.datetime.fromtimestamp(st.st_mtime).strftime('%d.%m.%Y %H:%M')
                    typ=file_type(p)
                    rel=str(p.relative_to(bim_root))
                    iid=tree.insert('', 'end', values=(rel,typ,changed,size_text(st.st_size)))
                    item_paths[iid]=p
                    type_counts[typ]=type_counts.get(typ,0)+1
                except OSError:
                    continue
            idea_n=type_counts.get('IDEA Connection',0)
            ifc_n=type_counts.get('IFC 3D',0)
            pdf_n=type_counts.get('PDF',0)
            info.configure(text=f'Ablage: {bim_root}   ·   {idea_n} IDEA · {ifc_n} IFC · {pdf_n} PDF')
            if not files:
                preview.configure(text='Der Ordner ist bereit.\n\nLege hier einen BIM-Anschluss aus IDEA StatiCa ab. IDEA-, IFC- und PDF-Dateien werden automatisch erkannt.')

        def open_selected(_evt=None):
            p=selected_path()
            if p:
                open_path(p)

        def update_preview(_evt=None):
            p=selected_path()
            if not p:
                return
            typ=file_type(p)
            if typ=='IFC 3D':
                preview.configure(
                    text=f'{p.name}\n\nIFC-3D-Modell erkannt.\n\nDieses Format eignet sich für unsere geplante drehbare Anschlussvorschau. Bis dahin öffnet ein Doppelklick die Datei mit dem auf Windows hinterlegten IFC-Viewer.'
                )
            elif typ=='IDEA Connection':
                preview.configure(
                    text=f'{p.name}\n\nIDEA-StatiCa-Anschluss erkannt.\n\nDoppelklick öffnet die Datei direkt über die Windows-Dateizuordnung.'
                )
            elif typ=='PDF':
                preview.configure(
                    text=f'{p.name}\n\nPDF-Ausgabe erkannt.\n\nDoppelklick öffnet den Nachweis.'
                )
            else:
                preview.configure(text=f'{p.name}\n\nTyp: {typ}\n\nDoppelklick zum Öffnen.')

        tree.bind('<Double-1>',open_selected)
        tree.bind('<Return>',open_selected)
        tree.bind('<<TreeviewSelect>>',update_preview)

        actions=tk.Frame(body,bg=PANEL)
        actions.pack(fill='x',pady=(10,0))
        tk.Button(actions,text='DATEI ÖFFNEN',command=open_selected,bg=DARK,fg='white',bd=0,padx=14,pady=7).pack(side='left')
        tk.Button(actions,text='AKTUALISIEREN',command=refresh,bg='#e7e4dc',fg=INK,bd=0,padx=14,pady=7).pack(side='left',padx=8)

        note=tk.Label(
            self.content,
            text='1.8.38 · bewusst schlank: IDEA starten, BIM-Anschluss projektbezogen ablegen, Dateien erkennen und öffnen. Die drehbare IFC-Vorschau bauen wir auf einem echten Anschluss aus dem Referenzprojekt weiter.',
            bg=BG,fg=MUTED,anchor='w',justify='left',wraplength=1050,font=('Segoe UI',9)
        )
        note.pack(fill='x',pady=(0,4))

        refresh()

'''
if marker not in app:
    raise RuntimeError("show_statics marker missing")
app=app.replace(marker,idea_method+marker,1)

APP.write_text(app,encoding="utf-8")

post=POST.read_text(encoding="utf-8")
post=post.replace("update_1837_install.log","update_1838_install.log")
post=post.replace("update_1837_error.txt","update_1838_error.txt")
post=one(post,'APP_VERSION = "1.8.37"','APP_VERSION = "1.8.38"',"post version")
post=post.replace("OK: Update 1.8.37 erfolgreich installiert.","OK: Update 1.8.38 erfolgreich installiert.")
POST.write_text(post,encoding="utf-8")

for p in (APP,POST):
    py_compile.compile(str(p),doraise=True)

check=APP.read_text(encoding="utf-8")
for marker in ("def show_idea_statica","IDEA STATICA STARTEN","BIM Anschluss","PZ_IDEA_STATICA_V1838"):
    if marker not in check:
        raise RuntimeError(marker)
if "('ALLPLAN'," in check or "('ALLMENU'," in check:
    raise RuntimeError("Allplan/Allmenu still present in program starter bar")

print("OK 1.8.38 IDEA StatiCa integration")
