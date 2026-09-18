from pathlib import Path
import py_compile
import sys

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
APP = ROOT / "app.py"
POST = ROOT / "post_update.py"

for path in (APP, POST):
    if not path.exists():
        raise RuntimeError(f"1.8.20: Update-Datei fehlt: {path.name}")

def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"1.8.20: Marker {label} erwartet 1x, gefunden {count}x")
    return text.replace(old, new, 1)

app = APP.read_text(encoding="utf-8")
app = replace_once(app, 'APP_VERSION = "1.8.19"', 'APP_VERSION = "1.8.20"', "APP_VERSION")

old_open = """        def open_folder():
            folder=find_folder()
            if not folder.exists():
                if not messagebox.askyesno('Statik PDF',f'Der Ordner ist noch nicht vorhanden:\\n{folder}\\n\\nJetzt anlegen?'):return
                try:folder.mkdir(parents=True,exist_ok=True)
                except Exception as exc:messagebox.showerror('Statik PDF',str(exc)); return
            self.open_external_path(folder); refresh()

"""
new_open = """        def open_folder():
            folder=find_folder()
            if not folder.exists():
                if not messagebox.askyesno('Statik PDF',f'Der Ordner ist noch nicht vorhanden:\\n{folder}\\n\\nJetzt anlegen?'):return
                try:folder.mkdir(parents=True,exist_ok=True)
                except Exception as exc:messagebox.showerror('Statik PDF',str(exc)); return
            self.open_external_path(folder); refresh()

        def prepare_strato_share():
            folder=find_folder()
            selected=[]
            for iid in tree.selection():
                p=pathmap.get(iid)
                if p is not None:
                    selected.append(p)
            try:
                from hidrive_share_v1820 import prepare_share
                release_dir,copied=prepare_share(
                    selected,
                    folder,
                    str(r['number'] or ''),
                    str(r['title'] or ''),
                )
            except ValueError as exc:
                messagebox.showwarning('STRATO-Freigabe',str(exc)); return
            except Exception as exc:
                messagebox.showerror('STRATO-Freigabe',str(exc)); return
            try:
                self.open_external_path(release_dir)
            except Exception:
                pass
            messagebox.showinfo(
                'STRATO-Freigabe',
                f'{len(copied)} PDF-Datei(en) als Kopie bereitgestellt.\\n\\n'
                f'{release_dir}\\n\\n'
                'Die Originaldateien im Projekt wurden nicht verändert. '
                'HiDrive synchronisiert diesen Ordner automatisch.',
            )

"""
app = replace_once(app, old_open, new_open, "open_folder / STRATO function")

old_buttons = """        tk.Button(tools,text='ORDNER ÖFFNEN',command=open_folder,bg=DARK,fg='white',bd=0,padx=13,pady=7).pack(side='right',padx=(6,0))
        tk.Button(tools,text='AUSGEWÄHLTE LÖSCHEN',command=delete_selected_files,bg='#7b2d2d',fg='white',bd=0,padx=13,pady=7).pack(side='right',padx=(6,0))
"""
new_buttons = """        tk.Button(tools,text='STRATO-FREIGABE',command=prepare_strato_share,bg=ACCENT,fg='white',bd=0,padx=13,pady=7).pack(side='right',padx=(6,0))
        tk.Button(tools,text='ORDNER ÖFFNEN',command=open_folder,bg=DARK,fg='white',bd=0,padx=13,pady=7).pack(side='right',padx=(6,0))
        tk.Button(tools,text='AUSGEWÄHLTE LÖSCHEN',command=delete_selected_files,bg='#7b2d2d',fg='white',bd=0,padx=13,pady=7).pack(side='right',padx=(6,0))
"""
app = replace_once(app, old_buttons, new_buttons, "toolbar button")

old_menu = """        menu.add_command(label='Pfad kopieren',command=copy_path)
        menu.add_separator()
        menu.add_command(label='Ausgewählte Datei(en) löschen …',command=delete_selected_files)
"""
new_menu = """        menu.add_command(label='Pfad kopieren',command=copy_path)
        menu.add_separator()
        menu.add_command(label='Für STRATO-Freigabe bereitstellen',command=prepare_strato_share)
        menu.add_separator()
        menu.add_command(label='Ausgewählte Datei(en) löschen …',command=delete_selected_files)
"""
app = replace_once(app, old_menu, new_menu, "context menu")
APP.write_text(app, encoding="utf-8")

post = POST.read_text(encoding="utf-8")
post = post.replace("update_1819_install.log", "update_1820_install.log")
post = post.replace("update_1819_error.txt", "update_1820_error.txt")
post = replace_once(post, 'APP_VERSION = "1.8.19"', 'APP_VERSION = "1.8.20"', "post version")
post = post.replace("OK: Update 1.8.19 erfolgreich installiert.", "OK: Update 1.8.20 erfolgreich installiert.")
POST.write_text(post, encoding="utf-8")

for path in (APP, POST, ROOT / "hidrive_share_v1820.py"):
    py_compile.compile(str(path), doraise=True)

check = APP.read_text(encoding="utf-8")
for marker in ("STRATO-FREIGABE", "prepare_strato_share", "hidrive_share_v1820"):
    if marker not in check:
        raise RuntimeError("1.8.20: STRATO-Freigabe fehlt: " + marker)

print("OK: Projektzentrale 1.8.20 STRATO/HiDrive-Freigabe gepatcht und geprueft.")
