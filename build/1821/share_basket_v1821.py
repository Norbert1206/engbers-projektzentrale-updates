from __future__ import annotations

import datetime as _dt
import json
import os
import re
import shutil
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


def _state_file() -> Path:
    base = Path(os.environ.get("APPDATA") or (Path.home() / ".engbers_projektzentrale"))
    folder = base / "Engbers Projektzentrale"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "freigabekorb.json"


def _load_state() -> dict:
    path = _state_file()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_state(data: dict) -> None:
    path = _state_file()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _key(project_id) -> str:
    return str(project_id)


def _safe_segment(value: str, fallback: str = "Projekt") -> str:
    text = str(value or "").strip()
    text = re.sub(r'[<>:"/\\|?*]+', " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text or fallback


def get_items(project_id) -> list[dict]:
    data = _load_state()
    items = data.get(_key(project_id), [])
    if not isinstance(items, list):
        return []
    cleaned = []
    for item in items:
        if not isinstance(item, dict):
            continue
        p = Path(str(item.get("path") or ""))
        root = Path(str(item.get("root") or ""))
        if not p.exists() or not root.exists():
            continue
        cleaned.append({
            "path": str(p),
            "root": str(root),
            "source": str(item.get("source") or ""),
        })
    if cleaned != items:
        data[_key(project_id)] = cleaned
        _save_state(data)
    return cleaned


def count_items(project_id) -> int:
    return len(get_items(project_id))


def add_items(project_id, paths, root, source="Projekt") -> tuple[int, int]:
    root = Path(root).resolve()
    data = _load_state()
    items = get_items(project_id)
    existing = {str(Path(x["path"]).resolve()).casefold() for x in items}
    added = 0
    for raw in paths:
        if raw is None:
            continue
        p = Path(raw)
        if not p.exists():
            continue
        try:
            p.resolve().relative_to(root)
        except Exception:
            continue
        key = str(p.resolve()).casefold()
        if key in existing:
            continue
        items.append({"path": str(p.resolve()), "root": str(root), "source": str(source or "Projekt")})
        existing.add(key)
        added += 1
    data[_key(project_id)] = items
    _save_state(data)
    return added, len(items)


def add_external_files(project_id, paths) -> tuple[int, int]:
    data = _load_state()
    items = get_items(project_id)
    existing = {str(Path(x["path"]).resolve()).casefold() for x in items}
    added = 0
    for raw in paths:
        p = Path(raw)
        if not p.is_file():
            continue
        key = str(p.resolve()).casefold()
        if key in existing:
            continue
        items.append({"path": str(p.resolve()), "root": str(p.parent.resolve()), "source": "Extern"})
        existing.add(key)
        added += 1
    data[_key(project_id)] = items
    _save_state(data)
    return added, len(items)


def remove_indices(project_id, indices) -> None:
    data = _load_state()
    items = get_items(project_id)
    drop = set(indices)
    data[_key(project_id)] = [item for i, item in enumerate(items) if i not in drop]
    _save_state(data)


def clear_items(project_id) -> None:
    data = _load_state()
    data[_key(project_id)] = []
    _save_state(data)


def default_share_root() -> Path:
    return Path.home() / "HiDrive" / "Engbers Projektfreigaben"


def _create_release_dir(project_number: str, project_title: str) -> Path:
    hidrive = Path.home() / "HiDrive"
    if not hidrive.exists():
        raise FileNotFoundError(
            f"Der lokale HiDrive-Ordner wurde nicht gefunden:\n{hidrive}\n\n"
            "Bitte HiDrive unter Windows einrichten."
        )
    root = default_share_root()
    root.mkdir(parents=True, exist_ok=True)
    project = root / _safe_segment(f"{project_number} {project_title}".strip())
    project.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y-%m-%d %H%M%S")
    target = project / f"Freigabe {stamp}"
    n = 2
    while target.exists():
        target = project / f"Freigabe {stamp} ({n})"
        n += 1
    target.mkdir(parents=True, exist_ok=False)
    return target


def _unique_target(target: Path) -> Path:
    if not target.exists():
        return target
    stem, suffix = target.stem, target.suffix
    n = 2
    while True:
        cand = target.with_name(f"{stem} ({n}){suffix}")
        if not cand.exists():
            return cand
        n += 1


def create_release(project_id, project_number: str, project_title: str) -> tuple[Path, int]:
    items = get_items(project_id)
    if not items:
        raise ValueError("Der Freigabekorb ist leer.")

    release = _create_release_dir(project_number, project_title)
    sources = {}
    for item in items:
        p = Path(item["path"])
        root = Path(item["root"])
        if not p.exists() or not root.exists():
            continue
        try:
            p.resolve().relative_to(root.resolve())
        except Exception:
            continue

        if p.is_file():
            sources[str(p.resolve()).casefold()] = (p, root)
        elif p.is_dir():
            try:
                for child in p.rglob("*"):
                    if child.is_file() and not child.is_symlink():
                        sources.setdefault(str(child.resolve()).casefold(), (child, root))
            except OSError:
                continue

    if not sources:
        shutil.rmtree(release, ignore_errors=True)
        raise ValueError("Im Freigabekorb wurden keine vorhandenen Dateien gefunden.")

    copied = 0
    for src, root in sorted(sources.values(), key=lambda x: str(x[0]).casefold()):
        try:
            rel = src.resolve().relative_to(root.resolve())
        except Exception:
            rel = Path(src.name)
        target = release / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target = _unique_target(target)
        shutil.copy2(src, target)
        copied += 1

    if not copied:
        shutil.rmtree(release, ignore_errors=True)
        raise ValueError("Es konnten keine Dateien kopiert werden.")
    return release, copied


def open_basket_dialog(app, project_id, project_number: str, project_title: str, on_change=None):
    w = tk.Toplevel(app)
    w.title("Freigabekorb")
    w.geometry("980x620")
    w.minsize(760, 480)
    try:
        w.transient(app)
    except Exception:
        pass

    BG = "#f5f2eb"
    PANEL = "#fbfaf6"
    INK = "#161616"
    MUTED = "#6c6c68"
    DARK = "#202020"
    ACCENT = "#b08b49"

    w.configure(bg=BG)
    outer = tk.Frame(w, bg=BG)
    outer.pack(fill="both", expand=True, padx=18, pady=16)
    tk.Label(outer, text="PROJEKTFREIGABE", bg=BG, fg=INK, font=("Segoe UI", 18, "bold")).pack(anchor="w")
    tk.Label(
        outer,
        text=f"{project_number} · {project_title} · beliebige Dateitypen möglich",
        bg=BG, fg=MUTED, font=("Segoe UI", 9)
    ).pack(anchor="w", pady=(2, 12))

    tools = tk.Frame(outer, bg=BG)
    tools.pack(fill="x", pady=(0, 10))
    count_lbl = tk.Label(tools, text="", bg=BG, fg=MUTED)
    count_lbl.pack(side="left")

    cols = ("Typ", "Quelle", "Pfad")
    tree = ttk.Treeview(outer, columns=cols, show="tree headings", selectmode="extended")
    tree.heading("#0", text="Datei / Ordner")
    tree.column("#0", width=310, minwidth=180, stretch=True)
    tree.heading("Typ", text="Typ"); tree.column("Typ", width=100, stretch=False)
    tree.heading("Quelle", text="Quelle"); tree.column("Quelle", width=110, stretch=False)
    tree.heading("Pfad", text="Pfad"); tree.column("Pfad", width=420, stretch=True)
    sy = ttk.Scrollbar(outer, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sy.set)
    tree.pack(side="left", fill="both", expand=True)
    sy.pack(side="right", fill="y")

    index_map = {}

    def refresh():
        for iid in tree.get_children(""):
            tree.delete(iid)
        index_map.clear()
        items = get_items(project_id)
        for idx, item in enumerate(items):
            p = Path(item["path"])
            typ = "Ordner" if p.is_dir() else (p.suffix.upper().lstrip(".") or "Datei")
            try:
                rel = p.relative_to(Path(item["root"]))
                rel_text = str(rel)
            except Exception:
                rel_text = str(p)
            iid = tree.insert("", "end", text=p.name, values=(typ, item.get("source") or "Projekt", rel_text))
            index_map[iid] = idx
        count_lbl.configure(text=f"{len(items)} Eintrag/Einträge im Freigabekorb")
        if on_change:
            try:
                on_change(len(items))
            except Exception:
                pass

    def add_files():
        paths = filedialog.askopenfilenames(parent=w, title="Dateien zur Projektfreigabe hinzufügen")
        if not paths:
            return
        added, total = add_external_files(project_id, paths)
        refresh()
        messagebox.showinfo("Freigabekorb", f"{added} Datei(en) hinzugefügt.\n\nInsgesamt: {total}", parent=w)

    def remove_selected():
        indices = [index_map[iid] for iid in tree.selection() if iid in index_map]
        if not indices:
            return
        remove_indices(project_id, indices)
        refresh()

    def clear_all():
        if not get_items(project_id):
            return
        if not messagebox.askyesno("Freigabekorb", "Freigabekorb wirklich leeren?", parent=w):
            return
        clear_items(project_id)
        refresh()

    def create_now():
        try:
            release, copied = create_release(project_id, project_number, project_title)
        except Exception as exc:
            messagebox.showerror("Projektfreigabe", str(exc), parent=w)
            return
        clear_items(project_id)
        refresh()
        try:
            app.open_external_path(release)
        except Exception:
            pass
        messagebox.showinfo(
            "Projektfreigabe",
            f"{copied} Datei(en) als Kopie bereitgestellt.\n\n{release}\n\n"
            "Die Originaldateien wurden nicht verändert. HiDrive synchronisiert den Ordner automatisch.",
            parent=w,
        )

    buttons = tk.Frame(w, bg=BG)
    buttons.pack(fill="x", padx=18, pady=(0, 16))
    tk.Button(buttons, text="DATEIEN HINZUFÜGEN", command=add_files, bg="#e7e4dc", fg=INK, bd=0, padx=14, pady=8).pack(side="left")
    tk.Button(buttons, text="AUSWAHL ENTFERNEN", command=remove_selected, bg="#e7e4dc", fg=INK, bd=0, padx=14, pady=8).pack(side="left", padx=8)
    tk.Button(buttons, text="KORB LEEREN", command=clear_all, bg="#7b2d2d", fg="white", bd=0, padx=14, pady=8).pack(side="left")
    tk.Button(buttons, text="FREIGABE ERSTELLEN", command=create_now, bg=ACCENT, fg="white", bd=0, padx=18, pady=8).pack(side="right")
    tk.Button(buttons, text="SCHLIESSEN", command=w.destroy, bg=DARK, fg="white", bd=0, padx=18, pady=8).pack(side="right", padx=8)

    refresh()
    return w
