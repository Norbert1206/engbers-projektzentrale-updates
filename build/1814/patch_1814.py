from pathlib import Path
import py_compile
import sys

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
APP = ROOT / "app.py"
POST = ROOT / "post_update.py"
CORR = ROOT / "correspondence_v1814.py"
CONTACTS = ROOT / "contacts_v1814.py"
TEMPLATE_HELPER = ROOT / "letter_template_v1814.py"

for path in (APP, POST, CORR, CONTACTS, TEMPLATE_HELPER):
    if not path.exists():
        raise RuntimeError(f"1.8.14: Update-Datei fehlt: {path.name}")


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"1.8.14: Marker {label} erwartet 1x, gefunden {count}x")
    return text.replace(old, new, 1)


app = APP.read_text(encoding="utf-8")
app = replace_once(app, 'APP_VERSION = "1.8.13"', 'APP_VERSION = "1.8.14"', "APP_VERSION")
app = replace_once(
    app,
    '    def show_comm(self):\n',
    '''    def create_correspondence(self):
        # PZ_CORRESPONDENCE_V1814: Engbers-Standardanschreiben direkt aus dem Projekt.
        try:
            from correspondence_v1814 import open_correspondence_dialog
            return open_correspondence_dialog(self, DB_PATH)
        except Exception as exc:
            messagebox.showerror('Anschreiben', str(exc), parent=self)

    def open_addressbook(self):
        # PZ_CONTACTS_V1814: lokales Adressbuch, vorbereitet fuer spaetere mobile Synchronisation.
        try:
            from contacts_v1814 import open_contact_picker
            return open_contact_picker(self, DB_PATH, self.project_id, None, False)
        except Exception as exc:
            messagebox.showerror('Adressbuch', str(exc), parent=self)

    def show_comm(self):
''',
    "correspondence and addressbook methods",
)
app = replace_once(
    app,
    "        for txt,cmd in [('E-Mail (.eml) importieren',self.import_eml),('WhatsApp (.txt) importieren',self.import_whatsapp),('Goodnotes-PDF importieren',self.import_goodnotes)]:\n",
    "        for txt,cmd in [('ANSCHREIBEN ERSTELLEN',self.create_correspondence),('ADRESSBUCH',self.open_addressbook),('E-Mail (.eml) importieren',self.import_eml),('WhatsApp (.txt) importieren',self.import_whatsapp),('Goodnotes-PDF importieren',self.import_goodnotes)]:\n",
    "communication toolbar",
)
APP.write_text(app, encoding="utf-8")

post = POST.read_text(encoding="utf-8")
post = replace_once(post, "update_1813_install.log", "update_1814_install.log", "post log")
post = replace_once(post, "update_1813_error.txt", "update_1814_error.txt", "post error")
post = replace_once(
    post,
    "    BASE / 'commercial_v1890.py',\n)",
    "    BASE / 'commercial_v1890.py',\n    BASE / 'correspondence_v1814.py',\n    BASE / 'contacts_v1814.py',\n    BASE / 'letter_template_v1814.py',\n)",
    "post required modules",
)
post = replace_once(post, 'APP_VERSION = "1.8.13"', 'APP_VERSION = "1.8.14"', "post version check")
post = replace_once(post, "OK: Update 1.8.13 erfolgreich installiert.", "OK: Update 1.8.14 erfolgreich installiert.", "post success")
POST.write_text(post, encoding="utf-8")

for path in (APP, POST, CORR, CONTACTS, TEMPLATE_HELPER):
    py_compile.compile(str(path), doraise=True)

app_text = APP.read_text(encoding="utf-8")
corr_text = CORR.read_text(encoding="utf-8")
contacts_text = CONTACTS.read_text(encoding="utf-8")
template_text = TEMPLATE_HELPER.read_text(encoding="utf-8")
if 'APP_VERSION = "1.8.14"' not in app_text:
    raise RuntimeError("1.8.14: Version wurde nicht gesetzt.")
for required in (
    "PZ_CORRESPONDENCE_V1814",
    "PZ_CONTACTS_V1814",
    "ANSCHREIBEN ERSTELLEN",
    "ADRESSBUCH",
    "open_correspondence_dialog",
):
    if required not in app_text and required not in corr_text and required not in contacts_text:
        raise RuntimeError("1.8.14: Funktionspruefung fehlt: " + required)
for required in ("PZ_CORRESPONDENCE_PRIVATE_TEMPLATE_V1814", "PRIVATE_TEMPLATE", "convert_original_template"):
    if required not in template_text and required not in corr_text:
        raise RuntimeError("1.8.14: Vorlagenpruefung fehlt: " + required)

print("OK: Projektzentrale 1.8.14 Anschreiben, lokales Adressbuch und private Vorlage vorbereitet.")
