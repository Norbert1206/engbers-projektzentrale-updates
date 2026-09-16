from pathlib import Path
import datetime
import py_compile
import shutil
import traceback

BASE=Path(__file__).resolve().parent
APP=BASE/'app.py'
MOD=BASE/'wordforms_v1700.py'
OLD='1.7.1'; NEW='1.7.2'
MARK='PZ_WORD_DATE_CHECKBOX_PDF_V1702'

IMPORT_OLD="import copy\nimport os\nimport re\nimport zipfile\n"
IMPORT_NEW="import copy\nimport os\nimport re\nimport zipfile\nimport datetime\nimport subprocess\nimport tempfile\n"

CLASSIFY_OLD="""    idx,_=_field_index(ff,parents)\n\n    # Bauvorhaben / Bauort.\n"""
CLASSIFY_NEW="""    idx,_=_field_index(ff,parents)\n\n    # Unterschriftsbereich: Ort und Datum stehen in zwei Formularfeldern\n    # der linken Zelle unter \"III. Unterschrift\".\n    if 'iii. unterschrift' in c:\n        if idx==0:\n            return 'signature_place'\n        if idx==1:\n            return 'signature_date'\n\n    # Bauvorhaben / Bauort.\n"""

VALUES_OLD="""        'architect_phone':str(data.get('architect_phone','') or '').strip(),\n        'architect_email':str(data.get('architect_email','') or '').strip(),\n    }\n"""
VALUES_NEW="""        'architect_phone':str(data.get('architect_phone','') or '').strip(),\n        'architect_email':str(data.get('architect_email','') or '').strip(),\n        'signature_place':str(data.get('engineer_city','') or 'Lingen').strip(),\n        'signature_date':datetime.date.today().strftime('%d.%m.%Y'),\n    }\n"""

FILL_ANCHOR="def fill_docx(src, dst, data):\n"
FILL_HELPER="""def _set_primary_checkbox(root, parents):\n    # PZ_WORD_DATE_CHECKBOX_PDF_V1702\n    # Nur die erste fachliche Bestätigung automatisch markieren:\n    # \"Die von mir aufgestellten ...\". Das Fachplaner/Prüfer-Kästchen bleibt frei.\n    for ff in root.iter(Q('ffData')):\n        cb=ff.find(Q('checkBox'))\n        if cb is None:\n            continue\n        p=_ancestor(ff,'p',parents)\n        text=_txt(p).casefold()\n        if 'von mir aufgestellten' not in text:\n            continue\n        if 'fachplaner' in text or 'von mir geprüften' in text:\n            continue\n        default=cb.find(Q('default'))\n        if default is None:\n            default=ET.SubElement(cb,Q('default'))\n        default.set(Q('val'),'1')\n        checked=cb.find(Q('checked'))\n        if checked is None:\n            checked=ET.SubElement(cb,Q('checked'))\n        checked.set(Q('val'),'1')\n        return 1\n    return 0\n\n\ndef fill_docx(src, dst, data):\n"""

FILL_OLD="""        if not plans:\n            return 0\n        success=0\n        for ff,key,value in plans:\n            if _flatten(ff,value,parents):\n                success+=1\n"""
FILL_NEW="""        success=_set_primary_checkbox(root,parents)\n        for ff,key,value in plans:\n            if _flatten(ff,value,parents):\n                success+=1\n        if not success:\n            return 0\n"""

OUT_OLD="""def _output_path(root, src, rel):\n    parent=(root/'Ausgefüllt'/rel.parent)\n    return parent/(src.stem+'_ausgefüllt'+src.suffix)\n\n\ndef open_wordforms(app):\n"""
OUT_NEW="""def _output_path(root, src, rel):\n    parent=(root/'Ausgefüllt'/rel.parent)\n    return parent/(src.stem+'_ausgefüllt'+src.suffix)\n\n\ndef _pdf_output_path(root, src, rel):\n    parent=(root/'Ausgefüllt'/rel.parent)\n    return parent/(src.stem+'_ausgefüllt.pdf')\n\n\ndef _export_pdf_with_word(docx_path, pdf_path):\n    # Word ist auf dem Büro-PC vorhanden. Export über Word-COM per cscript,\n    # damit keine zusätzliche Python-Bibliothek benötigt wird.\n    docx_path=Path(docx_path).resolve()\n    pdf_path=Path(pdf_path).resolve()\n    pdf_path.parent.mkdir(parents=True,exist_ok=True)\n    script='''On Error Resume Next\nSet a = WScript.Arguments\nSet w = CreateObject(\"Word.Application\")\nIf Err.Number <> 0 Then WScript.Quit 2\nw.Visible = False\nw.DisplayAlerts = 0\nSet d = w.Documents.Open(a(0), False, True)\nIf Err.Number <> 0 Then w.Quit : WScript.Quit 3\nd.ExportAsFixedFormat a(1), 17\nIf Err.Number <> 0 Then d.Close False : w.Quit : WScript.Quit 4\nd.Close False\nw.Quit\nWScript.Quit 0\n'''\n    tmp=None\n    try:\n        fd,tmp=tempfile.mkstemp(prefix='engbers_word_pdf_',suffix='.vbs')\n        os.close(fd)\n        Path(tmp).write_text(script,encoding='utf-8-sig')\n        cp=subprocess.run(\n            ['cscript.exe','//nologo',tmp,str(docx_path),str(pdf_path)],\n            capture_output=True,text=True,timeout=90,\n            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)\n        )\n        if cp.returncode==0 and pdf_path.exists() and pdf_path.stat().st_size>0:\n            return True,''\n        err=(cp.stderr or cp.stdout or f'Word-PDF-Export Rückgabecode {cp.returncode}').strip()\n        return False,err\n    except Exception as e:\n        return False,str(e)\n    finally:\n        if tmp:\n            try: Path(tmp).unlink()\n            except Exception: pass\n\n\ndef open_wordforms(app):\n"""

DOCS_OLD="docs[iid]={'root':root,'src':src,'rel':rel,'check':check,'dst':None}"
DOCS_NEW="docs[iid]={'root':root,'src':src,'rel':rel,'check':check,'dst':None,'pdf':None,'pdf_error':''}"

FILL_UI_OLD="""        made=[]; skipped=[]; failed=[]\n        for iid in ids:\n"""
FILL_UI_NEW="""        made=[]; pdf_made=[]; skipped=[]; failed=[]\n        for iid in ids:\n"""

FILL_UI_BODY_OLD="""                if n:\n                    item['dst']=dst; made.append(dst)\n                    vals=list(tree.item(iid,'values')); vals[3]=f'{n} Felder ausgefüllt'; tree.item(iid,values=vals)\n                else:\n                    skipped.append(item['src'].name)\n"""
FILL_UI_BODY_NEW="""                if n:\n                    item['dst']=dst; made.append(dst)\n                    pdf=_pdf_output_path(item['root'],item['src'],item['rel'])\n                    pdf_ok,pdf_err=_export_pdf_with_word(dst,pdf)\n                    item['pdf']=pdf if pdf_ok else None\n                    item['pdf_error']=pdf_err\n                    if pdf_ok:\n                        pdf_made.append(pdf)\n                    vals=list(tree.item(iid,'values'))\n                    vals[3]=(f'{n} automatisch · PDF erstellt' if pdf_ok else f'{n} automatisch · PDF-Fehler')\n                    tree.item(iid,values=vals)\n                else:\n                    skipped.append(item['src'].name)\n"""

MSG_OLD="""        if made: msg.append(f'{len(made)} ausgefüllte Kopie(n) erstellt.')\n        if skipped: msg.append(f'{len(skipped)} Datei(en) ohne passende/gefüllte Felder übersprungen.')\n"""
MSG_NEW="""        if made: msg.append(f'{len(made)} ausgefüllte Word-Kopie(n) erstellt.')\n        if pdf_made: msg.append(f'{len(pdf_made)} PDF-Datei(en) automatisch erzeugt.')\n        if made and len(pdf_made)!=len(made): msg.append('Bei mindestens einer Datei konnte Word kein PDF erzeugen; Statuszeile beachten.')\n        if skipped: msg.append(f'{len(skipped)} Datei(en) ohne passende/gefüllte Felder übersprungen.')\n"""

OPEN_OLD="""    def open_output():\n        sel=tree.selection()\n        if sel and docs[sel[0]].get('dst') and docs[sel[0]]['dst'].exists():\n            _open_generated(docs[sel[0]]['dst'])\n            return\n        for item in docs.values():\n            if item.get('dst') and item['dst'].exists():\n                _open_generated(item['dst']); return\n        if roots:\n            out=roots[0]/'Ausgefüllt'; out.mkdir(parents=True,exist_ok=True); app.open_external_path(str(out))\n\n    tree.bind('<Double-1>',open_original)\n"""
OPEN_NEW="""    def open_output():\n        sel=tree.selection()\n        if sel and docs[sel[0]].get('dst') and docs[sel[0]]['dst'].exists():\n            _open_generated(docs[sel[0]]['dst'])\n            return\n        for item in docs.values():\n            if item.get('dst') and item['dst'].exists():\n                _open_generated(item['dst']); return\n        if roots:\n            out=roots[0]/'Ausgefüllt'; out.mkdir(parents=True,exist_ok=True); app.open_external_path(str(out))\n\n    def open_pdf():\n        sel=tree.selection()\n        if sel and docs[sel[0]].get('pdf') and docs[sel[0]]['pdf'].exists():\n            _open_generated(docs[sel[0]]['pdf'])\n            return\n        for item in docs.values():\n            if item.get('pdf') and item['pdf'].exists():\n                _open_generated(item['pdf']); return\n        messagebox.showinfo('Word-Bescheinigungen','Für die aktuelle Auswahl wurde noch keine PDF-Datei erzeugt.',parent=w)\n\n    tree.bind('<Double-1>',open_original)\n"""

BUTTON_OLD="""    tk.Button(foot,text='AUSGEFÜLLTE DATEI ÖFFNEN',command=open_output,bg='#e7e4dc',fg=INK,bd=0,padx=14,pady=9).pack(side='left')\n"""
BUTTON_NEW="""    tk.Button(foot,text='WORD ÖFFNEN',command=open_output,bg='#e7e4dc',fg=INK,bd=0,padx=14,pady=9).pack(side='left')\n    tk.Button(foot,text='PDF ÖFFNEN',command=open_pdf,bg='#e7e4dc',fg=INK,bd=0,padx=14,pady=9).pack(side='left',padx=(8,0))\n"""


def _one(s,old,new,label):
    if old not in s:
        raise RuntimeError('1.7.2: '+label+' wurde nicht eindeutig gefunden.')
    return s.replace(old,new,1)


def main():
    if not APP.exists() or not MOD.exists():
        raise RuntimeError('1.7.2: app.py oder wordforms_v1700.py wurde nicht gefunden.')
    app=APP.read_text(encoding='utf-8')
    mod=MOD.read_text(encoding='utf-8')
    if f'APP_VERSION = "{NEW}"' in app and MARK in mod:
        return 0
    if f'APP_VERSION = "{OLD}"' not in app:
        raise RuntimeError('Update 1.7.2 erwartet Projektzentrale 1.7.1.')

    mod=_one(mod,IMPORT_OLD,IMPORT_NEW,'Importblock')
    mod=_one(mod,CLASSIFY_OLD,CLASSIFY_NEW,'Unterschriftsfelder')
    mod=_one(mod,VALUES_OLD,VALUES_NEW,'Ort/Datum-Werte')
    mod=_one(mod,FILL_ANCHOR,FILL_HELPER,'Kreuz-Funktion')
    mod=_one(mod,FILL_OLD,FILL_NEW,'Fülllogik')
    mod=_one(mod,OUT_OLD,OUT_NEW,'PDF-Export')
    mod=_one(mod,DOCS_OLD,DOCS_NEW,'Ausgabedaten')
    mod=_one(mod,FILL_UI_OLD,FILL_UI_NEW,'PDF-Zähler')
    mod=_one(mod,FILL_UI_BODY_OLD,FILL_UI_BODY_NEW,'PDF-Erzeugung')
    mod=_one(mod,MSG_OLD,MSG_NEW,'Ausgabemeldung')
    mod=_one(mod,OPEN_OLD,OPEN_NEW,'PDF-Öffnen')
    mod=_one(mod,BUTTON_OLD,BUTTON_NEW,'PDF-Button')

    app_new=app.replace(f'APP_VERSION = "{OLD}"',f'APP_VERSION = "{NEW}"',1).replace('Projektzentrale 1.7.1','Projektzentrale 1.7.2')
    if MARK not in mod:
        raise RuntimeError('1.7.2: Sicherheitsmarker fehlt.')

    chk1=APP.with_name('app.py.1702.check'); chk2=MOD.with_name('wordforms_v1700.py.1702.check')
    try:
        chk1.write_text(app_new,encoding='utf-8'); py_compile.compile(str(chk1),doraise=True)
        chk2.write_text(mod,encoding='utf-8'); py_compile.compile(str(chk2),doraise=True)
    finally:
        for p in (chk1,chk2):
            try:p.unlink()
            except Exception:pass

    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for p in (APP,MOD): shutil.copy2(p,p.with_name(p.name+'.vor_1_7_2_'+stamp+'.bak'))
    t=APP.with_name('app.py.1702.tmp'); t.write_text(app_new,encoding='utf-8'); t.replace(APP)
    t=MOD.with_name('wordforms_v1700.py.1702.tmp'); t.write_text(mod,encoding='utf-8'); t.replace(MOD)
    APP.with_name('patch_1702_report.txt').write_text(
        'OK: Projektzentrale 1.7.2 installiert.\n'
        'Erstes fachliches Kontrollkästchen wird automatisch angekreuzt.\n'
        'Ort und Tagesdatum werden im Unterschriftsbereich automatisch gesetzt.\n'
        'Zu jeder ausgefüllten Word-Datei wird über Microsoft Word eine PDF-Kopie erzeugt.\n'
        'Word und PDF liegen unter Bescheinigungen\\Ausgefüllt.\n'
        'Stempel/Unterschrift folgt nach Hinterlegung der echten Grafik.\n',encoding='utf-8')
    return 0

if __name__=='__main__':
    try: raise SystemExit(main())
    except SystemExit: raise
    except Exception:
        try: APP.with_name('patch_1702_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception: pass
        raise
