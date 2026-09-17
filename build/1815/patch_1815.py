from pathlib import Path
import py_compile
import re
import sys

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
APP = ROOT / "app.py"
POST = ROOT / "post_update.py"
CORR = ROOT / "correspondence_v1814.py"
LETTER = ROOT / "letter_template_v1814.py"

for path in (APP, POST, CORR, LETTER):
    if not path.exists():
        raise RuntimeError(f"1.8.15: Update-Datei fehlt: {path.name}")


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"1.8.15: Marker {label} erwartet 1x, gefunden {count}x")
    return text.replace(old, new, 1)


app = APP.read_text(encoding="utf-8")
app = replace_once(app, 'APP_VERSION = "1.8.14"', 'APP_VERSION = "1.8.15"', "APP_VERSION")
APP.write_text(app, encoding="utf-8")

corr = CORR.read_text(encoding="utf-8")
corr = replace_once(
    corr,
    '    subject_var = tk.StringVar(value=f"Unterlagen – {project[\'number\']} · {project[\'title\']}")\n',
    '    subject_var = tk.StringVar(value="Unterlagen")\n',
    "Betreff Standard",
)
corr = replace_once(
    corr,
    '        request_numbers = [number for number, variable in request_vars.items() if variable.get()]\n',
    '        request_numbers = [number for number, variable in request_vars.items() if variable.get()]\n'
    '        if len(request_numbers) > 5:\n'
    '            messagebox.showwarning("Anschreiben", "Bitte höchstens fünf Optionen unter ‚Mit der Bitte um‘ auswählen. So bleibt das Anschreiben sauber untereinander ausgerichtet.", parent=window)\n'
    '            return\n',
    "Bitte-um Limit",
)
CORR.write_text(corr, encoding="utf-8")

letter = LETTER.read_text(encoding="utf-8")
new_create = r'''REQUEST_LABELS_V1815 = {
    6: "Kenntnisnahme",
    7: "Prüfung",
    8: "Genehmigung",
    9: "Erledigung",
    10: "Weiterleitung an",
    11: "Unterschrift",
    12: "Rücksprache",
    13: "Rücksendung",
    14: "Angebot",
}


def _q1815(tag):
    return f"{{{WNS}}}{tag}"


def _set_stacked_row_v1815(paragraph, left_text, right_text):
    """Schreibt eine saubere zweispaltige Zeile ohne verstreute Alt-Checkboxfelder."""
    ppr = paragraph.find("w:pPr", NS)
    for child in list(paragraph):
        if child is not ppr:
            paragraph.remove(child)
    if ppr is None:
        ppr = ET.SubElement(paragraph, _q1815("pPr"))

    tabs = ppr.find("w:tabs", NS)
    if tabs is None:
        tabs = ET.SubElement(ppr, _q1815("tabs"))
    else:
        for child in list(tabs):
            tabs.remove(child)
    tab = ET.SubElement(tabs, _q1815("tab"))
    tab.set(_q1815("val"), "left")
    tab.set(_q1815("pos"), "3700")

    spacing = ppr.find("w:spacing", NS)
    if spacing is None:
        spacing = ET.SubElement(ppr, _q1815("spacing"))
    spacing.set(_q1815("before"), "0")
    spacing.set(_q1815("after"), "0")

    def add_text(value):
        run = ET.SubElement(paragraph, _q1815("r"))
        rpr = ET.SubElement(run, _q1815("rPr"))
        fonts = ET.SubElement(rpr, _q1815("rFonts"))
        fonts.set(_q1815("ascii"), "Arial")
        fonts.set(_q1815("hAnsi"), "Arial")
        size = ET.SubElement(rpr, _q1815("sz"))
        size.set(_q1815("val"), "22")
        text = ET.SubElement(run, _q1815("t"))
        text.text = value

    add_text(("☒ " + left_text) if left_text else "")
    tab_run = ET.SubElement(paragraph, _q1815("r"))
    ET.SubElement(tab_run, _q1815("tab"))
    add_text(("☒ " + right_text) if right_text else "")


def create_letter(template_path, output_path, values, document_items, requests):
    template_path = Path(template_path)
    output_path = Path(output_path)
    if not template_path.is_file():
        raise RuntimeError("Die private Anschreiben-Vorlage fehlt.")
    if len(document_items) > 5:
        raise RuntimeError("Im Anschreiben können maximal fünf Unterlagen gleichzeitig aufgeführt werden.")

    request_labels = []
    for number in requests:
        number = int(number)
        label = REQUEST_LABELS_V1815.get(number, "")
        if number == 10:
            target = str(values.get("forward_to", "") or "").strip()
            label = "Weiterleitung an" + ((": " + target) if target else "")
        if label:
            request_labels.append(label)
    if len(request_labels) > 5:
        raise RuntimeError("Bitte höchstens fünf Optionen unter ‚Mit der Bitte um‘ auswählen.")

    recipient = values.get("recipient", "")
    person = values.get("contact_person", "")
    if person and not recipient:
        recipient, person = person, ""
    replacements = {
        "EMPFAENGER": recipient,
        "ANSPRECHPARTNER": person,
        "STRASSE": values.get("street", ""),
        "PLZORT": values.get("city", ""),
        "DATUM": values.get("date", ""),
        "BETREFF": values.get("subject", ""),
        "ANREDE": values.get("greeting", ""),
        "TEXT": values.get("body", ""),
        "WEITERLEITUNG": "",
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(template_path, "r") as source:
        xml = source.read("word/document.xml").decode("utf-8")
        for key, value in replacements.items():
            xml = xml.replace("{{" + key + "}}", _xml_value(value))
        root = ET.fromstring(xml.encode("utf-8"))
        body = root.find("w:body", NS)
        if body is None:
            raise RuntimeError("Die Anschreiben-Vorlage enthält keinen Word-Dokumentkörper.")

        rows = []
        for paragraph in body.findall("w:p", NS):
            names = [node.get(_q1815("val")) for node in paragraph.findall(".//w:name", NS)]
            if any(name == f"Kontrollkästchen{i}" for i in range(1, 6) for name in names):
                rows.append(paragraph)
        if len(rows) != 5:
            raise RuntimeError("Die Anschreiben-Vorlage konnte nicht sauber auf fünf Auswahlzeilen aufgelöst werden.")

        for index, paragraph in enumerate(rows):
            left = document_items[index] if index < len(document_items) else ""
            right = request_labels[index] if index < len(request_labels) else ""
            _set_stacked_row_v1815(paragraph, left, right)

        converted = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as target:
            for info in source.infolist():
                target.writestr(info, converted if info.filename == "word/document.xml" else source.read(info.filename))
    return output_path
'''
pattern = re.compile(r'def create_letter\(template_path, output_path, values, document_items, requests\):.*?\n\n__all__ =', re.S)
letter, count = pattern.subn(new_create + '\n\n__all__ =', letter, count=1)
if count != 1:
    raise RuntimeError(f"1.8.15: create_letter Ersatz erwartet 1x, gefunden {count}x")
letter = letter.replace('MODULE_VERSION = "1.8.14"', 'MODULE_VERSION = "1.8.15"', 1)
if 'REQUEST_LABELS_V1815' not in letter or '_set_stacked_row_v1815' not in letter:
    raise RuntimeError("1.8.15: neue Anschreiben-Ausrichtung wurde nicht eingebaut.")
LETTER.write_text(letter, encoding="utf-8")

post = POST.read_text(encoding="utf-8")
post = post.replace("update_1814_install.log", "update_1815_install.log")
post = post.replace("update_1814_error.txt", "update_1815_error.txt")
post = replace_once(post, 'APP_VERSION = "1.8.14"', 'APP_VERSION = "1.8.15"', "post version")
post = post.replace("OK: Update 1.8.14 erfolgreich installiert.", "OK: Update 1.8.15 erfolgreich installiert.")
POST.write_text(post, encoding="utf-8")

for path in (APP, POST, CORR, LETTER):
    py_compile.compile(str(path), doraise=True)

if 'APP_VERSION = "1.8.15"' not in APP.read_text(encoding="utf-8"):
    raise RuntimeError("1.8.15: App-Version wurde nicht gesetzt.")
if 'subject_var = tk.StringVar(value="Unterlagen")' not in CORR.read_text(encoding="utf-8"):
    raise RuntimeError("1.8.15: Betreff wurde nicht vereinfacht.")
if '☒ ' not in LETTER.read_text(encoding="utf-8"):
    raise RuntimeError("1.8.15: gestapelte Auswahl wurde nicht aktiviert.")

print("OK: Projektzentrale 1.8.15 Anschreiben-Layout gepatcht und geprüft.")
