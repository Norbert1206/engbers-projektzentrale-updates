from pathlib import Path
import py_compile
import sqlite3
import sys

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
APP = ROOT / "app.py"
COMM = ROOT / "commercial_v1890.py"
POST = ROOT / "post_update.py"

for path in (APP, COMM, POST):
    if not path.exists():
        raise RuntimeError(f"1.8.13: Update-Datei fehlt: {path.name}")


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"1.8.13: Marker {label} erwartet 1x, gefunden {count}x")
    return text.replace(old, new, 1)


app = APP.read_text(encoding="utf-8")
app = replace_once(app, 'APP_VERSION = "1.8.12"', 'APP_VERSION = "1.8.13"', "APP_VERSION")
APP.write_text(app, encoding="utf-8")

comm = COMM.read_text(encoding="utf-8")
comm = replace_once(comm, 'MODULE_VERSION = "1.8.12"', 'MODULE_VERSION = "1.8.13"', "MODULE_VERSION")
feature_anchor = '# PZ_LEXWARE_M_WORKFLOW_V1812: Lexware Office M ohne API - direkte Beleglisten,\n# Projektbezug in die Zwischenablage und sicherer PDF-Import aus Downloads.\n'
comm = replace_once(
    comm,
    feature_anchor,
    feature_anchor + '# PZ_COMMERCIAL_DEFAULT_TEXTS_V1813: Fachlich sortierte Standard-Textbibliothek\n'
                     '# fuer Tragwerksplanung, Waermeschutz/KfW und DGNB/QNG.\n',
    "feature marker",
)
comm = replace_once(
    comm,
    'TEXT_CATEGORIES = ("Allgemein", "Angebot", "Auftragsbestätigung", "Abschlagsrechnung", "Schlussrechnung", "E-Mail")',
    'TEXT_CATEGORIES = ("Allgemein", "Angebot", "Auftragsbestätigung", "Rechnung", "Abschlagsrechnung", "Schlussrechnung", "E-Mail")',
    "text categories",
)

library_block = r'''

DEFAULT_COMMERCIAL_TEXTS_V1813 = (
    ("Tragwerksplanung – Rechnung Standard", "Rechnung",
     "Für die im Zusammenhang mit dem oben genannten Bauvorhaben erbrachten Leistungen der Tragwerksplanung erlauben wir uns, Ihnen unsere Leistungen wie folgt in Rechnung zu stellen."),
    ("Tragwerksplanung – Rechnung nach Leistungsstand", "Rechnung",
     "Entsprechend dem aktuellen Bearbeitungs- und Leistungsstand der Tragwerksplanung berechnen wir die bislang erbrachten Ingenieurleistungen wie folgt."),
    ("Tragwerksplanung – Abschlagsrechnung", "Abschlagsrechnung",
     "Entsprechend dem derzeitigen Bearbeitungs- und Leistungsstand der Tragwerksplanung erlauben wir uns, Ihnen für die bisher erbrachten Leistungen folgenden Abschlag in Rechnung zu stellen."),
    ("Tragwerksplanung – Schlussrechnung", "Schlussrechnung",
     "Nach Abschluss der beauftragten Leistungen der Tragwerksplanung erlauben wir uns, Ihnen unsere Leistungen abschließend in Rechnung zu stellen. Bereits geleistete Abschlagszahlungen werden entsprechend berücksichtigt."),
    ("Tragwerksplanung – Zusatzleistungen", "Rechnung",
     "Für die zusätzlich beauftragten beziehungsweise über den ursprünglich vereinbarten Leistungsumfang hinausgehenden Leistungen der Tragwerksplanung erlauben wir uns folgende Abrechnung."),
    ("Tragwerksplanung – Planungsänderungen", "Rechnung",
     "Für die infolge geänderter Planungsgrundlagen, zusätzlicher Abstimmungen oder nachträglicher Änderungen erforderlich gewordenen Leistungen der Tragwerksplanung berechnen wir wie folgt."),
    ("Tragwerksplanung – Statische Berechnungen", "Rechnung",
     "Für die Erstellung und Bearbeitung der statischen Berechnungen und erforderlichen Tragfähigkeits- und Gebrauchstauglichkeitsnachweise berechnen wir die erbrachten Leistungen wie folgt."),
    ("Tragwerksplanung – Ausführungs- und Detailplanung", "Rechnung",
     "Für die im Rahmen der konstruktiven Durcharbeitung, Ausführungs- und Detailplanung erbrachten Ingenieurleistungen erlauben wir uns folgende Abrechnung."),
    ("Tragwerksplanung – Prüfstatik / Prüfanmerkungen", "Rechnung",
     "Für die Bearbeitung der Prüfanmerkungen, ergänzenden Nachweise und erforderlichen Abstimmungen im Rahmen der statischen Prüfung berechnen wir die erbrachten Leistungen wie folgt."),
    ("Tragwerksplanung – Abrechnung nach Aufwand", "Rechnung",
     "Die nachfolgend aufgeführten zusätzlichen Ingenieurleistungen werden entsprechend dem tatsächlich angefallenen Bearbeitungs- und Abstimmungsaufwand abgerechnet."),

    ("Wärmeschutz / GEG – Rechnung Standard", "Rechnung",
     "Für die im Rahmen des energetischen Nachweises und der wärmeschutztechnischen Bearbeitung des Bauvorhabens erbrachten Ingenieurleistungen erlauben wir uns folgende Abrechnung."),
    ("Wärmeschutz / GEG – Abschlagsrechnung", "Abschlagsrechnung",
     "Entsprechend dem aktuellen Bearbeitungsstand der wärmeschutztechnischen Nachweise und der energetischen Planung berechnen wir die bisher erbrachten Leistungen wie folgt."),
    ("Wärmeschutz / GEG – Schlussrechnung", "Schlussrechnung",
     "Nach Abschluss der beauftragten wärmeschutztechnischen und energetischen Nachweise erlauben wir uns, Ihnen unsere Leistungen abschließend in Rechnung zu stellen. Bereits geleistete Abschläge werden berücksichtigt."),
    ("KfW / EEE – Fachplanung", "Rechnung",
     "Für die im Rahmen der energetischen Fachplanung und der Fördermittelbearbeitung erbrachten Leistungen als Energieeffizienz-Experte erlauben wir uns folgende Abrechnung."),
    ("KfW / EEE – Baubegleitung", "Rechnung",
     "Für die bisher durchgeführten Leistungen der energetischen Fachplanung und Baubegleitung einschließlich der erforderlichen Nachweise, Abstimmungen und Dokumentationen berechnen wir wie folgt."),
    ("KfW / EEE – Abschlagsrechnung", "Abschlagsrechnung",
     "Entsprechend dem aktuellen Bearbeitungsstand der energetischen Fachplanung, Fördermittelbegleitung und Dokumentation erlauben wir uns, die bisher erbrachten Leistungen mit folgendem Abschlag abzurechnen."),
    ("KfW / EEE – Abschluss", "Schlussrechnung",
     "Nach Abschluss der energetischen Fachplanung und Begleitung einschließlich der erforderlichen Nachweise und Abschlussdokumentation erlauben wir uns die abschließende Abrechnung unserer Leistungen."),
    ("Wärmebrücken – Detailnachweise", "Rechnung",
     "Für die Erstellung und Bearbeitung der wärmeschutztechnischen Detail- und Wärmebrückennachweise einschließlich der erforderlichen konstruktiven Abstimmungen berechnen wir die erbrachten Leistungen wie folgt."),
    ("Energetische Berechnungen – Zusatzleistungen", "Rechnung",
     "Für zusätzliche energetische Berechnungen, Variantenuntersuchungen und Nachweise, die über den ursprünglich vereinbarten Leistungsumfang hinausgehen, berechnen wir wie folgt."),
    ("Energetische Nachweise – Software / Varianten", "Rechnung",
     "Für die Bearbeitung zusätzlicher Berechnungsvarianten und programmbasierter Nachweise im Rahmen der energetischen Planung erlauben wir uns folgende Abrechnung."),

    ("DGNB / QNG – Rechnung Standard", "Rechnung",
     "Für die im Rahmen der DGNB-/QNG-Bearbeitung und der Nachhaltigkeitszertifizierung des Bauvorhabens erbrachten Leistungen erlauben wir uns folgende Abrechnung."),
    ("DGNB / QNG – Abschlagsrechnung", "Abschlagsrechnung",
     "Entsprechend dem aktuellen Bearbeitungsstand der DGNB-/QNG-Zertifizierung und der bislang erstellten Nachweise und Dokumentationen erlauben wir uns, die bisher erbrachten Leistungen wie folgt abzurechnen."),
    ("DGNB / QNG – Nachweise und Dokumentation", "Rechnung",
     "Für die Bearbeitung, Zusammenstellung und Prüfung der für die DGNB-/QNG-Zertifizierung erforderlichen Nachweise und Projektdokumentationen berechnen wir folgende Leistungen."),
    ("DGNB / QNG – Zertifizierungsbegleitung", "Rechnung",
     "Für die fachliche Begleitung des Zertifizierungsprozesses einschließlich Abstimmungen, Nachweisführung und Dokumentationsprüfung erlauben wir uns folgende Abrechnung."),
    ("DGNB / QNG – Zusatzleistungen", "Rechnung",
     "Für zusätzlich erforderliche Nachweise, Überarbeitungen und Abstimmungen im Rahmen der DGNB-/QNG-Zertifizierung, die über den vereinbarten Leistungsumfang hinausgehen, berechnen wir wie folgt."),
    ("DGNB / QNG – Schlussrechnung", "Schlussrechnung",
     "Nach Abschluss der vereinbarten Leistungen im Rahmen der DGNB-/QNG-Zertifizierung erlauben wir uns, Ihnen unsere Leistungen abschließend in Rechnung zu stellen. Bereits geleistete Abschläge werden berücksichtigt."),

    ("Allgemeine Rechnung – Ingenieurleistungen", "Rechnung",
     "Für die im Zusammenhang mit dem oben genannten Bauvorhaben erbrachten Ingenieurleistungen erlauben wir uns, Ihnen unsere Leistungen wie folgt in Rechnung zu stellen."),
    ("Allgemeine Abschlagsrechnung", "Abschlagsrechnung",
     "Auf Grundlage des aktuellen Leistungsstandes erlauben wir uns, die bislang erbrachten Ingenieurleistungen mit folgendem Abschlag abzurechnen."),
    ("Allgemeine Schlussrechnung", "Schlussrechnung",
     "Nach Abschluss der beauftragten Leistungen erfolgt mit dieser Rechnung die abschließende Abrechnung unserer Ingenieurleistungen unter Berücksichtigung bereits geleisteter Abschlagszahlungen."),
    ("Zusatzleistung – Allgemein", "Rechnung",
     "Für die zusätzlich beauftragten beziehungsweise über den ursprünglich vereinbarten Leistungsumfang hinausgehenden Leistungen erlauben wir uns folgende Abrechnung."),
    ("Abrechnung nach Zeitaufwand", "Rechnung",
     "Die nachfolgend aufgeführten Leistungen werden entsprechend dem tatsächlich angefallenen Zeit- und Bearbeitungsaufwand abgerechnet."),
    ("Zahlung – 14 Tage", "Allgemein",
     "Wir bitten um Überweisung des Rechnungsbetrages innerhalb von 14 Tagen ohne Abzug."),
    ("Zahlung – freundlich", "Allgemein",
     "Vielen Dank für die angenehme Zusammenarbeit. Wir bitten um Ausgleich des Rechnungsbetrages innerhalb von 14 Tagen ohne Abzug."),

    ("Angebot – Tragwerksplanung", "Angebot",
     "Gerne bieten wir Ihnen die erforderlichen Ingenieurleistungen für die Tragwerksplanung des oben genannten Bauvorhabens auf Grundlage der derzeit vorliegenden Planungsunterlagen wie folgt an."),
    ("Angebot – Wärmeschutz / KfW", "Angebot",
     "Gerne bieten wir Ihnen die erforderlichen Leistungen für die energetische Fachplanung, die wärmeschutztechnischen Nachweise und – soweit beauftragt – die KfW-/EEE-Begleitung wie folgt an."),
    ("Angebot – DGNB / QNG", "Angebot",
     "Gerne bieten wir Ihnen die fachliche Bearbeitung und Begleitung der DGNB-/QNG-Nachweise und der Nachhaltigkeitszertifizierung für das oben genannte Bauvorhaben wie folgt an."),
)


def ensure_default_commercial_texts(db_path):
    """Standardbibliothek genau einmal anlegen; vorhandene eigene Texte bleiben unverändert."""
    con = sqlite3.connect(db_path)
    try:
        con.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT)")
        marker = con.execute("SELECT value FROM meta WHERE key=?", ("commercial_default_texts_v1813",)).fetchone()
        if marker and str(marker[0]) == "1":
            return 0
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        added = 0
        for title, category, body in DEFAULT_COMMERCIAL_TEXTS_V1813:
            exists = con.execute(
                "SELECT 1 FROM commercial_texts WHERE lower(title)=lower(?) LIMIT 1", (title,)
            ).fetchone()
            if exists:
                continue
            con.execute(
                """INSERT INTO commercial_texts(project_id,title,category,body,is_global,created_at,updated_at)
                   VALUES(NULL,?,?,?,?,?,?)""",
                (title, category, body, 1, now, now),
            )
            added += 1
        con.execute(
            "INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)",
            ("commercial_default_texts_v1813", "1"),
        )
        con.commit()
        return added
    finally:
        con.close()
'''

comm = replace_once(comm, '\ndef _human_size(value):\n', library_block + '\n\ndef _human_size(value):\n', "default text library")
comm = replace_once(
    comm,
    '    ensure_schema(db_path)\n    project = app.project_row()\n',
    '    ensure_schema(db_path)\n    ensure_default_commercial_texts(db_path)\n    project = app.project_row()\n',
    "default text seed call",
)
COMM.write_text(comm, encoding="utf-8")

post = POST.read_text(encoding="utf-8")
for old, new, label in (
    ("update_1812_install.log", "update_1813_install.log", "post log"),
    ("update_1812_error.txt", "update_1813_error.txt", "post error"),
    ('APP_VERSION = "1.8.12"', 'APP_VERSION = "1.8.13"', "post version check"),
    ("('PZ_LEXWARE_M_WORKFLOW_V1812', commercial),", "('PZ_LEXWARE_M_WORKFLOW_V1812', commercial),\n            ('PZ_COMMERCIAL_DEFAULT_TEXTS_V1813', commercial),", "post feature check"),
    ("OK: Update 1.8.12 erfolgreich installiert.", "OK: Update 1.8.13 erfolgreich installiert.", "post success"),
):
    post = replace_once(post, old, new, label)
POST.write_text(post, encoding="utf-8")

for path in (APP, COMM, POST):
    py_compile.compile(str(path), doraise=True)

app_text = APP.read_text(encoding="utf-8")
comm_text = COMM.read_text(encoding="utf-8")
if 'APP_VERSION = "1.8.13"' not in app_text:
    raise RuntimeError("1.8.13: Version wurde nicht gesetzt.")
for required in (
    "PZ_COMMERCIAL_DEFAULT_TEXTS_V1813",
    "Tragwerksplanung – Rechnung Standard",
    "KfW / EEE – Fachplanung",
    "DGNB / QNG – Zertifizierungsbegleitung",
    "Zahlung – freundlich",
    '"Rechnung"',
):
    if required not in comm_text:
        raise RuntimeError("1.8.13: Funktionspruefung fehlt: " + required)

# Seed-Funktion mit einer frischen Testdatenbank prüfen.
namespace = {}
exec(compile(COMM.read_text(encoding="utf-8"), str(COMM), "exec"), namespace)
test_db = ROOT / "_test_1813.sqlite"
try:
    con = sqlite3.connect(test_db)
    con.execute("CREATE TABLE commercial_texts(id INTEGER PRIMARY KEY, project_id INTEGER, title TEXT NOT NULL, category TEXT, body TEXT, is_global INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT)")
    con.commit(); con.close()
    added = namespace["ensure_default_commercial_texts"](test_db)
    con = sqlite3.connect(test_db)
    count = con.execute("SELECT COUNT(*) FROM commercial_texts WHERE is_global=1").fetchone()[0]
    con.close()
    if added < 30 or count < 30:
        raise RuntimeError(f"1.8.13: Standardbibliothek unvollständig: added={added}, count={count}")
    if namespace["ensure_default_commercial_texts"](test_db) != 0:
        raise RuntimeError("1.8.13: Standardbibliothek wurde beim zweiten Lauf erneut angelegt.")
finally:
    try: test_db.unlink()
    except Exception: pass

print("Projektzentrale 1.8.13 Standard-Rechnungstexte gepatcht und geprüft.")
