from pathlib import Path
import py_compile
import sys

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
APP = ROOT / "app.py"
POST = ROOT / "post_update.py"
LETTER = ROOT / "letter_template_v1814.py"

for path in (APP, POST, LETTER):
    if not path.exists():
        raise RuntimeError(f"1.8.17: Update-Datei fehlt: {path.name}")

def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"1.8.17: Marker {label} erwartet 1x, gefunden {count}x")
    return text.replace(old, new, 1)

app = APP.read_text(encoding="utf-8")
app = replace_once(app, 'APP_VERSION = "1.8.16"', 'APP_VERSION = "1.8.17"', "APP_VERSION")
APP.write_text(app, encoding="utf-8")

letter = LETTER.read_text(encoding="utf-8")
letter = letter.replace('MODULE_VERSION = "1.8.16"', 'MODULE_VERSION = "1.8.17"', 1)
letter = replace_once(
    letter,
    '            row.append(_cell1816(4887, "Weiterleitung an :" + line, box=left_no in request_set, gridspan=2))\n',
    '            row.append(_cell1816(4887, "Weiterleitung an: " + line, box=left_no in request_set, gridspan=2))\n',
    "Weiterleitung Typografie",
)

helper = r'''
def _blank_paragraph_v1817():
    paragraph = ET.Element(_q1816("p"))
    ppr = ET.SubElement(paragraph, _q1816("pPr"))
    spacing = ET.SubElement(ppr, _q1816("spacing"))
    spacing.set(_q1816("before"), "0")
    spacing.set(_q1816("after"), "0")
    spacing.set(_q1816("line"), "240")
    spacing.set(_q1816("lineRule"), "auto")
    return paragraph


def _body_text_v1817(node):
    return "".join(t.text or "" for t in node.findall(".//w:t", NS))


def _is_blank_paragraph_v1817(node):
    return node.tag == _q1816("p") and not _body_text_v1817(node).strip()


def _replace_between_v1817(body, start_index, end_index, replacement):
    children = list(body)
    for child in children[start_index + 1:end_index]:
        body.remove(child)
    insert_at = start_index + 1
    for child in replacement:
        body.insert(insert_at, child)
        insert_at += 1


def _compact_letter_spacing_v1817(body):
    """Dezenter Feinschliff: weniger Leerraum, Originalcharakter bleibt erhalten."""
    def locate():
        children = list(body)
        subject = next(
            (i for i, node in enumerate(children)
             if node.tag == _q1816("p") and _body_text_v1817(node).strip().startswith("Betreff:")),
            None,
        )
        table = next((i for i, node in enumerate(children) if node.tag == _q1816("tbl")), None)
        closing = next(
            (i for i, node in enumerate(children)
             if node.tag == _q1816("p") and _body_text_v1817(node).strip().startswith("Mit freundlichen")),
            None,
        )
        signature = next(
            (i for i, node in enumerate(children)
             if node.tag == _q1816("p") and _body_text_v1817(node).strip().startswith("___")),
            None,
        )
        return subject, table, closing, signature

    subject, table, closing, signature = locate()
    if subject is not None and table is not None and table > subject:
        _replace_between_v1817(body, subject, table, [_blank_paragraph_v1817()])

    subject, table, closing, signature = locate()
    if table is not None and closing is not None and closing > table:
        children = list(body)
        middle = children[table + 1:closing]
        compact = [_blank_paragraph_v1817()]
        pending_blank = False
        for node in middle:
            if _is_blank_paragraph_v1817(node):
                pending_blank = True
                continue
            if pending_blank and compact and not _is_blank_paragraph_v1817(compact[-1]):
                compact.append(_blank_paragraph_v1817())
            compact.append(node)
            pending_blank = False
        if not compact or not _is_blank_paragraph_v1817(compact[-1]):
            compact.append(_blank_paragraph_v1817())
        _replace_between_v1817(body, table, closing, compact)

    subject, table, closing, signature = locate()
    if closing is not None and signature is not None and signature > closing:
        _replace_between_v1817(
            body,
            closing,
            signature,
            [_blank_paragraph_v1817(), _blank_paragraph_v1817()],
        )
'''
letter = letter.rstrip() + "\n\n" + helper + "\n"

call_old = '        body.insert(start, _selection_table_v1816(document_items, requests, values.get("forward_to", "")))\n\n        converted = ET.tostring(root, encoding="utf-8", xml_declaration=True)\n'
call_new = '        body.insert(start, _selection_table_v1816(document_items, requests, values.get("forward_to", "")))\n        _compact_letter_spacing_v1817(body)\n\n        converted = ET.tostring(root, encoding="utf-8", xml_declaration=True)\n'
letter = replace_once(letter, call_old, call_new, "Spacing-Aufruf")
LETTER.write_text(letter, encoding="utf-8")

post = POST.read_text(encoding="utf-8")
post = post.replace("update_1816_install.log", "update_1817_install.log")
post = post.replace("update_1816_error.txt", "update_1817_error.txt")
post = replace_once(post, 'APP_VERSION = "1.8.16"', 'APP_VERSION = "1.8.17"', "post version")
post = post.replace("OK: Update 1.8.16 erfolgreich installiert.", "OK: Update 1.8.17 erfolgreich installiert.")
POST.write_text(post, encoding="utf-8")

for path in (APP, POST, LETTER):
    py_compile.compile(str(path), doraise=True)

letter_text = LETTER.read_text(encoding="utf-8")
if 'APP_VERSION = "1.8.17"' not in APP.read_text(encoding="utf-8"):
    raise RuntimeError("1.8.17: App-Version wurde nicht gesetzt.")
for marker in ("_compact_letter_spacing_v1817", "_blank_paragraph_v1817", "Weiterleitung an: "):
    if marker not in letter_text:
        raise RuntimeError("1.8.17: Feinschliff-Prüfung fehlt: " + marker)

print("OK: Projektzentrale 1.8.17 Anschreiben-Feinschliff gepatcht und geprüft.")
