from pathlib import Path
import py_compile, sys

ROOT=Path(sys.argv[1]).resolve()
APP=ROOT/"app.py"
POST=ROOT/"post_update.py"

def one(text, old, new, label):
    c=text.count(old)
    if c != 1:
        raise RuntimeError(f"{label}: expected 1 match, got {c}")
    return text.replace(old,new,1)

app=APP.read_text(encoding="utf-8")
app=one(app,'APP_VERSION = "1.8.39"','APP_VERSION = "1.8.40"',"app version")

# IDEA detail pane: render real line breaks instead of literal "\n".
app=one(
    app,
    "            preview.configure(text='\\\\n'.join(lines))",
    "            preview.configure(text='\\n'.join(lines))",
    "IDEA preview line breaks"
)
app=one(
    app,
    "                    text='Noch kein IDEA-Anschluss erkannt.\\\\n\\\\nDie Projektzentrale erkennt echte *.ideaCon-Dateien automatisch und ordnet IFC, PDF, Word, Archiv und Backup anhand der Anschlussbezeichnung zu.'",
    "                    text='Noch kein IDEA-Anschluss erkannt.\\n\\nDie Projektzentrale erkennt echte *.ideaCon-Dateien automatisch und ordnet IFC, PDF, Word, Archiv und Backup anhand der Anschlussbezeichnung zu.'",
    "IDEA empty preview line breaks"
)

APP.write_text(app,encoding="utf-8")

post=POST.read_text(encoding="utf-8")
post=post.replace("update_1839_install.log","update_1840_install.log")
post=post.replace("update_1839_error.txt","update_1840_error.txt")
post=one(post,'APP_VERSION = "1.8.39"','APP_VERSION = "1.8.40"',"post version")
post=post.replace("OK: Update 1.8.39 erfolgreich installiert.","OK: Update 1.8.40 erfolgreich installiert.")
POST.write_text(post,encoding="utf-8")

for p in (APP,POST):
    py_compile.compile(str(p),doraise=True)

a=APP.read_text(encoding="utf-8")
assert "preview.configure(text='\\n'.join(lines))" in a
print("OK 1.8.40 IDEA preview line breaks")
