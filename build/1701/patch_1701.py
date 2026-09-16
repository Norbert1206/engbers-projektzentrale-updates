from pathlib import Path
import datetime
import py_compile
import shutil
import traceback

BASE=Path(__file__).resolve().parent
APP=BASE/'app.py'
MOD=BASE/'wordforms_v1700.py'
OLD='1.7.0'; NEW='1.7.1'
MARK='PZ_WORD_OUTPUT_DIRECT_V1701'

OLD_FILL="""        for ff,key,value in plans:\n            _flatten(ff,value,parents)\n        new_xml=ET.tostring(root,encoding='utf-8',xml_declaration=True)\n"""
NEW_FILL="""        success=0\n        for ff,key,value in plans:\n            if _flatten(ff,value,parents):\n                success+=1\n        new_xml=ET.tostring(root,encoding='utf-8',xml_declaration=True)\n"""
OLD_RETURN='    return len(plans)\n\n\ndef _project_sources(app):\n'
NEW_RETURN='    return success\n\n\ndef _project_sources(app):\n'
OLD_SELECTED="""    def fill_selected():\n        _fill(list(tree.selection()))\n\n    def fill_all():\n        _fill(list(docs.keys()))\n\n    def open_original(event=None):\n"""
NEW_SELECTED="""    def fill_selected():\n        ids=list(tree.selection())\n        _fill(ids)\n        if len(ids)==1:\n            item=docs.get(ids[0])\n            if item and item.get('dst') and item['dst'].exists():\n                _open_generated(item['dst'])\n\n    def fill_all():\n        _fill(list(docs.keys()))\n\n    def open_original(event=None):\n"""
OLD_OPEN="""    def open_output():\n        sel=tree.selection()\n        if sel and docs[sel[0]].get('dst') and docs[sel[0]]['dst'].exists():\n            app.open_external_path(str(docs[sel[0]]['dst']))\n            return\n        for item in docs.values():\n            if item.get('dst') and item['dst'].exists():\n                app.open_external_path(str(item['dst'].parent)); return\n        if roots:\n            out=roots[0]/'Ausgefüllt'; out.mkdir(parents=True,exist_ok=True); app.open_external_path(str(out))\n\n    tree.bind('<Double-1>',open_original)\n"""
NEW_OPEN="""    def _open_generated(path):\n        # PZ_WORD_OUTPUT_DIRECT_V1701: erzeugte Word-Datei unter Windows direkt öffnen.\n        try:\n            if hasattr(__import__('os'),'startfile'):\n                os.startfile(str(path))\n            else:\n                app.open_external_path(str(path))\n            return True\n        except Exception as e:\n            try:\n                app.open_external_path(str(path))\n                return True\n            except Exception:\n                messagebox.showerror('Word-Bescheinigungen',f'Ausgefüllte Datei konnte nicht geöffnet werden.\\n\\n{path}\\n\\n{e}',parent=w)\n                return False\n\n    def open_output():\n        sel=tree.selection()\n        if sel and docs[sel[0]].get('dst') and docs[sel[0]]['dst'].exists():\n            _open_generated(docs[sel[0]]['dst'])\n            return\n        for item in docs.values():\n            if item.get('dst') and item['dst'].exists():\n                _open_generated(item['dst']); return\n        if roots:\n            out=roots[0]/'Ausgefüllt'; out.mkdir(parents=True,exist_ok=True); app.open_external_path(str(out))\n\n    tree.bind('<Double-1>',open_original)\n"""
OLD_BUTTON="tk.Button(foot,text='AUSGABE ÖFFNEN',command=open_output"
NEW_BUTTON="tk.Button(foot,text='AUSGEFÜLLTE DATEI ÖFFNEN',command=open_output"


def main():
    if not APP.exists() or not MOD.exists():
        raise RuntimeError('1.7.1: app.py oder wordforms_v1700.py wurde nicht gefunden.')
    app=APP.read_text(encoding='utf-8')
    mod=MOD.read_text(encoding='utf-8')
    if f'APP_VERSION = "{NEW}"' in app and MARK in mod:
        return 0
    if f'APP_VERSION = "{OLD}"' not in app:
        raise RuntimeError('Update 1.7.1 erwartet Projektzentrale 1.7.0.')
    for label,needle in [('Fülllogik',OLD_FILL),('Rückgabewert',OLD_RETURN),('Auswahlaktion',OLD_SELECTED),('Öffnen-Aktion',OLD_OPEN),('Button',OLD_BUTTON)]:
        if needle not in mod:
            raise RuntimeError('1.7.1: '+label+' wurde nicht eindeutig gefunden.')
    mod_new=mod.replace(OLD_FILL,NEW_FILL,1).replace(OLD_RETURN,NEW_RETURN,1).replace(OLD_SELECTED,NEW_SELECTED,1).replace(OLD_OPEN,NEW_OPEN,1).replace(OLD_BUTTON,NEW_BUTTON,1)
    app_new=app.replace(f'APP_VERSION = "{OLD}"',f'APP_VERSION = "{NEW}"',1).replace('Projektzentrale 1.7.0','Projektzentrale 1.7.1')
    chk1=APP.with_name('app.py.1701.check'); chk2=MOD.with_name('wordforms_v1700.py.1701.check')
    try:
        chk1.write_text(app_new,encoding='utf-8'); py_compile.compile(str(chk1),doraise=True)
        chk2.write_text(mod_new,encoding='utf-8'); py_compile.compile(str(chk2),doraise=True)
    finally:
        for p in (chk1,chk2):
            try:p.unlink()
            except Exception:pass
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for p in (APP,MOD): shutil.copy2(p,p.with_name(p.name+'.vor_1_7_1_'+stamp+'.bak'))
    t=APP.with_name('app.py.1701.tmp'); t.write_text(app_new,encoding='utf-8'); t.replace(APP)
    t=MOD.with_name('wordforms_v1700.py.1701.tmp'); t.write_text(mod_new,encoding='utf-8'); t.replace(MOD)
    APP.with_name('patch_1701_report.txt').write_text(
        'OK: Projektzentrale 1.7.1 installiert.\n'
        'Ausgefüllte Word-Dateien werden jetzt direkt geöffnet.\n'
        'Der Button heißt AUSGEFÜLLTE DATEI ÖFFNEN.\n'
        'Bei einer markierten Datei wird die erzeugte Kopie nach dem Ausfüllen direkt geöffnet.\n'
        'Die Feldanzahl zählt nur tatsächlich geschriebene Felder.\n',encoding='utf-8')
    return 0

if __name__=='__main__':
    try: raise SystemExit(main())
    except SystemExit: raise
    except Exception:
        try: APP.with_name('patch_1701_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception: pass
        raise
