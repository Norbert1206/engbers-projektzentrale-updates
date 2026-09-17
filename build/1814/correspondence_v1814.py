"""Projektbezogene Anschreiben aus dem Engbers-Standardanschreiben."""

from __future__ import annotations

import datetime
import re
import sqlite3
import tkinter as tk
import zipfile
from pathlib import Path
from tkinter import messagebox
from xml.sax.saxutils import escape


MODULE_VERSION = "1.8.14"
# PZ_CORRESPONDENCE_V1814: Projektbezogenes Word-Anschreiben aus der
# Engbers-Vorlage, mit Empfaenger, Betreff, Uebergabeliste und Bitte-um-Auswahl.

BG = "#f4f1ea"
PANEL = "#fbfaf6"
INK = "#161616"
MUTED = "#6c6c68"
LINE = "#c8c5bd"
DARK = "#202020"
ACCENT = "#b08b49"

TEMPLATE_NAME = "anschreiben_template.docx"

DOCUMENT_OPTIONS = (
    "Unterlagen",
    "Statische Berechnung",
    "Positionspläne",
    "Zeichnungen",
    "Bewehrungspläne",
    "Wärmeschutz / GEG",
    "KfW / EEE",
    "DGNB / QNG",
    "Bescheinigungen",
    "Ausschreibung",
    "Angebot",
    "Rechnung",
    "Abschlagsrechnung",
    "Schlussrechnung",
)

REQUEST_OPTIONS = (
    ("Kenntnisnahme", 6),
    ("Prüfung", 7),
    ("Genehmigung", 8),
    ("Erledigung", 9),
    ("Unterschrift", 11),
    ("Rücksprache", 12),
    ("Rücksendung", 13),
    ("Angebot", 14),
    ("Weiterleitung an", 10),
)


def _safe_filename(text):
    text = re.sub(r"\s+", "_", str(text or "").strip())
    text = re.sub(r"[^A-Za-z0-9ÄÖÜäöüß._-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("._-")
    return text[:80] or "Empfaenger"


def _unique_destination(folder, filename):
    folder = Path(folder)
    candidate = folder / filename
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    number = 2
    while candidate.exists():
        candidate = folder / f"{stem} ({number}){suffix}"
        number += 1
    return candidate


def _set_checkbox(xml, number, checked):
    pattern = re.compile(
        r'(<w:ffData>.*?<w:name w:val="Kontrollkästchen' + re.escape(str(number))
        + r'"/>.*?<w:checkBox>.*?<w:default w:val=")[01]("/>)',
        re.S,
    )
    xml, count = pattern.subn(r"\g<1>" + ("1" if checked else "0") + r"\2", xml, count=1)
    if count != 1:
        raise RuntimeError(f"Kontrollkästchen {number} wurde in der Anschreiben-Vorlage nicht gefunden.")
    return xml


def create_letter(template_path, output_path, values, document_items, requests):
    template_path = Path(template_path)
    output_path = Path(output_path)
    if not template_path.is_file():
        raise RuntimeError("Die Anschreiben-Vorlage fehlt: " + str(template_path))
    if len(document_items) > 5:
        raise RuntimeError("Im Anschreiben können maximal fünf Unterlagen gleichzeitig aufgeführt werden.")

    replacements = {
        "EMPFAENGER": values.get("recipient", ""),
        "STRASSE": values.get("street", ""),
        "PLZORT": values.get("city", ""),
        "DATUM": values.get("date", ""),
        "BETREFF": values.get("subject", ""),
        "ANREDE": values.get("greeting", ""),
        "TEXT": values.get("body", ""),
        "WEITERLEITUNG": (" " + values.get("forward_to", "").strip()) if values.get("forward_to", "").strip() else "_______________________",
    }
    for index in range(5):
        replacements[f"ITEM{index + 1}"] = document_items[index] if index < len(document_items) else ""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(template_path, "r") as source, zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == "word/document.xml":
                xml = data.decode("utf-8")
                for key, value in replacements.items():
                    xml = xml.replace("{{" + key + "}}", escape(str(value or "")))
                for number in range(1, 6):
                    xml = _set_checkbox(xml, number, number <= len(document_items))
                requested_numbers = {int(number) for number in requests}
                for number in range(6, 15):
                    xml = _set_checkbox(xml, number, number in requested_numbers)
                data = xml.encode("utf-8")
            target.writestr(info, data)
    return output_path


def _register_in_communication(db_path, project_id, recipient, subject, body, output_path):
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            """INSERT INTO comm(project_id,ts,channel,sender,recipient,subject,body,attachment,original_path,immutable)
               VALUES(?,?,?,?,?,?,?,?,?,1)""",
            (
                project_id,
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Anschreiben",
                "Engbers Ingenieurbau",
                recipient,
                subject,
                body,
                str(output_path),
                str(output_path),
            ),
        )
        con.commit()
    finally:
        con.close()


def open_correspondence_dialog(app, db_path):
    project = app.project_row()
    if not project:
        messagebox.showwarning("Anschreiben", "Bitte zuerst ein Projekt auswählen.", parent=app)
        return

    base_dir = Path(__file__).resolve().parent
    template_path = base_dir / TEMPLATE_NAME
    if not template_path.is_file():
        messagebox.showerror("Anschreiben", "Die Engbers-Anschreiben-Vorlage wurde nicht gefunden.", parent=app)
        return

    window = tk.Toplevel(app)
    window.title("Anschreiben erstellen")
    window.configure(bg=BG)
    sw = max(900, int(window.winfo_screenwidth()))
    sh = max(700, int(window.winfo_screenheight()))
    width = min(980, sw - 80)
    height = min(790, sh - 90)
    window.geometry(f"{width}x{height}")
    window.minsize(840, 650)
    window.transient(app)
    window.grab_set()

    tk.Label(window, text="ANSCHREIBEN ERSTELLEN", bg=BG, fg=INK,
             font=("Segoe UI Semibold", 16)).pack(anchor="w", padx=24, pady=(18, 3))
    tk.Label(window, text=f"{project['number']} · {project['title']}  ·  Vorlage: Engbers Standardanschreiben",
             bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=24, pady=(0, 12))

    canvas = tk.Canvas(window, bg=BG, highlightthickness=0)
    scroll = tk.Scrollbar(window, orient="vertical", command=canvas.yview)
    inner = tk.Frame(canvas, bg=BG)
    inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=scroll.set)
    canvas.pack(side="left", fill="both", expand=True, padx=(18, 0), pady=(0, 64))
    scroll.pack(side="right", fill="y", padx=(0, 8), pady=(0, 64))

    def sync_scroll(_event=None):
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.itemconfigure(inner_id, width=max(780, canvas.winfo_width()))
    inner.bind("<Configure>", sync_scroll)
    canvas.bind("<Configure>", sync_scroll)

    recipient_var = tk.StringVar(value=str(project["client"] or ""))
    street_var = tk.StringVar()
    city_var = tk.StringVar()
    date_var = tk.StringVar(value=datetime.date.today().strftime("%d.%m.%Y"))
    subject_var = tk.StringVar(value=f"Unterlagen – {project['number']} · {project['title']}")
    greeting_var = tk.StringVar(value="Sehr geehrte Damen und Herren,")
    forward_var = tk.StringVar()
    custom_var = tk.StringVar()

    form = tk.Frame(inner, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
    form.pack(fill="x", padx=6, pady=(0, 12))
    form.columnconfigure(1, weight=1)

    fields = (
        ("Empfänger / Firma", recipient_var),
        ("Straße", street_var),
        ("PLZ / Ort", city_var),
        ("Datum", date_var),
        ("Betreff", subject_var),
        ("Anrede", greeting_var),
    )
    for row, (label, variable) in enumerate(fields):
        tk.Label(form, text=label, width=18, anchor="w", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9)).grid(row=row, column=0, sticky="w", padx=(16, 8), pady=5)
        entry = tk.Entry(form, textvariable=variable, font=("Segoe UI", 10), bd=0,
                         highlightthickness=1, highlightbackground=LINE)
        entry.grid(row=row, column=1, sticky="ew", padx=(0, 16), pady=5, ipady=5)

    selection_row = tk.Frame(inner, bg=BG)
    selection_row.pack(fill="x", padx=6, pady=(0, 12))
    selection_row.columnconfigure(0, weight=1)
    selection_row.columnconfigure(1, weight=1)

    left = tk.Frame(selection_row, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
    left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
    right = tk.Frame(selection_row, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
    right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

    tk.Label(left, text="WIR ÜBERREICHEN IHNEN", bg=PANEL, fg=INK,
             font=("Segoe UI Semibold", 10)).pack(anchor="w", padx=14, pady=(12, 6))
    tk.Label(left, text="Bis zu 5 Positionen auswählen.", bg=PANEL, fg=MUTED,
             font=("Segoe UI", 8)).pack(anchor="w", padx=14, pady=(0, 5))
    document_vars = {}
    for option in DOCUMENT_OPTIONS:
        variable = tk.BooleanVar(value=(option == "Unterlagen"))
        document_vars[option] = variable
        tk.Checkbutton(left, text=option, variable=variable, bg=PANEL, fg=INK,
                       activebackground=PANEL, selectcolor=PANEL, anchor="w",
                       font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=1)
    custom_line = tk.Frame(left, bg=PANEL)
    custom_line.pack(fill="x", padx=12, pady=(3, 10))
    tk.Label(custom_line, text="Eigener Eintrag:", bg=PANEL, fg=MUTED,
             font=("Segoe UI", 8)).pack(side="left")
    tk.Entry(custom_line, textvariable=custom_var, font=("Segoe UI", 9), bd=0,
             highlightthickness=1, highlightbackground=LINE).pack(side="left", fill="x", expand=True, padx=(6, 0), ipady=3)

    tk.Label(right, text="MIT DER BITTE UM", bg=PANEL, fg=INK,
             font=("Segoe UI Semibold", 10)).pack(anchor="w", padx=14, pady=(12, 6))
    request_vars = {}
    for label, number in REQUEST_OPTIONS:
        variable = tk.BooleanVar(value=(label == "Kenntnisnahme"))
        request_vars[number] = variable
        tk.Checkbutton(right, text=label, variable=variable, bg=PANEL, fg=INK,
                       activebackground=PANEL, selectcolor=PANEL, anchor="w",
                       font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=2)
    forward_line = tk.Frame(right, bg=PANEL)
    forward_line.pack(fill="x", padx=12, pady=(3, 12))
    tk.Label(forward_line, text="Weiterleitung an:", bg=PANEL, fg=MUTED,
             font=("Segoe UI", 8)).pack(side="left")
    tk.Entry(forward_line, textvariable=forward_var, font=("Segoe UI", 9), bd=0,
             highlightthickness=1, highlightbackground=LINE).pack(side="left", fill="x", expand=True, padx=(6, 0), ipady=3)

    note_box = tk.Frame(inner, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
    note_box.pack(fill="x", padx=6, pady=(0, 14))
    tk.Label(note_box, text="OPTIONALER BEGLEITTEXT", bg=PANEL, fg=INK,
             font=("Segoe UI Semibold", 10)).pack(anchor="w", padx=14, pady=(10, 4))
    note = tk.Text(note_box, height=3, wrap="word", font=("Segoe UI", 9), bd=0,
                   highlightthickness=1, highlightbackground=LINE)
    note.pack(fill="x", padx=14, pady=(0, 12))

    status = tk.Label(inner, text="Das Word-Dokument wird unter 08_Kommunikation\\Anschreiben gespeichert und in der Kommunikationsakte eingetragen.",
                      bg=BG, fg=MUTED, font=("Segoe UI", 8), justify="left")
    status.pack(anchor="w", padx=8, pady=(0, 12))

    actions = tk.Frame(window, bg=BG)
    actions.place(relx=0, rely=1, relwidth=1, anchor="sw", height=58)

    def create():
        recipient = recipient_var.get().strip()
        subject = subject_var.get().strip()
        if not recipient:
            messagebox.showwarning("Anschreiben", "Bitte einen Empfänger eintragen.", parent=window)
            return
        if not subject:
            messagebox.showwarning("Anschreiben", "Bitte einen Betreff eintragen.", parent=window)
            return

        items = [label for label, variable in document_vars.items() if variable.get()]
        custom = custom_var.get().strip()
        if custom:
            if len(custom) > 24:
                messagebox.showwarning("Anschreiben", "Der eigene Eintrag ist für die Vorlage zu lang. Bitte maximal 24 Zeichen verwenden.", parent=window)
                return
            items.append(custom)
        if not items:
            messagebox.showwarning("Anschreiben", "Bitte mindestens eine Unterlage auswählen.", parent=window)
            return
        if len(items) > 5:
            messagebox.showwarning("Anschreiben", "Bitte höchstens fünf Unterlagen auswählen.", parent=window)
            return
        too_long = [item for item in items if len(item) > 24]
        if too_long:
            messagebox.showwarning(
                "Anschreiben",
                "Ein Eintrag ist für die Vorlage zu lang. Bitte kürzer formulieren (maximal 24 Zeichen):\n\n" + "\n".join(too_long),
                parent=window,
            )
            return

        request_numbers = [number for number, variable in request_vars.items() if variable.get()]
        if request_vars[10].get() and not forward_var.get().strip():
            if not messagebox.askyesno("Anschreiben", "Weiterleitung ist ausgewählt, aber kein Empfänger dafür eingetragen. Trotzdem erstellen?", parent=window):
                return
        if forward_var.get().strip() and len(forward_var.get().strip()) > 22:
            messagebox.showwarning("Anschreiben", "Der Eintrag bei ‚Weiterleitung an‘ ist für die Vorlage zu lang. Bitte maximal 22 Zeichen verwenden.", parent=window)
            return

        root = Path(app.get_project_folder(project))
        output_folder = root / "08_Kommunikation" / "Anschreiben"
        filename = f"{datetime.date.today().isoformat()}_Anschreiben_{_safe_filename(recipient)}.docx"
        output = _unique_destination(output_folder, filename)
        body = note.get("1.0", "end").strip().replace("\n", " ")
        values = {
            "recipient": recipient,
            "street": street_var.get().strip(),
            "city": city_var.get().strip(),
            "date": date_var.get().strip(),
            "subject": subject,
            "greeting": greeting_var.get().strip() or "Sehr geehrte Damen und Herren,",
            "body": body,
            "forward_to": forward_var.get().strip(),
        }
        try:
            create_letter(template_path, output, values, items, request_numbers)
            _register_in_communication(db_path, int(project["id"]), recipient, subject, body, output)
        except Exception as exc:
            messagebox.showerror("Anschreiben", str(exc), parent=window)
            return

        window.destroy()
        try:
            app.show_comm()
        except Exception:
            pass
        try:
            app.open_external_path(output)
        except Exception:
            pass
        messagebox.showinfo(
            "Anschreiben erstellt",
            "Das Anschreiben wurde erstellt und in der Kommunikationsakte abgelegt.\n\n" + str(output),
            parent=app,
        )

    tk.Button(actions, text="ABBRECHEN", command=window.destroy, bg="#dedbd2", fg=INK,
              bd=0, padx=18, pady=9, font=("Segoe UI", 9)).pack(side="right", padx=(8, 20), pady=10)
    tk.Button(actions, text="WORD ERSTELLEN & ÖFFNEN", command=create, bg=ACCENT, fg="white",
              activebackground="#9b783d", activeforeground="white", bd=0, padx=20, pady=9,
              font=("Segoe UI Semibold", 9), cursor="hand2").pack(side="right", pady=10)

    window.update_idletasks()
    try:
        canvas.yview_moveto(0)
    except Exception:
        pass


__all__ = ["open_correspondence_dialog", "create_letter"]
