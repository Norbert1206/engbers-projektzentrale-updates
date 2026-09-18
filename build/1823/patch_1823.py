from pathlib import Path
import py_compile
import sys

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
APP = ROOT / "app.py"
POST = ROOT / "post_update.py"
OUTLOOK = ROOT / "outlook_v1822.py"
BASKET = ROOT / "share_basket_v1821.py"
ARCHIVE = ROOT / "outlook_archive_v1823.py"

for path in (APP, POST, OUTLOOK, BASKET, ARCHIVE):
    if not path.exists():
        raise RuntimeError(f"1.8.23: Update-Datei fehlt: {path.name}")

def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"1.8.23: Marker {label} erwartet 1x, gefunden {count}x")
    return text.replace(old, new, 1)

app = APP.read_text(encoding="utf-8")
app = replace_once(app, 'APP_VERSION = "1.8.22"', 'APP_VERSION = "1.8.23"', "APP_VERSION")

old_show = """    def show_comm(self):
        self.clear(); self.titleblock(self.content,'Kommunikation','Chronologische Projektakte · Original und interne Auswertung getrennt')
        tools=tk.Frame(self.content,bg=BG); tools.pack(fill='x',pady=(0,10))
        for txt,cmd in [('ANSCHREIBEN ERSTELLEN',self.create_correspondence),('ADRESSBUCH',self.open_addressbook),('E-Mail (.eml) importieren',self.import_eml),('WhatsApp (.txt) importieren',self.import_whatsapp),('Goodnotes-PDF importieren',self.import_goodnotes)]:
            tk.Button(tools,text=txt,command=cmd,bg=DARK,fg='white',bd=0,padx=14,pady=8).pack(side='left',padx=(0,8))
        con=db(); rows=con.execute('SELECT ts,channel,sender,recipient,subject,attachment FROM comm WHERE project_id=? ORDER BY ts DESC',(self.project_id,)).fetchall(); con.close()
        pan,b=self.panel(self.content,'Kommunikationsakte'); pan.pack(fill='both',expand=True); self.tree(b,('Zeit','Kanal','Von','An','Betreff / Thema','Anlage'),[tuple(r) for r in rows],[140,100,170,190,420,160])

"""
new_show = """    def show_comm(self):
        self.clear()
        r=self.project_row()
        project_root=Path(self.get_project_folder(r))
        self.titleblock(self.content,'Kommunikation','Chronologische Projektakte · Outlook-Eingang und -Ausgang projektbezogen archivieren')
        tools=tk.Frame(self.content,bg=BG); tools.pack(fill='x',pady=(0,10))

        def outlook_sync():
            try:
                from outlook_archive_v1823 import sync_project
                new_count,matched=sync_project(DB_PATH,self.project_id,str(r['number'] or ''),project_root,days=365)
            except Exception as exc:
                messagebox.showerror('Outlook synchronisieren',str(exc),parent=self); return
            messagebox.showinfo('Outlook synchronisieren',f'{new_count} neue Mail(s) archiviert.\\n\\n{matched} passende Outlook-Mail(s) gefunden.',parent=self)
            self.show_comm()

        def outlook_assign():
            try:
                from outlook_archive_v1823 import open_recent_picker
                open_recent_picker(self,DB_PATH,self.project_id,str(r['number'] or ''),project_root,on_done=self.show_comm)
            except Exception as exc:
                messagebox.showerror('Outlook zuordnen',str(exc),parent=self)

        for txt,cmd,bg in [
            ('OUTLOOK SYNCHRONISIEREN',outlook_sync,ACCENT),
            ('OUTLOOK-MAIL ZUORDNEN',outlook_assign,DARK),
            ('ANSCHREIBEN ERSTELLEN',self.create_correspondence,DARK),
            ('ADRESSBUCH',self.open_addressbook,DARK),
            ('E-Mail (.eml) importieren',self.import_eml,DARK),
            ('WhatsApp (.txt) importieren',self.import_whatsapp,DARK),
            ('Goodnotes-PDF importieren',self.import_goodnotes,DARK),
        ]:
            tk.Button(tools,text=txt,command=cmd,bg=bg,fg='white',bd=0,padx=13,pady=8).pack(side='left',padx=(0,7))

        con=db()
        try:
            from outlook_archive_v1823 import ensure_schema
            ensure_schema(DB_PATH)
        except Exception:
            pass
        rows=con.execute('SELECT id,ts,channel,sender,recipient,subject,attachment,original_path FROM comm WHERE project_id=? ORDER BY ts DESC',(self.project_id,)).fetchall()
        con.close()

        pan,b=self.panel(self.content,'Kommunikationsakte'); pan.pack(fill='both',expand=True)
        cols=('Zeit','Kanal','Von','An','Betreff / Thema','Anlage')
        tr=ttk.Treeview(b,columns=cols,show='headings',height=18)
        widths=[145,115,180,200,430,180]
        for i,c in enumerate(cols):
            tr.heading(c,text=c); tr.column(c,width=widths[i],anchor='w',stretch=(c=='Betreff / Thema'))
        pathmap={}
        for row in rows:
            iid=tr.insert('', 'end', values=(row['ts'],row['channel'],row['sender'],row['recipient'],row['subject'],row['attachment']))
            pathmap[iid]=str(row['original_path'] or '')
        sy=ttk.Scrollbar(b,orient='vertical',command=tr.yview); tr.configure(yscrollcommand=sy.set)
        tr.pack(side='left',fill='both',expand=True); sy.pack(side='right',fill='y')

        def open_comm(_evt=None):
            sel=tr.selection()
            if not sel:return
            p=pathmap.get(sel[0],'')
            if not p:return
            try:self.open_external_path(p)
            except Exception as exc:messagebox.showerror('Kommunikation',str(exc),parent=self)

        tr.bind('<Double-1>',open_comm); tr.bind('<Return>',open_comm)

"""
app = replace_once(app, old_show, new_show, "show_comm")
APP.write_text(app, encoding="utf-8")

outlook = OUTLOOK.read_text(encoding="utf-8")
outlook = replace_once(
    outlook,
    'def open_outlook_draft(to: str, subject: str, body: str, attachments=None, cc: str = "") -> None:',
    'def open_outlook_draft(to: str, subject: str, body: str, attachments=None, cc: str = "", project_number: str = "") -> None:',
    "outlook signature"
)
outlook = replace_once(
    outlook,
    '    env["PZ_OUTLOOK_ATTACH_B64"] = _b64(json.dumps(attachments, ensure_ascii=False))\n',
    '    env["PZ_OUTLOOK_ATTACH_B64"] = _b64(json.dumps(attachments, ensure_ascii=False))\n    env["PZ_PROJECT_NUMBER"] = str(project_number or "")\n',
    "project env"
)
outlook = replace_once(
    outlook,
    '$mail.Subject = $subject\n$mail.Display()',
    '$mail.Subject = $subject\nif (-not [string]::IsNullOrWhiteSpace($env:PZ_PROJECT_NUMBER)) {\n    try { $mail.PropertyAccessor.SetProperty("http://schemas.microsoft.com/mapi/string/{00020329-0000-0000-C000-000000000046}/EngbersProjectNumber", $env:PZ_PROJECT_NUMBER) } catch {}\n}\n$mail.Display()',
    "hidden project marker"
)
OUTLOOK.write_text(outlook, encoding="utf-8")

basket = BASKET.read_text(encoding="utf-8")
old_call = """                    open_outlook_draft(
                        to_var.get().strip(),
                        subject_var.get().strip(),
                        body.get("1.0", "end").strip(),
                        chosen,
                        cc_var.get().strip(),
                    )
"""
new_call = """                    open_outlook_draft(
                        to_var.get().strip(),
                        subject_var.get().strip(),
                        body.get("1.0", "end").strip(),
                        chosen,
                        cc_var.get().strip(),
                        project_number=project_number,
                    )
"""
basket = replace_once(basket, old_call, new_call, "basket Outlook project marker")
BASKET.write_text(basket, encoding="utf-8")

post = POST.read_text(encoding="utf-8")
post = post.replace("update_1822_install.log", "update_1823_install.log")
post = post.replace("update_1822_error.txt", "update_1823_error.txt")
post = replace_once(post, 'APP_VERSION = "1.8.22"', 'APP_VERSION = "1.8.23"', "post version")
post = post.replace("OK: Update 1.8.22 erfolgreich installiert.", "OK: Update 1.8.23 erfolgreich installiert.")
POST.write_text(post, encoding="utf-8")

for path in (APP, POST, OUTLOOK, BASKET, ARCHIVE):
    py_compile.compile(str(path), doraise=True)

for marker in ('OUTLOOK SYNCHRONISIEREN','OUTLOOK-MAIL ZUORDNEN','outlook_archive_v1823'):
    if marker not in APP.read_text(encoding="utf-8"):
        raise RuntimeError("1.8.23: Kommunikationsakte fehlt: "+marker)
if 'EngbersProjectNumber' not in OUTLOOK.read_text(encoding="utf-8"):
    raise RuntimeError("1.8.23: Outlook-Projektkennung fehlt")

print("OK: Projektzentrale 1.8.23 Outlook-Projektakte gepatcht und geprüft.")
