from __future__ import annotations

import base64
import datetime as _dt
import hashlib
import json
import os
import re
import sqlite3
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

MAPI_PROJECT_PROP = "http://schemas.microsoft.com/mapi/string/{00020329-0000-0000-C000-000000000046}/EngbersProjectNumber"


def _b64(value: str) -> str:
    return base64.b64encode(str(value or "").encode("utf-8")).decode("ascii")


def _powershell(script: str, env_extra=None, timeout=45) -> str:
    if os.name != "nt":
        raise RuntimeError("Die Outlook-Anbindung ist nur unter Windows verfügbar.")
    env = os.environ.copy()
    if env_extra:
        env.update({str(k): str(v) for k, v in env_extra.items()})
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            env=env, capture_output=True, text=True, timeout=timeout, creationflags=flags,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("Windows PowerShell wurde nicht gefunden.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Outlook hat nicht rechtzeitig reagiert.") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        if detail:
            detail = detail.splitlines()[-1]
        raise RuntimeError(detail or "Outlook konnte nicht gelesen werden.")
    return result.stdout.strip()


def ensure_schema(db_path) -> None:
    con = sqlite3.connect(db_path)
    try:
        cols = {row[1] for row in con.execute("PRAGMA table_info(comm)").fetchall()}
        if "outlook_entry_id" not in cols:
            con.execute("ALTER TABLE comm ADD COLUMN outlook_entry_id TEXT DEFAULT ''")
        if "outlook_store_id" not in cols:
            con.execute("ALTER TABLE comm ADD COLUMN outlook_store_id TEXT DEFAULT ''")
        con.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_comm_outlook_unique "
            "ON comm(project_id,outlook_entry_id,outlook_store_id) "
            "WHERE outlook_entry_id<>''"
        )
        con.commit()
    finally:
        con.close()


def _scan_script() -> str:
    return r'''
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

function Clean-Text([object]$Value) {
    if ($null -eq $Value) { return "" }
    return [string]$Value
}

function Add-FolderItems([object]$store, [int]$folderType, [string]$direction) {
    try { $folder = $store.GetDefaultFolder($folderType) } catch { return }
    if ($null -eq $folder) { return }
    $items = $folder.Items
    if ($direction -eq "Eingang") {
        try { $items.Sort("[ReceivedTime]", $true) } catch {}
    } else {
        try { $items.Sort("[SentOn]", $true) } catch {}
    }
    $count = [Math]::Min($items.Count, $limit)
    for ($i = 1; $i -le $count; $i++) {
        try { $item = $items.Item($i) } catch { continue }
        if ($null -eq $item) { continue }
        try { if ([int]$item.Class -ne 43) { continue } } catch { continue }

        try {
            if ($direction -eq "Eingang") { $stamp = [datetime]$item.ReceivedTime }
            else { $stamp = [datetime]$item.SentOn }
        } catch { continue }
        if ($stamp -lt $cutoff) { break }

        $subject = Clean-Text $item.Subject
        $body = Clean-Text $item.Body
        $tag = ""
        try { $tag = Clean-Text $item.PropertyAccessor.GetProperty($projectProp) } catch {}

        $match = $false
        if ($mode -eq "recent") { $match = $true }
        elseif (-not [string]::IsNullOrWhiteSpace($projectNumber)) {
            if ($tag -eq $projectNumber) { $match = $true }
            elseif ($subject.IndexOf($projectNumber, [StringComparison]::OrdinalIgnoreCase) -ge 0) { $match = $true }
            elseif ($body.IndexOf($projectNumber, [StringComparison]::OrdinalIgnoreCase) -ge 0) { $match = $true }
        }
        if (-not $match) { continue }

        $sender = ""
        $recipient = ""
        if ($direction -eq "Eingang") {
            try { $sender = Clean-Text $item.SenderName } catch {}
            if ([string]::IsNullOrWhiteSpace($sender)) { try { $sender = Clean-Text $item.SenderEmailAddress } catch {} }
            try { $recipient = Clean-Text $item.To } catch {}
        } else {
            try { $sender = Clean-Text $item.SenderName } catch {}
            try { $recipient = Clean-Text $item.To } catch {}
        }

        $attachmentNames = New-Object System.Collections.Generic.List[string]
        try {
            for ($a=1; $a -le $item.Attachments.Count; $a++) {
                try { [void]$attachmentNames.Add((Clean-Text $item.Attachments.Item($a).FileName)) } catch {}
            }
        } catch {}

        $preview = $body
        if ($preview.Length -gt 12000) { $preview = $preview.Substring(0,12000) }

        [void]$result.Add([pscustomobject]@{
            ts = $stamp.ToString("yyyy-MM-dd HH:mm:ss")
            direction = $direction
            sender = $sender
            recipient = $recipient
            subject = $subject
            body = $preview
            attachment = ($attachmentNames -join "; ")
            entry_id = (Clean-Text $item.EntryID)
            store_id = (Clean-Text $store.StoreID)
            tagged_project = $tag
            account = (Clean-Text $store.DisplayName)
        })
    }
}

foreach ($store in @($ns.Stores)) {
    Add-FolderItems $store 6 "Eingang"
    Add-FolderItems $store 5 "Ausgang"
}
$result | Sort-Object ts -Descending | ConvertTo-Json -Compress -Depth 4
'''


def scan_outlook(project_number: str = "", *, recent=False, days=180, limit=700) -> list[dict]:
    raw = _powershell(
        _scan_script(),
        {
            "PZ_PROJECT_NUMBER_B64": _b64(project_number),
            "PZ_SCAN_MODE": "recent" if recent else "project",
            "PZ_SCAN_DAYS": str(int(days)),
            "PZ_SCAN_LIMIT": str(int(limit)),
        },
        timeout=60,
    )
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Outlook-Antwort konnte nicht ausgewertet werden.") from exc
    if isinstance(data, dict):
        data = [data]
    return [x for x in data if isinstance(x, dict) and x.get("entry_id")]


def _safe_name(value: str) -> str:
    text = re.sub(r'[<>:"/\\|?*]+', " ", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip(" .")
    return (text or "Outlook-Mail")[:105]


def archive_dir(project_root) -> Path:
    root = Path(project_root)
    folder = root / "08_Kommunikation" / "Outlook"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def save_outlook_message(entry_id: str, store_id: str, target: Path) -> None:
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    script = r'''
$ErrorActionPreference = "Stop"
function D([string]$Value) {
    if ([string]::IsNullOrEmpty($Value)) { return "" }
    return [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($Value))
}
$entryId = D $env:PZ_ENTRY_B64
$storeId = D $env:PZ_STORE_B64
$target = D $env:PZ_TARGET_B64
try { $outlook = [Runtime.InteropServices.Marshal]::GetActiveObject("Outlook.Application") }
catch {
    $outlookType = [type]::GetTypeFromProgID("Outlook.Application")
    if ($null -eq $outlookType) { throw "Outlook (klassisch) wurde nicht gefunden." }
    $outlook = [Activator]::CreateInstance($outlookType)
}
$ns = $outlook.GetNamespace("MAPI")
$item = $ns.GetItemFromID($entryId, $storeId)
if ($null -eq $item) { throw "Die Outlook-Mail wurde nicht mehr gefunden." }
$item.SaveAs($target, 3)
'''
    _powershell(
        script,
        {
            "PZ_ENTRY_B64": _b64(entry_id),
            "PZ_STORE_B64": _b64(store_id),
            "PZ_TARGET_B64": _b64(str(target)),
        },
        timeout=30,
    )


def _existing_ids(db_path, project_id) -> set[tuple[str, str]]:
    ensure_schema(db_path)
    con = sqlite3.connect(db_path)
    try:
        return {
            (str(r[0] or ""), str(r[1] or ""))
            for r in con.execute(
                "SELECT outlook_entry_id,outlook_store_id FROM comm "
                "WHERE project_id=? AND outlook_entry_id<>''",
                (int(project_id),),
            ).fetchall()
        }
    finally:
        con.close()


def _archive_one(db_path, project_id, project_root, msg: dict) -> bool:
    ensure_schema(db_path)
    entry_id = str(msg.get("entry_id") or "")
    store_id = str(msg.get("store_id") or "")
    if not entry_id:
        return False

    con = sqlite3.connect(db_path)
    try:
        exists = con.execute(
            "SELECT 1 FROM comm WHERE project_id=? AND outlook_entry_id=? AND outlook_store_id=? LIMIT 1",
            (int(project_id), entry_id, store_id),
        ).fetchone()
    finally:
        con.close()
    if exists:
        return False

    stamp = str(msg.get("ts") or _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    day = stamp[:10] if len(stamp) >= 10 else _dt.date.today().isoformat()
    direction = str(msg.get("direction") or "Outlook")
    subject = _safe_name(msg.get("subject") or "ohne Betreff")
    short = hashlib.sha1((entry_id + store_id).encode("utf-8", "ignore")).hexdigest()[:8]
    target = archive_dir(project_root) / f"{day} {direction} - {subject} [{short}].msg"
    if not target.exists():
        save_outlook_message(entry_id, store_id, target)

    channel = f"Outlook {direction}"
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            """INSERT OR IGNORE INTO comm(
                 project_id,ts,channel,sender,recipient,subject,body,attachment,original_path,immutable,
                 outlook_entry_id,outlook_store_id
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                int(project_id), stamp, channel,
                str(msg.get("sender") or ""), str(msg.get("recipient") or ""),
                str(msg.get("subject") or ""), str(msg.get("body") or ""),
                str(msg.get("attachment") or ""), str(target), 1,
                entry_id, store_id,
            ),
        )
        con.commit()
        return con.total_changes > 0
    finally:
        con.close()


def sync_project(db_path, project_id, project_number: str, project_root, *, days=365) -> tuple[int, int]:
    messages = scan_outlook(project_number, recent=False, days=days, limit=1200)
    new_count = 0
    for msg in messages:
        if _archive_one(db_path, project_id, project_root, msg):
            new_count += 1
    return new_count, len(messages)


def open_recent_picker(parent, db_path, project_id, project_number: str, project_root, on_done=None):
    try:
        messages = scan_outlook("", recent=True, days=60, limit=220)
    except Exception as exc:
        messagebox.showerror("Outlook", str(exc), parent=parent)
        return

    w = tk.Toplevel(parent)
    w.title(f"Outlook-Mail zuordnen · {project_number}")
    w.geometry("1180x650")
    w.minsize(900, 500)
    w.transient(parent)

    top = tk.Frame(w)
    top.pack(fill="x", padx=14, pady=(14, 8))
    tk.Label(top, text="OUTLOOK-MAIL DEM PROJEKT ZUORDNEN", font=("Segoe UI", 15, "bold")).pack(anchor="w")
    tk.Label(top, text="Letzte 60 Tage · Mehrfachauswahl möglich · Original wird als .msg im Projekt archiviert.", fg="#666").pack(anchor="w", pady=(2, 0))

    cols = ("Zeit", "Richtung", "Von", "An", "Betreff", "Konto")
    tree = ttk.Treeview(w, columns=cols, show="headings", selectmode="extended")
    widths = (145, 85, 180, 210, 400, 170)
    for c, width in zip(cols, widths):
        tree.heading(c, text=c)
        tree.column(c, width=width, minwidth=70, stretch=(c == "Betreff"))
    sy = ttk.Scrollbar(w, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sy.set)
    tree.pack(side="left", fill="both", expand=True, padx=(14, 0), pady=(0, 58))
    sy.pack(side="left", fill="y", pady=(0, 58))

    index_map = {}
    for idx, msg in enumerate(messages):
        iid = tree.insert(
            "", "end",
            values=(
                msg.get("ts", ""), msg.get("direction", ""), msg.get("sender", ""),
                msg.get("recipient", ""), msg.get("subject", ""), msg.get("account", ""),
            ),
        )
        index_map[iid] = idx

    buttons = tk.Frame(w)
    buttons.place(relx=0, rely=1, relwidth=1, anchor="sw", x=0, y=0, height=58)
    status = tk.Label(buttons, text=f"{len(messages)} Outlook-Mails geladen", fg="#666")
    status.pack(side="left", padx=14)

    def assign():
        selected = [index_map[i] for i in tree.selection() if i in index_map]
        if not selected:
            messagebox.showwarning("Outlook", "Bitte mindestens eine Mail auswählen.", parent=w)
            return
        imported = 0
        try:
            for idx in selected:
                if _archive_one(db_path, project_id, project_root, messages[idx]):
                    imported += 1
        except Exception as exc:
            messagebox.showerror("Outlook", str(exc), parent=w)
            return
        messagebox.showinfo("Outlook", f"{imported} Mail(s) dem Projekt zugeordnet und archiviert.", parent=w)
        if callable(on_done):
            try: on_done()
            except Exception: pass
        w.destroy()

    tk.Button(buttons, text="ZUORDNEN & ARCHIVIEREN", command=assign, bg="#b08b49", fg="white", bd=0, padx=18, pady=8).pack(side="right", padx=(8, 14), pady=10)
    tk.Button(buttons, text="ABBRECHEN", command=w.destroy, bg="#202020", fg="white", bd=0, padx=18, pady=8).pack(side="right", pady=10)
    return w
