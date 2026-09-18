from pathlib import Path
import py_compile, sys

ROOT=Path(sys.argv[1]).resolve()
APP=ROOT/"app.py"; POST=ROOT/"post_update.py"; BASKET=ROOT/"share_basket_v1821.py"; SHARE=ROOT/"hidrive_sharelink_v1834.py"

def one(t,a,b,label):
    c=t.count(a)
    if c!=1: raise RuntimeError(f"{label}: {c}")
    return t.replace(a,b,1)

app=APP.read_text(encoding="utf-8")
app=one(app,'APP_VERSION = "1.8.33"','APP_VERSION = "1.8.34"',"app")
APP.write_text(app,encoding="utf-8")

basket=BASKET.read_text(encoding="utf-8")
if "import threading\n" not in basket:
    basket=basket.replace("import shutil\n","import shutil\nimport threading\n",1)

basket=one(
    basket,
    "    index_map = {}\n\n    def refresh():\n",
    "    index_map = {}\n    pending_release = {\"path\": None}\n\n    def refresh():\n",
    "state",
)

anchor="\n    def _attachment_files():\n"
if basket.count(anchor)!=1: raise RuntimeError("attachment anchor")
func=r'''
    def create_hidrive_link():
        if not get_items(project_id) and not pending_release["path"]:
            messagebox.showwarning("HiDrive-Freigabe", "Der Freigabekorb ist leer.", parent=w)
            return
        try:
            from hidrive_oauth_v1832 import connection_summary
            from hidrive_sharelink_v1834 import create_share_link_for_local_dir
            if "verbunden" not in connection_summary().casefold():
                messagebox.showwarning("HiDrive-Freigabe", "HiDrive ist noch nicht verbunden.", parent=w)
                return
        except Exception as exc:
            messagebox.showerror("HiDrive-Freigabe", str(exc), parent=w)
            return

        link_btn.configure(state="disabled", text="HIDRIVE WIRD VORBEREITET …")

        def worker():
            release = pending_release["path"]
            try:
                if not release:
                    release, _copied = create_release(project_id, project_number, project_title)
                    pending_release["path"] = release
                share = create_share_link_for_local_dir(release, wait_seconds=90)
                result = ("ok", release, share)
            except Exception as exc:
                result = ("error", release, str(exc))

            def done():
                link_btn.configure(state="normal", text="HIDRIVE-LINK")
                if result[0] == "ok":
                    release, share = result[1], result[2]
                    url = str(share.get("uri") or "").strip()
                    pending_release["path"] = None
                    clear_items(project_id)
                    refresh()
                    try:
                        app.clipboard_clear(); app.clipboard_append(url)
                    except Exception:
                        pass
                    messagebox.showinfo(
                        "HiDrive-Freigabe",
                        "Freigabelink wurde erstellt und in die Zwischenablage kopiert.\n\n" + url,
                        parent=w,
                    )
                else:
                    release, detail = result[1], result[2]
                    if release:
                        detail += (
                            "\n\nDer Freigabeordner wurde bereits erstellt. "
                            "Beim nächsten Klick auf HIDRIVE-LINK wird derselbe Ordner erneut versucht."
                        )
                    messagebox.showerror("HiDrive-Freigabe", detail, parent=w)
            try: w.after(0, done)
            except Exception: pass

        threading.Thread(target=worker, daemon=True).start()
'''
basket=basket.replace(anchor,"\n"+func+anchor,1)

old='''    tk.Button(buttons, text="FREIGABE ERSTELLEN", command=create_now, bg=ACCENT, fg="white", bd=0, padx=18, pady=8).pack(side="right")
    tk.Button(buttons, text="OUTLOOK-MAIL", command=open_outlook_mail, bg=DARK, fg="white", bd=0, padx=18, pady=8).pack(side="right", padx=8)
'''
new='''    tk.Button(buttons, text="FREIGABE ERSTELLEN", command=create_now, bg=ACCENT, fg="white", bd=0, padx=14, pady=8).pack(side="right")
    link_btn = tk.Button(buttons, text="HIDRIVE-LINK", command=create_hidrive_link, bg=ACCENT, fg="white", bd=0, padx=14, pady=8)
    link_btn.pack(side="right", padx=8)
    tk.Button(buttons, text="OUTLOOK-MAIL", command=open_outlook_mail, bg=DARK, fg="white", bd=0, padx=14, pady=8).pack(side="right")
'''
basket=one(basket,old,new,"buttons")
BASKET.write_text(basket,encoding="utf-8")

post=POST.read_text(encoding="utf-8")
post=post.replace("update_1833_install.log","update_1834_install.log").replace("update_1833_error.txt","update_1834_error.txt")
post=one(post,'APP_VERSION = "1.8.33"','APP_VERSION = "1.8.34"',"post")
post=post.replace("OK: Update 1.8.33 erfolgreich installiert.","OK: Update 1.8.34 erfolgreich installiert.")
POST.write_text(post,encoding="utf-8")

for p in (APP,POST,BASKET,SHARE): py_compile.compile(str(p),doraise=True)
print("OK 1.8.34")
