from pathlib import Path
import py_compile
import sys

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
APP = ROOT / "app.py"
POST = ROOT / "post_update.py"
BASKET = ROOT / "share_basket_v1821.py"

for path in (APP, POST, BASKET, ROOT / "outlook_v1822.py"):
    if not path.exists():
        raise RuntimeError(f"1.8.22: Update-Datei fehlt: {path.name}")

def replace_exact(text, old, new, label, expected=1):
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"1.8.22: Marker {label} erwartet {expected}x, gefunden {count}x")
    return text.replace(old, new)

app = APP.read_text(encoding="utf-8")
app = replace_exact(app, 'APP_VERSION = "1.8.21"', 'APP_VERSION = "1.8.22"', "APP_VERSION")
old_call = "open_basket_dialog(self,self.project_id,str(r['number'] or ''),str(r['title'] or ''))"
new_call = "open_basket_dialog(self,self.project_id,str(r['number'] or ''),str(r['title'] or ''),db_path=DB_PATH)"
app = replace_exact(app, old_call, new_call, "Freigabekorb DB_PATH", expected=2)
APP.write_text(app, encoding="utf-8")

basket = BASKET.read_text(encoding="utf-8")
basket = replace_exact(
    basket,
    "def open_basket_dialog(app, project_id, project_number: str, project_title: str, on_change=None):",
    "def open_basket_dialog(app, project_id, project_number: str, project_title: str, on_change=None, db_path=None):",
    "basket signature"
)

anchor = '''    def create_now():
        try:
            release, copied = create_release(project_id, project_number, project_title)
        except Exception as exc:
            messagebox.showerror("Projektfreigabe", str(exc), parent=w)
            return
        clear_items(project_id)
        refresh()
        try:
            app.open_external_path(release)
        except Exception:
            pass
        messagebox.showinfo(
            "Projektfreigabe",
            f"{copied} Datei(en) als Kopie bereitgestellt.\\n\\n{release}\\n\\n"
            "Die Originaldateien wurden nicht verändert. HiDrive synchronisiert den Ordner automatisch.",
            parent=w,
        )

'''
addition = anchor + '''    def _attachment_files():
        files = {}
        for item in get_items(project_id):
            p = Path(item["path"])
            if p.is_file():
                files[str(p.resolve()).casefold()] = p
            elif p.is_dir():
                try:
                    for child in p.rglob("*"):
                        if child.is_file() and not child.is_symlink():
                            files.setdefault(str(child.resolve()).casefold(), child)
                except OSError:
                    continue
        return sorted(files.values(), key=lambda x: str(x).casefold())

    def open_outlook_mail():
        if not db_path:
            messagebox.showerror("Outlook", "Das lokale Adressbuch ist nicht verfügbar.", parent=w)
            return

        try:
            from contacts_v1814 import open_contact_picker, greeting_for
        except Exception as exc:
            messagebox.showerror("Outlook", str(exc), parent=w)
            return

        def contact_selected(row):
            email = str(row["email"] or "").strip()
            if not email:
                messagebox.showwarning("Outlook", "Für diesen Kontakt ist keine E-Mail-Adresse hinterlegt.", parent=w)
                return

            compose = tk.Toplevel(w)
            compose.title("Outlook-Mail vorbereiten")
            compose.geometry("760x610")
            compose.minsize(660, 520)
            compose.transient(w)
            compose.configure(bg=BG)

            frame = tk.Frame(compose, bg=BG)
            frame.pack(fill="both", expand=True, padx=18, pady=16)

            tk.Label(frame, text="OUTLOOK-MAIL", bg=BG, fg=INK, font=("Segoe UI", 17, "bold")).pack(anchor="w")
            tk.Label(frame, text="Es wird nur ein Entwurf geöffnet – die Projektzentrale versendet niemals automatisch.", bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 12))

            form = tk.Frame(frame, bg=BG)
            form.pack(fill="x")
            form.grid_columnconfigure(1, weight=1)

            to_var = tk.StringVar(value=email)
            cc_var = tk.StringVar()
            subject_var = tk.StringVar(value=f"{project_number} · {project_title} – Unterlagen")
            attach_var = tk.BooleanVar(value=False)

            for rr, (label, var) in enumerate((("An:", to_var), ("Cc:", cc_var), ("Betreff:", subject_var))):
                tk.Label(form, text=label, bg=BG, fg=INK, width=9, anchor="w").grid(row=rr, column=0, sticky="w", pady=4)
                tk.Entry(form, textvariable=var, bd=1, relief="solid").grid(row=rr, column=1, sticky="ew", pady=4, ipady=5)

            try:
                greeting = greeting_for(row)
            except Exception:
                greeting = "Guten Tag"
            body = tk.Text(frame, height=13, wrap="word", font=("Segoe UI", 10), bd=1, relief="solid")
            body.pack(fill="both", expand=True, pady=(12, 8))
            body.insert("1.0", f"{greeting},\\n\\nanbei erhalten Sie die aktuellen Unterlagen zum Bauvorhaben {project_number} – {project_title}.\\n")

            attachments = _attachment_files()
            total_bytes = 0
            for p in attachments:
                try: total_bytes += p.stat().st_size
                except OSError: pass
            total_mb = total_bytes / (1024 * 1024)
            attach_text = f"Dateien aus dem Freigabekorb direkt anhängen ({len(attachments)} Datei(en), ca. {total_mb:.1f} MB)"
            tk.Checkbutton(frame, text=attach_text, variable=attach_var, bg=BG, fg=INK, activebackground=BG, anchor="w").pack(fill="x", pady=(0, 8))

            status = tk.Label(frame, text="Für große Unterlagen ist später der HiDrive-Link die bessere Variante.", bg=BG, fg=MUTED, anchor="w")
            status.pack(fill="x")

            actions = tk.Frame(frame, bg=BG)
            actions.pack(fill="x", pady=(14, 0))

            def create_draft():
                chosen = attachments if attach_var.get() else []
                if chosen and total_mb > 20:
                    if not messagebox.askyesno(
                        "Große Anhänge",
                        f"Die ausgewählten Anhänge sind zusammen ca. {total_mb:.1f} MB groß.\\n\\n"
                        "Das kann die maximale Mailgröße überschreiten. Trotzdem als Outlook-Entwurf öffnen?",
                        parent=compose,
                    ):
                        return
                try:
                    from outlook_v1822 import open_outlook_draft
                    open_outlook_draft(
                        to_var.get().strip(),
                        subject_var.get().strip(),
                        body.get("1.0", "end").strip(),
                        chosen,
                        cc_var.get().strip(),
                    )
                except Exception as exc:
                    messagebox.showerror("Outlook", str(exc), parent=compose)
                    return
                compose.destroy()

            tk.Button(actions, text="OUTLOOK-ENTWURF ÖFFNEN", command=create_draft, bg=ACCENT, fg="white", bd=0, padx=18, pady=9).pack(side="right")
            tk.Button(actions, text="ABBRECHEN", command=compose.destroy, bg=DARK, fg="white", bd=0, padx=18, pady=9).pack(side="right", padx=8)

        open_contact_picker(w, db_path, project_id, contact_selected, True)

'''
basket = replace_exact(basket, anchor, addition, "Outlook compose function")

old_buttons = '''    tk.Button(buttons, text="KORB LEEREN", command=clear_all, bg="#7b2d2d", fg="white", bd=0, padx=14, pady=8).pack(side="left")
    tk.Button(buttons, text="FREIGABE ERSTELLEN", command=create_now, bg=ACCENT, fg="white", bd=0, padx=18, pady=8).pack(side="right")
    tk.Button(buttons, text="SCHLIESSEN", command=w.destroy, bg=DARK, fg="white", bd=0, padx=18, pady=8).pack(side="right", padx=8)
'''
new_buttons = '''    tk.Button(buttons, text="KORB LEEREN", command=clear_all, bg="#7b2d2d", fg="white", bd=0, padx=14, pady=8).pack(side="left")
    tk.Button(buttons, text="FREIGABE ERSTELLEN", command=create_now, bg=ACCENT, fg="white", bd=0, padx=18, pady=8).pack(side="right")
    tk.Button(buttons, text="OUTLOOK-MAIL", command=open_outlook_mail, bg=DARK, fg="white", bd=0, padx=18, pady=8).pack(side="right", padx=8)
    tk.Button(buttons, text="SCHLIESSEN", command=w.destroy, bg="#e7e4dc", fg=INK, bd=0, padx=18, pady=8).pack(side="right")
'''
basket = replace_exact(basket, old_buttons, new_buttons, "Outlook button")
BASKET.write_text(basket, encoding="utf-8")

post = POST.read_text(encoding="utf-8")
post = post.replace("update_1821_install.log", "update_1822_install.log")
post = post.replace("update_1821_error.txt", "update_1822_error.txt")
post = replace_exact(post, 'APP_VERSION = "1.8.21"', 'APP_VERSION = "1.8.22"', "post version")
post = post.replace("OK: Update 1.8.21 erfolgreich installiert.", "OK: Update 1.8.22 erfolgreich installiert.")
POST.write_text(post, encoding="utf-8")

for path in (APP, POST, BASKET, ROOT / "outlook_v1822.py"):
    py_compile.compile(str(path), doraise=True)

check = BASKET.read_text(encoding="utf-8")
for marker in ("OUTLOOK-MAIL", "OUTLOOK-ENTWURF ÖFFNEN", "outlook_v1822", "open_contact_picker"):
    if marker not in check:
        raise RuntimeError("1.8.22: Outlook-Anbindung fehlt: " + marker)

print("OK: Projektzentrale 1.8.22 Outlook-Entwurfsanbindung gepatcht und geprüft.")
