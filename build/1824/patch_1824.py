from pathlib import Path
import py_compile
import sys

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
APP = ROOT / "app.py"
POST = ROOT / "post_update.py"
ARCH = ROOT / "outlook_archive_v1823.py"

def replace_once(text, old, new, label):
    count=text.count(old)
    if count!=1:
        raise RuntimeError(f"1.8.24: Marker {label} erwartet 1x, gefunden {count}x")
    return text.replace(old,new,1)

app=APP.read_text(encoding="utf-8")
app=replace_once(app,'APP_VERSION = "1.8.23"','APP_VERSION = "1.8.24"',"app version")
APP.write_text(app,encoding="utf-8")

arch=ARCH.read_text(encoding="utf-8")
arch=replace_once(arch,'    return result.stdout.strip()\n','    return (result.stdout or "").strip()\n',"stdout None guard")
arch=replace_once(
    arch,
    '    if isinstance(data, dict):\n        data = [data]\n    return [x for x in data if isinstance(x, dict) and x.get("entry_id")]\n',
    '    if data is None:\n        return []\n    if isinstance(data, dict):\n        data = [data]\n    if not isinstance(data, list):\n        return []\n    return [x for x in data if isinstance(x, dict) and x.get("entry_id")]\n',
    "json null guard"
)
ARCH.write_text(arch,encoding="utf-8")

post=POST.read_text(encoding="utf-8")
post=post.replace("update_1823_install.log","update_1824_install.log")
post=post.replace("update_1823_error.txt","update_1824_error.txt")
post=replace_once(post,'APP_VERSION = "1.8.23"','APP_VERSION = "1.8.24"',"post version")
post=post.replace("OK: Update 1.8.23 erfolgreich installiert.","OK: Update 1.8.24 erfolgreich installiert.")
POST.write_text(post,encoding="utf-8")

for p in (APP,POST,ARCH):
    py_compile.compile(str(p),doraise=True)

print("OK: 1.8.24 Outlook Sync None hotfix")
