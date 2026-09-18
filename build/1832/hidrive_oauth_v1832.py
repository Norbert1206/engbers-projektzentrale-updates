from __future__ import annotations

import ctypes
from ctypes import wintypes
import http.server
import json
import os
from pathlib import Path
import secrets
import socket
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import tkinter as tk
from tkinter import messagebox

AUTH_URL = "https://my.hidrive.com/client/authorize"
TOKEN_URL = "https://my.hidrive.com/oauth2/token"
API_BASE = "https://api.hidrive.strato.com/2.1"
REDIRECT_URI = "http://localhost:8765"
REQUESTED_SCOPE = "user,rw"
TIMEOUT_SECONDS = 30


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _blob_from_bytes(data):
    raw = bytes(data)
    buffer = (ctypes.c_ubyte * max(1, len(raw)))()
    if raw:
        ctypes.memmove(buffer, raw, len(raw))
    return _DataBlob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))), buffer


def _protect(data: bytes) -> bytes:
    if sys.platform != "win32":
        raise RuntimeError("Die sichere HiDrive-Schluesselspeicherung ist nur unter Windows verfuegbar.")
    in_blob, _buffer = _blob_from_bytes(data)
    out_blob = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    ok = crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        "Engbers Projektzentrale - HiDrive OAuth",
        None, None, None, 0x01, ctypes.byref(out_blob),
    )
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        if out_blob.pbData:
            kernel32.LocalFree(out_blob.pbData)


def _unprotect(data: bytes) -> bytes:
    if sys.platform != "win32":
        return b""
    in_blob, _buffer = _blob_from_bytes(data)
    out_blob = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    ok = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob), None, None, None, None, 0x01, ctypes.byref(out_blob)
    )
    if not ok:
        return b""
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        if out_blob.pbData:
            kernel32.LocalFree(out_blob.pbData)


def _config_path() -> Path:
    base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    return base / "Engbers Projektzentrale" / "hidrive_oauth.dat"


def load_config() -> dict:
    path = _config_path()
    if not path.is_file():
        return {}
    try:
        raw = _unprotect(path.read_bytes())
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_config(data: dict) -> Path:
    payload = json.dumps(dict(data), ensure_ascii=False).encode("utf-8")
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_protect(payload))
    return path


def clear_config() -> None:
    path = _config_path()
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def connection_summary() -> str:
    cfg = load_config()
    if cfg.get("refresh_token"):
        alias = str(cfg.get("alias") or "").strip()
        return "HiDrive: verbunden" + (f" ({alias})" if alias else "")
    if cfg.get("client_id") and cfg.get("client_secret"):
        return "HiDrive: Zugangsdaten gespeichert"
    return "HiDrive: nicht eingerichtet"


def _post_form(url: str, values: dict) -> dict:
    data = urllib.parse.urlencode(values).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            parsed = json.loads(exc.read().decode("utf-8", errors="replace"))
            detail = str(parsed.get("error_description") or parsed.get("error") or "").strip()
        except Exception:
            pass
        raise RuntimeError(f"HiDrive-Fehler {exc.code}" + (f": {detail}" if detail else "")) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("HiDrive konnte nicht erreicht werden. Bitte Internetverbindung pruefen.") from exc
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("HiDrive hat eine unerwartete Antwort geliefert.") from exc


def _api_get(path: str, access_token: str, params=None) -> dict:
    qs = urllib.parse.urlencode(params or {})
    url = API_BASE + path + (("?" + qs) if qs else "")
    req = urllib.request.Request(
        url,
        headers={"Authorization": "Bearer " + access_token},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            parsed = json.loads(exc.read().decode("utf-8", errors="replace"))
            detail = str(parsed.get("error_description") or parsed.get("error") or "").strip()
        except Exception:
            pass
        raise RuntimeError(f"HiDrive-API Fehler {exc.code}" + (f": {detail}" if detail else "")) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("HiDrive-API konnte nicht erreicht werden.") from exc
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("HiDrive-API hat eine unerwartete Antwort geliefert.") from exc


def _exchange_code(client_id: str, client_secret: str, code: str) -> dict:
    return _post_form(
        TOKEN_URL,
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "authorization_code",
            "code": code,
        },
    )


def refresh_access_token(cfg=None) -> dict:
    cfg = dict(cfg or load_config())
    refresh_token = str(cfg.get("refresh_token") or "").strip()
    if not refresh_token:
        raise RuntimeError("HiDrive ist noch nicht verbunden.")
    result = _post_form(
        TOKEN_URL,
        {
            "client_id": str(cfg.get("client_id") or ""),
            "client_secret": str(cfg.get("client_secret") or ""),
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )
    cfg.update({
        "access_token": result.get("access_token") or "",
        "refresh_token": result.get("refresh_token") or refresh_token,
        "scope": result.get("scope") or cfg.get("scope") or "",
        "alias": result.get("alias") or cfg.get("alias") or "",
    })
    save_config(cfg)
    return cfg


def verify_connection(cfg=None) -> dict:
    cfg = refresh_access_token(cfg)
    token = str(cfg.get("access_token") or "")
    app_info = _api_get(
        "/app/me",
        token,
        {"fields": "id,name,status,refresh_token.expires,refresh_token.scope"},
    )
    try:
        user_info = _api_get("/user/me", token, {"fields": "alias,home,home_id"})
    except Exception:
        user_info = {}
    if isinstance(user_info, dict):
        cfg["alias"] = user_info.get("alias") or cfg.get("alias") or ""
        cfg["home"] = user_info.get("home") or cfg.get("home") or ""
        cfg["home_id"] = user_info.get("home_id") or cfg.get("home_id") or ""
    cfg["app_name"] = app_info.get("name") if isinstance(app_info, dict) else ""
    cfg["app_status"] = app_info.get("status") if isinstance(app_info, dict) else ""
    save_config(cfg)
    return cfg


def authorize_interactive(client_id: str, client_secret: str, timeout=180) -> dict:
    client_id = str(client_id or "").strip()
    client_secret = str(client_secret or "").strip()
    if not client_id or not client_secret:
        raise ValueError("Bitte client_id und client_secret eingeben.")

    state = secrets.token_urlsafe(24)
    callback = {"code": "", "error": ""}
    event = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            if qs.get("state", [""])[0] != state:
                callback["error"] = "Ungueltige OAuth-Rueckmeldung (state)."
            elif qs.get("error"):
                callback["error"] = qs.get("error_description", qs.get("error", ["HiDrive-Zugriff abgelehnt."]))[0]
            else:
                callback["code"] = qs.get("code", [""])[0]
                if not callback["code"]:
                    callback["error"] = "HiDrive hat keinen Autorisierungscode geliefert."

            html = (
                "<!doctype html><html><head><meta charset='utf-8'><title>Engbers Projektzentrale</title></head>"
                "<body style='font-family:Segoe UI,Arial,sans-serif;padding:40px'>"
                "<h2>HiDrive-Verbindung abgeschlossen</h2>"
                "<p>Sie koennen dieses Browserfenster jetzt schliessen und zur Projektzentrale zurueckkehren.</p>"
                "</body></html>"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
            event.set()

        def log_message(self, _format, *_args):
            return

    try:
        server = http.server.ThreadingHTTPServer(("localhost", 8765), Handler)
    except OSError as exc:
        raise RuntimeError(
            "Der lokale Rueckruf-Port 8765 ist belegt. Bitte andere Programme mit lokalem Port 8765 schliessen und erneut versuchen."
        ) from exc

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    params = {
        "client_id": client_id,
        "response_type": "code",
        "scope": REQUESTED_SCOPE,
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "lang": "de",
    }
    url = AUTH_URL + "?" + urllib.parse.urlencode(params)
    if not webbrowser.open(url):
        server.shutdown()
        server.server_close()
        raise RuntimeError("Der Browser fuer die HiDrive-Anmeldung konnte nicht geoeffnet werden.")

    try:
        if not event.wait(timeout):
            raise RuntimeError("Die HiDrive-Anmeldung wurde nicht innerhalb von 3 Minuten abgeschlossen.")
    finally:
        server.shutdown()
        server.server_close()

    if callback["error"]:
        raise RuntimeError(callback["error"])

    result = _exchange_code(client_id, client_secret, callback["code"])
    refresh_token = str(result.get("refresh_token") or "").strip()
    access_token = str(result.get("access_token") or "").strip()
    if not refresh_token or not access_token:
        raise RuntimeError("HiDrive hat kein vollstaendiges Token-Paar geliefert.")

    cfg = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "access_token": access_token,
        "scope": result.get("scope") or "",
        "alias": result.get("alias") or "",
    }
    save_config(cfg)
    return verify_connection(cfg)


def open_setup_dialog(parent, on_change=None):
    current = load_config()

    w = tk.Toplevel(parent)
    w.title("HiDrive einrichten")
    w.geometry("650x390")
    w.minsize(580, 350)
    try:
        w.transient(parent)
    except Exception:
        pass

    frame = tk.Frame(w)
    frame.pack(fill="both", expand=True, padx=18, pady=16)

    tk.Label(frame, text="HIDRIVE EINRICHTEN", font=("Segoe UI", 16, "bold")).pack(anchor="w")
    tk.Label(
        frame,
        text="client_id und client_secret aus der STRATO-Mail. Die Daten werden nur auf diesem Windows-PC verschluesselt gespeichert.",
        fg="#666666",
        wraplength=600,
        justify="left",
    ).pack(anchor="w", pady=(4, 14))

    form = tk.Frame(frame)
    form.pack(fill="x")
    form.grid_columnconfigure(1, weight=1)

    id_var = tk.StringVar(value=str(current.get("client_id") or ""))
    secret_var = tk.StringVar(value=str(current.get("client_secret") or ""))

    tk.Label(form, text="client_id:", width=16, anchor="w").grid(row=0, column=0, sticky="w", pady=6)
    tk.Entry(form, textvariable=id_var).grid(row=0, column=1, sticky="ew", pady=6, ipady=5)
    tk.Label(form, text="client_secret:", width=16, anchor="w").grid(row=1, column=0, sticky="w", pady=6)
    tk.Entry(form, textvariable=secret_var, show="*").grid(row=1, column=1, sticky="ew", pady=6, ipady=5)

    status_var = tk.StringVar(value=connection_summary())
    tk.Label(frame, textvariable=status_var, fg="#666666", anchor="w").pack(fill="x", pady=(14, 4))
    tk.Label(
        frame,
        text="Beim Verbinden oeffnet sich einmalig der HiDrive-Browserlogin. Die Projektzentrale fordert nur Benutzer-Lese/Schreibzugriff (user,rw) an.",
        fg="#666666",
        wraplength=600,
        justify="left",
    ).pack(anchor="w", pady=(0, 12))

    buttons = tk.Frame(frame)
    buttons.pack(fill="x", side="bottom")

    def finish_change():
        status_var.set(connection_summary())
        if callable(on_change):
            try:
                on_change()
            except Exception:
                pass

    def connect():
        client_id = id_var.get().strip()
        client_secret = secret_var.get().strip()
        if not client_id or not client_secret:
            messagebox.showwarning("HiDrive", "Bitte client_id und client_secret eingeben.", parent=w)
            return

        for child in buttons.winfo_children():
            try:
                child.configure(state="disabled")
            except Exception:
                pass
        status_var.set("HiDrive: Browser-Anmeldung wird geoeffnet …")

        def worker():
            try:
                cfg = authorize_interactive(client_id, client_secret)
                result = ("ok", cfg)
            except Exception as exc:
                result = ("error", str(exc))

            def done():
                for child in buttons.winfo_children():
                    try:
                        child.configure(state="normal")
                    except Exception:
                        pass
                if result[0] == "ok":
                    finish_change()
                    alias = str(result[1].get("alias") or "").strip()
                    messagebox.showinfo(
                        "HiDrive verbunden",
                        "HiDrive wurde erfolgreich mit der Projektzentrale verbunden."
                        + (f"\n\nBenutzer: {alias}" if alias else ""),
                        parent=w,
                    )
                else:
                    status_var.set(connection_summary())
                    messagebox.showerror("HiDrive verbinden", result[1], parent=w)
            try:
                w.after(0, done)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def test():
        status_var.set("HiDrive: Verbindung wird geprueft …")
        def worker():
            try:
                cfg = verify_connection()
                result = ("ok", cfg)
            except Exception as exc:
                result = ("error", str(exc))
            def done():
                if result[0] == "ok":
                    finish_change()
                    messagebox.showinfo("HiDrive", "Verbindung ist in Ordnung.", parent=w)
                else:
                    status_var.set(connection_summary())
                    messagebox.showerror("HiDrive", result[1], parent=w)
            try:
                w.after(0, done)
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True).start()

    def remove():
        if not messagebox.askyesno(
            "HiDrive trennen",
            "Gespeicherte HiDrive-Zugangsdaten und Tokens auf diesem PC entfernen?",
            parent=w,
        ):
            return
        clear_config()
        secret_var.set("")
        finish_change()

    tk.Button(buttons, text="SPEICHERN & VERBINDEN", command=connect, padx=14, pady=8).pack(side="right")
    tk.Button(buttons, text="VERBINDUNG PRÜFEN", command=test, padx=14, pady=8).pack(side="right", padx=8)
    tk.Button(buttons, text="TRENNEN", command=remove, padx=14, pady=8).pack(side="left")
    tk.Button(buttons, text="SCHLIESSEN", command=w.destroy, padx=14, pady=8).pack(side="left", padx=8)

    return w


__all__ = [
    "open_setup_dialog",
    "connection_summary",
    "load_config",
    "verify_connection",
    "refresh_access_token",
]
