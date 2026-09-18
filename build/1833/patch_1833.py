from pathlib import Path
import py_compile, sys

ROOT=Path(sys.argv[1]).resolve()
APP=ROOT/"app.py"
POST=ROOT/"post_update.py"
HIDRIVE=ROOT/"hidrive_oauth_v1832.py"

def one(t,a,b,label):
    c=t.count(a)
    if c!=1:
        raise RuntimeError(f"{label}: {c}")
    return t.replace(a,b,1)

app=APP.read_text(encoding="utf-8")
app=one(app,'APP_VERSION = "1.8.32"','APP_VERSION = "1.8.33"',"app version")
APP.write_text(app,encoding="utf-8")

hid=HIDRIVE.read_text(encoding="utf-8")
old='''    params = {
        "client_id": client_id,
        "response_type": "code",
        "scope": REQUESTED_SCOPE,
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "lang": "de",
    }
'''
new='''    # HiDrive accepts only the redirect URI stored for the registered app.
    # Omitting redirect_uri makes HiDrive use that registered default directly.
    # Our localhost listener still accepts the callback on port 8765.
    params = {
        "client_id": client_id,
        "response_type": "code",
        "scope": REQUESTED_SCOPE,
        "state": state,
        "lang": "de",
    }
'''
hid=one(hid,old,new,"authorize redirect parameter")
HIDRIVE.write_text(hid,encoding="utf-8")

post=POST.read_text(encoding="utf-8")
post=post.replace("update_1832_install.log","update_1833_install.log")
post=post.replace("update_1832_error.txt","update_1833_error.txt")
post=one(post,'APP_VERSION = "1.8.32"','APP_VERSION = "1.8.33"',"post version")
post=post.replace("OK: Update 1.8.32 erfolgreich installiert.","OK: Update 1.8.33 erfolgreich installiert.")
POST.write_text(post,encoding="utf-8")

for p in (APP,POST,HIDRIVE):
    py_compile.compile(str(p),doraise=True)

check=HIDRIVE.read_text(encoding="utf-8")
authorize_block=check[check.index('params = {'):check.index('url = AUTH_URL',check.index('params = {'))]
if '"redirect_uri"' in authorize_block:
    raise RuntimeError("redirect_uri is still sent")
if 'REDIRECT_URI = "http://localhost:8765"' not in check:
    raise RuntimeError("local callback listener constant missing")
print("OK 1.8.33 HiDrive default redirect URI")
