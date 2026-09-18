"""KI-Formulierung fuer Engbers Projektzentrale 1.8.18.

Der API-Schluessel wird unter Windows mit DPAPI fuer das aktuelle Windows-Konto
verschluesselt gespeichert. An OpenAI gehen nur der Begleittext/Stichpunkte und
der fachliche Auswahlkontext, keine Empfaenger- oder Adressdaten.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request
from tkinter import messagebox, simpledialog

MODULE_VERSION = "1.8.18"
MODEL = "gpt-5.6-terra"
API_URL = "https://api.openai.com/v1/responses"
TIMEOUT_SECONDS = 60

INSTRUCTIONS = """Du formulierst professionelle deutsche Geschaeftskorrespondenz fuer ein Ingenieurbuero
mit Schwerpunkt Tragwerksplanung, Statik, Waermeschutz/GEG, KfW/EEE und DGNB/QNG.
Formuliere praezise, sachlich und professionell. Erhalte alle fachlichen Aussagen des
Nutzers unveraendert und erfinde keine Termine, Zusagen, Pruefergebnisse, Normen,
Leistungen oder sonstigen Tatsachen. Gib ausschliesslich den eigentlichen Begleittext
zurueck: keinen Betreff, keine Anrede, keine Grussformel, keine Signatur, kein Markdown.
Wenn Stichpunkte sprachlich unklar sind, formuliere vorsichtig, ohne neue Fakten
hinzuzufuegen."""

STYLE_GUIDANCE = {
    "kurz": "Sehr kurz und sachlich formulieren, in der Regel 1 bis 3 Saetze.",
    "freundlich": "Freundlich und professionell formulieren, natuerlich und verbindlich, in der Regel 2 bis 4 Saetze.",
    "foermlich": "Foermlich, praezise und zurueckhaltend formulieren, in der Regel 2 bis 4 Saetze.",
    "verbessern": "Den vorhandenen Text nur sprachlich verbessern: Grammatik, Rechtschreibung, Satzbau und Ausdruck. Inhalt und Aussage nicht veraendern und keine neuen Fakten hinzufuegen.",
}


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _key_path():
    base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    return base / "Engbers Projektzentrale" / "openai_api_key.dat"


def _blob_from_bytes(data):
    raw = bytes(data)
    buffer = (ctypes.c_ubyte * max(1, len(raw)))()
    if raw:
        ctypes.memmove(buffer, raw, len(raw))
    return _DataBlob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))), buffer


def _protect(data):
    if sys.platform != "win32":
        raise RuntimeError("Die sichere Windows-Schluesselspeicherung ist nur unter Windows verfuegbar.")
    in_blob, _buffer = _blob_from_bytes(data)
    out_blob = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    ok = crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        "Engbers Projektzentrale - OpenAI API",
        None,
        None,
        None,
        0x01,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        if out_blob.pbData:
            kernel32.LocalFree(out_blob.pbData)


def _unprotect(data):
    if sys.platform != "win32":
        return ""
    in_blob, _buffer = _blob_from_bytes(data)
    out_blob = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    ok = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0x01,
        ctypes.byref(out_blob),
    )
    if not ok:
        return ""
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData).decode("utf-8").strip()
    finally:
        if out_blob.pbData:
            kernel32.LocalFree(out_blob.pbData)


def load_api_key():
    env_key = str(os.environ.get("OPENAI_API_KEY") or "").strip()
    if env_key:
        return env_key
    path = _key_path()
    if not path.is_file():
        return ""
    try:
        return _unprotect(path.read_bytes())
    except Exception:
        return ""


def save_api_key(api_key):
    api_key = str(api_key or "").strip()
    if not api_key:
        raise ValueError("Der API-Schluessel ist leer.")
    path = _key_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_protect(api_key.encode("utf-8")))
    return path


def configure_api_key(parent=None):
    current = load_api_key()
    prompt = (
        "OpenAI API-Schluessel eingeben.\n\n"
        "Der Schluessel wird auf diesem PC mit Windows verschluesselt gespeichert "
        "und nicht in Projektdateien oder Updates geschrieben."
    )
    value = simpledialog.askstring(
        "KI einrichten",
        prompt,
        show="*",
        initialvalue=current if current and not os.environ.get("OPENAI_API_KEY") else "",
        parent=parent,
    )
    if value is None:
        return current
    value = value.strip()
    if not value:
        messagebox.showwarning("KI einrichten", "Bitte einen API-Schluessel eingeben.", parent=parent)
        return ""
    try:
        save_api_key(value)
    except Exception as exc:
        messagebox.showerror("KI einrichten", "Der API-Schluessel konnte nicht sicher gespeichert werden.\n\n" + str(exc), parent=parent)
        return ""
    messagebox.showinfo(
        "KI eingerichtet",
        "Der API-Schluessel wurde verschluesselt fuer dieses Windows-Konto gespeichert.",
        parent=parent,
    )
    return value


def ensure_api_key(parent=None):
    key = load_api_key()
    if key:
        return key
    if not messagebox.askyesno(
        "KI einrichten",
        "Fuer die KI-Formulierung wird einmalig ein OpenAI-API-Schluessel benoetigt.\n\n"
        "Soll der Schluessel jetzt eingerichtet werden?",
        parent=parent,
    ):
        return ""
    return configure_api_key(parent)


def _build_prompt(source_text, mode, document_items=None, requests=None):
    source_text = str(source_text or "").strip()
    if not source_text:
        raise ValueError("Bitte zuerst Stichpunkte oder einen Text eingeben.")
    guidance = STYLE_GUIDANCE.get(mode, STYLE_GUIDANCE["freundlich"])
    docs = [str(x).strip() for x in (document_items or []) if str(x).strip()]
    reqs = [str(x).strip() for x in (requests or []) if str(x).strip()]
    context = []
    if docs:
        context.append("Uebermittelte Unterlagen: " + ", ".join(docs))
    if reqs:
        context.append("Gewuenschte Reaktion: " + ", ".join(reqs))
    context_text = "\n".join(context) if context else "Kein weiterer Kontext."
    label = "Vorhandener Text" if mode == "verbessern" else "Stichpunkte / Rohtext"
    return (
        f"Aufgabe: {guidance}\n\n"
        f"Fachlicher Kontext:\n{context_text}\n\n"
        f"{label}:\n{source_text}"
    )


def _extract_output_text(payload):
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    texts = []
    for item in payload.get("output") or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content") or []:
            if not isinstance(content, dict):
                continue
            if content.get("type") in ("output_text", "text"):
                value = content.get("text")
                if isinstance(value, str) and value.strip():
                    texts.append(value.strip())
    return "\n".join(texts).strip()


def _http_error_message(exc):
    detail = ""
    try:
        raw = exc.read().decode("utf-8", errors="replace")
        parsed = json.loads(raw)
        detail = str((parsed.get("error") or {}).get("message") or "").strip()
    except Exception:
        detail = ""
    if exc.code == 401:
        return "Der OpenAI-API-Schluessel wurde nicht akzeptiert. Bitte ueber „KI EINRICHTEN“ pruefen oder ersetzen."
    if exc.code == 429:
        return "Die OpenAI-API meldet ein Limit oder fehlendes Guthaben. Bitte API-Abrechnung und Nutzungslimit pruefen."
    if detail:
        return f"OpenAI-API Fehler {exc.code}: {detail}"
    return f"OpenAI-API Fehler {exc.code}."


def formulate_letter_text(api_key, source_text, mode="freundlich", document_items=None, requests=None):
    api_key = str(api_key or "").strip()
    if not api_key:
        raise RuntimeError("Kein OpenAI-API-Schluessel eingerichtet.")
    prompt = _build_prompt(source_text, mode, document_items=document_items, requests=requests)
    payload = {
        "model": MODEL,
        "instructions": INSTRUCTIONS,
        "input": prompt,
        "max_output_tokens": 700,
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(_http_error_message(exc)) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("Die KI konnte nicht erreicht werden. Bitte Internetverbindung pruefen.") from exc
    except TimeoutError as exc:
        raise RuntimeError("Die KI-Anfrage hat zu lange gedauert. Bitte erneut versuchen.") from exc

    text = _extract_output_text(parsed)
    if not text:
        raise RuntimeError("Die KI hat keinen Text zurueckgegeben.")
    return text


__all__ = [
    "configure_api_key",
    "ensure_api_key",
    "formulate_letter_text",
    "load_api_key",
]
