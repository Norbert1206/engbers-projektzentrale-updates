from pathlib import Path
import py_compile, sys

ROOT=Path(sys.argv[1]).resolve()
APP=ROOT/"app.py"
POST=ROOT/"post_update.py"
OUTLOOK=ROOT/"outlook_v1822.py"

def one(t,a,b,label):
    c=t.count(a)
    if c!=1:
        raise RuntimeError(f"{label}: {c}")
    return t.replace(a,b,1)

app=APP.read_text(encoding="utf-8")
app=one(app,'APP_VERSION = "1.8.36"','APP_VERSION = "1.8.37"',"app version")
APP.write_text(app,encoding="utf-8")

out=OUTLOOK.read_text(encoding="utf-8")

anchor='''$ErrorActionPreference = "Stop"
function Decode-Utf8([string]$Value) {
'''
insert='''$ErrorActionPreference = "Stop"

Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class PZWindow {
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
}
"@

function Focus-OutlookInspector($mail) {
    try {
        $inspector = $mail.GetInspector
        Start-Sleep -Milliseconds 180
        $hwnd = [IntPtr]$inspector.HWND
        if ($hwnd -ne [IntPtr]::Zero) {
            if ([PZWindow]::IsIconic($hwnd)) {
                [void][PZWindow]::ShowWindow($hwnd, 9)
            } else {
                [void][PZWindow]::ShowWindow($hwnd, 5)
            }
            [void][PZWindow]::BringWindowToTop($hwnd)
            [void][PZWindow]::SetForegroundWindow($hwnd)
        }
    } catch {
        try {
            $shell = New-Object -ComObject WScript.Shell
            [void]$shell.AppActivate($mail.Subject)
        } catch {}
    }
}

function Decode-Utf8([string]$Value) {
'''
out=one(out,anchor,insert,"PowerShell focus helper")

old='''foreach ($path in $attachments) {
    if (Test-Path -LiteralPath $path -PathType Leaf) { [void]$mail.Attachments.Add($path) }
}
$mail.Display()
'''
new='''foreach ($path in $attachments) {
    if (Test-Path -LiteralPath $path -PathType Leaf) { [void]$mail.Attachments.Add($path) }
}
$mail.Display()
Focus-OutlookInspector $mail
'''
out=one(out,old,new,"focus after final display")
OUTLOOK.write_text(out,encoding="utf-8")

post=POST.read_text(encoding="utf-8")
post=post.replace("update_1836_install.log","update_1837_install.log")
post=post.replace("update_1836_error.txt","update_1837_error.txt")
post=one(post,'APP_VERSION = "1.8.36"','APP_VERSION = "1.8.37"',"post version")
post=post.replace("OK: Update 1.8.36 erfolgreich installiert.","OK: Update 1.8.37 erfolgreich installiert.")
POST.write_text(post,encoding="utf-8")

for p in (APP,POST,OUTLOOK):
    py_compile.compile(str(p),doraise=True)

check=OUTLOOK.read_text(encoding="utf-8")
for marker in ("Focus-OutlookInspector","SetForegroundWindow","BringWindowToTop","AppActivate"):
    if marker not in check:
        raise RuntimeError(marker)

print("OK 1.8.37 Outlook foreground")
