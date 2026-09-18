from __future__ import annotations

import datetime as _dt
import re
import shutil
from pathlib import Path


def default_hidrive_root() -> Path:
    return Path.home() / "HiDrive"


def default_share_root() -> Path:
    return default_hidrive_root() / "Engbers Projektfreigaben"


def _safe_segment(value: str, fallback: str = "Projekt") -> str:
    text = str(value or "").strip()
    text = re.sub(r'[<>:"/\\|?*]+', " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text or fallback


def collect_pdfs(selected_paths, statik_root: Path):
    statik_root = Path(statik_root).resolve()
    found = {}
    for raw in selected_paths:
        if raw is None:
            continue
        p = Path(raw)
        try:
            p.resolve().relative_to(statik_root)
        except Exception:
            continue
        if p.is_file() and p.suffix.casefold() == ".pdf":
            found[str(p.resolve()).casefold()] = p
        elif p.is_dir():
            try:
                for child in p.rglob("*.pdf"):
                    if child.is_file():
                        found[str(child.resolve()).casefold()] = child
            except OSError:
                continue
    return sorted(found.values(), key=lambda x: str(x).casefold())


def create_release_dir(share_root: Path, project_number: str, project_title: str, now=None) -> Path:
    share_root = Path(share_root)
    project_name = _safe_segment(f"{project_number} {project_title}".strip())
    stamp = (now or _dt.datetime.now()).strftime("%Y-%m-%d %H%M%S")
    release = share_root / project_name / f"Freigabe {stamp}"
    suffix = 2
    candidate = release
    while candidate.exists():
        candidate = release.with_name(f"{release.name} ({suffix})")
        suffix += 1
    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def copy_pdfs(files, statik_root: Path, release_dir: Path):
    statik_root = Path(statik_root).resolve()
    release_dir = Path(release_dir)
    copied = []
    for src in files:
        src = Path(src)
        try:
            rel = src.resolve().relative_to(statik_root)
        except Exception:
            rel = Path(src.name)
        target = release_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        copied.append(target)
    return copied


def prepare_share(selected_paths, statik_root: Path, project_number: str, project_title: str, share_root: Path | None = None):
    statik_root = Path(statik_root)
    files = collect_pdfs(selected_paths, statik_root)
    if not files:
        raise ValueError("Bitte mindestens eine PDF-Datei oder einen Ordner mit PDFs auswählen.")

    if share_root is None:
        hidrive_root = default_hidrive_root()
        if not hidrive_root.exists():
            raise FileNotFoundError(
                f"Der lokale HiDrive-Ordner wurde nicht gefunden:\n{hidrive_root}\n\n"
                "Bitte HiDrive unter Windows einrichten."
            )
        share_root = default_share_root()

    share_root = Path(share_root)
    share_root.mkdir(parents=True, exist_ok=True)
    release_dir = create_release_dir(share_root, project_number, project_title)
    copied = copy_pdfs(files, statik_root, release_dir)
    return release_dir, copied
