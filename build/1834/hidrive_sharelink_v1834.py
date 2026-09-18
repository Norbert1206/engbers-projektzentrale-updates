from __future__ import annotations

import json
import time
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

from hidrive_oauth_v1832 import API_BASE, TIMEOUT_SECONDS, verify_connection


def _api_get(path: str, access_token: str, params=None) -> dict:
    qs = urllib.parse.urlencode(params or {})
    url = API_BASE + path + (("?" + qs) if qs else "")
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + access_token}, method="GET")
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
    if not body.strip():
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("HiDrive-API hat eine unerwartete Antwort geliefert.") from exc


def _api_post(path: str, access_token: str, params=None) -> dict:
    qs = urllib.parse.urlencode(params or {})
    url = API_BASE + path + (("?" + qs) if qs else "")
    req = urllib.request.Request(
        url,
        data=b"",
        headers={"Authorization": "Bearer " + access_token},
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
        raise RuntimeError(f"HiDrive-API Fehler {exc.code}" + (f": {detail}" if detail else "")) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("HiDrive-API konnte nicht erreicht werden.") from exc
    if not body.strip():
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("HiDrive-API hat eine unerwartete Antwort geliefert.") from exc


def remote_path_for_local(local_path) -> tuple[dict, str]:
    cfg = verify_connection()
    local_root = (Path.home() / "HiDrive").resolve()
    target = Path(local_path).resolve()
    try:
        rel = target.relative_to(local_root)
    except Exception as exc:
        raise RuntimeError(
            "Der Freigabeordner liegt nicht innerhalb des lokalen HiDrive-Ordners."
        ) from exc

    home = str(cfg.get("home") or "").strip()
    if not home:
        raise RuntimeError("HiDrive hat keinen Home-Pfad fuer den angemeldeten Benutzer geliefert.")

    remote = home.rstrip("/") + "/" + rel.as_posix()
    return cfg, remote


def create_share_link_for_local_dir(local_dir, wait_seconds=90) -> dict:
    cfg, remote_path = remote_path_for_local(local_dir)
    token = str(cfg.get("access_token") or "").strip()
    if not token:
        raise RuntimeError("HiDrive ist nicht verbunden.")

    deadline = time.time() + max(5, int(wait_seconds))
    last_error = ""
    while time.time() < deadline:
        try:
            _api_get("/dir", token, {"path": remote_path, "fields": "id,path,name"})
            last_error = ""
            break
        except Exception as exc:
            last_error = str(exc)
            if "404" not in last_error:
                raise
            time.sleep(2.5)
    else:
        raise RuntimeError(
            "Der neue Freigabeordner ist noch nicht in HiDrive angekommen. "
            "Bitte kurz warten und den HiDrive-Link erneut erzeugen."
            + (f"\n\nLetzte API-Meldung: {last_error}" if last_error else "")
        )

    share = _api_post(
        "/share",
        token,
        {
            "path": remote_path,
            "writable": "false",
            "fields": "id,uri,path,status,ttl,valid_until,has_password",
        },
    )
    uri = str(share.get("uri") or "").strip() if isinstance(share, dict) else ""
    if not uri:
        raise RuntimeError("HiDrive hat die Freigabe erstellt, aber keinen Freigabelink zurueckgegeben.")
    share["remote_path"] = remote_path
    return share
