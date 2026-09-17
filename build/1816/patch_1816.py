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
        raise RuntimeError(f"1.8.16: Update-Datei fehlt: {path.name}")


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"1.8.16: Marker {label} erwartet 1x, gefunden {count}x")
    return text.replace(old, new, 1)


app = APP.read_text(encoding="utf-8")
app = replace_once(app, 'APP_VERSION = "1.8.15"', 'APP_VERSION = "1.8.16"', "APP_VERSION")
APP.write_text(app, encoding="utf-8")

corr = CORR.read_text(encoding="utf-8")
corr = corr.replace('MODULE_VERSION = "1.8.14"', 'MODULE_VERSION = "1.8.16"', 1)
limit_block = '''        request_numbers = [number for number, variable in request_vars.items() if variable.get()]\n        if len(request_numbers) > 5:\n            messagebox.showwarning("Anschreiben", "Bitte höchstens fünf Optionen unter ‚Mit der Bitte um‘ auswählen. So bleibt das Anschreiben sauber untereinander ausgerichtet.", parent=window)\n            return\n'''
if limit_block in corr:
    corr = corr.replace(limit_block, '        request_numbers = [number for number, variable in request_vars.items() if variable.get()]\n', 1)
CORR.write_text(corr, encoding="utf-8")

letter = LETTER.read_text(encoding="utf-8")
letter = letter.replace('MODULE_VERSION = "1.8.15"', 'MODULE_VERSION = "1.8.16"', 1)

new_create = r'''DEFAULT_DOCUMENT_ROWS_V1816 = (
    "Ausschreibung",
    "Zeichnungen",
    "Schlussrechnung",
    "Angebote",
    "Unterlagen",
)

REQUEST_GRID_V1816 = (
    (6, "Kenntnisnahme", 11, "Unterschrift"),
    (7, "Prüfung", 12, "Rücksprache"),
    (8, "Genehmigung", 13, "Rücksendung"),
    (9, "Erledigung", 14, "Angebot"),
    (10, "Weiterleitung an", None, None),
)


def _q1816(tag):
    return f"{{{WNS}}}{tag}"


def _norm1816(value):
    return str(value or "").strip().casefold()


def _document_rows_v1816(document_items):
    """Behält die fünf festen Originalzeilen und setzt Sonderauswahlen in freie Zeilen."""
    selected = [str(x or "").strip() for x in document_items if str(x or "").strip()][:5]
    display = list(DEFAULT_DOCUMENT_ROWS_V1816)
    checked = [False] * 5
    used = set()

    aliases = {
        "angebot": "angebote",
        "angebote": "angebote",
    }

    # Zuerst Originalbegriffe an ihrer gewohnten Stelle markieren.
    consumed = set()
    for index, item in enumerate(selected):
        key = aliases.get(_norm1816(item), _norm1816(item))
        for row, default in enumerate(display):
            if row in used:
                continue
            if _norm1816(default) == key:
                display[row] = item if key != "angebote" else "Angebote"
                checked[row] = True
                used.add(row)
                consumed.add(index)
                break

    # Neue Begriffe kommen in die ersten noch freien Originalzeilen.
    for index, item in enumerate(selected):
        if index in consumed:
            continue
        for row in range(5):
            if row not in used:
                display[row] = item
                checked[row] = True
                used.add(row)
                break

    return display, checked


def _run1816(text, bold=False, font="Arial", size=22):
    run = ET.Element(_q1816("r"))
    rpr = ET.SubElement(run, _q1816("rPr"))
    fonts = ET.SubElement(rpr, _q1816("rFonts"))
    fonts.set(_q1816("ascii"), font)
    fonts.set(_q1816("hAnsi"), font)
    fonts.set(_q1816("cs"), font)
    sz = ET.SubElement(rpr, _q1816("sz"))
    sz.set(_q1816("val"), str(size))
    szcs = ET.SubElement(rpr, _q1816("szCs"))
    szcs.set(_q1816("val"), str(size))
    if bold:
        ET.SubElement(rpr, _q1816("b"))
    node = ET.SubElement(run, _q1816("t"))
    node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    node.text = str(text or "")
    return run


def _paragraph1816(text="", bold=False, box=None):
    paragraph = ET.Element(_q1816("p"))
    ppr = ET.SubElement(paragraph, _q1816("pPr"))
    spacing = ET.SubElement(ppr, _q1816("spacing"))
    spacing.set(_q1816("before"), "0")
    spacing.set(_q1816("after"), "0")
    spacing.set(_q1816("line"), "276")
    spacing.set(_q1816("lineRule"), "auto")
    if box is not None:
        paragraph.append(_run1816(("☒" if box else "☐") + " ", font="Segoe UI Symbol", size=22))
        paragraph.append(_run1816(text, size=22))
    else:
        paragraph.append(_run1816(text, bold=bold, size=22))
    return paragraph


def _cell1816(width, text="", bold=False, box=None, gridspan=None):
    cell = ET.Element(_q1816("tc"))
    tcpr = ET.SubElement(cell, _q1816("tcPr"))
    tcw = ET.SubElement(tcpr, _q1816("tcW"))
    tcw.set(_q1816("w"), str(width))
    tcw.set(_q1816("type"), "dxa")
    if gridspan:
        span = ET.SubElement(tcpr, _q1816("gridSpan"))
        span.set(_q1816("val"), str(gridspan))
    margins = ET.SubElement(tcpr, _q1816("tcMar"))
    for side, value in (("top", "60"), ("left", "0"), ("bottom", "60"), ("right", "100")):
        node = ET.SubElement(margins, _q1816(side))
        node.set(_q1816("w"), value)
        node.set(_q1816("type"), "dxa")
    cell.append(_paragraph1816(text, bold=bold, box=box))
    return cell


def _row_height1816(row, value="520"):
    trpr = ET.SubElement(row, _q1816("trPr"))
    height = ET.SubElement(trpr, _q1816("trHeight"))
    height.set(_q1816("val"), value)
    height.set(_q1816("hRule"), "atLeast")


def _selection_table_v1816(document_items, requests, forward_to=""):
    documents, doc_checks = _document_rows_v1816(document_items)
    request_set = {int(x) for x in requests}

    table = ET.Element(_q1816("tbl"))
    tblpr = ET.SubElement(table, _q1816("tblPr"))
    tblw = ET.SubElement(tblpr, _q1816("tblW"))
    tblw.set(_q1816("w"), "8787")
    tblw.set(_q1816("type"), "dxa")
    layout = ET.SubElement(tblpr, _q1816("tblLayout"))
    layout.set(_q1816("type"), "fixed")
    align = ET.SubElement(tblpr, _q1816("jc"))
    align.set(_q1816("val"), "left")
    borders = ET.SubElement(tblpr, _q1816("tblBorders"))
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        border = ET.SubElement(borders, _q1816(side))
        border.set(_q1816("val"), "nil")

    grid = ET.SubElement(table, _q1816("tblGrid"))
    for width in (3900, 2450, 2437):
        col = ET.SubElement(grid, _q1816("gridCol"))
        col.set(_q1816("w"), str(width))

    header = ET.SubElement(table, _q1816("tr"))
    _row_height1816(header)
    header.append(_cell1816(3900, "Wir überreichen Ihnen:", bold=True))
    header.append(_cell1816(4887, "Mit der Bitte um:", bold=True, gridspan=2))

    for index, (left_no, left_label, right_no, right_label) in enumerate(REQUEST_GRID_V1816):
        row = ET.SubElement(table, _q1816("tr"))
        _row_height1816(row)
        row.append(_cell1816(3900, documents[index], box=doc_checks[index]))
        if index < 4:
            row.append(_cell1816(2450, left_label, box=left_no in request_set))
            row.append(_cell1816(2437, right_label, box=right_no in request_set))
        else:
            target = str(forward_to or "").strip()
            line = target if target else "__________________"
            row.append(_cell1816(4887, "Weiterleitung an :" + line, box=left_no in request_set, gridspan=2))

    return table


def create_letter(template_path, output_path, values, document_items, requests):
    template_path = Path(template_path)
    output_path = Path(output_path)
    if not template_path.is_file():
        raise RuntimeError("Die private Anschreiben-Vorlage fehlt.")
    if len(document_items) > 5:
        raise RuntimeError("Im Anschreiben können maximal fünf Unterlagen gleichzeitig aufgeführt werden.")

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

        children = list(body)
        start = None
        end = None
        for index, child in enumerate(children):
            if child.tag != _q1816("p"):
                continue
            text = "".join(node.text or "" for node in child.findall(".//w:t", NS))
            if "Wir überreichen Ihnen:" in text and "Mit der Bitte um:" in text:
                start = index
            names = [node.get(_q1816("val")) for node in child.findall(".//w:name", NS)]
            if "Kontrollkästchen5" in names:
                end = index

        if start is None or end is None or end < start:
            raise RuntimeError("Der Auswahlbereich des Engbers-Anschreibens konnte nicht gefunden werden.")

        for child in children[start:end + 1]:
            body.remove(child)
        body.insert(start, _selection_table_v1816(document_items, requests, values.get("forward_to", "")))

        converted = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as target:
            for info in source.infolist():
                target.writestr(info, converted if info.filename == "word/document.xml" else source.read(info.filename))
    return output_path
'''

pattern = re.compile(r'(?:REQUEST_LABELS_V1815\s*=.*?|DEFAULT_DOCUMENT_ROWS_V1816\s*=.*?)\n\n__all__ =', re.S)
letter, count = pattern.subn(new_create + '\n\n__all__ =', letter, count=1)
if count != 1:
    raise RuntimeError(f"1.8.16: Anschreiben-Generator Ersatz erwartet 1x, gefunden {count}x")
LETTER.write_text(letter, encoding="utf-8")

post = POST.read_text(encoding="utf-8")
post = post.replace("update_1815_install.log", "update_1816_install.log")
post = post.replace("update_1815_error.txt", "update_1816_error.txt")
post = replace_once(post, 'APP_VERSION = "1.8.15"', 'APP_VERSION = "1.8.16"', "post version")
post = post.replace("OK: Update 1.8.15 erfolgreich installiert.", "OK: Update 1.8.16 erfolgreich installiert.")
POST.write_text(post, encoding="utf-8")

for path in (APP, POST, CORR, LETTER):
    py_compile.compile(str(path), doraise=True)

letter_text = LETTER.read_text(encoding="utf-8")
if 'APP_VERSION = "1.8.16"' not in APP.read_text(encoding="utf-8"):
    raise RuntimeError("1.8.16: App-Version wurde nicht gesetzt.")
for marker in ("DEFAULT_DOCUMENT_ROWS_V1816", "REQUEST_GRID_V1816", "_selection_table_v1816", "Segoe UI Symbol"):
    if marker not in letter_text:
        raise RuntimeError("1.8.16: Layout-Funktionsprüfung fehlt: " + marker)

print("OK: Projektzentrale 1.8.16 festes Anschreiben-Raster gepatcht und geprüft.")
