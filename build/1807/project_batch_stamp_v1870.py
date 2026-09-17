from __future__ import annotations

import datetime as _dt
import os
import re
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from pdf_stamp_v1870 import pdf_stamp_info, stamp_pdf, _load_fitz


MODULE_VERSION = "1.8.7"
MARKER = "PZ_PROJECT_BATCH_STAMP_V1870"


PLAN_WORDS = (
    "plan", "positionsplan", "schalplan", "bewehrungsplan", "sparrenlage",
    "deckenplan", "fundamentplan", "detail", "grundriss", "schnitt",
)
CALC_WORDS = (
    "statische berechnung", "statik", "berechnung", "nachweis", "bemessung",
)


def _norm(path) -> Path:
    return Path(path).expanduser().resolve()


def _looks_like_plan(path: Path) -> bool:
    low = path.stem.casefold()
    return any(word in low for word in PLAN_WORDS)


def _looks_like_calculation(path: Path) -> bool:
    low = path.stem.casefold()
    return any(word in low for word in CALC_WORDS) and not _looks_like_plan(path)


def _kind_text(path: Path) -> str:
    if _looks_like_plan(path):
        return "Plan"
    if _looks_like_calculation(path):
        return "Berechnung"
    return "PDF"


def _open_path(path: Path):
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


class ProjectBatchStampDialog(tk.Toplevel):
    def __init__(
        self,
        parent,
        pdf_paths,
        profile="plan",
        project_root=None,
        preselected_paths=None,
        on_complete=None,
    ):
        super().__init__(parent)
        self.profile = "statik" if profile == "statik" else "plan"
        self.project_root = _norm(project_root) if project_root else None
        self.on_complete = on_complete
        self.paths = []
        seen = set()
        for raw in pdf_paths or ():
            try:
                path = _norm(raw)
            except Exception:
                continue
            key = str(path).casefold()
            if key in seen or not path.is_file() or path.suffix.casefold() != ".pdf":
                continue
            seen.add(key)
            self.paths.append(path)
        self.paths.sort(key=lambda path: str(path).casefold())

        self.preselected = set()
        for raw in preselected_paths or ():
            try:
                self.preselected.add(str(_norm(raw)).casefold())
            except Exception:
                pass
        self.checked = set()
        self.item_paths = {}
        self.replace_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="")

        mode = "Statikberechnungen" if self.profile == "statik" else "Statikpläne"
        self.title(mode + " gesammelt stempeln")
        self.geometry("1180x720")
        self.minsize(940, 580)
        self.transient(parent)
        self._build_ui()
        self._fill_tree()
        self.grab_set()

    def _build_ui(self):
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)
        title = "STATIKBERECHNUNGEN STEMPELN" if self.profile == "statik" else "STATIKPLÄNE STEMPELN"
        ttk.Label(outer, text=title, font=("Segoe UI", 17, "bold")).pack(anchor="w")
        detail = (
            "Der Statikstempel wird auf der ersten und letzten Seite gesetzt."
            if self.profile == "statik"
            else "Der Statikstempel wird auf jeder ausgewählten Planseite unten rechts im Schriftfeld gesetzt."
        )
        ttk.Label(outer, text=detail).pack(anchor="w", pady=(3, 14))

        tools = ttk.Frame(outer)
        tools.pack(fill="x", pady=(0, 8))
        ttk.Button(tools, text="ALLE AUSWÄHLEN", command=self._select_all).pack(side="left")
        ttk.Button(tools, text="AUSWAHL AUFHEBEN", command=self._clear_all).pack(side="left", padx=6)
        ttk.Button(tools, text="NUR ERKANNTE AUSWÄHLEN", command=self._select_detected).pack(side="left")
        self.selection_label = ttk.Label(tools, text="0 ausgewählt")
        self.selection_label.pack(side="right")

        columns = ("check", "file", "kind", "pages", "changed", "folder")
        grid = ttk.Frame(outer)
        grid.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(grid, columns=columns, show="headings", height=20)
        headings = {
            "check": "Auswahl", "file": "PDF-Datei", "kind": "Erkannt als",
            "pages": "Seiten", "changed": "Geändert", "folder": "Ordner",
        }
        widths = {"check": 80, "file": 360, "kind": 110, "pages": 65, "changed": 135, "folder": 410}
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(
                column,
                width=widths[column],
                minwidth=55,
                anchor="center" if column in ("check", "pages") else "w",
                stretch=column in ("file", "folder"),
            )
        scroll_y = ttk.Scrollbar(grid, orient="vertical", command=self.tree.yview)
        scroll_x = ttk.Scrollbar(grid, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")
        grid.grid_rowconfigure(0, weight=1)
        grid.grid_columnconfigure(0, weight=1)
        self.tree.bind("<Button-1>", self._toggle_click)
        self.tree.bind("<Double-1>", self._open_clicked)
        self.tree.bind("<space>", self._toggle_focused)

        options = ttk.LabelFrame(outer, text="Ausgabe", padding=10)
        options.pack(fill="x", pady=(12, 8))
        ttk.Checkbutton(
            options,
            text="Original-PDFs ersetzen",
            variable=self.replace_var,
        ).pack(side="left")
        ttk.Label(
            options,
            text="Ohne Haken entstehen neue Dateien mit dem Zusatz _gestempelt. Bereits gestempelte Dateien werden übersprungen.",
        ).pack(side="left", padx=14)

        progress_row = ttk.Frame(outer)
        progress_row.pack(fill="x", pady=(2, 10))
        self.progress = ttk.Progressbar(progress_row, mode="determinate", maximum=1)
        self.progress.pack(side="left", fill="x", expand=True)
        ttk.Label(progress_row, textvariable=self.status_var, width=30).pack(side="left", padx=(10, 0))

        actions = ttk.Frame(outer)
        actions.pack(fill="x")
        ttk.Button(actions, text="SCHLIESSEN", command=self.destroy).pack(side="right")
        self.apply_button = ttk.Button(
            actions,
            text="AUSGEWÄHLTE PDFS JETZT STEMPELN",
            command=self._apply,
        )
        self.apply_button.pack(side="right", padx=(0, 8))

    def _relative_folder(self, path: Path) -> str:
        if self.project_root:
            try:
                rel = path.parent.relative_to(self.project_root)
                return str(rel) if str(rel) != "." else self.project_root.name
            except Exception:
                pass
        return str(path.parent)

    def _page_count(self, path: Path) -> str:
        try:
            document = _load_fitz().open(str(path))
            try:
                return str(len(document))
            finally:
                document.close()
        except Exception:
            return "—"

    def _default_checked(self, path: Path) -> bool:
        if self.preselected:
            return str(path).casefold() in self.preselected
        if self.profile == "plan":
            return _looks_like_plan(path)
        return _looks_like_calculation(path)

    def _fill_tree(self):
        for path in self.paths:
            try:
                changed = _dt.datetime.fromtimestamp(path.stat().st_mtime).strftime("%d.%m.%Y %H:%M")
            except Exception:
                changed = "—"
            chosen = self._default_checked(path)
            if chosen:
                self.checked.add(path)
            iid = self.tree.insert(
                "",
                "end",
                values=(
                    "☑" if chosen else "☐",
                    path.name,
                    _kind_text(path),
                    self._page_count(path),
                    changed,
                    self._relative_folder(path),
                ),
            )
            self.item_paths[iid] = path
        self._update_selection_label()
        if not self.paths:
            self.status_var.set("Keine PDF-Dateien gefunden")

    def _set_checked(self, iid, chosen: bool):
        path = self.item_paths.get(iid)
        if path is None:
            return
        if chosen:
            self.checked.add(path)
        else:
            self.checked.discard(path)
        values = list(self.tree.item(iid, "values"))
        if values:
            values[0] = "☑" if chosen else "☐"
            self.tree.item(iid, values=values)

    def _update_selection_label(self):
        self.selection_label.configure(text=f"{len(self.checked)} von {len(self.paths)} ausgewählt")

    def _toggle_click(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        self.tree.selection_set(iid)
        self.tree.focus(iid)
        self._set_checked(iid, self.item_paths[iid] not in self.checked)
        self._update_selection_label()
        return "break"

    def _toggle_focused(self, _event=None):
        iid = self.tree.focus()
        if iid in self.item_paths:
            self._set_checked(iid, self.item_paths[iid] not in self.checked)
            self._update_selection_label()
        return "break"

    def _open_clicked(self, event=None):
        iid = self.tree.identify_row(event.y) if event is not None else self.tree.focus()
        path = self.item_paths.get(iid)
        if path:
            _open_path(path)
        return "break"

    def _select_all(self):
        for iid in self.tree.get_children(""):
            self._set_checked(iid, True)
        self._update_selection_label()

    def _clear_all(self):
        for iid in self.tree.get_children(""):
            self._set_checked(iid, False)
        self._update_selection_label()

    def _select_detected(self):
        for iid, path in self.item_paths.items():
            chosen = _looks_like_plan(path) if self.profile == "plan" else _looks_like_calculation(path)
            self._set_checked(iid, chosen)
        self._update_selection_label()

    @staticmethod
    def _output_path(path: Path) -> Path:
        return path.with_name(path.stem + "_gestempelt.pdf")

    def _apply(self):
        selected = sorted(self.checked, key=lambda path: str(path).casefold())
        if not selected:
            messagebox.showwarning("PDFs stempeln", "Bitte mindestens eine PDF-Datei auswählen.", parent=self)
            return
        replace = self.replace_var.get()
        action = "Die Originaldateien werden ersetzt." if replace else "Es entstehen neue Dateien mit dem Zusatz _gestempelt."
        if not messagebox.askyesno(
            "Auswahl stempeln",
            f"{len(selected)} PDF-Datei(en) werden jetzt gestempelt.\n\n{action}\n\nFortfahren?",
            parent=self,
        ):
            return

        self.apply_button.configure(state="disabled")
        self.progress.configure(maximum=max(1, len(selected)), value=0)
        created = []
        skipped = []
        failed = []
        try:
            for index, path in enumerate(selected, start=1):
                self.status_var.set(f"{index}/{len(selected)} · {path.name}")
                self.progress.configure(value=index - 1)
                self.update_idletasks()
                try:
                    if pdf_stamp_info(path):
                        skipped.append((path, "bereits von der Projektzentrale gestempelt"))
                        continue
                    if re.search(r"_gestempelt(?:_\d+)?$", path.stem, flags=re.IGNORECASE):
                        skipped.append((path, "Dateiname weist bereits auf eine gestempelte Fassung hin"))
                        continue
                    output = path if replace else self._output_path(path)
                    if not replace and output.exists():
                        skipped.append((path, f"Ausgabedatei bereits vorhanden: {output.name}"))
                        continue
                    result = stamp_pdf(
                        path,
                        output,
                        self.profile,
                        stamp_kind="statik",
                    )
                    created.append(result)
                except Exception as exc:
                    failed.append((path, str(exc)))
                finally:
                    self.progress.configure(value=index)
                    self.update_idletasks()
        finally:
            self.apply_button.configure(state="normal")
            self.status_var.set("Fertig")

        lines = [
            f"Erfolgreich gestempelt: {len(created)}",
            f"Übersprungen: {len(skipped)}",
            f"Fehler: {len(failed)}",
        ]
        details = []
        for path, reason in skipped:
            details.append(f"ÜBERSPRUNGEN · {path.name}\n{reason}")
        for path, reason in failed:
            details.append(f"FEHLER · {path.name}\n{reason}")
        if details:
            lines.append("\n" + "\n\n".join(details[:12]))
            if len(details) > 12:
                lines.append(f"\n… und {len(details) - 12} weitere Meldung(en)")
        messagebox.showinfo("Stempelvorgang abgeschlossen", "\n".join(lines), parent=self)
        if callable(self.on_complete):
            try:
                self.on_complete()
            except Exception:
                pass


def open_project_batch_stamp_dialog(
    parent,
    pdf_paths,
    profile="plan",
    project_root=None,
    preselected_paths=None,
    on_complete=None,
):
    return ProjectBatchStampDialog(
        parent,
        pdf_paths,
        profile=profile,
        project_root=project_root,
        preselected_paths=preselected_paths,
        on_complete=on_complete,
    )
