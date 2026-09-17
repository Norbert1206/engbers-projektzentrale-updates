"""Lokales Adressbuch fuer Engbers Projektzentrale."""
from __future__ import annotations

import datetime
import re
import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

MODULE_VERSION = "1.8.14"
# PZ_CONTACTS_V1814: Lokales, spaeter mobil synchronisierbares Adressbuch.

BG = "#f4f1ea"
PANEL = "#fbfaf6"
INK = "#161616"
MUTED = "#6c6c68"
LINE = "#c8c5bd"
DARK = "#202020"
ACCENT = "#b08b49"
DELETE = "#7b2d2d"

ROLES = ("Bauherr", "Architekt", "Prüfingenieur", "Fachplaner", "Bauleiter", "Unternehmer", "Behörde", "Korrespondenz", "Sonstiges")


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def _norm(value):
    return re.sub(r"\W+", "", str(value or "").casefold())


def ensure_contact_schema(db_path):
    con = sqlite3.connect(db_path)
    try:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS contacts(
              id INTEGER PRIMARY KEY,
              company TEXT DEFAULT '', salutation TEXT DEFAULT '', title TEXT DEFAULT '',
              first_name TEXT DEFAULT '', last_name TEXT DEFAULT '',
              street TEXT DEFAULT '', postal_code TEXT DEFAULT '', city TEXT DEFAULT '', country TEXT DEFAULT 'Deutschland',
              email TEXT DEFAULT '', phone TEXT DEFAULT '', mobile TEXT DEFAULT '', website TEXT DEFAULT '',
              source TEXT DEFAULT 'Manuell', source_checked_at TEXT DEFAULT '', notes TEXT DEFAULT '',
              created_at TEXT DEFAULT '', updated_at TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS project_contacts(
              id INTEGER PRIMARY KEY,
              project_id INTEGER NOT NULL, contact_id INTEGER NOT NULL,
              role TEXT DEFAULT 'Korrespondenz', is_primary INTEGER DEFAULT 0, created_at TEXT DEFAULT '',
              UNIQUE(project_id, contact_id, role)
            );
            """
        )
        con.commit()
    finally:
        con.close()


def contact_display(row):
    company = str(row["company"] or "").strip()
    person = " ".join(x for x in (str(row["title"] or "").strip(), str(row["first_name"] or "").strip(), str(row["last_name"] or "").strip()) if x)
    return company or person or "Kontakt"


def recipient_lines(row):
    company = str(row["company"] or "").strip()
    salutation = str(row["salutation"] or "").strip()
    title = str(row["title"] or "").strip()
    first = str(row["first_name"] or "").strip()
    last = str(row["last_name"] or "").strip()
    person = " ".join(x for x in (salutation, title, first, last) if x)
    if company and person:
        return company, person
    return company or person, ""


def greeting_for(row):
    salutation = str(row["salutation"] or "").strip().casefold()
    title = str(row["title"] or "").strip()
    last = str(row["last_name"] or "").strip()
    name = " ".join(x for x in (title, last) if x)
    if salutation == "herr" and name:
        return f"Sehr geehrter Herr {name},"
    if salutation == "frau" and name:
        return f"Sehr geehrte Frau {name},"
    return "Sehr geehrte Damen und Herren,"


def _possible_duplicate(con, values, ignore_id=None):
    email = str(values.get("email") or "").strip().casefold()
    phone = _norm(values.get("phone") or values.get("mobile"))
    company = _norm(values.get("company"))
    city = _norm(values.get("city"))
    rows = con.execute("SELECT * FROM contacts").fetchall()
    for row in rows:
        if ignore_id and int(row["id"]) == int(ignore_id):
            continue
        if email and str(row["email"] or "").strip().casefold() == email:
            return row
        row_phone = _norm(row["phone"] or row["mobile"])
        if phone and row_phone and phone == row_phone:
            return row
        if company and city and _norm(row["company"]) == company and _norm(row["city"]) == city:
            return row
    return None


def _edit_contact(parent, db_path, contact_id=None, after_save=None):
    ensure_contact_schema(db_path)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    row = con.execute("SELECT * FROM contacts WHERE id=?", (contact_id,)).fetchone() if contact_id else None
    con.close()

    w = tk.Toplevel(parent)
    w.title("Kontakt bearbeiten" if row else "Neuer Kontakt")
    w.geometry("720x690")
    w.configure(bg=BG)
    w.transient(parent)
    w.grab_set()

    tk.Label(w, text="KONTAKT", bg=BG, fg=INK, font=("Segoe UI Semibold", 15)).pack(anchor="w", padx=22, pady=(18, 10))
    form = tk.Frame(w, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
    form.pack(fill="both", expand=True, padx=22, pady=(0, 12))
    form.columnconfigure(1, weight=1)

    specs = [
        ("Firma / Büro", "company"), ("Anrede (Herr/Frau)", "salutation"), ("Titel", "title"),
        ("Vorname", "first_name"), ("Nachname", "last_name"), ("Straße / Nr.", "street"),
        ("PLZ", "postal_code"), ("Ort", "city"), ("Land", "country"), ("E-Mail", "email"),
        ("Telefon", "phone"), ("Mobil", "mobile"), ("Webseite", "website"), ("Quelle", "source"),
        ("Notiz", "notes"),
    ]
    vars_ = {}
    for i, (label, key) in enumerate(specs):
        value = str(row[key] or "") if row else ("Deutschland" if key == "country" else ("Manuell" if key == "source" else ""))
        var = tk.StringVar(value=value); vars_[key] = var
        tk.Label(form, text=label, bg=PANEL, fg=MUTED, width=20, anchor="w", font=("Segoe UI", 9)).grid(row=i, column=0, sticky="w", padx=(14, 8), pady=5)
        e = tk.Entry(form, textvariable=var, bd=0, highlightthickness=1, highlightbackground=LINE, font=("Segoe UI", 10))
        e.grid(row=i, column=1, sticky="ew", padx=(0, 14), pady=5, ipady=5)

    actions = tk.Frame(w, bg=BG); actions.pack(fill="x", padx=22, pady=(0, 18))

    def save():
        values = {k: v.get().strip() for k, v in vars_.items()}
        if not values["company"] and not values["last_name"]:
            messagebox.showwarning("Kontakt", "Bitte Firma oder Nachname eintragen.", parent=w); return
        con = sqlite3.connect(db_path); con.row_factory = sqlite3.Row
        try:
            dup = _possible_duplicate(con, values, contact_id)
            if dup is not None:
                if not messagebox.askyesno("Möglicher doppelter Kontakt", f"Ein ähnlicher Kontakt ist bereits vorhanden:\n\n{contact_display(dup)} · {dup['city'] or ''}\n\nTrotzdem speichern?", parent=w):
                    return
            now = _now()
            if contact_id:
                con.execute(
                    """UPDATE contacts SET company=?,salutation=?,title=?,first_name=?,last_name=?,street=?,postal_code=?,city=?,country=?,email=?,phone=?,mobile=?,website=?,source=?,source_checked_at=?,notes=?,updated_at=? WHERE id=?""",
                    (values["company"],values["salutation"],values["title"],values["first_name"],values["last_name"],values["street"],values["postal_code"],values["city"],values["country"],values["email"],values["phone"],values["mobile"],values["website"],values["source"],now if values["source"] else "",values["notes"],now,contact_id),
                )
                saved_id = int(contact_id)
            else:
                cur = con.execute(
                    """INSERT INTO contacts(company,salutation,title,first_name,last_name,street,postal_code,city,country,email,phone,mobile,website,source,source_checked_at,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (values["company"],values["salutation"],values["title"],values["first_name"],values["last_name"],values["street"],values["postal_code"],values["city"],values["country"],values["email"],values["phone"],values["mobile"],values["website"],values["source"] or "Manuell",now,values["notes"],now,now),
                )
                saved_id = int(cur.lastrowid)
            con.commit()
        finally:
            con.close()
        w.destroy()
        if callable(after_save): after_save(saved_id)

    tk.Button(actions, text="ABBRECHEN", command=w.destroy, bg="#dedbd2", fg=INK, bd=0, padx=18, pady=9).pack(side="right", padx=(8, 0))
    tk.Button(actions, text="SPEICHERN", command=save, bg=ACCENT, fg="white", bd=0, padx=20, pady=9, font=("Segoe UI Semibold", 9)).pack(side="right")


def open_contact_picker(parent, db_path, project_id=None, on_select=None, select_mode=True):
    ensure_contact_schema(db_path)
    w = tk.Toplevel(parent)
    w.title("Adressbuch")
    w.geometry("980x620")
    w.configure(bg=BG)
    w.transient(parent)
    w.grab_set()

    tk.Label(w, text="ADRESSBUCH", bg=BG, fg=INK, font=("Segoe UI Semibold", 16)).pack(anchor="w", padx=22, pady=(18, 4))
    tk.Label(w, text="Lokale Kontaktdatenbank · vorbereitet für spätere mobile Synchronisation", bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=22, pady=(0, 12))

    top = tk.Frame(w, bg=BG); top.pack(fill="x", padx=22, pady=(0, 8))
    search_var = tk.StringVar()
    tk.Label(top, text="Suchen", bg=BG, fg=MUTED).pack(side="left")
    search = tk.Entry(top, textvariable=search_var, bd=0, highlightthickness=1, highlightbackground=LINE, font=("Segoe UI", 10))
    search.pack(side="left", fill="x", expand=True, padx=(8, 10), ipady=6)

    cols = ("Firma / Name", "Ort", "Telefon", "E-Mail", "Quelle")
    tree = ttk.Treeview(w, columns=cols, show="headings", selectmode="browse")
    widths = (270, 150, 150, 260, 120)
    for c, width in zip(cols, widths):
        tree.heading(c, text=c); tree.column(c, width=width, anchor="w")
    tree.pack(fill="both", expand=True, padx=22, pady=(0, 10))
    current = []

    def refresh(*_):
        q = search_var.get().strip().casefold()
        con = sqlite3.connect(db_path); con.row_factory = sqlite3.Row
        rows = con.execute("SELECT * FROM contacts ORDER BY company COLLATE NOCASE,last_name COLLATE NOCASE,city COLLATE NOCASE").fetchall(); con.close()
        tree.delete(*tree.get_children()); current.clear()
        for row in rows:
            hay = " ".join(str(row[k] or "") for k in ("company","first_name","last_name","city","email","phone","mobile")).casefold()
            if q and q not in hay: continue
            current.append(row)
            tree.insert("", "end", iid=str(row["id"]), values=(contact_display(row), row["city"] or "", row["phone"] or row["mobile"] or "", row["email"] or "", row["source"] or ""))

    search_var.trace_add("write", refresh)

    actions = tk.Frame(w, bg=BG); actions.pack(fill="x", padx=22, pady=(0, 18))

    def selected_row():
        sel = tree.selection()
        if not sel: return None
        cid = int(sel[0])
        con = sqlite3.connect(db_path); con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM contacts WHERE id=?", (cid,)).fetchone(); con.close(); return row

    def new_contact(): _edit_contact(w, db_path, after_save=lambda _cid: refresh())
    def edit_contact():
        row = selected_row()
        if row is None: messagebox.showwarning("Adressbuch", "Bitte einen Kontakt auswählen.", parent=w); return
        _edit_contact(w, db_path, int(row["id"]), after_save=lambda _cid: refresh())
    def delete_contact():
        row = selected_row()
        if row is None: return
        if not messagebox.askyesno("Kontakt löschen", f"Kontakt wirklich löschen?\n\n{contact_display(row)}", parent=w): return
        con = sqlite3.connect(db_path)
        con.execute("DELETE FROM project_contacts WHERE contact_id=?", (int(row["id"]),)); con.execute("DELETE FROM contacts WHERE id=?", (int(row["id"]),)); con.commit(); con.close(); refresh()
    def choose():
        row = selected_row()
        if row is None: messagebox.showwarning("Adressbuch", "Bitte einen Kontakt auswählen.", parent=w); return
        if project_id:
            con = sqlite3.connect(db_path)
            con.execute("INSERT OR IGNORE INTO project_contacts(project_id,contact_id,role,is_primary,created_at) VALUES(?,?,?,?,?)", (int(project_id),int(row["id"]),"Korrespondenz",0,_now()))
            con.commit(); con.close()
        if callable(on_select): on_select(row)
        w.destroy()

    tk.Button(actions, text="NEUER KONTAKT", command=new_contact, bg=ACCENT, fg="white", bd=0, padx=16, pady=9, font=("Segoe UI Semibold", 9)).pack(side="left")
    tk.Button(actions, text="BEARBEITEN", command=edit_contact, bg=DARK, fg="white", bd=0, padx=16, pady=9).pack(side="left", padx=(8,0))
    tk.Button(actions, text="LÖSCHEN", command=delete_contact, bg=DELETE, fg="white", bd=0, padx=16, pady=9).pack(side="left", padx=(8,0))
    tk.Button(actions, text="SCHLIESSEN", command=w.destroy, bg="#dedbd2", fg=INK, bd=0, padx=16, pady=9).pack(side="right")
    if select_mode:
        tk.Button(actions, text="EMPFÄNGER ÜBERNEHMEN", command=choose, bg=ACCENT, fg="white", bd=0, padx=18, pady=9, font=("Segoe UI Semibold", 9)).pack(side="right", padx=(0,8))
        tree.bind("<Double-1>", lambda _e: choose())
    refresh(); search.focus_set()


__all__ = ["ensure_contact_schema", "open_contact_picker", "recipient_lines", "greeting_for", "contact_display"]
