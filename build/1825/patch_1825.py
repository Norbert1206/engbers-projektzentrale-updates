from pathlib import Path
import py_compile, sys
ROOT=Path(sys.argv[1]).resolve()
APP=ROOT/"app.py"; POST=ROOT/"post_update.py"; ARCH=ROOT/"outlook_archive_v1823.py"
def one(t,a,b,label):
    if t.count(a)!=1: raise RuntimeError(label)
    return t.replace(a,b,1)
app=APP.read_text(encoding="utf-8")
app=one(app,'APP_VERSION = "1.8.24"','APP_VERSION = "1.8.25"',"app")
APP.write_text(app,encoding="utf-8")
arch=ARCH.read_text(encoding="utf-8")
old='foreach ($store in @($ns.Stores)) {\n    Add-FolderItems $store 6 "Eingang"\n    Add-FolderItems $store 5 "Ausgang"\n}\n$result | Sort-Object ts -Descending | ConvertTo-Json -Compress -Depth 4\n'
new='$stores = $ns.Stores\nfor ($s = 1; $s -le $stores.Count; $s++) {\n    try { $store = $stores.Item($s) } catch { continue }\n    if ($null -eq $store) { continue }\n    Add-FolderItems $store 6 "Eingang"\n    Add-FolderItems $store 5 "Ausgang"\n}\n$sorted = @($result | Sort-Object ts -Descending)\nConvertTo-Json -InputObject $sorted -Compress -Depth 4\n'
arch=one(arch,old,new,"stores")
ARCH.write_text(arch,encoding="utf-8")
post=POST.read_text(encoding="utf-8")
post=post.replace("update_1824_install.log","update_1825_install.log").replace("update_1824_error.txt","update_1825_error.txt")
post=one(post,'APP_VERSION = "1.8.24"','APP_VERSION = "1.8.25"',"post")
post=post.replace("OK: Update 1.8.24 erfolgreich installiert.","OK: Update 1.8.25 erfolgreich installiert.")
POST.write_text(post,encoding="utf-8")
for p in (APP,POST,ARCH): py_compile.compile(str(p),doraise=True)
print("OK 1.8.25")
