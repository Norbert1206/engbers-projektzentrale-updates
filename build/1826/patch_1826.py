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
old='''$stores = $ns.Stores
for ($s = 1; $s -le $stores.Count; $s++) {
    try { $store = $stores.Item($s) } catch { continue }
    if ($null -eq $store) { continue }
    $seen = @{}
    try { Add-FolderIfNew ($store.GetDefaultFolder(6)) "Eingang" $seen } catch {}
    try { Add-FolderIfNew ($store.GetDefaultFolder(5)) "Ausgang" $seen } catch {}
    try {
        $root = $store.GetRootFolder()
        Visit-Children $root 2 $seen
    } catch {}
}

$sorted = @($result | Sort-Object ts -Descending)
ConvertTo-Json -InputObject $sorted -Compress -Depth 4
'''
if old not in arch:
    old='''$stores = $ns.Stores
for ($s = 1; $s -le $stores.Count; $s++) {
    try { $store = $stores.Item($s) } catch { continue }
    if ($null -eq $store) { continue }
    Add-FolderItems $store 6 "Eingang"
    Add-FolderItems $store 5 "Ausgang"
}
$sorted = @($result | Sort-Object ts -Descending)
ConvertTo-Json -InputObject $sorted -Compress -Depth 4
'''

new='''function ScanNamedFolders([object]$folder, [int]$depth, [object]$store) {
    if ($null -eq $folder -or $depth -lt 0) { return }
    try { $children = $folder.Folders } catch { return }
    for ($j=1; $j -le $children.Count; $j++) {
        try { $child = $children.Item($j) } catch { continue }
        if ($null -eq $child) { continue }
        $n = ""
        try { $n = ([string]$child.Name).Trim().ToLowerInvariant() } catch {}
        if ($n -eq "posteingang" -or $n -eq "inbox") {
            try { Add-FolderItems $store 6 "Eingang" } catch {}
        }
        if ($n -eq "gesendete elemente" -or $n -eq "sent items" -or $n -eq "gesendet" -or $n -eq "sent") {
            try { Add-FolderItems $store 5 "Ausgang" } catch {}
        }
        if ($depth -gt 0) { ScanNamedFolders $child ($depth-1) $store }
    }
}

$stores = $ns.Stores
for ($s = 1; $s -le $stores.Count; $s++) {
    try { $store = $stores.Item($s) } catch { continue }
    if ($null -eq $store) { continue }
    try { Add-FolderItems $store 6 "Eingang" } catch {}
    try { Add-FolderItems $store 5 "Ausgang" } catch {}
    try { ScanNamedFolders ($store.GetRootFolder()) 2 $store } catch {}
}

$sorted = @($result | Sort-Object ts -Descending)
ConvertTo-Json -InputObject $sorted -Compress -Depth 4
'''
arch=one(arch,old,new,"scanner")
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
