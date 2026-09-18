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
app=one(app,'APP_VERSION = "1.8.33"','APP_VERSION = "1.8.34"',"app version")
APP.write_text(app,encoding="utf-8")

hid=HIDRIVE.read_text(encoding="utf-8")
if "import time\n" not in hid:
    hid=hid.replace("import threading\n","import threading\nimport time\n",1)

insert_after='''def _api_get(path: str, access_token: str, params=None) -> dict:
'''
pos=hid.index(insert_after)
# insert helper before _exchange_code by locating its definition
end=hid.index("\n\ndef _exchange_code", pos)
extra=r'''

def _api_post(path: str, access_token: str, params=None) -> dict:
    qs = urllib.parse.urlencode(params or {})
    url = API_BASE + path + (("?" + qs) if qs else "")
    req = urllib.request.Request(
        url,
        data=b"",
        headers={"Authorization": "Bearer " + access_token},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            parsed = json.loads(exc.read().decode("utf-8", errors="replace"))
            detail = str(parsed.get("error_description") or parsed.get("error") or "").strip()
        except Exception:
            pass
        raise RuntimeError(f"HiDrive-API Fehler {exc.code}" + (f": {detail}" if detail else "")) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("HiDrive-API konnte nicht erreicht werden.") from exc
    if not body.strip():
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("HiDrive-API hat eine unerwartete Antwort geliefert.") from exc


def remote_path_for_local(local_path) -> tuple[dict, str]:
    cfg = verify_connection()
    local_root = (Path.home() / "HiDrive").resolve()
    target = Path(local_path).resolve()
    try:
        rel = target.relative_to(local_root)
    except Exception as exc:
        raise RuntimeError(
            "Der Freigabeordner liegt nicht innerhalb des lokalen HiDrive-Ordners."
        ) from exc

    home = str(cfg.get("home") or "").strip()
    if not home:
        raise RuntimeError("HiDrive hat keinen Home-Pfad fuer den angemeldeten Benutzer geliefert.")

    remote = home.rstrip("/") + "/" + rel.as_posix()
    return cfg, remote


def create_share_link_for_local_dir(local_dir, wait_seconds=90) -> dict:
    cfg, remote_path = remote_path_for_local(local_dir)
    token = str(cfg.get("access_token") or "").strip()
    if not token:
        raise RuntimeError("HiDrive ist nicht verbunden.")

    deadline = time.time() + max(5, int(wait_seconds))
    last_error = ""
    while time.time() < deadline:
        try:
            _api_get("/dir", token, {"path": remote_path, "fields": "id,path,name"})
            last_error = ""
            break
        except Exception as exc:
            last_error = str(exc)
            if "404" not in last_error:
                raise
            time.sleep(2.5)
    else:
        raise RuntimeError(
            "Der neue Freigabeordner ist noch nicht in HiDrive angekommen. "
            "Bitte kurz warten und den HiDrive-Link erneut erzeugen."
            + (f"\n\nLetzte API-Meldung: {last_error}" if last_error else "")
        )

    share = _api_post(
        "/share",
        token,
        {
            "path": remote_path,
            "writable": "false",
            "fields": "id,uri,path,status,ttl,valid_until,has_password",
        },
    )
    uri = str(share.get("uri") or "").strip() if isinstance(share, dict) else ""
    if not uri:
        raise RuntimeError("HiDrive hat die Freigabe erstellt, aber keinen Freigabelink zurueckgegeben.")
    share["remote_path"] = remote_path
    return share
'''
hid=hid[:end]+extra+hid[end:]

old_all='''__all__ = [
    "open_setup_dialog",
    "connection_summary",
    "load_config",
    "verify_connection",
    "refresh_access_token",
]
'''
new_all='''__all__ = [
    "open_setup_dialog",
    "connection_summary",
    "load_config",
    "verify_connection",
    "refresh_access_token",
    "create_share_link_for_local_dir",
]
'''
hid=one(hid,old_all,new_all,"hidrive exports")
HIDRIVE.write_text(hid,encoding="utf-8")

basket=BASKET.read_text(encoding="utf-8")

old='''    index_map = {}

    def refresh():
'''
new='''    index_map = {}
    last_share_link = {"url": ""}
    pending_release = {"path": None}

    def refresh():
'''
basket=one(basket,old,new,"basket state")

old='''    def create_now():
        try:
            release, copied = create_release(project_id, project_number, project_title)
        except Exception as exc:
            messagebox.showerror("Projektfreigabe", str(exc), parent=w)
            return
        clear_items(project_id)
        refresh()
        try:
            app.open_external_path(release)
        except Exception:
            pass
        messagebox.showinfo(
            "Projektfreigabe",
            f"{copied} Datei(en) als Kopie bereitgestellt.\n\n{release}\n\n"
            "Die Originaldateien wurden nicht verändert. HiDrive synchronisiert den Ordner automatisch.",
            parent=w,
        )
'''
new='''    def create_now():
        try:
            release, copied = create_release(project_id, project_number, project_title)
        except Exception as exc:
            messagebox.showerror("Projektfreigabe", str(exc), parent=w)
            return
        clear_items(project_id)
        refresh()
        try:
            app.open_external_path(release)
        except Exception:
            pass
        messagebox.showinfo(
            "Projektfreigabe",
            f"{copied} Datei(en) als Kopie bereitgestellt.\n\n{release}\n\n"
            "Die Originaldateien wurden nicht verändert. HiDrive synchronisiert den Ordner automatisch.",
            parent=w,
        )

    def create_hidrive_link():
        if not get_items(project_id) and not pending_release["path"]:
            messagebox.showwarning("HiDrive-Freigabe", "Der Freigabekorb ist leer.", parent=w)
            return

        try:
            from hidrive_oauth_v1832 import create_share_link_for_local_dir, connection_summary
            if "verbunden" not in connection_summary().casefold():
                messagebox.showwarning(
                    "HiDrive-Freigabe",
                    "HiDrive ist noch nicht verbunden. Bitte zuerst HIDRIVE EINRICHTEN verwenden.",
                    parent=w,
                )
                return
        except Exception as exc:
            messagebox.showerror("HiDrive-Freigabe", str(exc), parent=w)
            return

        link_btn.configure(state="disabled", text="HIDRIVE WIRD VORBEREITET …")

        def worker():
            created_now = False
            release = pending_release["path"]
            copied = 0
            try:
                if not release:
                    release, copied = create_release(project_id, project_number, project_title)
                    pending_release["path"] = release
                    created_now = True
                share = create_share_link_for_local_dir(release, wait_seconds=90)
                result = ("ok", release, copied, share)
            except Exception as exc:
                result = ("error", release, copied, str(exc), created_now)

            def done():
                link_btn.configure(state="normal", text="HIDRIVE-LINK")
                if result[0] == "ok":
                    release, copied, share = result[1], result[2], result[3]
                    url = str(share.get("uri") or "").strip()
                    last_share_link["url"] = url
                    pending_release["path"] = None
                    clear_items(project_id)
                    refresh()
                    try:
                        app.clipboard_clear()
                        app.clipboard_append(url)
                    except Exception:
                        pass
                    messagebox.showinfo(
                        "HiDrive-Freigabe",
                        "Freigabelink wurde erstellt und in die Zwischenablage kopiert.\n\n"
                        + url
                        + "\n\nMit OUTLOOK-MAIL wird der Link automatisch in den Mailtext eingefügt.",
                        parent=w,
                    )
                else:
                    release = result[1]
                    detail = result[3]
                    msg = detail
                    if release:
                        msg += (
                            "\n\nDer Freigabeordner wurde bereits erstellt und bleibt erhalten. "
                            "Beim nächsten Klick auf HIDRIVE-LINK wird derselbe Ordner erneut versucht."
                            f"\n\n{release}"
                        )
                    messagebox.showerror("HiDrive-Freigabe", msg, parent=w)

            try:
                w.after(0, done)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()
'''
basket=one(basket,old,new,"create_hidrive_link")

if "import threading" not in basket:
    basket=basket.replace("import shutil\n","import shutil\nimport threading\n",1)

old='''            body = tk.Text(frame, height=13, wrap="word", font=("Segoe UI", 10), bd=1, relief="solid")
            body.pack(fill="both", expand=True, pady=(12, 8))
            body.insert("1.0", f"{greeting},\n\nanbei erhalten Sie die aktuellen Unterlagen zum Bauvorhaben {project_number} – {project_title}.\n")

            attachments = _attachment_files()
'''
new='''            body = tk.Text(frame, height=13, wrap="word", font=("Segoe UI", 10), bd=1, relief="solid")
            body.pack(fill="both", expand=True, pady=(12, 8))
            initial_body = f"{greeting},\n\nanbei erhalten Sie die aktuellen Unterlagen zum Bauvorhaben {project_number} – {project_title}.\n"
            if last_share_link["url"]:
                initial_body += f"\nHiDrive-Freigabelink:\n{last_share_link['url']}\n"
            body.insert("1.0", initial_body)

            attachments = _attachment_files()
'''
basket=one(basket,old,new,"outlook body link")

old='''            status = tk.Label(frame, text="Für große Unterlagen ist später der HiDrive-Link die bessere Variante.", bg=BG, fg=MUTED, anchor="w")
            status.pack(fill="x")
'''
new='''            status_text = (
                "Der erzeugte HiDrive-Link ist bereits im Mailtext eingefügt."
                if last_share_link["url"]
                else "Für große Unterlagen ist der HiDrive-Link die bessere Variante."
            )
            status = tk.Label(frame, text=status_text, bg=BG, fg=MUTED, anchor="w")
            status.pack(fill="x")
'''
basket=one(basket,old,new,"outlook status")

old='''    tk.Button(buttons, text="FREIGABE ERSTELLEN", command=create_now, bg=ACCENT, fg="white", bd=0, padx=18, pady=8).pack(side="right")
    tk.Button(buttons, text="OUTLOOK-MAIL", command=open_outlook_mail, bg=DARK, fg="white", bd=0, padx=18, pady=8).pack(side="right", padx=8)
'''
new='''    tk.Button(buttons, text="FREIGABE ERSTELLEN", command=create_now, bg=ACCENT, fg="white", bd=0, padx=14, pady=8).pack(side="right")
    link_btn = tk.Button(buttons, text="HIDRIVE-LINK", command=create_hidrive_link, bg=ACCENT, fg="white", bd=0, padx=14, pady=8)
    link_btn.pack(side="right", padx=8)
    tk.Button(buttons, text="OUTLOOK-MAIL", command=open_outlook_mail, bg=DARK, fg="white", bd=0, padx=14, pady=8).pack(side="right")
'''
basket=one(basket,old,new,"link button")
BASKET.write_text(basket,encoding="utf-8")

post=POST.read_text(encoding="utf-8")
post=post.replace("update_1833_install.log","update_1834_install.log")
post=post.replace("update_1833_error.txt","update_1834_error.txt")
post=one(post,'APP_VERSION = "1.8.33"','APP_VERSION = "1.8.34"',"post version")
post=post.replace("OK: Update 1.8.33 erfolgreich installiert.","OK: Update 1.8.34 erfolgreich installiert.")
POST.write_text(post,encoding="utf-8")

for p in (APP,POST,BASKET,HIDRIVE):
    py_compile.compile(str(p),doraise=True)

for marker in ("HIDRIVE-LINK","create_hidrive_link","last_share_link","pending_release"):
    if marker not in BASKET.read_text(encoding="utf-8"):
        raise RuntimeError("1.8.34 marker fehlt: "+marker)
for marker in ("create_share_link_for_local_dir","remote_path_for_local","/share"):
    if marker not in HIDRIVE.read_text(encoding="utf-8"):
        raise RuntimeError("1.8.34 HiDrive marker fehlt: "+marker)

print("OK 1.8.34 HiDrive link generation")
