from pathlib import Path
import py_compile, sys

ROOT=Path(sys.argv[1]).resolve()
APP=ROOT/"app.py"; POST=ROOT/"post_update.py"; ARCH=ROOT/"outlook_archive_v1823.py"

def one(t,a,b,label):
    c=t.count(a)
    if c!=1: raise RuntimeError(f"{label}: {c}")
    return t.replace(a,b,1)

app=APP.read_text(encoding="utf-8")
app=one(app,'APP_VERSION = "1.8.26"','APP_VERSION = "1.8.27"',"app version")
APP.write_text(app,encoding="utf-8")

arch=ARCH.read_text(encoding="utf-8")
marker="\n\ndef scan_outlook(project_number: str = \"\", *, recent=False, days=180, limit=700) -> list[dict]:\n"
if marker not in arch: raise RuntimeError("scan_outlook marker missing")
new_func=r'''
def _scan_script_v1827() -> str:
    return r"""
$ErrorActionPreference = "Stop"
$projectNumber = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($env:PZ_PROJECT_NUMBER_B64))
$mode = $env:PZ_SCAN_MODE
$limit = [int]$env:PZ_SCAN_LIMIT
$days = [int]$env:PZ_SCAN_DAYS
$cutoff = (Get-Date).AddDays(-1 * $days)
$projectProp = "http://schemas.microsoft.com/mapi/string/{00020329-0000-0000-C000-000000000046}/EngbersProjectNumber"

try { $outlook = [Runtime.InteropServices.Marshal]::GetActiveObject("Outlook.Application") }
catch {
    $outlookType = [type]::GetTypeFromProgID("Outlook.Application")
    if ($null -eq $outlookType) { throw "Outlook (klassisch) wurde auf diesem Windows-PC nicht gefunden." }
    $outlook = [Activator]::CreateInstance($outlookType)
}
$ns = $outlook.GetNamespace("MAPI")
$result = New-Object System.Collections.Generic.List[object]
$seen = @{}

function T([object]$v) {
    if ($null -eq $v) { return "" }
    return [string]$v
}

function Folder-Direction([object]$folder) {
    $name = ""
    $path = ""
    try { $name = (T $folder.Name).ToLowerInvariant() } catch {}
    try { $path = (T $folder.FolderPath).ToLowerInvariant() } catch {}
    $all = $name + " " + $path
    if ($all -match "gesend|sent items|\\sent($|\\)|/sent($|/)" ) { return "Ausgang" }
    if ($all -match "posteingang|inbox") { return "Eingang" }
    return ""
}

function Add-RealFolder([object]$folder, [object]$store, [string]$direction) {
    if ($null -eq $folder) { return }
    try { $items = $folder.Items } catch { return }
    if ($null -eq $items) { return }

    if ($direction -eq "Ausgang") {
        try { $items.Sort("[SentOn]", $true) } catch {}
    } else {
        try { $items.Sort("[ReceivedTime]", $true) } catch {}
    }

    $count = [Math]::Min($items.Count, $limit)
    for ($i=1; $i -le $count; $i++) {
        try { $item = $items.Item($i) } catch { continue }
        if ($null -eq $item) { continue }
        try { if ([int]$item.Class -ne 43) { continue } } catch { continue }

        $entry = ""
        try { $entry = T $item.EntryID } catch {}
        if ([string]::IsNullOrWhiteSpace($entry)) { continue }
        if ($seen.ContainsKey($entry)) { continue }

        $stamp = $null
        if ($direction -eq "Ausgang") {
            try { $stamp = [datetime]$item.SentOn } catch {}
        } else {
            try { $stamp = [datetime]$item.ReceivedTime } catch {}
        }
        if ($null -eq $stamp) {
            try { $stamp = [datetime]$item.ReceivedTime } catch {}
        }
        if ($null -eq $stamp) {
            try { $stamp = [datetime]$item.SentOn } catch {}
        }
        if ($null -eq $stamp -or $stamp -lt $cutoff) { continue }

        $subject = T $item.Subject
        $body = T $item.Body
        $tag = ""
        try { $tag = T $item.PropertyAccessor.GetProperty($projectProp) } catch {}

        $match = $false
        if ($mode -eq "recent") { $match = $true }
        elseif (-not [string]::IsNullOrWhiteSpace($projectNumber)) {
            if ($tag -eq $projectNumber) { $match = $true }
            elseif ($subject.IndexOf($projectNumber,[StringComparison]::OrdinalIgnoreCase) -ge 0) { $match = $true }
            elseif ($body.IndexOf($projectNumber,[StringComparison]::OrdinalIgnoreCase) -ge 0) { $match = $true }
        }
        if (-not $match) { continue }

        $seen[$entry] = $true
        $sender = ""; $recipient = ""
        try { $sender = T $item.SenderName } catch {}
        if ([string]::IsNullOrWhiteSpace($sender)) { try { $sender = T $item.SenderEmailAddress } catch {} }
        try { $recipient = T $item.To } catch {}

        $att = New-Object System.Collections.Generic.List[string]
        try {
            for ($a=1; $a -le $item.Attachments.Count; $a++) {
                try { [void]$att.Add((T $item.Attachments.Item($a).FileName)) } catch {}
            }
        } catch {}

        $preview = $body
        if ($preview.Length -gt 12000) { $preview = $preview.Substring(0,12000) }
        $storeId = ""; $account = ""
        try { $storeId = T $store.StoreID } catch {}
        try { $account = T $store.DisplayName } catch {}

        [void]$result.Add([pscustomobject]@{
            ts=$stamp.ToString("yyyy-MM-dd HH:mm:ss")
            direction=($(if ($direction) { $direction } else { "Outlook" }))
            sender=$sender
            recipient=$recipient
            subject=$subject
            body=$preview
            attachment=($att -join "; ")
            entry_id=$entry
            store_id=$storeId
            tagged_project=$tag
            account=$account
        })
    }
}

function Walk-Folders([object]$folder, [object]$store, [int]$depth) {
    if ($null -eq $folder -or $depth -lt 0) { return }
    $direction = Folder-Direction $folder
    if (-not [string]::IsNullOrWhiteSpace($direction)) {
        Add-RealFolder $folder $store $direction
    }
    try { $children = $folder.Folders } catch { return }
    for ($j=1; $j -le $children.Count; $j++) {
        try { $child = $children.Item($j) } catch { continue }
        Walk-Folders $child $store ($depth-1)
    }
}

$stores = $ns.Stores
for ($s=1; $s -le $stores.Count; $s++) {
    try { $store = $stores.Item($s) } catch { continue }
    if ($null -eq $store) { continue }

    try { Add-RealFolder ($store.GetDefaultFolder(6)) $store "Eingang" } catch {}
    try { Add-RealFolder ($store.GetDefaultFolder(5)) $store "Ausgang" } catch {}
    try { Walk-Folders ($store.GetRootFolder()) $store 4 } catch {}
}

$sorted = @($result | Sort-Object ts -Descending)
ConvertTo-Json -InputObject $sorted -Compress -Depth 4
"""
'''
arch=arch.replace(marker,"\n\n"+new_func+marker,1)
arch=one(arch,"        _scan_script(),\n","        _scan_script_v1827(),\n","scanner call")
ARCH.write_text(arch,encoding="utf-8")

post=POST.read_text(encoding="utf-8")
post=post.replace("update_1826_install.log","update_1827_install.log")
post=post.replace("update_1826_error.txt","update_1827_error.txt")
post=one(post,'APP_VERSION = "1.8.26"','APP_VERSION = "1.8.27"',"post version")
post=post.replace("OK: Update 1.8.26 erfolgreich installiert.","OK: Update 1.8.27 erfolgreich installiert.")
POST.write_text(post,encoding="utf-8")

for p in (APP,POST,ARCH): py_compile.compile(str(p),doraise=True)
print("OK 1.8.27 recursive Outlook folder reader")
