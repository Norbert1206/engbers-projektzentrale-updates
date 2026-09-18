from pathlib import Path
import py_compile, sys

ROOT=Path(sys.argv[1]).resolve()
APP=ROOT/"app.py"
POST=ROOT/"post_update.py"
BASKET=ROOT/"share_basket_v1821.py"

def one(t,a,b,label):
    c=t.count(a)
    if c!=1:
        raise RuntimeError(f"{label}: {c}")
    return t.replace(a,b,1)

app=APP.read_text(encoding="utf-8")
app=one(app,'APP_VERSION = "1.8.35"','APP_VERSION = "1.8.36"',"app version")
APP.write_text(app,encoding="utf-8")

basket=BASKET.read_text(encoding="utf-8")

basket=one(
    basket,
    '    pending_release = {"path": None}\n\n    def refresh():\n',
    '    pending_release = {"path": None}\n    last_share_link = {"url": ""}\n\n    def refresh():\n',
    "share link state",
)

basket=one(
    basket,
    '                    url = str(share.get("uri") or "").strip()\n                    pending_release["path"] = None\n',
    '                    url = str(share.get("uri") or "").strip()\n                    last_share_link["url"] = url\n                    pending_release["path"] = None\n',
    "store successful link",
)

anchor='    def _attachment_files():\n'
helper='''    def _current_share_link():
        url = str(last_share_link.get("url") or "").strip()
        if url:
            return url
        try:
            clip = str(app.clipboard_get() or "").strip()
        except Exception:
            clip = ""
        if clip.startswith("https://my.hidrive.com/share/"):
            last_share_link["url"] = clip
            return clip
        return ""

'''
basket=one(basket,anchor,helper+anchor,"share link helper")

old='            body.insert("1.0", f"{greeting},\\n\\nanbei erhalten Sie die aktuellen Unterlagen zum Bauvorhaben {project_number} – {project_title}.\\n")\n'
new='''            initial_body = f"{greeting},\\n\\nanbei erhalten Sie die aktuellen Unterlagen zum Bauvorhaben {project_number} – {project_title}.\\n"
            share_url = _current_share_link()
            if share_url:
                initial_body += f"\\nDie Unterlagen können Sie über folgenden HiDrive-Link herunterladen:\\n{share_url}\\n"
            body.insert("1.0", initial_body)
'''
basket=one(basket,old,new,"Outlook body link")

old='            status = tk.Label(frame, text="Für große Unterlagen ist später der HiDrive-Link die bessere Variante.", bg=BG, fg=MUTED, anchor="w")\n'
new='''            status_text = (
                "HiDrive-Freigabelink wurde automatisch in den Mailtext übernommen."
                if share_url
                else "Für große Unterlagen ist der HiDrive-Link die bessere Variante."
            )
            status = tk.Label(frame, text=status_text, bg=BG, fg=MUTED, anchor="w")
'''
basket=one(basket,old,new,"Outlook status")
BASKET.write_text(basket,encoding="utf-8")

post=POST.read_text(encoding="utf-8")
post=post.replace("update_1835_install.log","update_1836_install.log")
post=post.replace("update_1835_error.txt","update_1836_error.txt")
post=one(post,'APP_VERSION = "1.8.35"','APP_VERSION = "1.8.36"',"post version")
post=post.replace("OK: Update 1.8.35 erfolgreich installiert.","OK: Update 1.8.36 erfolgreich installiert.")
POST.write_text(post,encoding="utf-8")

for p in (APP,POST,BASKET):
    py_compile.compile(str(p),doraise=True)

check=BASKET.read_text(encoding="utf-8")
for marker in ("last_share_link","_current_share_link","HiDrive-Freigabelink wurde automatisch","my.hidrive.com/share/"):
    if marker not in check:
        raise RuntimeError(marker)

print("OK 1.8.36")
