from __future__ import annotations

import json
import time
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

from hidrive_oauth_v1832 import API_BASE, TIMEOUT_SECONDS, verify_connection


def _http_detail(exc) -> str:
    try:
        raw = exc.read().decode("utf-8", errors="replace").strip()
    except Exception:
        return ""
    if not raw:
        return ""
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return str(
                parsed.get("error_description")
                or parsed.get("message")
                or parsed.get("error")
                or raw
            ).strip()
    except Exception:
        pass
    return raw


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
        detail = _http_detail(exc)
        raise RuntimeError(
            f"HiDrive-API Fehler {exc.code}" + (f": {detail}" if detail else "")
        ) from exc
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
        detail = _http_detail(exc)
        raise RuntimeError(
            f"HiDrive-API Fehler {exc.code}" + (f": {detail}" if detail else "")
        ) from exc
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
        raise RuntimeError(
            "HiDrive hat keinen Home-Pfad fuer den angemeldeten Benutzer geliefert."
        )

    remote = home.rstrip("/") + "/" + rel.as_posix()
    return cfg, remote


def create_share_link_for_local_dir(local_dir, wait_seconds=90) -> dict:
    cfg, remote_path = remote_path_for_local(local_dir)
    token = str(cfg.get("access_token") or "").strip()
    if not token:
        raise RuntimeError("HiDrive ist nicht verbunden.")

    deadline = time.time() + max(5, int(wait_seconds))
    last_error = ""
    dir_info = {}

    while time.time() < deadline:
        try:
            dir_info = _api_get(
                "/dir",
                token,
                {"path": remote_path, "fields": "id,path,name"},
            )
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
            "Bitte kurz warten und HIDRIVE-LINK erneut anklicken."
            + (f"\n\nLetzte API-Meldung: {last_error}" if last_error else "")
        )

    dir_id = str(dir_info.get("id") or "").strip() if isinstance(dir_info, dict) else ""
    if not dir_id:
        raise RuntimeError(
            "HiDrive hat fuer den Freigabeordner keine Verzeichnis-ID geliefert."
        )

    # Laut HiDrive ist eine neue Verzeichnisfreigabe standardmaessig read-only.
    # Minimaler Request per pid vermeidet optionale Parameter und Pfad-Encoding.
    share = _api_post("/share", token, {"pid": dir_id})

    uri = str(share.get("uri") or "").strip() if isinstance(share, dict) else ""
    if not uri:
        # Defaultantwort sollte uri enthalten; falls nicht, einmal per ID nachladen.
        share_id = str(share.get("id") or "").strip() if isinstance(share, dict) else ""
        if share_id:
            share = _api_get("/share", token, {"id": share_id})
            uri = str(share.get("uri") or "").strip() if isinstance(share, dict) else ""

    if not uri:
        raise RuntimeError(
            "HiDrive hat die Freigabe erstellt, aber keinen Freigabelink zurueckgegeben."
        )

    share["remote_path"] = remote_path
    return share
