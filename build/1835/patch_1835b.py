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

post=POST.read_text(encoding="utf-8")
post=post.replace("update_1834_install.log","update_1835_install.log")
post=post.replace("update_1834_error.txt","update_1835_error.txt")
post=one(post,'APP_VERSION = "1.8.34"','APP_VERSION = "1.8.35"',"post version")
post=post.replace("OK: Update 1.8.34 erfolgreich installiert.","OK: Update 1.8.35 erfolgreich installiert.")
POST.write_text(post,encoding="utf-8")

for p in (APP,POST,SHARE):
    py_compile.compile(str(p),doraise=True)

print("OK 1.8.35")
