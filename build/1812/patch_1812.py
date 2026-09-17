from pathlib import Path
import py_compile
import sys

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
APP = ROOT / "app.py"
COMM = ROOT / "commercial_v1890.py"
POST = ROOT / "post_update.py"

for path in (APP, COMM, POST):
    if not path.exists():
        raise RuntimeError(f"1.8.12: Update-Datei fehlt: {path.name}")

def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"1.8.12: Marker {label} erwartet 1x, gefunden {count}x")
    return text.replace(old, new, 1)

# app.py: only the program version changes. The commercial UI lives in its own module.
app = APP.read_text(encoding="utf-8")
app = replace_once(app, 'APP_VERSION = "1.8.11"', 'APP_VERSION = "1.8.12"', "APP_VERSION")
APP.write_text(app, encoding="utf-8")

comm = COMM.read_text(encoding="utf-8")
comm = replace_once(comm, 'MODULE_VERSION = "1.8.11"', 'MODULE_VERSION = "1.8.12"', "MODULE_VERSION")
marker = '# PZ_TEXT_EDITOR_FIT_V1811: Editor passt sich der Bildschirmhoehe an;\n# Speichern und Abbrechen bleiben fest am unteren Fensterrand sichtbar.\n'
comm = replace_once(
    comm,
    marker,
    marker + '# PZ_LEXWARE_M_WORKFLOW_V1812: Lexware Office M ohne API - direkte Beleglisten,\n'
             '# Projektbezug in die Zwischenablage und sicherer PDF-Import aus Downloads.\n',
    "feature marker",
)
anchor = 'TEXT_CATEGORIES = ("Allgemein", "Angebot", "Auftragsbestätigung", "Abschlagsrechnung", "Schlussrechnung", "E-Mail")\n'
comm = replace_once(
    comm,
    anchor,
    anchor
    + 'LEXWARE_OFFERS_URL = "https://app.lexware.de/vouchers#!/VoucherList/?filter=quotation&sort=sortByVoucherDate&sortDirection=desc"\n'
    + 'LEXWARE_INVOICES_URL = "https://app.lexware.de/vouchers#!/VoucherList/?filter=invoice&sort=sortByVoucherDate&sortDirection=desc"\n',
    "Lexware URLs",
)

old_toolbar = '''    _button(toolbar, "KAUFMÄNNISCHEN ORDNER ÖFFNEN", lambda: app.open_external_path(base)).pack(side="left")
    lexware_button = _button(toolbar, "LEXWARE ONLINE ÖFFNEN", lambda: webbrowser.open("https://app.lexware.de"), accent=True)
    lexware_button.pack(side="left", padx=8)
    tk.Label(toolbar, text="Lexware-Verknüpfung vorbereitet · keine Zugangsdaten werden gespeichert",
             bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(side="left", padx=8)
'''
new_toolbar = '''    _button(toolbar, "KAUFMÄNNISCHEN ORDNER ÖFFNEN", lambda: app.open_external_path(base)).pack(side="left")

    def copy_project_reference():
        reference = f"{project['number']} · {project['title']}"
        app.clipboard_clear()
        app.clipboard_append(reference)
        app.update_idletasks()
        messagebox.showinfo("Projektbezug kopiert",
                            f"Für Lexware kopiert:\\n\\n{reference}",
                            parent=app)

    _button(toolbar, "LEXWARE ANGEBOTE", lambda: webbrowser.open(LEXWARE_OFFERS_URL), accent=True).pack(side="left", padx=(8, 0))
    _button(toolbar, "LEXWARE RECHNUNGEN", lambda: webbrowser.open(LEXWARE_INVOICES_URL)).pack(side="left", padx=(8, 0))
    _button(toolbar, "PROJEKTBEZUG KOPIEREN", copy_project_reference).pack(side="left", padx=(8, 0))
    tk.Label(toolbar, text="Lexware Office M · ohne API · keine Zugangsdaten",
             bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(side="left", padx=10)
'''
comm = replace_once(comm, old_toolbar, new_toolbar, "commercial toolbar")

old_import = '''    def import_documents():
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
            messagebox.showwarning("Dateien ablegen", f"{len(copied)} Datei(en) kopiert.\\n\\n" + "\\n".join(errors[:8]), parent=app)
        elif copied:
            messagebox.showinfo("Dateien ablegen", f"{len(copied)} Datei(en) wurden nach „{category_var.get()}“ kopiert.", parent=app)
'''
new_import = '''    def _copy_documents(source_names, dialog_title):
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
            messagebox.showwarning(dialog_title, f"{len(copied)} Datei(en) kopiert.\\n\\n" + "\\n".join(errors[:8]), parent=app)
        elif copied:
            messagebox.showinfo(dialog_title,
                                f"{len(copied)} Datei(en) wurden als Kopie nach „{category_var.get()}“ abgelegt.\\n\\n"
                                "Die Originaldatei bleibt unverändert.",
                                parent=app)

    def import_documents():
        source_names = filedialog.askopenfilenames(title="Dateien ablegen", parent=app)
        if source_names:
            _copy_documents(source_names, "Dateien ablegen")

    def import_lexware_pdfs():
        downloads = Path.home() / "Downloads"
        initial = downloads if downloads.exists() else Path.home()
        source_names = filedialog.askopenfilenames(
            title=f"Lexware-PDF nach „{category_var.get()}“ ablegen",
            initialdir=str(initial),
            filetypes=[("PDF-Dateien", "*.pdf"), ("Alle Dateien", "*.*")],
            parent=app,
        )
        if source_names:
            _copy_documents(source_names, "Lexware-PDF ablegen")
'''
comm = replace_once(comm, old_import, new_import, "document import")

old_actions = '''    _button(doc_actions, "DATEIEN ABLEGEN", import_documents, accent=True).pack(side="left")
    _button(doc_actions, "ÖFFNEN", open_document).pack(side="left", padx=(8, 0))
'''
new_actions = '''    _button(doc_actions, "LEXWARE-PDF ABLEGEN", import_lexware_pdfs, accent=True).pack(side="left")
    _button(doc_actions, "DATEIEN ABLEGEN", import_documents).pack(side="left", padx=(8, 0))
    _button(doc_actions, "ÖFFNEN", open_document).pack(side="left", padx=(8, 0))
'''
comm = replace_once(comm, old_actions, new_actions, "document action buttons")
COMM.write_text(comm, encoding="utf-8")

post = POST.read_text(encoding="utf-8")
for old, new, label in (
    ("update_1811_install.log", "update_1812_install.log", "post log"),
    ("update_1811_error.txt", "update_1812_error.txt", "post error"),
    ('APP_VERSION = "1.8.11"', 'APP_VERSION = "1.8.12"', "post version check"),
    ("('PZ_TEXT_EDITOR_FIT_V1811', commercial),", "('PZ_TEXT_EDITOR_FIT_V1811', commercial),\\n            ('PZ_LEXWARE_M_WORKFLOW_V1812', commercial),", "post feature check"),
    ("OK: Update 1.8.11 erfolgreich installiert.", "OK: Update 1.8.12 erfolgreich installiert.", "post success"),
):
    post = replace_once(post, old, new, label)
POST.write_text(post, encoding="utf-8")

for path in (APP, COMM, POST):
    py_compile.compile(str(path), doraise=True)

# Final guards.
app_text = APP.read_text(encoding="utf-8")
comm_text = COMM.read_text(encoding="utf-8")
if 'APP_VERSION = "1.8.12"' not in app_text:
    raise RuntimeError("1.8.12: Version wurde nicht gesetzt.")
for required in (
    "PZ_LEXWARE_M_WORKFLOW_V1812",
    "LEXWARE ANGEBOTE",
    "LEXWARE RECHNUNGEN",
    "PROJEKTBEZUG KOPIEREN",
    "LEXWARE-PDF ABLEGEN",
    'Path.home() / "Downloads"',
):
    if required not in comm_text:
        raise RuntimeError("1.8.12: Funktionspruefung fehlt: " + required)
print("Projektzentrale 1.8.12 Lexware-M-Workflow gepatcht und kompiliert.")
