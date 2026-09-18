from pathlib import Path
import py_compile
import sys

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
APP = ROOT / "app.py"
POST = ROOT / "post_update.py"
CORR = ROOT / "correspondence_v1814.py"

for path in (APP, POST, CORR):
    if not path.exists():
        raise RuntimeError(f"1.8.19: Update-Datei fehlt: {path.name}")

def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"1.8.19: Marker {label} erwartet 1x, gefunden {count}x")
    return text.replace(old, new, 1)

app = APP.read_text(encoding="utf-8")
app = replace_once(app, 'APP_VERSION = "1.8.18"', 'APP_VERSION = "1.8.19"', "APP_VERSION")
APP.write_text(app, encoding="utf-8")

corr = CORR.read_text(encoding="utf-8")
corr = corr.replace('MODULE_VERSION = "1.8.18"', 'MODULE_VERSION = "1.8.19"', 1)
corr = replace_once(corr, "import sqlite3\nimport threading\n", "import sqlite3\nimport threading\nimport queue\n", "queue import")

old = '''        docs, reqs = _selected_context()
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
'''
new = '''        docs, reqs = _selected_context()
        _set_ai_busy(True, "KI formuliert …")
        result_queue = queue.Queue()

        def worker():
            try:
                result = formulate_letter_text(api_key, raw, mode=mode, document_items=docs, requests=reqs)
                result_queue.put(("ok", result))
            except Exception as exc:
                result_queue.put(("error", str(exc)))

        def poll_result():
            if not window.winfo_exists():
                return
            try:
                kind, payload = result_queue.get_nowait()
            except queue.Empty:
                window.after(100, poll_result)
                return
            _set_ai_busy(False)
            if kind == "error":
                ai_status.configure(text="KI-Anfrage fehlgeschlagen.")
                messagebox.showerror("KI formulieren", payload, parent=window)
                return
            note.delete("1.0", "end")
            note.insert("1.0", payload)
            ai_status.configure(text="KI-Text übernommen. Bitte kurz prüfen oder direkt weiterbearbeiten.")

        threading.Thread(target=worker, daemon=True).start()
        window.after(100, poll_result)
'''
corr = replace_once(corr, old, new, "thread-safe AI result handling")
CORR.write_text(corr, encoding="utf-8")

post = POST.read_text(encoding="utf-8")
post = post.replace("update_1818_install.log", "update_1819_install.log")
post = post.replace("update_1818_error.txt", "update_1819_error.txt")
post = replace_once(post, 'APP_VERSION = "1.8.18"', 'APP_VERSION = "1.8.19"', "post version")
post = post.replace("OK: Update 1.8.18 erfolgreich installiert.", "OK: Update 1.8.19 erfolgreich installiert.")
POST.write_text(post, encoding="utf-8")

for path in (APP, POST, CORR):
    py_compile.compile(str(path), doraise=True)

corr_text = CORR.read_text(encoding="utf-8")
for marker in ("import queue", "result_queue = queue.Queue()", "poll_result", "window.after(100, poll_result)"):
    if marker not in corr_text:
        raise RuntimeError("1.8.19: KI-Ergebnisbehandlung fehlt: " + marker)

print("OK: Projektzentrale 1.8.19 KI-Rueckgabe thread-sicher gepatcht und geprueft.")
