from pathlib import Path
import py_compile, sys

ROOT=Path(sys.argv[1]).resolve()
APP=ROOT/"app.py"; POST=ROOT/"post_update.py"; DIAG=ROOT/"outlook_diag_v1828.py"

def one(t,a,b,label):
    c=t.count(a)
    if c!=1: raise RuntimeError(f"{label}: {c}")
    return t.replace(a,b,1)

app=APP.read_text(encoding="utf-8")
app=one(app,'APP_VERSION = "1.8.27"','APP_VERSION = "1.8.28"',"app version")

old='''        def outlook_assign():
            try:
                from outlook_archive_v1823 import open_recent_picker
                open_recent_picker(self,DB_PATH,self.project_id,str(r['number'] or ''),project_root,on_done=self.show_comm)
            except Exception as exc:
                messagebox.showerror('Outlook zuordnen',str(exc),parent=self)

        for txt,cmd,bg in [
            ('OUTLOOK SYNCHRONISIEREN',outlook_sync,ACCENT),
            ('OUTLOOK-MAIL ZUORDNEN',outlook_assign,DARK),
'''
new='''        def outlook_assign():
            try:
                from outlook_archive_v1823 import open_recent_picker
                open_recent_picker(self,DB_PATH,self.project_id,str(r['number'] or ''),project_root,on_done=self.show_comm)
            except Exception as exc:
                messagebox.showerror('Outlook zuordnen',str(exc),parent=self)

        def outlook_diag():
            try:
                from outlook_diag_v1828 import open_outlook_diagnostics
                open_outlook_diagnostics(self)
            except Exception as exc:
                messagebox.showerror('Outlook-Diagnose',str(exc),parent=self)

        for txt,cmd,bg in [
            ('OUTLOOK SYNCHRONISIEREN',outlook_sync,ACCENT),
            ('OUTLOOK-MAIL ZUORDNEN',outlook_assign,DARK),
            ('OUTLOOK DIAGNOSE',outlook_diag,DARK),
'''
app=one(app,old,new,"communication diag button")
APP.write_text(app,encoding="utf-8")

post=POST.read_text(encoding="utf-8")
post=post.replace("update_1827_install.log","update_1828_install.log")
post=post.replace("update_1827_error.txt","update_1828_error.txt")
post=one(post,'APP_VERSION = "1.8.27"','APP_VERSION = "1.8.28"',"post version")
post=post.replace("OK: Update 1.8.27 erfolgreich installiert.","OK: Update 1.8.28 erfolgreich installiert.")
POST.write_text(post,encoding="utf-8")

for p in (APP,POST,DIAG):
    py_compile.compile(str(p),doraise=True)

print("OK 1.8.28 Outlook diagnostic")
