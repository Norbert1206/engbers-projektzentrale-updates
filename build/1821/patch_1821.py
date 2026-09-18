from pathlib import Path
import py_compile
import sys

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
APP = ROOT / "app.py"
POST = ROOT / "post_update.py"

for path in (APP, POST):
    if not path.exists():
        raise RuntimeError(f"1.8.21: Update-Datei fehlt: {path.name}")

def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"1.8.21: Marker {label} erwartet 1x, gefunden {count}x")
    return text.replace(old, new, 1)

app = APP.read_text(encoding="utf-8")
app = replace_once(app, 'APP_VERSION = "1.8.20"', 'APP_VERSION = "1.8.21"', "APP_VERSION")

# Projekt-Explorer: eigener Freigabekorb-Block unter den normalen Dateiaktionen.
old_ui = """        btns=tk.Frame(right,bg=PANEL); btns.pack(fill='x',padx=12,pady=8)
        open_btn=tk.Button(btns,text='ÖFFNEN',bg=DARK,fg='white',bd=0,padx=10,pady=7); open_btn.pack(side='left')
        explorer_btn=tk.Button(btns,text='EXPLORER',bg='#e7e4dc',fg=INK,bd=0,padx=10,pady=7); explorer_btn.pack(side='left',padx=6)
        copy_btn=tk.Button(btns,text='PFAD KOPIEREN',bg='#e7e4dc',fg=INK,bd=0,padx=9,pady=7); copy_btn.pack(side='left')
        delete_btn=tk.Button(btns,text='LÖSCHEN',bg='#7b2d2d',fg='white',bd=0,padx=10,pady=7); delete_btn.pack(side='left',padx=(6,0))
"""
new_ui = """        btns=tk.Frame(right,bg=PANEL); btns.pack(fill='x',padx=12,pady=8)
        open_btn=tk.Button(btns,text='ÖFFNEN',bg=DARK,fg='white',bd=0,padx=10,pady=7); open_btn.pack(side='left')
        explorer_btn=tk.Button(btns,text='EXPLORER',bg='#e7e4dc',fg=INK,bd=0,padx=10,pady=7); explorer_btn.pack(side='left',padx=6)
        copy_btn=tk.Button(btns,text='PFAD KOPIEREN',bg='#e7e4dc',fg=INK,bd=0,padx=9,pady=7); copy_btn.pack(side='left')
        delete_btn=tk.Button(btns,text='LÖSCHEN',bg='#7b2d2d',fg='white',bd=0,padx=10,pady=7); delete_btn.pack(side='left',padx=(6,0))
        share_btns=tk.Frame(right,bg=PANEL); share_btns.pack(fill='x',padx=12,pady=(0,8))
        share_add_btn=tk.Button(share_btns,text='ZUR FREIGABE',bg=ACCENT,fg='white',bd=0,padx=12,pady=7); share_add_btn.pack(side='left')
        share_basket_btn=tk.Button(share_btns,text='FREIGABEKORB',bg=DARK,fg='white',bd=0,padx=12,pady=7); share_basket_btn.pack(side='left',padx=6)
"""
app = replace_once(app, old_ui, new_ui, "project explorer share UI")

old_delete_end = """        def delete_selected_files():
            files=[]
            try:
                for iid in tr.selection():
                    pp=pathmap.get(iid); root=rootmap.get(iid)
                    if pp is None or root is None or bool(isdirmap.get(iid,False)):continue
                    try:pp.resolve().relative_to(root.resolve())
                    except Exception:continue
                    if pp.is_file():files.append(pp)
                confirm_recycle_files(self,files,on_success=render_normal,title='Projekt-Explorer')
            except Exception:log_error('delete_selected_files')

        def on_tree_open(_evt=None):
"""
new_delete_end = """        def delete_selected_files():
            files=[]
            try:
                for iid in tr.selection():
                    pp=pathmap.get(iid); root=rootmap.get(iid)
                    if pp is None or root is None or bool(isdirmap.get(iid,False)):continue
                    try:pp.resolve().relative_to(root.resolve())
                    except Exception:continue
                    if pp.is_file():files.append(pp)
                confirm_recycle_files(self,files,on_success=render_normal,title='Projekt-Explorer')
            except Exception:log_error('delete_selected_files')

        def add_selected_to_share_basket():
            grouped={}
            for iid in tr.selection():
                pp=pathmap.get(iid); root=rootmap.get(iid)
                if pp is None or root is None:continue
                grouped.setdefault(str(root),[]).append(pp)
            if not grouped:
                messagebox.showwarning('Freigabekorb','Bitte mindestens eine Datei oder einen Ordner auswählen.',parent=self); return
            try:
                from share_basket_v1821 import add_items,count_items
                added=0
                for root_text,paths in grouped.items():
                    n,_=add_items(self.project_id,paths,Path(root_text),source='Projekt-Explorer')
                    added+=n
                total=count_items(self.project_id)
                messagebox.showinfo('Freigabekorb',f'{added} Eintrag/Einträge hinzugefügt.\\n\\nIm Korb: {total}',parent=self)
            except Exception as exc:
                messagebox.showerror('Freigabekorb',str(exc),parent=self)

        def open_share_basket():
            try:
                from share_basket_v1821 import open_basket_dialog
                open_basket_dialog(self,self.project_id,str(r['number'] or ''),str(r['title'] or ''))
            except Exception as exc:
                messagebox.showerror('Freigabekorb',str(exc),parent=self)

        def on_tree_open(_evt=None):
"""
app = replace_once(app, old_delete_end, new_delete_end, "project explorer share functions")

old_config = """        open_btn.configure(command=open_selected); explorer_btn.configure(command=show_in_explorer); copy_btn.configure(command=copy_path); delete_btn.configure(command=delete_selected_files)
        tk.Button(toolbar,text='AKTUALISIEREN',command=render_normal,bg='#e7e4dc',fg=INK,bd=0,padx=10,pady=7).pack(side='right')
"""
new_config = """        open_btn.configure(command=open_selected); explorer_btn.configure(command=show_in_explorer); copy_btn.configure(command=copy_path); delete_btn.configure(command=delete_selected_files)
        share_add_btn.configure(command=add_selected_to_share_basket); share_basket_btn.configure(command=open_share_basket)
        tk.Button(toolbar,text='FREIGABEKORB',command=open_share_basket,bg=ACCENT,fg='white',bd=0,padx=10,pady=7).pack(side='right',padx=(6,0))
        tk.Button(toolbar,text='AKTUALISIEREN',command=render_normal,bg='#e7e4dc',fg=INK,bd=0,padx=10,pady=7).pack(side='right')
"""
app = replace_once(app, old_config, new_config, "project explorer share config")

old_menu = """        menu=tk.Menu(self,tearoff=0)
        menu.add_command(label='Öffnen',command=open_selected); menu.add_command(label='Im Windows-Explorer zeigen',command=show_in_explorer); menu.add_separator(); menu.add_command(label='Pfad kopieren',command=copy_path); menu.add_separator(); menu.add_command(label='Ausgewählte Datei(en) löschen …',command=delete_selected_files)
"""
new_menu = """        menu=tk.Menu(self,tearoff=0)
        menu.add_command(label='Öffnen',command=open_selected); menu.add_command(label='Im Windows-Explorer zeigen',command=show_in_explorer); menu.add_separator(); menu.add_command(label='Pfad kopieren',command=copy_path); menu.add_separator(); menu.add_command(label='Zur Projektfreigabe hinzufügen',command=add_selected_to_share_basket); menu.add_command(label='Freigabekorb öffnen',command=open_share_basket); menu.add_separator(); menu.add_command(label='Ausgewählte Datei(en) löschen …',command=delete_selected_files)
"""
app = replace_once(app, old_menu, new_menu, "project explorer context menu")

# Statik PDF: direkten Einmal-Kopiervorgang durch Freigabekorb ersetzen.
start = app.index("        def prepare_strato_share():")
end = app.index("        def open_batch_stamp(profile):", start)
new_stat_func = """        def add_selected_to_share_basket():
            selected=[]
            for iid in tree.selection():
                p=pathmap.get(iid)
                if p is not None:selected.append(p)
            if not selected:
                messagebox.showwarning('Freigabekorb','Bitte mindestens eine PDF-Datei oder einen Ordner auswählen.',parent=self); return
            try:
                from share_basket_v1821 import add_items
                added,total=add_items(self.project_id,selected,project_root,source='Statik PDF')
                messagebox.showinfo('Freigabekorb',f'{added} Eintrag/Einträge hinzugefügt.\\n\\nIm Korb: {total}',parent=self)
            except Exception as exc:
                messagebox.showerror('Freigabekorb',str(exc),parent=self)

        def open_share_basket():
            try:
                from share_basket_v1821 import open_basket_dialog
                open_basket_dialog(self,self.project_id,str(r['number'] or ''),str(r['title'] or ''))
            except Exception as exc:
                messagebox.showerror('Freigabekorb',str(exc),parent=self)

"""
app = app[:start] + new_stat_func + app[end:]

old_stat_button = """        tk.Button(tools,text='STRATO-FREIGABE',command=prepare_strato_share,bg=ACCENT,fg='white',bd=0,padx=13,pady=7).pack(side='right',padx=(6,0))
        tk.Button(tools,text='ORDNER ÖFFNEN',command=open_folder,bg=DARK,fg='white',bd=0,padx=13,pady=7).pack(side='right',padx=(6,0))
"""
new_stat_button = """        tk.Button(tools,text='FREIGABEKORB',command=open_share_basket,bg=DARK,fg='white',bd=0,padx=13,pady=7).pack(side='right',padx=(6,0))
        tk.Button(tools,text='ZUR FREIGABE',command=add_selected_to_share_basket,bg=ACCENT,fg='white',bd=0,padx=13,pady=7).pack(side='right',padx=(6,0))
        tk.Button(tools,text='ORDNER ÖFFNEN',command=open_folder,bg=DARK,fg='white',bd=0,padx=13,pady=7).pack(side='right',padx=(6,0))
"""
app = replace_once(app, old_stat_button, new_stat_button, "statik share buttons")

old_stat_menu = """        menu.add_command(label='Pfad kopieren',command=copy_path)
        menu.add_separator()
        menu.add_command(label='Für STRATO-Freigabe bereitstellen',command=prepare_strato_share)
        menu.add_separator()
        menu.add_command(label='Ausgewählte Datei(en) löschen …',command=delete_selected_files)
"""
new_stat_menu = """        menu.add_command(label='Pfad kopieren',command=copy_path)
        menu.add_separator()
        menu.add_command(label='Zur Projektfreigabe hinzufügen',command=add_selected_to_share_basket)
        menu.add_command(label='Freigabekorb öffnen',command=open_share_basket)
        menu.add_separator()
        menu.add_command(label='Ausgewählte Datei(en) löschen …',command=delete_selected_files)
"""
app = replace_once(app, old_stat_menu, new_stat_menu, "statik context menu")

APP.write_text(app, encoding="utf-8")

post = POST.read_text(encoding="utf-8")
post = post.replace("update_1820_install.log", "update_1821_install.log")
post = post.replace("update_1820_error.txt", "update_1821_error.txt")
post = replace_once(post, 'APP_VERSION = "1.8.20"', 'APP_VERSION = "1.8.21"', "post version")
post = post.replace("OK: Update 1.8.20 erfolgreich installiert.", "OK: Update 1.8.21 erfolgreich installiert.")
POST.write_text(post, encoding="utf-8")

for path in (APP, POST, ROOT / "share_basket_v1821.py"):
    py_compile.compile(str(path), doraise=True)

check = APP.read_text(encoding="utf-8")
for marker in ("ZUR FREIGABE", "FREIGABEKORB", "share_basket_v1821"):
    if marker not in check:
        raise RuntimeError("1.8.21: Freigabekorb fehlt: " + marker)

print("OK: Projektzentrale 1.8.21 Projektfreigabekorb gepatcht und geprueft.")
