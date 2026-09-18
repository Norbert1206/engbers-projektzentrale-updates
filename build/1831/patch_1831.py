from pathlib import Path
import py_compile, sys

ROOT=Path(sys.argv[1]).resolve()
APP=ROOT/"app.py"
POST=ROOT/"post_update.py"
ARCH=ROOT/"outlook_archive_v1823.py"

def one(t,a,b,label):
    c=t.count(a)
    if c!=1:
        raise RuntimeError(f"{label}: {c}")
    return t.replace(a,b,1)

app=APP.read_text(encoding="utf-8")
app=one(app,'APP_VERSION = "1.8.30"','APP_VERSION = "1.8.31"',"app version")
APP.write_text(app,encoding="utf-8")

arch=ARCH.read_text(encoding="utf-8")

old='''    top = tk.Frame(w)
    top.pack(fill="x", padx=14, pady=(14, 8))
    tk.Label(top, text="OUTLOOK-MAIL DEM PROJEKT ZUORDNEN", font=("Segoe UI", 15, "bold")).pack(anchor="w")
    tk.Label(top, text="Letzte 60 Tage · Mehrfachauswahl möglich · Original wird als .msg im Projekt archiviert.", fg="#666").pack(anchor="w", pady=(2, 0))

    cols = ("Zeit", "Richtung", "Von", "An", "Betreff", "Konto")
    tree = ttk.Treeview(w, columns=cols, show="headings", selectmode="extended")
'''

new='''    top = tk.Frame(w)
    top.pack(fill="x", padx=14, pady=(14, 8))
    tk.Label(top, text="OUTLOOK-MAIL DEM PROJEKT ZUORDNEN", font=("Segoe UI", 15, "bold")).pack(anchor="w")
    tk.Label(top, text="Letzte 60 Tage · Mehrfachauswahl möglich · Original wird als .msg im Projekt archiviert.", fg="#666").pack(anchor="w", pady=(2, 6))

    searchbar = tk.Frame(top)
    searchbar.pack(fill="x", pady=(4, 0))

    tk.Label(searchbar, text="FILTER", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
    direction_var = tk.StringVar(value="Alle")
    direction_combo = ttk.Combobox(searchbar, textvariable=direction_var, state="readonly", width=12, values=("Alle", "Eingang", "Ausgang"))
    direction_combo.pack(side="left", padx=(0, 14))

    tk.Label(searchbar, text="SUCHE", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
    search_var = tk.StringVar()
    search_entry = tk.Entry(searchbar, textvariable=search_var, font=("Segoe UI", 10), bd=1, relief="solid")
    search_entry.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 8))

    result_var = tk.StringVar(value="")
    tk.Label(searchbar, textvariable=result_var, fg="#666").pack(side="right")

    cols = ("Zeit", "Richtung", "Von", "An", "Betreff", "Konto")
    tree = ttk.Treeview(w, columns=cols, show="headings", selectmode="extended")
'''
arch=one(arch,old,new,"picker search bar")

old='''    index_map = {}
    for idx, msg in enumerate(messages):
        iid = tree.insert(
            "", "end",
            values=(
                msg.get("ts", ""), msg.get("direction", ""), msg.get("sender", ""),
                msg.get("recipient", ""), msg.get("subject", ""), msg.get("account", ""),
            ),
        )
        index_map[iid] = idx

    buttons = tk.Frame(w)
'''

new='''    index_map = {}

    def refill():
        for iid in tree.get_children():
            tree.delete(iid)
        index_map.clear()

        needle = search_var.get().strip().casefold()
        mode = direction_var.get()
        shown = 0

        for idx, msg in enumerate(messages):
            direction = str(msg.get("direction", ""))
            if mode != "Alle" and direction != mode:
                continue

            if needle:
                haystack = " ".join([
                    str(msg.get("ts", "")),
                    direction,
                    str(msg.get("sender", "")),
                    str(msg.get("recipient", "")),
                    str(msg.get("subject", "")),
                    str(msg.get("account", "")),
                ]).casefold()
                if needle not in haystack:
                    continue

            iid = tree.insert(
                "", "end",
                values=(
                    msg.get("ts", ""), msg.get("direction", ""), msg.get("sender", ""),
                    msg.get("recipient", ""), msg.get("subject", ""), msg.get("account", ""),
                ),
            )
            index_map[iid] = idx
            shown += 1

        result_var.set(f"{shown} von {len(messages)} Mails")

    def reset_filter():
        direction_var.set("Alle")
        search_var.set("")
        refill()
        search_entry.focus_set()

    direction_combo.bind("<<ComboboxSelected>>", lambda _evt: refill())
    search_var.trace_add("write", lambda *_args: refill())
    tk.Button(searchbar, text="ZURÜCKSETZEN", command=reset_filter, bd=0, padx=10, pady=5).pack(side="right", padx=(8, 0))
    refill()

    buttons = tk.Frame(w)
'''
arch=one(arch,old,new,"picker refill")

old='''    status = tk.Label(buttons, text=f"{len(messages)} Outlook-Mails geladen", fg="#666")
    status.pack(side="left", padx=14)
'''
new='''    status = tk.Label(buttons, text=f"{len(messages)} Outlook-Mails geladen", fg="#666")
    status.pack(side="left", padx=14)
'''
# no-op marker check
if old not in arch:
    raise RuntimeError("status marker missing")

ARCH.write_text(arch,encoding="utf-8")

post=POST.read_text(encoding="utf-8")
post=post.replace("update_1830_install.log","update_1831_install.log")
post=post.replace("update_1830_error.txt","update_1831_error.txt")
post=one(post,'APP_VERSION = "1.8.30"','APP_VERSION = "1.8.31"',"post version")
post=post.replace("OK: Update 1.8.30 erfolgreich installiert.","OK: Update 1.8.31 erfolgreich installiert.")
POST.write_text(post,encoding="utf-8")

for p in (APP,POST,ARCH):
    py_compile.compile(str(p),doraise=True)

check=ARCH.read_text(encoding="utf-8")
for marker in ('direction_var = tk.StringVar(value="Alle")','SUCHE','ZURÜCKSETZEN','def refill()'):
    if marker not in check:
        raise RuntimeError("1.8.31 marker fehlt: "+marker)

print("OK 1.8.31 Outlook assignment search")
