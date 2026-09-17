"""Private lokale Word-Briefkopfvorlage fuer Projektzentrale 1.8.14."""
from __future__ import annotations

import os
import re
import shutil
import tkinter as tk
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from tkinter import filedialog, messagebox
from xml.sax.saxutils import escape

MODULE_VERSION = "1.8.14"
# PZ_CORRESPONDENCE_PRIVATE_TEMPLATE_V1814: Der persoenliche Briefkopf bleibt lokal auf dem PC.

APPDATA = Path(os.environ.get("APPDATA", str(Path.home()))) / "Engbers Projektzentrale"
TEMPLATE_DIR = APPDATA / "templates"
PRIVATE_TEMPLATE = TEMPLATE_DIR / "anschreiben_template_private.docx"
SOURCE_INFO = TEMPLATE_DIR / "anschreiben_template_source.txt"

WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": WNS}
ET.register_namespace("w", WNS)


def _paragraph_text(paragraph):
    return "".join(t.text or "" for t in paragraph.findall(".//w:t", NS))


def _set_first_text(paragraph, value, clear_rest=False):
    texts = paragraph.findall(".//w:t", NS)
    if not texts:
        return False
    texts[0].text = value
    if clear_rest:
        for t in texts[1:]:
            t.text = ""
    return True


def _replace_text_node(paragraph, old, new):
    for t in paragraph.findall(".//w:t", NS):
        if (t.text or "") == old:
            t.text = new
            return True
    return False


def validate_private_template(path):
    with zipfile.ZipFile(path, "r") as z:
        text = z.read("word/document.xml").decode("utf-8")
    for marker in (
        "{{EMPFAENGER}}", "{{DATUM}}", "{{ANSPRECHPARTNER}}", "{{STRASSE}}", "{{PLZORT}}",
        "{{BETREFF}}", "{{ANREDE}}", "{{TEXT}}", "{{ITEM1}}", "{{ITEM5}}", "{{WEITERLEITUNG}}",
    ):
        if marker not in text:
            raise RuntimeError("Vorlagenprüfung fehlgeschlagen: " + marker)
    for number in range(1, 15):
        if f"Kontrollkästchen{number}" not in text:
            raise RuntimeError(f"Vorlagenprüfung fehlgeschlagen: Kontrollkästchen {number}")
    return True


def convert_original_template(source_path, target_path=PRIVATE_TEMPLATE):
    """Erzeugt aus dem vorhandenen Engbers-Musteranschreiben eine private dynamische Arbeitskopie."""
    source_path = Path(source_path)
    target_path = Path(target_path)
    if source_path.suffix.lower() != ".docx" or not source_path.is_file():
        raise RuntimeError("Bitte eine vorhandene Word-Datei (.docx) auswählen.")

    with zipfile.ZipFile(source_path, "r") as source:
        try:
            raw = source.read("word/document.xml")
        except KeyError as exc:
            raise RuntimeError("Die ausgewählte Datei ist keine gültige Word-Vorlage.") from exc
        xml_text = raw.decode("utf-8")
        if all(x in xml_text for x in ("{{EMPFAENGER}}", "{{DATUM}}", "{{STRASSE}}", "{{BETREFF}}", "{{ITEM1}}")):
            TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)
            validate_private_template(target_path)
            return target_path

        root = ET.fromstring(raw)
        paragraphs = root.findall(".//w:p", NS)
        found = {"recipient": False, "street": False, "city": False, "subject": False, "greeting": False, "items": 0, "forward": False}
        greeting_para = None

        for idx, p in enumerate(paragraphs):
            text = _paragraph_text(p)
            if text.startswith("Mustermann"):
                texts = p.findall(".//w:t", NS)
                if texts:
                    texts[0].text = "{{EMPFAENGER}}"
                    found["recipient"] = True
                    date_started = False
                    for t in texts[1:]:
                        val = t.text or ""
                        if not date_started and re.fullmatch(r"20", val):
                            t.text = "{{DATUM}}"
                            date_started = True
                        elif date_started and val.strip():
                            t.text = ""
            elif text.strip().casefold() in ("musterstraße", "musterstrasse"):
                _set_first_text(p, "{{ANSPRECHPARTNER}}", True)
                if idx + 1 < len(paragraphs) and not _paragraph_text(paragraphs[idx + 1]).strip():
                    blank = paragraphs[idx + 1]
                    r = ET.SubElement(blank, f"{{{WNS}}}r")
                    t = ET.SubElement(r, f"{{{WNS}}}t")
                    t.text = "{{STRASSE}}"
                    found["street"] = True
            elif "Musterstadt" in text:
                _set_first_text(p, "{{PLZORT}}", True)
                found["city"] = True
            elif text.startswith("Betreff:"):
                for t in p.findall(".//w:t", NS):
                    if "Unterlagen" in (t.text or ""):
                        t.text = "{{BETREFF}}"
                        found["subject"] = True
                        break
            elif "Ausschreibung" in text and "Kenntnisnahme" in text:
                if _replace_text_node(p, " Ausschreibung", " {{ITEM1}}"):
                    found["items"] += 1
            elif "Zeichnungen" in text and "Prüfung" in text:
                if _replace_text_node(p, " Zeichnungen", " {{ITEM2}}"):
                    found["items"] += 1
            elif "Schlussrechnung" in text and "Genehmigung" in text:
                if _replace_text_node(p, " Schlussrechnung", " {{ITEM3}}"):
                    found["items"] += 1
            elif "Angebote" in text and "Erledigung" in text:
                if _replace_text_node(p, " Angebote", " {{ITEM4}}"):
                    found["items"] += 1
            elif "Weiterleitung" in text and "Unterlagen" in text:
                if _replace_text_node(p, "Unterlagen", "{{ITEM5}}"):
                    found["items"] += 1
                for name in p.findall(".//w:name", NS):
                    if not (name.get(f"{{{WNS}}}val") or "").strip():
                        name.set(f"{{{WNS}}}val", "Kontrollkästchen5")
                        break
                for t in p.findall(".//w:t", NS):
                    if "________________" in (t.text or ""):
                        t.text = "{{WEITERLEITUNG}}"
                        found["forward"] = True
                        break
            elif text.startswith("Sehr geehrte"):
                _set_first_text(p, "{{ANREDE}}", True)
                found["greeting"] = True
                greeting_para = p

        if not all((found["recipient"], found["street"], found["city"], found["subject"], found["greeting"], found["items"] >= 5, found["forward"])):
            raise RuntimeError("Diese Word-Datei entspricht nicht dem erwarteten Engbers-Musteranschreiben. Bitte die bisher verwendete Musteranschreiben.docx auswählen.")

        if greeting_para is not None:
            parent = None
            for candidate in root.iter():
                if greeting_para in list(candidate):
                    parent = candidate
                    break
            if parent is not None:
                idx = list(parent).index(greeting_para)
                p = ET.Element(f"{{{WNS}}}p")
                r = ET.SubElement(p, f"{{{WNS}}}r")
                t = ET.SubElement(r, f"{{{WNS}}}t")
                t.text = "{{TEXT}}"
                parent.insert(idx + 1, p)

        converted = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(target_path, "w", zipfile.ZIP_DEFLATED) as target:
            for info in source.infolist():
                target.writestr(info, converted if info.filename == "word/document.xml" else source.read(info.filename))

    validate_private_template(target_path)
    SOURCE_INFO.write_text(str(source_path), encoding="utf-8")
    return target_path


def choose_private_template(parent):
    source = filedialog.askopenfilename(
        title="Engbers-Musteranschreiben auswählen",
        filetypes=[("Word-Dokument", "*.docx")],
        parent=parent,
    )
    if not source:
        return None
    try:
        path = convert_original_template(source, PRIVATE_TEMPLATE)
    except Exception as exc:
        messagebox.showerror("Anschreiben-Vorlage", str(exc), parent=parent)
        return None
    messagebox.showinfo(
        "Anschreiben-Vorlage",
        "Die Vorlage wurde als private lokale Arbeitskopie eingerichtet.\n\nDie Originaldatei bleibt unverändert.",
        parent=parent,
    )
    return path


def get_private_template(parent, prompt=True):
    try:
        if PRIVATE_TEMPLATE.is_file():
            validate_private_template(PRIVATE_TEMPLATE)
            return PRIVATE_TEMPLATE
    except Exception:
        pass
    if not prompt:
        return None
    messagebox.showinfo(
        "Anschreiben-Vorlage",
        "Beim ersten Mal wählst du einmal dein vorhandenes Musteranschreiben aus.\n\nDer Briefkopf bleibt ausschließlich lokal auf diesem PC.",
        parent=parent,
    )
    return choose_private_template(parent)


def _set_checkbox(xml, number, checked):
    pattern = re.compile(
        r'(<w:ffData>.*?<w:name w:val="Kontrollkästchen' + re.escape(str(number))
        + r'"\s*/>.*?<w:checkBox>.*?<w:default w:val=")[01]("\s*/>)',
        re.S,
    )
    xml, count = pattern.subn(r"\g<1>" + ("1" if checked else "0") + r"\2", xml, count=1)
    if count != 1:
        raise RuntimeError(f"Kontrollkästchen {number} wurde in der Anschreiben-Vorlage nicht gefunden.")
    return xml


def _xml_value(value):
    return escape(str(value or "")).replace("\n", "</w:t><w:br/><w:t>")


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
                    xml = xml.replace("{{" + key + "}}", _xml_value(value))
                for number in range(1, 6):
                    xml = _set_checkbox(xml, number, number <= len(document_items))
                requested_numbers = {int(number) for number in requests}
                for number in range(6, 15):
                    xml = _set_checkbox(xml, number, number in requested_numbers)
                data = xml.encode("utf-8")
            target.writestr(info, data)
    return output_path


__all__ = ["choose_private_template", "get_private_template", "create_letter", "convert_original_template", "validate_private_template"]
