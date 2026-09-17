"""Projektbezogene Ablage fuer Angebote, Rechnungen und Textbausteine."""

from __future__ import annotations

import datetime
import os
import shutil
import sqlite3
import subprocess
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk


MODULE_VERSION = "1.8.11"
# PZ_COMMERCIAL_V1890: lokale kaufmaennische Projektablage mit Textbausteinen.
# PZ_COMMERCIAL_GENERIC_INVOICE_V1810: allgemeine Rechnungsablage zusaetzlich
# zu Abschlags- und Schlussrechnungen.
# PZ_TEXT_EDITOR_FIT_V1811: Editor passt sich der Bildschirmhoehe an;
# Speichern und Abbrechen bleiben fest am unteren Fensterrand sichtbar.

BG = "#f4f1ea"
PANEL = "#fbfaf6"
INK = "#161616"
MUTED = "#6c6c68"
LINE = "#c8c5bd"
DARK = "#202020"
ACCENT = "#b08b49"
DELETE = "#7b2d2d"

COMMERCIAL_FOLDER = "10_Angebote_Rechnungen"
CATEGORIES = (
    ("Angebote", "01_Angebote"),
    ("Auftragsbestätigungen", "02_Auftragsbestaetigungen"),
    ("Rechnungen", "03_Rechnungen"),
    ("Abschlagsrechnungen", "03_Abschlagsrechnungen"),
    ("Schlussrechnungen", "04_Schlussrechnungen"),
    ("Eingangsbelege", "05_Eingangsbelege"),
    ("Sonstiges", "06_Sonstiges"),
)
CATEGORY_FOLDER = dict(CATEGORIES)
FOLDER_CATEGORY = {folder: label for label, folder in CATEGORIES}
TEXT_CATEGORIES = ("Allgemein", "Angebot", "Auftragsbestätigung", "Abschlagsrechnung", "Schlussrechnung", "E-Mail")


def ensure_commercial_folders(project_root):
    base = Path(project_root) / COMMERCIAL_FOLDER
    base.mkdir(parents=True, exist_ok=True)
    for _label, folder in CATEGORIES:
        (base / folder).mkdir(parents=True, exist_ok=True)
    return base


def unique_destination(folder, filename):
    folder = Path(folder)
    source = Path(filename)
    candidate = folder / source.name
    number = 2
    while candidate.exists():
        candidate = folder / f"{source.stem} ({number}){source.suffix}"
        number += 1
    return candidate


def scan_commercial_documents(base):
    base = Path(base)
    result = []
    for label, folder_name in CATEGORIES:
        folder = base / folder_name
        if not folder.exists():
            continue
        try:
            files = sorted((p for p in folder.rglob("*") if p.is_file()), key=lambda p: p.name.casefold())
        except OSError:
            files = []
        for path in files:
            try:
                stat = path.stat()
                changed = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%d.%m.%Y %H:%M")
                size = stat.st_size
            except OSError:
                changed, size = "—", 0
            result.append({
                "category": label,
                "name": path.name,
                "type": path.suffix[1:].upper() if path.suffix else "DATEI",
                "size": size,
                "changed": changed,
                "path": path,
            })
    return result


def ensure_schema(db_path):
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            """CREATE TABLE IF NOT EXISTS commercial_texts(
                id INTEGER PRIMARY KEY,
                project_id INTEGER,
                title TEXT NOT NULL,
                category TEXT,
                body TEXT,
                is_global INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )"""
        )
        con.commit()
    finally:
        con.close()


def _human_size(value):
    value = float(value or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024


def _open_in_explorer(app, path, select=False):
    path = Path(path)
    try:
        if os.name == "nt":
            if select and path.is_file():
                subprocess.Popen(["explorer.exe", "/select,", str(path)])
            else:
                os.startfile(str(path if path.is_dir() else path.parent))
        else:
            app.open_external_path(path if path.is_dir() else path.parent)
    except Exception as exc:
        messagebox.showerror("Explorer", str(exc), parent=app)


def _button(parent, text, command, accent=False, delete=False):
    color = DELETE if delete else (ACCENT if accent else DARK)
    return tk.Button(parent, text=text, command=command, bg=color, fg="white", bd=0,
                     padx=13, pady=8, font=("Segoe UI Semibold", 9), cursor="hand2")


class TextEditor(tk.Toplevel):
    def __init__(self, app, initial=None):
        super().__init__(app)
        self.result = None
        self.title("Textbaustein")
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        width = min(860, max(660, screen_width - 140))
        height = min(720, max(520, screen_height - 160))
        left = max(20, (screen_width - width) // 2)
        top = max(20, (screen_height - height) // 3)
        self.geometry(f"{width}x{height}+{left}+{top}")
        self.minsize(min(620, width), min(500, height))
        self.configure(bg=BG)
        self.transient(app)
        self.grab_set()
        initial = initial or {}

        tk.Label(self, text="TEXTBAUSTEIN", bg=BG, fg=INK,
                 font=("Segoe UI Semibold", 20)).pack(anchor="w", padx=24, pady=(22, 16))

        actions = tk.Frame(self, bg=BG)
        actions.pack(side="bottom", fill="x", padx=24, pady=(0, 20))
        tk.Button(actions, text="ABBRECHEN", command=self.destroy, bg="#e7e4dc", fg=INK,
                  bd=0, padx=18, pady=9).pack(side="right")
        tk.Button(actions, text="SPEICHERN", command=self._save, bg=ACCENT, fg="white",
                  bd=0, padx=20, pady=9).pack(side="right", padx=(0, 8))

        form = tk.Frame(self, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        form.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        self.title_var = tk.StringVar(value=initial.get("title", ""))
        self.category_var = tk.StringVar(value=initial.get("category", TEXT_CATEGORIES[0]))
        self.global_var = tk.BooleanVar(value=bool(initial.get("is_global", 0)))

        tk.Label(form, text="Bezeichnung", bg=PANEL, fg=MUTED).grid(row=0, column=0, sticky="w", padx=18, pady=(18, 7))
        title_entry = tk.Entry(form, textvariable=self.title_var, font=("Segoe UI", 10), bd=1, relief="solid")
        title_entry.grid(row=0, column=1, sticky="ew", padx=(8, 18), pady=(18, 7), ipady=5)
        tk.Label(form, text="Kategorie", bg=PANEL, fg=MUTED).grid(row=1, column=0, sticky="w", padx=18, pady=7)
        ttk.Combobox(form, textvariable=self.category_var, values=TEXT_CATEGORIES, state="readonly").grid(
            row=1, column=1, sticky="ew", padx=(8, 18), pady=7
        )
        tk.Checkbutton(form, text="Projektübergreifend verwenden", variable=self.global_var,
                       bg=PANEL, fg=INK, activebackground=PANEL, selectcolor=PANEL).grid(
            row=2, column=1, sticky="w", padx=(8, 18), pady=7
        )
        tk.Label(form, text="Text", bg=PANEL, fg=MUTED).grid(row=3, column=0, sticky="nw", padx=18, pady=7)
        self.body = tk.Text(form, wrap="word", undo=True, font=("Segoe UI", 10), bd=1, relief="solid")
        self.body.grid(row=3, column=1, sticky="nsew", padx=(8, 18), pady=(7, 18))
        self.body.insert("1.0", initial.get("body", ""))
        form.columnconfigure(1, weight=1)
        form.rowconfigure(3, weight=1)

        title_entry.focus_set()
        self.bind("<Escape>", lambda _event: self.destroy())

    def _save(self):
        title = self.title_var.get().strip()
        if not title:
            messagebox.showwarning("Textbaustein", "Bitte eine Bezeichnung eingeben.", parent=self)
            return
        self.result = {
            "title": title,
            "category": self.category_var.get().strip() or "Allgemein",
            "body": self.body.get("1.0", "end-1c").strip(),
            "is_global": 1 if self.global_var.get() else 0,
        }
        self.destroy()


def render_commercial(app, parent, db_path):
    ensure_schema(db_path)
    project = app.project_row()
    project_root = Path(app.get_project_folder(project))
    base = ensure_commercial_folders(project_root)

    app.titleblock(parent, "Angebote & Rechnungen",
                   f"{project['number']} · {project['title']} · lokale kaufmännische Projektablage")

    toolbar = tk.Frame(parent, bg=BG)
    toolbar.pack(fill="x", pady=(0, 12))
    _button(toolbar, "KAUFMÄNNISCHEN ORDNER ÖFFNEN", lambda: app.open_external_path(base)).pack(side="left")
    lexware_button = _button(toolbar, "LEXWARE ONLINE ÖFFNEN", lambda: webbrowser.open("https://app.lexware.de"), accent=True)
    lexware_button.pack(side="left", padx=8)
    tk.Label(toolbar, text="Lexware-Verknüpfung vorbereitet · keine Zugangsdaten werden gespeichert",
             bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(side="left", padx=8)

    notebook = ttk.Notebook(parent)
    notebook.pack(fill="both", expand=True)
    documents_tab = tk.Frame(notebook, bg=PANEL)
    texts_tab = tk.Frame(notebook, bg=PANEL)
    notebook.add(documents_tab, text="Dokumente")
    notebook.add(texts_tab, text="Textbausteine")

    # Dokumentablage
    doc_tools = tk.Frame(documents_tab, bg=PANEL)
    doc_tools.pack(fill="x", padx=14, pady=(14, 10))
    category_var = tk.StringVar(value=CATEGORIES[0][0])
    tk.Label(doc_tools, text="Ablageziel:", bg=PANEL, fg=MUTED).pack(side="left")
    ttk.Combobox(doc_tools, textvariable=category_var, values=[x[0] for x in CATEGORIES],
                 state="readonly", width=24).pack(side="left", padx=(6, 10))
    search_var = tk.StringVar()
    search_entry = tk.Entry(doc_tools, textvariable=search_var, width=28, bd=1, relief="solid")
    search_entry.pack(side="right", ipady=5)
    tk.Label(doc_tools, text="Suchen:", bg=PANEL, fg=MUTED).pack(side="right", padx=(8, 6))

    doc_actions = tk.Frame(documents_tab, bg=PANEL)
    doc_actions.pack(side="bottom", fill="x", padx=14, pady=(0, 14))
    doc_status = tk.Label(doc_actions, text="", bg=PANEL, fg=MUTED, font=("Segoe UI", 9))
    doc_status.pack(side="right")
    doc_table = tk.Frame(documents_tab, bg=PANEL)
    doc_table.pack(fill="both", expand=True, padx=14, pady=(0, 8))

    columns = ("Kategorie", "Datei", "Typ", "Größe", "Geändert", "Pfad")
    doc_tree = ttk.Treeview(doc_table, columns=columns, show="headings", selectmode="extended")
    for name, width in zip(columns, (180, 330, 70, 90, 145, 540)):
        doc_tree.heading(name, text=name)
        doc_tree.column(name, width=width, anchor="w", stretch=name in ("Datei", "Pfad"))
    doc_scroll = ttk.Scrollbar(doc_table, orient="vertical", command=doc_tree.yview)
    doc_tree.configure(yscrollcommand=doc_scroll.set)
    doc_tree.pack(side="left", fill="both", expand=True)
    doc_scroll.pack(side="left", fill="y")
    doc_paths = {}

    def selected_documents():
        return [doc_paths[iid] for iid in doc_tree.selection() if iid in doc_paths]

    def refresh_documents(*_args):
        query = search_var.get().strip().casefold()
        doc_tree.delete(*doc_tree.get_children())
        doc_paths.clear()
        rows = scan_commercial_documents(base)
        shown = 0
        for row in rows:
            haystack = f"{row['category']} {row['name']} {row['path']}".casefold()
            if query and query not in haystack:
                continue
            iid = doc_tree.insert("", "end", values=(
                row["category"], row["name"], row["type"], _human_size(row["size"]),
                row["changed"], str(row["path"]),
            ))
            doc_paths[iid] = row["path"]
            shown += 1
        doc_status.configure(text=f"{shown} von {len(rows)} Datei(en)")

    def import_documents():
        source_names = filedialog.askopenfilenames(title="Dateien ablegen", parent=app)
        if not source_names:
            return
        target_folder = base / CATEGORY_FOLDER[category_var.get()]
        copied = []
        errors = []
        for source_name in source_names:
            source = Path(source_name)
            try:
                if not source.is_file():
                    continue
                target = unique_destination(target_folder, source.name)
                shutil.copy2(source, target)
                copied.append(target)
            except Exception as exc:
                errors.append(f"{source.name}: {exc}")
        refresh_documents()
        if errors:
            messagebox.showwarning("Dateien ablegen", f"{len(copied)} Datei(en) kopiert.\n\n" + "\n".join(errors[:8]), parent=app)
        elif copied:
            messagebox.showinfo("Dateien ablegen", f"{len(copied)} Datei(en) wurden nach „{category_var.get()}“ kopiert.", parent=app)

    def open_document(_event=None):
        paths = selected_documents()
        if paths:
            app.open_external_path(paths[0])
        return "break"

    def rename_document():
        paths = selected_documents()
        if len(paths) != 1:
            messagebox.showwarning("Umbenennen", "Bitte genau eine Datei auswählen.", parent=app)
            return
        source = paths[0]
        new_name = simpledialog.askstring("Datei umbenennen", "Neuer Dateiname:", initialvalue=source.name, parent=app)
        if not new_name:
            return
        new_name = new_name.strip()
        if not new_name or new_name in (".", "..") or Path(new_name).name != new_name:
            messagebox.showerror("Umbenennen", "Der Dateiname ist nicht gültig.", parent=app)
            return
        if not Path(new_name).suffix and source.suffix:
            new_name += source.suffix
        target = source.with_name(new_name)
        if target.exists():
            messagebox.showerror("Umbenennen", "Eine Datei mit diesem Namen ist bereits vorhanden.", parent=app)
            return
        try:
            source.rename(target)
            refresh_documents()
        except Exception as exc:
            messagebox.showerror("Umbenennen", str(exc), parent=app)

    def delete_documents():
        app.recycle_files(selected_documents(), on_success=refresh_documents, title="Kaufmännische Dokumente")

    _button(doc_actions, "DATEIEN ABLEGEN", import_documents, accent=True).pack(side="left")
    _button(doc_actions, "ÖFFNEN", open_document).pack(side="left", padx=(8, 0))
    _button(doc_actions, "IM EXPLORER", lambda: _open_in_explorer(app, selected_documents()[0], True) if selected_documents() else None).pack(side="left", padx=(8, 0))
    _button(doc_actions, "UMBENENNEN", rename_document).pack(side="left", padx=(8, 0))
    _button(doc_actions, "LÖSCHEN", delete_documents, delete=True).pack(side="left", padx=(8, 0))
    doc_tree.bind("<Double-1>", open_document)
    doc_tree.bind("<Delete>", lambda _event: delete_documents())
    search_var.trace_add("write", refresh_documents)

    doc_menu = tk.Menu(doc_tree, tearoff=False)
    doc_menu.add_command(label="Öffnen", command=open_document)
    doc_menu.add_command(label="Im Explorer anzeigen", command=lambda: _open_in_explorer(app, selected_documents()[0], True) if selected_documents() else None)
    doc_menu.add_command(label="Umbenennen", command=rename_document)
    doc_menu.add_separator()
    doc_menu.add_command(label="In den Papierkorb", command=delete_documents)

    def show_doc_menu(event):
        iid = doc_tree.identify_row(event.y)
        if iid and iid not in doc_tree.selection():
            doc_tree.selection_set(iid)
        if iid:
            doc_menu.tk_popup(event.x_root, event.y_root)

    doc_tree.bind("<Button-3>", show_doc_menu)

    # Textbausteine
    text_split = tk.PanedWindow(texts_tab, orient="horizontal", bg=LINE, sashwidth=5, bd=0)
    text_split.pack(fill="both", expand=True, padx=14, pady=(14, 8))
    list_frame = tk.Frame(text_split, bg=PANEL)
    preview_frame = tk.Frame(text_split, bg=PANEL)
    text_split.add(list_frame, minsize=430)
    text_split.add(preview_frame, minsize=350)
    text_columns = ("Bezeichnung", "Kategorie", "Gültigkeit", "Geändert")
    text_tree = ttk.Treeview(list_frame, columns=text_columns, show="headings", selectmode="browse")
    for name, width in zip(text_columns, (260, 150, 130, 145)):
        text_tree.heading(name, text=name)
        text_tree.column(name, width=width, anchor="w")
    text_tree.pack(fill="both", expand=True)
    tk.Label(preview_frame, text="VORSCHAU", bg=PANEL, fg=INK,
             font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=12, pady=(2, 8))
    preview = tk.Text(preview_frame, wrap="word", state="disabled", bg="#fffefa", fg=INK,
                      bd=1, relief="solid", font=("Segoe UI", 10))
    preview.pack(fill="both", expand=True, padx=12, pady=(0, 2))
    text_records = {}

    def connect():
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        return con

    def refresh_texts(select_id=None):
        con = connect()
        rows = con.execute(
            """SELECT id, project_id, title, category, body, is_global, created_at, updated_at
               FROM commercial_texts
               WHERE (project_id=? AND is_global=0) OR is_global=1
               ORDER BY category, title""", (app.project_id,)
        ).fetchall()
        con.close()
        text_tree.delete(*text_tree.get_children())
        text_records.clear()
        select_iid = None
        for row in rows:
            iid = text_tree.insert("", "end", values=(row["title"], row["category"],
                "Alle Projekte" if row["is_global"] else "Dieses Projekt", row["updated_at"] or row["created_at"] or "—"))
            text_records[iid] = dict(row)
            if select_id == row["id"]:
                select_iid = iid
        if select_iid:
            text_tree.selection_set(select_iid)
            text_tree.focus(select_iid)
            text_tree.see(select_iid)
        update_preview()

    def selected_text():
        selection = text_tree.selection()
        return text_records.get(selection[0]) if selection else None

    def update_preview(_event=None):
        row = selected_text()
        preview.configure(state="normal")
        preview.delete("1.0", "end")
        if row:
            preview.insert("1.0", row.get("body") or "")
        preview.configure(state="disabled")

    def edit_text(existing=None):
        editor = TextEditor(app, existing)
        app.wait_window(editor)
        if not editor.result:
            return
        values = editor.result
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        con = connect()
        if existing:
            con.execute(
                """UPDATE commercial_texts
                   SET project_id=?, title=?, category=?, body=?, is_global=?, updated_at=? WHERE id=?""",
                (None if values["is_global"] else app.project_id, values["title"], values["category"],
                 values["body"], values["is_global"], now, existing["id"]),
            )
            row_id = existing["id"]
        else:
            cursor = con.execute(
                """INSERT INTO commercial_texts(project_id,title,category,body,is_global,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (None if values["is_global"] else app.project_id, values["title"], values["category"],
                 values["body"], values["is_global"], now, now),
            )
            row_id = cursor.lastrowid
        con.commit()
        con.close()
        refresh_texts(row_id)

    def delete_text():
        row = selected_text()
        if not row:
            messagebox.showwarning("Textbaustein", "Bitte einen Textbaustein auswählen.", parent=app)
            return
        if not messagebox.askyesno("Textbaustein löschen", f"„{row['title']}“ dauerhaft löschen?", parent=app):
            return
        con = connect()
        con.execute("DELETE FROM commercial_texts WHERE id=?", (row["id"],))
        con.commit()
        con.close()
        refresh_texts()

    def copy_text():
        row = selected_text()
        if not row:
            messagebox.showwarning("Text kopieren", "Bitte einen Textbaustein auswählen.", parent=app)
            return
        app.clipboard_clear()
        app.clipboard_append(row.get("body") or "")
        app.update_idletasks()

    text_actions = tk.Frame(texts_tab, bg=PANEL)
    text_actions.pack(fill="x", padx=14, pady=(0, 14))
    _button(text_actions, "NEUER TEXTBAUSTEIN", lambda: edit_text(), accent=True).pack(side="left")
    _button(text_actions, "BEARBEITEN", lambda: edit_text(selected_text()) if selected_text() else None).pack(side="left", padx=(8, 0))
    _button(text_actions, "TEXT KOPIEREN", copy_text).pack(side="left", padx=(8, 0))
    _button(text_actions, "LÖSCHEN", delete_text, delete=True).pack(side="left", padx=(8, 0))
    tk.Label(text_actions, text="Projektbezogene und projektübergreifende Formulierungen",
             bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(side="right")
    text_tree.bind("<<TreeviewSelect>>", update_preview)
    text_tree.bind("<Double-1>", lambda _event: edit_text(selected_text()) if selected_text() else None)
    text_tree.bind("<Delete>", lambda _event: delete_text())

    refresh_documents()
    refresh_texts()
    return {"base": base, "document_tree": doc_tree, "text_tree": text_tree}
