from pathlib import Path
import py_compile
import sys

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
CORR = ROOT / "correspondence_v1814.py"
if not CORR.exists():
    raise RuntimeError("1.8.14: correspondence_v1814.py fehlt")


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"1.8.14 correspondence: {label} erwartet 1x, gefunden {count}x")
    return text.replace(old, new, 1)


text = CORR.read_text(encoding="utf-8")
text = replace_once(
    text,
    "from xml.sax.saxutils import escape\n",
    "from xml.sax.saxutils import escape\n\n"
    "from contacts_v1814 import ensure_contact_schema, greeting_for, open_contact_picker, recipient_lines\n"
    "from letter_template_v1814 import choose_private_template, get_private_template, create_letter as create_private_letter\n",
    "helper imports",
)
text = replace_once(
    text,
    "# PZ_CORRESPONDENCE_V1814: Projektbezogenes Word-Anschreiben aus der\n# Engbers-Vorlage, mit Empfaenger, Betreff, Uebergabeliste und Bitte-um-Auswahl.\n",
    "# PZ_CORRESPONDENCE_V1814: Projektbezogenes Word-Anschreiben aus der\n# Engbers-Vorlage, mit Empfaenger, Betreff, Uebergabeliste und Bitte-um-Auswahl.\n"
    "# PZ_CORRESPONDENCE_PRIVATE_TEMPLATE_V1814: Briefkopf bleibt als private lokale Vorlage auf dem PC.\n"
    "# PZ_CONTACT_PICKER_V1814: Empfaenger kann direkt aus dem lokalen Adressbuch uebernommen werden.\n",
    "feature markers",
)
old_template = '''    base_dir = Path(__file__).resolve().parent
    template_path = base_dir / TEMPLATE_NAME
    if not template_path.is_file():
        messagebox.showerror("Anschreiben", "Die Engbers-Anschreiben-Vorlage wurde nicht gefunden.", parent=app)
        return
'''
new_template = '''    ensure_contact_schema(db_path)
    template_path = get_private_template(app, prompt=True)
    if not template_path:
        return
'''
text = replace_once(text, old_template, new_template, "private template selection")
old_vars = '''    recipient_var = tk.StringVar(value=str(project["client"] or ""))
    street_var = tk.StringVar()
    city_var = tk.StringVar()
    date_var = tk.StringVar(value=datetime.date.today().strftime("%d.%m.%Y"))
    subject_var = tk.StringVar(value=f"Unterlagen – {project['number']} · {project['title']}")
    greeting_var = tk.StringVar(value="Sehr geehrte Damen und Herren,")
    forward_var = tk.StringVar()
    custom_var = tk.StringVar()

    form = tk.Frame(inner, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
'''
new_vars = '''    recipient_var = tk.StringVar(value=str(project["client"] or ""))
    contact_person_var = tk.StringVar()
    street_var = tk.StringVar()
    city_var = tk.StringVar()
    date_var = tk.StringVar(value=datetime.date.today().strftime("%d.%m.%Y"))
    subject_var = tk.StringVar(value=f"Unterlagen – {project['number']} · {project['title']}")
    greeting_var = tk.StringVar(value="Sehr geehrte Damen und Herren,")
    forward_var = tk.StringVar()
    custom_var = tk.StringVar()

    contact_tools = tk.Frame(inner, bg=BG)
    contact_tools.pack(fill="x", padx=6, pady=(0, 10))

    def take_contact(row):
        recipient, person = recipient_lines(row)
        recipient_var.set(recipient)
        contact_person_var.set(person)
        street_var.set(str(row["street"] or ""))
        city_var.set(" ".join(x for x in (str(row["postal_code"] or "").strip(), str(row["city"] or "").strip()) if x))
        greeting_var.set(greeting_for(row))

    tk.Button(contact_tools, text="EMPFÄNGER AUS ADRESSBUCH",
              command=lambda: open_contact_picker(window, db_path, int(project["id"]), take_contact, True),
              bg=ACCENT, fg="white", bd=0, padx=14, pady=8,
              font=("Segoe UI Semibold", 9)).pack(side="left")
    tk.Button(contact_tools, text="ADRESSBUCH",
              command=lambda: open_contact_picker(window, db_path, int(project["id"]), None, False),
              bg=DARK, fg="white", bd=0, padx=14, pady=8).pack(side="left", padx=(8, 0))
    tk.Button(contact_tools, text="VORLAGE ÄNDERN", command=lambda: choose_private_template(window),
              bg=DARK, fg="white", bd=0, padx=14, pady=8).pack(side="right")

    form = tk.Frame(inner, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
'''
text = replace_once(text, old_vars, new_vars, "contact tools")
text = replace_once(
    text,
    '''    fields = (
        ("Empfänger / Firma", recipient_var),
        ("Straße", street_var),
''',
    '''    fields = (
        ("Empfänger / Firma", recipient_var),
        ("Ansprechpartner", contact_person_var),
        ("Straße", street_var),
''',
    "contact person field",
)
text = replace_once(
    text,
    '            "recipient": recipient,\n            "street": street_var.get().strip(),\n',
    '            "recipient": recipient,\n            "contact_person": contact_person_var.get().strip(),\n            "street": street_var.get().strip(),\n',
    "contact person value",
)
text = replace_once(text, "            create_letter(template_path, output, values, items, request_numbers)\n", "            create_private_letter(template_path, output, values, items, request_numbers)\n", "private letter generator")
text = text.replace(
    "Das Word-Dokument wird unter 08_Kommunikation\\\\Anschreiben gespeichert und in der Kommunikationsakte eingetragen.",
    "Das Word-Dokument wird unter 08_Kommunikation\\\\Anschreiben gespeichert. Die Briefkopfvorlage bleibt privat auf diesem PC.",
)
CORR.write_text(text, encoding="utf-8")
py_compile.compile(str(CORR), doraise=True)
for marker in ("PZ_CORRESPONDENCE_PRIVATE_TEMPLATE_V1814", "PZ_CONTACT_PICKER_V1814", "EMPFÄNGER AUS ADRESSBUCH", "create_private_letter"):
    if marker not in text:
        raise RuntimeError("1.8.14 correspondence: Funktionspruefung fehlt: " + marker)
print("OK: correspondence_v1814 um private Vorlage und Adressbuch erweitert")
