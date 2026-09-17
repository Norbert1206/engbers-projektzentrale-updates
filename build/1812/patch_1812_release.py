from pathlib import Path
import py_compile
import sys

root = Path(sys.argv[1]).resolve()
app_path = root / "app.py"
comm_path = root / "commercial_v1890.py"
post_path = root / "post_update.py"

def one(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f"{label}: erwartet 1 Treffer, gefunden {n}")
    return text.replace(old, new, 1)

def region(text, start, end, new, label):
    a = text.find(start)
    if a < 0:
        raise RuntimeError(label + ": Startmarker fehlt")
    b = text.find(end, a)
    if b < 0:
        raise RuntimeError(label + ": Endmarker fehlt")
    return text[:a] + new + text[b:]

app = app_path.read_text(encoding="utf-8")
app = one(app, 'APP_VERSION = "1.8.11"', 'APP_VERSION = "1.8.12"', "APP_VERSION")
app_path.write_text(app, encoding="utf-8")

c = comm_path.read_text(encoding="utf-8")
c = one(c, 'MODULE_VERSION = "1.8.11"', 'MODULE_VERSION = "1.8.12"', "MODULE_VERSION")
old_marker = (
    "# PZ_TEXT_EDITOR_FIT_V1811: Editor passt sich der Bildschirmhoehe an;\n"
    "# Speichern und Abbrechen bleiben fest am unteren Fensterrand sichtbar.\n"
)
c = one(
    c, old_marker,
    old_marker
    + "# PZ_LEXWARE_M_WORKFLOW_V1812: Lexware Office M ohne API - direkte Beleglisten,\n"
      "# Projektbezug in die Zwischenablage und sicherer PDF-Import aus Downloads.\n",
    "Featuremarker",
)
cat_anchor = 'TEXT_CATEGORIES = ("Allgemein", "Angebot", "Auftragsbestätigung", "Abschlagsrechnung", "Schlussrechnung", "E-Mail")\n'
c = one(
    c, cat_anchor,
    cat_anchor
    + 'LEXWARE_OFFERS_URL = "https://app.lexware.de/vouchers#!/VoucherList/?filter=quotation&sort=sortByVoucherDate&sortDirection=desc"\n'
      'LEXWARE_INVOICES_URL = "https://app.lexware.de/vouchers#!/VoucherList/?filter=invoice&sort=sortByVoucherDate&sortDirection=desc"\n',
    "Lexware-URLs",
)

toolbar_start = '    _button(toolbar, "KAUFMÄNNISCHEN ORDNER ÖFFNEN"'
toolbar_end = '\n\n    notebook = ttk.Notebook(parent)'
toolbar_new = '''    _button(toolbar, "KAUFMÄNNISCHEN ORDNER ÖFFNEN", lambda: app.open_external_path(base)).pack(side="left")

    def copy_project_reference():
        reference = f"{project['number']} · {project['title']}"
        app.clipboard_clear()
        app.clipboard_append(reference)
        app.update_idletasks()
        messagebox.showinfo("Projektbezug kopiert", f"Für Lexware kopiert:\\n\\n{reference}", parent=app)

    _button(toolbar, "LEXWARE ANGEBOTE", lambda: webbrowser.open(LEXWARE_OFFERS_URL), accent=True).pack(side="left", padx=(8, 0))
    _button(toolbar, "LEXWARE RECHNUNGEN", lambda: webbrowser.open(LEXWARE_INVOICES_URL)).pack(side="left", padx=(8, 0))
    _button(toolbar, "PROJEKTBEZUG KOPIEREN", copy_project_reference).pack(side="left", padx=(8, 0))
    tk.Label(toolbar, text="Lexware Office M · ohne API · keine Zugangsdaten",
             bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(side="left", padx=10)'''
c = region(c, toolbar_start, toolbar_end, toolbar_new, "Toolbar")

import_start = "    def import_documents():\n"
import_end = "    def open_document(_event=None):\n"
import_new = '''    def _copy_documents(source_names, dialog_title):
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
            messagebox.showinfo(
                dialog_title,
                f"{len(copied)} Datei(en) wurden als Kopie nach „{category_var.get()}“ abgelegt.\\n\\n"
                "Die Originaldatei bleibt unverändert.",
                parent=app,
            )

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
c = region(c, import_start, import_end, import_new, "Import")

old_action = '    _button(doc_actions, "DATEIEN ABLEGEN", import_documents, accent=True).pack(side="left")\n'
new_action = (
    '    _button(doc_actions, "LEXWARE-PDF ABLEGEN", import_lexware_pdfs, accent=True).pack(side="left")\n'
    '    _button(doc_actions, "DATEIEN ABLEGEN", import_documents).pack(side="left", padx=(8, 0))\n'
)
c = one(c, old_action, new_action, "Aktionsleiste")
comm_path.write_text(c, encoding="utf-8")

post = post_path.read_text(encoding="utf-8")
post = one(post, "update_1811_install.log", "update_1812_install.log", "Install-Log")
post = one(post, "update_1811_error.txt", "update_1812_error.txt", "Fehler-Log")
post = one(post, 'APP_VERSION = "1.8.11"', 'APP_VERSION = "1.8.12"', "Post-Version")
post = one(post, "OK: Update 1.8.11 erfolgreich installiert.", "OK: Update 1.8.12 erfolgreich installiert.", "Post-Erfolg")
post_path.write_text(post, encoding="utf-8")

for p in (app_path, comm_path, post_path):
    py_compile.compile(str(p), doraise=True)

check = comm_path.read_text(encoding="utf-8")
for marker in (
    "PZ_LEXWARE_M_WORKFLOW_V1812",
    "LEXWARE ANGEBOTE",
    "LEXWARE RECHNUNGEN",
    "PROJEKTBEZUG KOPIEREN",
    "LEXWARE-PDF ABLEGEN",
    'Path.home() / "Downloads"',
):
    if marker not in check:
        raise RuntimeError("Funktionspruefung fehlt: " + marker)

print("1.8.12 vorbereitet: Lexware Office M ohne API.")
