from pathlib import Path
import py_compile, sys

ROOT=Path(sys.argv[1]).resolve()
APP=ROOT/"app.py"
POST=ROOT/"post_update.py"
SHARE=ROOT/"hidrive_sharelink_v1834.py"

def one(t,a,b,label):
    c=t.count(a)
    if c!=1:
        raise RuntimeError(f"{label}: {c}")
    return t.replace(a,b,1)

app=APP.read_text(encoding="utf-8")
app=one(app,'APP_VERSION = "1.8.34"','APP_VERSION = "1.8.35"',"app version")
APP.write_text(app,encoding="utf-8")

share=SHARE.read_text(encoding="utf-8")

old='''    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            parsed = json.loads(exc.read().decode("utf-8", errors="replace"))
            detail = str(parsed.get("error_description") or parsed.get("error") or "").strip()
        except Exception:
            pass
        raise RuntimeError(f"HiDrive-API Fehler {exc.code}" + (f": {detail}" if detail else "")) from exc
'''
new='''    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            raw = exc.read().decode("utf-8", errors="replace").strip()
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    detail = str(
                        parsed.get("error_description")
                        or parsed.get("message")
                        or parsed.get("error")
                        or raw
                    ).strip()
                else:
                    detail = raw
            except Exception:
                detail = raw
        except Exception:
            pass
        raise RuntimeError(f"HiDrive-API Fehler {exc.code}" + (f": {detail}" if detail else "")) from exc
'''
# replace both GET and POST handlers
if share.count(old) != 2:
    raise RuntimeError(f"http error blocks: {share.count(old)}")
share=share.replace(old,new,2)

old='''    deadline = time.time() + max(5, int(wait_seconds))
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
'''
new='''    deadline = time.time() + max(5, int(wait_seconds))
    last_error = ""
    dir_info = {}
    while time.time() < deadline:
        try:
            dir_info = _api_get("/dir", token, {"path": remote_path, "fields": "id,path,name"})
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

    dir_id = str(dir_info.get("id") or "").strip() if isinstance(dir_info, dict) else ""
    if not dir_id:
        raise RuntimeError("HiDrive hat für den Freigabeordner keine Verzeichnis-ID geliefert.")

    # Minimaler POST: Die HiDrive-Dokumentation definiert die Freigabe standardmäßig
    # als read-only. Über die Verzeichnis-ID vermeiden wir Pfad-/Encoding-Probleme.
    share = _api_post("/share", token, {"pid": dir_id})
'''
share=one(share,old,new,"share creation block")
SHARE.write_text(share,encoding="utf-8")

post=POST.read_text(encoding="utf-8")
post=post.replace("update_1834_install.log","update_1835_install.log")
post=post.replace("update_1834_error.txt","update_1835_error.txt")
post=one(post,'APP_VERSION = "1.8.34"','APP_VERSION = "1.8.35"',"post version")
post=post.replace("OK: Update 1.8.34 erfolgreich installiert.","OK: Update 1.8.35 erfolgreich installiert.")
POST.write_text(post,encoding="utf-8")

for p in (APP,POST,SHARE):
    py_compile.compile(str(p),doraise=True)

check=SHARE.read_text(encoding="utf-8")
for marker in ('{"pid": dir_id}','dir_info = _api_get("/dir"','keine Verzeichnis-ID','detail = raw'):
    if marker not in check:
        raise RuntimeError(marker)

print("OK 1.8.35 HiDrive share PID fix")
