from __future__ import annotations

import base64
import html
import json
import os
import subprocess
from pathlib import Path


def _html_body(text: str) -> str:
    raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [html.escape(line) for line in raw.split("\n")]
    return "<div style=\"font-family:Calibri,Arial,sans-serif;font-size:11pt\">" + "<br>".join(lines) + "</div><br>"


def _b64(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def open_outlook_draft(to: str, subject: str, body: str, attachments=None, cc: str = "") -> None:
    if os.name != "nt":
        raise RuntimeError("Die Outlook-Anbindung ist nur unter Windows verfügbar.")

    attachments = [str(Path(p).resolve()) for p in (attachments or []) if Path(p).is_file()]
    env = os.environ.copy()
    env["PZ_OUTLOOK_TO"] = str(to or "")
    env["PZ_OUTLOOK_CC"] = str(cc or "")
    env["PZ_OUTLOOK_SUBJECT_B64"] = _b64(str(subject or ""))
    env["PZ_OUTLOOK_BODY_B64"] = _b64(_html_body(body))
    env["PZ_OUTLOOK_ATTACH_B64"] = _b64(json.dumps(attachments, ensure_ascii=False))

    script = r'''
$ErrorActionPreference = "Stop"
function Decode-Utf8([string]$Value) {
    if ([string]::IsNullOrEmpty($Value)) { return "" }
    return [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($Value))
}
$subject = Decode-Utf8 $env:PZ_OUTLOOK_SUBJECT_B64
$bodyHtml = Decode-Utf8 $env:PZ_OUTLOOK_BODY_B64
$attachJson = Decode-Utf8 $env:PZ_OUTLOOK_ATTACH_B64
$attachments = @()
if (-not [string]::IsNullOrWhiteSpace($attachJson)) {
    $parsed = ConvertFrom-Json $attachJson
    if ($parsed -is [System.Array]) { $attachments = $parsed } elseif ($null -ne $parsed) { $attachments = @($parsed) }
}
$outlookType = [type]::GetTypeFromProgID("Outlook.Application")
if ($null -eq $outlookType) { throw "Outlook (klassisch) wurde auf diesem Windows-PC nicht gefunden." }
$outlook = [Activator]::CreateInstance($outlookType)
$mail = $outlook.CreateItem(0)
$mail.To = $env:PZ_OUTLOOK_TO
$mail.CC = $env:PZ_OUTLOOK_CC
$mail.Subject = $subject
$mail.Display()
Start-Sleep -Milliseconds 350
$signature = $mail.HTMLBody
$mail.HTMLBody = $bodyHtml + $signature
foreach ($path in $attachments) {
    if (Test-Path -LiteralPath $path -PathType Leaf) { [void]$mail.Attachments.Add($path) }
}
$mail.Display()
'''

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
            creationflags=flags,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("Windows PowerShell wurde nicht gefunden.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Outlook hat nicht rechtzeitig reagiert.") from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        if detail:
            detail = detail.splitlines()[-1]
        raise RuntimeError(detail or "Outlook-Entwurf konnte nicht erstellt werden.")
