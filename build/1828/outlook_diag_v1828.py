from __future__ import annotations

import os
import subprocess
import tkinter as tk
from tkinter import messagebox


def _run_diag() -> str:
    if os.name != "nt":
        raise RuntimeError("Die Outlook-Diagnose ist nur unter Windows verfügbar.")

    script = r'''
$ErrorActionPreference = "Stop"
try { $outlook = [Runtime.InteropServices.Marshal]::GetActiveObject("Outlook.Application") }
catch {
    $t = [type]::GetTypeFromProgID("Outlook.Application")
    if ($null -eq $t) { throw "Outlook (klassisch) wurde nicht gefunden." }
    $outlook = [Activator]::CreateInstance($t)
}
$ns = $outlook.GetNamespace("MAPI")
$lines = New-Object System.Collections.Generic.List[string]

function Add-Line([string]$s) { [void]$lines.Add($s) }
function C([object]$v) { if ($null -eq $v) { return "" }; return [string]$v }

Add-Line "OUTLOOK-DIAGNOSE"
Add-Line ("Stores: " + $ns.Stores.Count)
try { Add-Line ("Accounts: " + $ns.Accounts.Count) } catch { Add-Line "Accounts: nicht lesbar" }
Add-Line ""

function Walk([object]$folder, [int]$depth, [string]$prefix) {
    if ($null -eq $folder -or $depth -lt 0) { return }
    $name = ""
    $path = ""
    $count = "?"
    try { $name = C $folder.Name } catch {}
    try { $path = C $folder.FolderPath } catch {}
    try { $count = C $folder.Items.Count } catch {}
    Add-Line ($prefix + "- " + $name + " | Elemente: " + $count + " | Pfad: " + $path)
    if ($depth -eq 0) { return }
    try { $children = $folder.Folders } catch { return }
    for ($i=1; $i -le $children.Count; $i++) {
        try { $child = $children.Item($i) } catch { continue }
        Walk $child ($depth-1) ($prefix + "  ")
    }
}

$stores = $ns.Stores
for ($s=1; $s -le $stores.Count; $s++) {
    $store = $null
    try { $store = $stores.Item($s) } catch {}
    if ($null -eq $store) { continue }

    Add-Line ("KONTO " + $s)
    try {
        $f = $store.GetDefaultFolder(6)
        Add-Line ("  Standard-Posteingang: OK | Elemente: " + $f.Items.Count + " | " + (C $f.FolderPath))
    } catch {
        Add-Line ("  Standard-Posteingang: FEHLER | " + $_.Exception.Message)
    }
    try {
        $f = $store.GetDefaultFolder(5)
        Add-Line ("  Standard-Gesendet: OK | Elemente: " + $f.Items.Count + " | " + (C $f.FolderPath))
    } catch {
        Add-Line ("  Standard-Gesendet: FEHLER | " + $_.Exception.Message)
    }
    Add-Line "  Ordnerstruktur:"
    try { Walk ($store.GetRootFolder()) 4 "    " } catch { Add-Line ("    FEHLER: " + $_.Exception.Message) }
    Add-Line ""
}

$lines -join [Environment]::NewLine
'''
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, text=True, timeout=45, creationflags=flags,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Outlook-Diagnose hat nicht rechtzeitig reagiert.") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(detail.splitlines()[-1] if detail else "Outlook-Diagnose fehlgeschlagen.")
    return (result.stdout or "").strip() or "Keine Diagnosedaten zurückgegeben."


def open_outlook_diagnostics(parent):
    try:
        text = _run_diag()
    except Exception as exc:
        messagebox.showerror("Outlook-Diagnose", str(exc), parent=parent)
        return

    w = tk.Toplevel(parent)
    w.title("Outlook-Diagnose")
    w.geometry("1050x720")
    w.minsize(780, 520)
    try:
        w.transient(parent)
    except Exception:
        pass

    tk.Label(
        w,
        text="OUTLOOK-DIAGNOSE",
        font=("Segoe UI", 16, "bold"),
        anchor="w",
    ).pack(fill="x", padx=16, pady=(14, 2))
    tk.Label(
        w,
        text="Zeigt nur Konten-/Ordnerstruktur und Elementanzahlen – keine Mailtexte.",
        fg="#666666",
        anchor="w",
    ).pack(fill="x", padx=16, pady=(0, 10))

    box = tk.Text(w, wrap="none", font=("Consolas", 9))
    box.pack(fill="both", expand=True, padx=16, pady=(0, 10))
    box.insert("1.0", text)
    box.configure(state="disabled")

    def copy_all():
        try:
            parent.clipboard_clear()
            parent.clipboard_append(text)
            messagebox.showinfo("Outlook-Diagnose", "Diagnose wurde in die Zwischenablage kopiert.", parent=w)
        except Exception as exc:
            messagebox.showerror("Outlook-Diagnose", str(exc), parent=w)

    bar = tk.Frame(w)
    bar.pack(fill="x", padx=16, pady=(0, 14))
    tk.Button(bar, text="DIAGNOSE KOPIEREN", command=copy_all, padx=16, pady=8).pack(side="left")
    tk.Button(bar, text="SCHLIESSEN", command=w.destroy, padx=16, pady=8).pack(side="right")
    return w
