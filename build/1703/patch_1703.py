from pathlib import Path
import datetime
import py_compile
import shutil
import traceback

BASE=Path(__file__).resolve().parent
APP=BASE/'app.py'
MOD=BASE/'wordforms_v1700.py'
OLD='1.7.2'; NEW='1.7.3'
MARK='PZ_WORD_INPLACE_FIELDS_V1703'

IMPORT_OLD="import datetime\nimport subprocess\nimport tempfile\n"
IMPORT_NEW="import datetime\nimport subprocess\nimport tempfile\nimport hashlib\nimport shutil\n"

HELPER_ANCHOR="""def _address(street, zip_code, city):\n"""
HELPER_NEW="""def _set_form_result(ff, value, parents):\n    # PZ_WORD_INPLACE_FIELDS_V1703: Ergebnis eines alten Word-Formularfeldes\n    # aktualisieren, ohne das eigentliche Formularfeld zu entfernen.\n    fld=parents.get(ff)\n    begin=_ancestor(fld,'r',parents)\n    p=_ancestor(begin,'p',parents)\n    if begin is None or p is None:\n        return False\n    children=list(p)\n    try:\n        bi=children.index(begin)\n    except ValueError:\n        return False\n    sep_i=end_i=None\n    for i,el in enumerate(children[bi:],bi):\n        fc=el.find('.//'+Q('fldChar'))\n        if fc is None:\n            continue\n        typ=fc.get(Q('fldCharType'))\n        if typ=='separate' and sep_i is None:\n            sep_i=i\n        elif typ=='end' and sep_i is not None:\n            end_i=i\n            break\n    if sep_i is None or end_i is None:\n        return False\n    rpr=None\n    for el in children[sep_i+1:end_i]:\n        if el.tag==Q('r'):\n            old_rpr=el.find(Q('rPr'))\n            if old_rpr is not None:\n                rpr=copy.deepcopy(old_rpr)\n            break\n    if rpr is None:\n        old_rpr=begin.find(Q('rPr'))\n        if old_rpr is not None:\n            rpr=copy.deepcopy(old_rpr)\n    for el in children[sep_i+1:end_i]:\n        p.remove(el)\n    run=ET.Element(Q('r'))\n    if rpr is not None:\n        run.append(rpr)\n    t=ET.SubElement(run,Q('t'))\n    t.text=str(value)\n    p.insert(sep_i+1,run)\n    return True\n\n\ndef _safety_backup(src):\n    # Eine einzige Sicherheitskopie außerhalb des Projektordners.\n    # Im Projekt selbst entsteht dadurch keine zweite Word-Datei.\n    try:\n        src=Path(src)\n        base=Path(os.environ.get('LOCALAPPDATA') or tempfile.gettempdir())/'Engbers Projektzentrale'/'word_backups'\n        base.mkdir(parents=True,exist_ok=True)\n        token=hashlib.sha1(str(src.resolve()).encode('utf-8',errors='ignore')).hexdigest()[:12]\n        dst=base/(src.stem+'_'+token+'_vor_automatik'+src.suffix)\n        shutil.copy2(src,dst)\n        return dst\n    except Exception:\n        return None\n\n\ndef _address(street, zip_code, city):\n"""

FILL_OLD="""def fill_docx(src, dst, data):\n    vals=_values(data)\n    with zipfile.ZipFile(src,'r') as zin:\n        root=ET.fromstring(zin.read('word/document.xml'))\n        parents={c:p for p in root.iter() for c in p}\n        fields=list(root.iter(Q('ffData')))\n        plans=[]\n        for ff in fields:\n            key=_classify(ff,parents)\n            if key and vals.get(key):\n                plans.append((ff,key,vals[key]))\n        success=_set_primary_checkbox(root,parents)\n        for ff,key,value in plans:\n            if _flatten(ff,value,parents):\n                success+=1\n        if not success:\n            return 0\n        new_xml=ET.tostring(root,encoding='utf-8',xml_declaration=True)\n        dst=Path(dst)\n        dst.parent.mkdir(parents=True,exist_ok=True)\n        with zipfile.ZipFile(dst,'w',zipfile.ZIP_DEFLATED) as zout:\n            for item in zin.infolist():\n                content=new_xml if item.filename=='word/document.xml' else zin.read(item.filename)\n                zout.writestr(item,content)\n    return success\n"""
FILL_NEW="""def fill_docx(src, dst, data):\n    src=Path(src)\n    dst=Path(dst)\n    vals=_values(data)\n    same_target=False\n    try:\n        same_target=src.resolve()==dst.resolve()\n    except Exception:\n        same_target=str(src).casefold()==str(dst).casefold()\n    if same_target:\n        _safety_backup(src)\n    dst.parent.mkdir(parents=True,exist_ok=True)\n    tmp=None\n    try:\n        with zipfile.ZipFile(src,'r') as zin:\n            root=ET.fromstring(zin.read('word/document.xml'))\n            parents={c:p for p in root.iter() for c in p}\n            fields=list(root.iter(Q('ffData')))\n            plans=[]\n            for ff in fields:\n                key=_classify(ff,parents)\n                if key and vals.get(key):\n                    plans.append((ff,key,vals[key]))\n            success=_set_primary_checkbox(root,parents)\n            for ff,key,value in plans:\n                if _set_form_result(ff,value,parents):\n                    success+=1\n            if not success:\n                return 0\n            new_xml=ET.tostring(root,encoding='utf-8',xml_declaration=True)\n            fd,tmp=tempfile.mkstemp(prefix=dst.stem+'_pz_',suffix=dst.suffix,dir=str(dst.parent))\n            os.close(fd)\n            with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as zout:\n                for item in zin.infolist():\n                    content=new_xml if item.filename=='word/document.xml' else zin.read(item.filename)\n                    zout.writestr(item,content)\n        os.replace(tmp,dst)\n        tmp=None\n        return success\n    finally:\n        if tmp:\n            try: Path(tmp).unlink()\n            except Exception: pass\n"""

OUT_OLD="""def _output_path(root, src, rel):\n    parent=(root/'Ausgefüllt'/rel.parent)\n    return parent/(src.stem+'_ausgefüllt'+src.suffix)\n\n\ndef _pdf_output_path(root, src, rel):\n    parent=(root/'Ausgefüllt'/rel.parent)\n    return parent/(src.stem+'_ausgefüllt.pdf')\n"""
OUT_NEW="""def _output_path(root, src, rel):\n    # Vorhandenes Projektformular direkt aktualisieren.\n    return Path(src)\n\n\ndef _pdf_output_path(root, src, rel):\n    # PDF liegt direkt neben dem Word-Formular.\n    return Path(src).with_suffix('.pdf')\n"""

HEAD_OLD="Quelle: Ordner Bescheinigungen · Ausgabe: Bescheinigungen\\\\Ausgefüllt · Originaldateien bleiben unverändert"
HEAD_NEW="Quelle: Ordner Bescheinigungen · Word-Datei wird direkt aktualisiert · PDF wird direkt daneben gespeichert"

STATUS_OLD="status_lbl.configure(text=f'{len(made)} Datei(en) erstellt · Originale unverändert')"
STATUS_NEW="status_lbl.configure(text=f'{len(made)} Word-Datei(en) aktualisiert · PDF direkt daneben')"

MSG_OLD="if made: msg.append(f'{len(made)} ausgefüllte Word-Kopie(n) erstellt.')"
MSG_NEW="if made: msg.append(f'{len(made)} Word-Datei(en) direkt aktualisiert.')"

OUTPUT_MSG_OLD="msg.append('\\nAusgabe unter Bescheinigungen\\\\Ausgefüllt.')"
OUTPUT_MSG_NEW="msg.append('\\nPDF-Datei liegt jeweils direkt neben dem Word-Formular.')"

FALLBACK_OLD="out=roots[0]/'Ausgefüllt'; out.mkdir(parents=True,exist_ok=True); app.open_external_path(str(out))"
FALLBACK_NEW="app.open_external_path(str(roots[0]))"

OPEN_ERROR_OLD="f'Ausgefüllte Datei konnte nicht geöffnet werden.\\n\\n{path}\\n\\n{e}'"
OPEN_ERROR_NEW="f'Datei konnte nicht geöffnet werden.\\n\\n{path}\\n\\n{e}'"


def _one(s,old,new,label):
    if old not in s:
        raise RuntimeError('1.7.3: '+label+' wurde nicht eindeutig gefunden.')
    return s.replace(old,new,1)


def main():
    if not APP.exists() or not MOD.exists():
        raise RuntimeError('1.7.3: app.py oder wordforms_v1700.py wurde nicht gefunden.')
    app=APP.read_text(encoding='utf-8')
    mod=MOD.read_text(encoding='utf-8')
    if f'APP_VERSION = "{NEW}"' in app and MARK in mod:
        return 0
    if f'APP_VERSION = "{OLD}"' not in app:
        raise RuntimeError('Update 1.7.3 erwartet Projektzentrale 1.7.2.')

    mod=_one(mod,IMPORT_OLD,IMPORT_NEW,'Importblock')
    mod=_one(mod,HELPER_ANCHOR,HELPER_NEW,'Formularfeld-Erhalt')
    mod=_one(mod,FILL_OLD,FILL_NEW,'Direktes Word-Aktualisieren')
    mod=_one(mod,OUT_OLD,OUT_NEW,'Direkte Ausgabe')
    mod=_one(mod,HEAD_OLD,HEAD_NEW,'Hinweistext')
    mod=_one(mod,STATUS_OLD,STATUS_NEW,'Statuszeile')
    mod=_one(mod,MSG_OLD,MSG_NEW,'Erfolgsmeldung')
    mod=_one(mod,OUTPUT_MSG_OLD,OUTPUT_MSG_NEW,'Ausgabehinweis')
    # Fallback: ohne erzeugte Datei einfach den Bescheinigungen-Ordner öffnen.
    if FALLBACK_OLD in mod:
        mod=mod.replace(FALLBACK_OLD,FALLBACK_NEW,1)
    mod=mod.replace(OPEN_ERROR_OLD,OPEN_ERROR_NEW,1)

    app_new=app.replace(f'APP_VERSION = "{OLD}"',f'APP_VERSION = "{NEW}"',1).replace('Projektzentrale 1.7.2','Projektzentrale 1.7.3')
    if MARK not in mod:
        raise RuntimeError('1.7.3: Sicherheitsmarker fehlt.')

    chk1=APP.with_name('app.py.1703.check'); chk2=MOD.with_name('wordforms_v1700.py.1703.check')
    try:
        chk1.write_text(app_new,encoding='utf-8'); py_compile.compile(str(chk1),doraise=True)
        chk2.write_text(mod,encoding='utf-8'); py_compile.compile(str(chk2),doraise=True)
    finally:
        for p in (chk1,chk2):
            try:p.unlink()
            except Exception:pass

    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for p in (APP,MOD): shutil.copy2(p,p.with_name(p.name+'.vor_1_7_3_'+stamp+'.bak'))
    t=APP.with_name('app.py.1703.tmp'); t.write_text(app_new,encoding='utf-8'); t.replace(APP)
    t=MOD.with_name('wordforms_v1700.py.1703.tmp'); t.write_text(mod,encoding='utf-8'); t.replace(MOD)
    APP.with_name('patch_1703_report.txt').write_text(
        'OK: Projektzentrale 1.7.3 installiert.\n'
        'Word-Bescheinigungen werden direkt im Projekt aktualisiert; keine _ausgefüllt-Kopie mehr.\n'
        'Die Word-Formularfelder bleiben erhalten und können später erneut aktualisiert werden.\n'
        'Eine Sicherheitskopie liegt nur lokal außerhalb des Projektordners.\n'
        'Die PDF-Datei wird direkt neben der Word-Datei gespeichert.\n'
        'Kreuz sowie Ort/Datum bleiben automatisch.\n',encoding='utf-8')
    return 0

if __name__=='__main__':
    try: raise SystemExit(main())
    except SystemExit: raise
    except Exception:
        try: APP.with_name('patch_1703_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception: pass
        raise
