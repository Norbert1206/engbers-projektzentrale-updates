from pathlib import Path
import py_compile, sys

ROOT=Path(sys.argv[1]).resolve()
APP=ROOT/"app.py"
POST=ROOT/"post_update.py"
ARCH=ROOT/"outlook_archive_v1823.py"

def one(t,a,b,label):
    if t.count(a)!=1:
        raise RuntimeError(label)
    return t.replace(a,b,1)

app=APP.read_text(encoding="utf-8")
app=one(app,'APP_VERSION = "1.8.25"','APP_VERSION = "1.8.26"',"app")
APP.write_text(app,encoding="utf-8")

arch=ARCH.read_text(encoding="utf-8")
old='''function Add-FolderItems([object]$store, [int]$folderType, [string]$direction) {
    try { $folder = $store.GetDefaultFolder($folderType) } catch { return }
    if ($null -eq $folder) { return }
    $items = $folder.Items
'''
new='''function Add-FolderItems([object]$store, [int]$folderType, [string]$direction) {
    $folder = $null
    try { $folder = $store.GetDefaultFolder($folderType) } catch {}
    if ($null -eq $folder) {
        $wanted = @()
        if ($folderType -eq 6) { $wanted = @("posteingang","inbox") }
        if ($folderType -eq 5) { $wanted = @("gesendete elemente","gesendet","sent items","sent") }
        try {
            $root = $store.GetRootFolder()
            $folders = $root.Folders
            for ($k=1; $k -le $folders.Count; $k++) {
                $candidate = $folders.Item($k)
                $name = ([string]$candidate.Name).Trim().ToLowerInvariant()
                if ($wanted -contains $name) { $folder = $candidate; break }
            }
        } catch {}
    }
    if ($null -eq $folder) { return }
    $items = $folder.Items
'''
arch=one(arch,old,new,"folder")
ARCH.write_text(arch,encoding="utf-8")

post=POST.read_text(encoding="utf-8")
post=post.replace("update_1825_install.log","update_1826_install.log")
post=post.replace("update_1825_error.txt","update_1826_error.txt")
post=one(post,'APP_VERSION = "1.8.25"','APP_VERSION = "1.8.26"',"post")
post=post.replace("OK: Update 1.8.25 erfolgreich installiert.","OK: Update 1.8.26 erfolgreich installiert.")
POST.write_text(post,encoding="utf-8")

for p in (APP,POST,ARCH):
    py_compile.compile(str(p),doraise=True)
print("OK")
