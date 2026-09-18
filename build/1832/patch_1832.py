from pathlib import Path
import py_compile, sys

ROOT=Path(sys.argv[1]).resolve()
APP=ROOT/"app.py"
POST=ROOT/"post_update.py"
BASKET=ROOT/"share_basket_v1821.py"
HIDRIVE=ROOT/"hidrive_oauth_v1832.py"

def one(t,a,b,label):
    c=t.count(a)
    if c!=1:
        raise RuntimeError(f"{label}: {c}")
    return t.replace(a,b,1)

app=APP.read_text(encoding="utf-8")
app=one(app,'APP_VERSION = "1.8.31"','APP_VERSION = "1.8.32"',"app version")
APP.write_text(app,encoding="utf-8")

basket=BASKET.read_text(encoding="utf-8")
old='''    count_lbl = tk.Label(tools, text="", bg=BG, fg=MUTED)
    count_lbl.pack(side="left")

    cols = ("Typ", "Quelle", "Pfad")
'''
new='''    count_lbl = tk.Label(tools, text="", bg=BG, fg=MUTED)
    count_lbl.pack(side="left")

    hidrive_status_var = tk.StringVar(value="")
    hidrive_status_lbl = tk.Label(tools, textvariable=hidrive_status_var, bg=BG, fg=MUTED, font=("Segoe UI", 9))
    hidrive_status_lbl.pack(side="right", padx=(8, 0))

    def refresh_hidrive_status():
        try:
            from hidrive_oauth_v1832 import connection_summary
            hidrive_status_var.set(connection_summary())
        except Exception:
            hidrive_status_var.set("HiDrive: Status unbekannt")

    def setup_hidrive():
        try:
            from hidrive_oauth_v1832 import open_setup_dialog
            open_setup_dialog(w, on_change=refresh_hidrive_status)
        except Exception as exc:
            messagebox.showerror("HiDrive", str(exc), parent=w)

    tk.Button(
        tools,
        text="HIDRIVE EINRICHTEN",
        command=setup_hidrive,
        bg=DARK,
        fg="white",
        bd=0,
        padx=12,
        pady=6,
    ).pack(side="right", padx=(8, 0))
    refresh_hidrive_status()

    cols = ("Typ", "Quelle", "Pfad")
'''
basket=one(basket,old,new,"HiDrive setup UI")
BASKET.write_text(basket,encoding="utf-8")

post=POST.read_text(encoding="utf-8")
post=post.replace("update_1831_install.log","update_1832_install.log")
post=post.replace("update_1831_error.txt","update_1832_error.txt")
post=one(post,'APP_VERSION = "1.8.31"','APP_VERSION = "1.8.32"',"post version")
post=post.replace("OK: Update 1.8.31 erfolgreich installiert.","OK: Update 1.8.32 erfolgreich installiert.")
POST.write_text(post,encoding="utf-8")

for p in (APP,POST,BASKET,HIDRIVE):
    py_compile.compile(str(p),doraise=True)

for marker in ("HIDRIVE EINRICHTEN","refresh_hidrive_status","hidrive_oauth_v1832"):
    if marker not in BASKET.read_text(encoding="utf-8"):
        raise RuntimeError("1.8.32 marker fehlt: "+marker)

print("OK 1.8.32 HiDrive OAuth setup")
