from pathlib import Path
import datetime
import py_compile
import re
import shutil
import traceback

BASE=Path(__file__).resolve().parent
APP=BASE/'app.py'
CARDS=BASE/'masterdata_v1604.py'
GEOM=BASE/'masterdata_v1601.py'
OLD='1.6.5'; NEW='1.6.6'
MARK='PZ_MASTERDATA_RUNTIME_NAME_AND_PROJECT_ADDRESS_V1606'

CARDS_ANCHOR="def _masterdata_row(app):\n    db,_,_,_,_,_,_,_=_base._env(app); _base._schema(db)\n"
CARDS_REPL="""def _pz_project_name_from_folder(number, folder):
    try:
        name=Path(str(folder or '')).name.strip()
    except Exception:
        return ''
    if not name:
        return ''
    num=str(number or '').strip()
    if num and name.casefold().startswith(num.casefold()):
        rest=name[len(num):].lstrip(' .·_-')
        if rest:
            return rest
    m=re.match(r'^\\d{2}-\\d{3}\\s*[.·_\\-]*\\s*(.+)$',name)
    return m.group(1).strip() if m else ''


def _masterdata_row(app):
    # PZ_MASTERDATA_RUNTIME_NAME_AND_PROJECT_ADDRESS_V1606:
    # Falls 1.6.0-1.6.4 den Projektnamen versehentlich auf die
    # Bauvorhaben-Bezeichnung gesetzt hat, wird er beim Öffnen der Projektakte
    # aus dem echten Projektordner wiederhergestellt.
    try:
        _r0=app.project_row()
        _db0,_,_,_,_,_,_,_=_base._env(app)
        _con0=_db0()
        try:
            _md0=_con0.execute('SELECT project_title FROM project_masterdata WHERE project_id=?',(app.project_id,)).fetchone()
            _master0=str(_md0['project_title'] or '').strip() if _md0 else ''
            _current0=str(_r0['title'] or '').strip()
            if _master0 and _current0 and _master0.casefold()==_current0.casefold():
                _folder0=app.get_project_folder(_r0)
                _restored0=_pz_project_name_from_folder(_r0['number'],_folder0)
                if _restored0 and _restored0.casefold()!=_current0.casefold():
                    _con0.execute('UPDATE projects SET title=? WHERE id=?',(_restored0,app.project_id))
                    _con0.commit()
                    try:
                        app.after_idle(lambda: (app.refresh_project_combo(),app.show_project()))
                    except Exception:
                        pass
        finally:
            _con0.close()
    except Exception:
        pass
    db,_,_,_,_,_,_,_=_base._env(app); _base._schema(db)
"""

GEOM_ANCHOR="""    _,lab,val,x=_best(frags,LABELS['project'])
    if lab and val:
        parts=[val]
        for f in _below(frags,lab,x,max_lines=2,depth=65):
            if _address(f['text']):continue
            if x is not None and abs(f['x']-x)<lab['W']*.10 and len(f['text'])>3:parts.append(f['text'])
        d['project_title']=_clean(' '.join(parts))
"""
GEOM_REPL="""    _,lab,val,x=_best(frags,LABELS['project'])
    if lab and val:
        parts=[val]
        below_project=_below(frags,lab,x,max_lines=6,depth=130)
        for f in below_project:
            if _address(f['text']):continue
            if x is not None and abs(f['x']-x)<lab['W']*.10 and len(f['text'])>3:parts.append(f['text'])
        d['project_title']=_clean(' '.join(parts))

        # PZ_MASTERDATA_RUNTIME_NAME_AND_PROJECT_ADDRESS_V1606:
        # Viele Statik-/Architektur-Titelblätter schreiben die Bauadresse nicht
        # hinter 'Bauort', sondern direkt unter die Bauvorhaben-Bezeichnung.
        # Deshalb wird dieser lokale Block zusätzlich nach einer Anschrift geprüft.
        if not d.get('project_street'):
            address_texts=[]
            if val:address_texts.append(val)
            address_texts.extend(f['text'] for f in below_project)
            candidates=list(address_texts)
            for i in range(len(address_texts)):
                candidates.append(' '.join(address_texts[i:i+2]))
                candidates.append(' '.join(address_texts[i:i+3]))
            for candidate in candidates:
                a=_address(candidate)
                if a:
                    d.update(project_street=a.get('street',''),project_zip=a.get('zip',''),project_city=a.get('city',''))
                    break
"""


def _compile_text(text,name):
    p=BASE/name
    try:
        p.write_text(text,encoding='utf-8')
        py_compile.compile(str(p),doraise=True)
    finally:
        try:p.unlink()
        except Exception:pass


def patch_cards(text):
    if MARK in text:return text
    if CARDS_ANCHOR not in text:
        raise RuntimeError('1.6.6: Stammdaten-Kartenfunktion nicht gefunden.')
    text=text.replace('import json, os, queue, threading\n','import json, os, queue, threading, re\n',1)
    return text.replace(CARDS_ANCHOR,CARDS_REPL,1)


def patch_geometry(text):
    if MARK in text:return text
    if GEOM_ANCHOR not in text:
        raise RuntimeError('1.6.6: Bauvorhaben-Auswertung nicht gefunden.')
    return text.replace(GEOM_ANCHOR,GEOM_REPL,1)


def main():
    if not APP.exists() or not CARDS.exists() or not GEOM.exists():
        raise RuntimeError('1.6.6: erforderliche Programmdateien nicht gefunden.')
    app=APP.read_text(encoding='utf-8')
    if f'APP_VERSION = "{NEW}"' in app:return 0
    if f'APP_VERSION = "{OLD}"' not in app:
        raise RuntimeError('Update 1.6.6 erwartet Projektzentrale 1.6.5.')

    cards_old=CARDS.read_text(encoding='utf-8');geom_old=GEOM.read_text(encoding='utf-8')
    cards_new=patch_cards(cards_old);geom_new=patch_geometry(geom_old)
    app_new=app.replace(f'APP_VERSION = "{OLD}"',f'APP_VERSION = "{NEW}"',1)
    app_new=app_new.replace('Projektzentrale 1.6.5','Projektzentrale 1.6.6')

    _compile_text(app_new,'app.py.1606.check')
    _compile_text(cards_new,'masterdata_v1604.py.1606.check')
    _compile_text(geom_new,'masterdata_v1601.py.1606.check')

    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for p in (APP,CARDS,GEOM):shutil.copy2(p,p.with_name(p.name+'.vor_1_6_6_'+stamp+'.bak'))
    tmp=APP.with_name('app.py.1606.tmp');tmp.write_text(app_new,encoding='utf-8');tmp.replace(APP)
    tmp=CARDS.with_name('masterdata_v1604.py.1606.tmp');tmp.write_text(cards_new,encoding='utf-8');tmp.replace(CARDS)
    tmp=GEOM.with_name('masterdata_v1601.py.1606.tmp');tmp.write_text(geom_new,encoding='utf-8');tmp.replace(GEOM)

    APP.with_name('patch_1606_report.txt').write_text(
        'OK: Projektzentrale 1.6.6 installiert.\n'
        'Projektname wird beim Öffnen der Projektakte aus dem echten Projektordner repariert, falls er versehentlich der Bauvorhaben-Bezeichnung entspricht.\n'
        'Bauvorhaben-Adresse wird zusätzlich direkt unterhalb der Bauvorhaben-Bezeichnung gesucht.\n',encoding='utf-8')
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except SystemExit:raise
    except Exception:
        try:APP.with_name('patch_1606_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception:pass
        raise
