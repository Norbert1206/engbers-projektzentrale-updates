from pathlib import Path
import py_compile
import sys

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
APP = ROOT / "app.py"
POST = ROOT / "post_update.py"
CORR = ROOT / "correspondence_v1814.py"
AI = ROOT / "ai_writer_v1818.py"

for path in (APP, POST, CORR, AI):
    if not path.exists():
        raise RuntimeError(f"1.8.18: Update-Datei fehlt: {path.name}")

def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"1.8.18: Marker {label} erwartet 1x, gefunden {count}x")
    return text.replace(old, new, 1)

app = APP.read_text(encoding="utf-8")
app = replace_once(app, 'APP_VERSION = "1.8.17"', 'APP_VERSION = "1.8.18"', "APP_VERSION")
APP.write_text(app, encoding="utf-8")

corr = CORR.read_text(encoding="utf-8")
corr = corr.replace('MODULE_VERSION = "1.8.16"', 'MODULE_VERSION = "1.8.18"', 1)
corr = replace_once(corr, "import sqlite3\n", "import sqlite3\nimport threading\n", "threading import")

old_note = '''    note = tk.Text(note_box, height=3, wrap="word", font=("Segoe UI", 9), bd=0,
                   highlightthickness=1, highlightbackground=LINE)
    note.pack(fill="x", padx=14, pady=(0, 12))
'''
new_note = '''    note = tk.Text(note_box, height=5, wrap="word", font=("Segoe UI", 9), bd=0,
                   highlightthickness=1, highlightbackground=LINE)
    note.pack(fill="x", padx=14, pady=(0, 7))

    ai_bar = tk.Frame(note_box, bg=PANEL)
    ai_bar.pack(fill="x", padx=12, pady=(0, 4))
    for col in range(5):
        ai_bar.columnconfigure(col, weight=1)

    ai_status = tk.Label(
        note_box,
        text="Stichpunkte eingeben und KI-Stil wählen. Übertragen werden nur Begleittext und fachlicher Auswahlkontext – keine Adressdaten.",
        bg=PANEL, fg=MUTED, font=("Segoe UI", 8), justify="left", wraplength=760,
    )
    ai_status.pack(anchor="w", padx=14, pady=(0, 10))

    ai_buttons = []

    def _selected_context():
        items = [label for label, variable in document_vars.items() if variable.get()]
        custom = custom_var.get().strip()
        if custom:
            items.append(custom)
        reqs = [label for label, number in REQUEST_OPTIONS if request_vars[number].get()]
        return items[:5], reqs

    def _set_ai_busy(busy, message=None):
        state = "disabled" if busy else "normal"
        for button in ai_buttons:
            try:
                button.configure(state=state)
            except Exception:
                pass
        if message is not None:
            ai_status.configure(text=message)

    def _configure_ai():
        try:
            from ai_writer_v1818 import configure_api_key
            configure_api_key(window)
        except Exception as exc:
            messagebox.showerror("KI einrichten", str(exc), parent=window)

    def _run_ai(mode):
        raw = note.get("1.0", "end").strip()
        if not raw:
            messagebox.showwarning("KI formulieren", "Bitte zuerst Stichpunkte oder einen Text in das Feld ‚Optionaler Begleittext‘ eingeben.", parent=window)
            return
        try:
            from ai_writer_v1818 import ensure_api_key, formulate_letter_text
            api_key = ensure_api_key(window)
        except Exception as exc:
            messagebox.showerror("KI formulieren", str(exc), parent=window)
            return
        if not api_key:
            return
        docs, reqs = _selected_context()
        _set_ai_busy(True, "KI formuliert …")

        def worker():
            try:
                result = formulate_letter_text(api_key, raw, mode=mode, document_items=docs, requests=reqs)
                error = None
            except Exception as exc:
                result = None
                error = str(exc)

            def finish():
                if not window.winfo_exists():
                    return
                _set_ai_busy(False)
                if error:
                    ai_status.configure(text="KI-Anfrage fehlgeschlagen.")
                    messagebox.showerror("KI formulieren", error, parent=window)
                    return
                note.delete("1.0", "end")
                note.insert("1.0", result)
                ai_status.configure(text="KI-Text übernommen. Bitte kurz prüfen oder direkt weiterbearbeiten.")

            try:
                window.after(0, finish)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    for col, (label, mode) in enumerate((
        ("KI: KURZ", "kurz"),
        ("KI: FREUNDLICH", "freundlich"),
        ("KI: FÖRMLICH", "foermlich"),
        ("TEXT VERBESSERN", "verbessern"),
    )):
        button = tk.Button(
            ai_bar, text=label, command=lambda m=mode: _run_ai(m),
            bg="#e7e3d9", fg=INK, activebackground="#d9d3c6",
            bd=0, padx=5, pady=6, font=("Segoe UI Semibold", 8), cursor="hand2",
        )
        button.grid(row=0, column=col, sticky="ew", padx=2)
        ai_buttons.append(button)

    setup_button = tk.Button(
        ai_bar, text="KI EINRICHTEN", command=_configure_ai,
        bg="#dedbd2", fg=INK, activebackground="#d1cdc3",
        bd=0, padx=5, pady=6, font=("Segoe UI", 8), cursor="hand2",
    )
    setup_button.grid(row=0, column=4, sticky="ew", padx=2)
    ai_buttons.append(setup_button)
'''
corr = replace_once(corr, old_note, new_note, "KI-Begleittext UI")
CORR.write_text(corr, encoding="utf-8")

post = POST.read_text(encoding="utf-8")
post = post.replace("update_1817_install.log", "update_1818_install.log")
post = post.replace("update_1817_error.txt", "update_1818_error.txt")
post = replace_once(
    post,
    "    BASE / 'letter_template_v1814.py',\n)",
    "    BASE / 'letter_template_v1814.py',\n    BASE / 'ai_writer_v1818.py',\n)",
    "post required AI module",
)
post = replace_once(post, 'APP_VERSION = "1.8.17"', 'APP_VERSION = "1.8.18"', "post version")
post = post.replace("OK: Update 1.8.17 erfolgreich installiert.", "OK: Update 1.8.18 erfolgreich installiert.")
POST.write_text(post, encoding="utf-8")

for path in (APP, POST, CORR, AI):
    py_compile.compile(str(path), doraise=True)

corr_text = CORR.read_text(encoding="utf-8")
ai_text = AI.read_text(encoding="utf-8")
if 'APP_VERSION = "1.8.18"' not in APP.read_text(encoding="utf-8"):
    raise RuntimeError("1.8.18: App-Version wurde nicht gesetzt.")
for marker in ("KI: KURZ", "KI: FREUNDLICH", "KI: FÖRMLICH", "TEXT VERBESSERN", "KI EINRICHTEN", "_run_ai"):
    if marker not in corr_text:
        raise RuntimeError("1.8.18: KI-UI-Prüfung fehlt: " + marker)
for marker in ("gpt-5.6-terra", "CryptProtectData", "/v1/responses", "formulate_letter_text"):
    if marker not in ai_text:
        raise RuntimeError("1.8.18: KI-Modul-Prüfung fehlt: " + marker)

print("OK: Projektzentrale 1.8.18 KI-Anschreiben gepatcht und geprüft.")
