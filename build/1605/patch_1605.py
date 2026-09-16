from pathlib import Path
import datetime
import os
import py_compile
import re
import shutil
import sqlite3
import traceback

BASE=Path(__file__).resolve().parent
APP=BASE/'app.py'
CARDS=BASE/'masterdata_v1604.py'
GEOM=BASE/'masterdata_v1601.py'
OLD='1.6.4'; NEW='1.6.5'
MARK='PZ_MASTERDATA_NAME_ADDRESS_FIX_V1605'

OLD_SAVE="c.execute('UPDATE projects SET title=?,address=?,client=?,architect=? WHERE id=?',(d['project_title'] or r['title'],address or r['address'],d['client_name'] or r['client'],arch or r['architect'],app.project_id))"
NEW_SAVE="c.execute('UPDATE projects SET address=?,client=?,architect=? WHERE id=?',(address or r['address'],d['client_name'] or r['client'],arch or r['architect'],app.project_id))"

OLD_LOC="""    _,loc,lval,lx=_best(frags,LABELS['location'])\n    if loc:\n        txt=lval or ' '.join(f['text'] for f in _below(frags,loc,lx,max_lines=2,depth=60));a=_address(txt)\n        if a:d.update(project_street=a['street'],project_zip=a['zip'],project_city=a['city'])\n"""
NEW_LOC="""    _,loc,lval,lx=_best(frags,LABELS['location'])\n    if loc:\n        # PZ_MASTERDATA_NAME_ADDRESS_FIX_V1605: Bauort steht in CAD-Plankoepfen\n        # haeufig zweizeilig: Strasse rechts vom Label, PLZ/Ort darunter.\n        parts=[]\n        if lval: parts.append(lval)\n        below=_below(frags,loc,lx,max_lines=5,depth=110)\n        parts.extend(f['text'] for f in below)\n        txt=' '.join(parts)\n        a=_address(txt)\n        if not a:\n            # Zweiter Versuch: alle geometrisch nahen Textfragmente rechts/unterhalb\n            # des Bauort-/Grundstueck-Labels in Lesereihenfolge zusammensetzen.\n            near=[]\n            x0=lx if lx is not None else loc['x']\n            for f in frags:\n                if f['page']!=loc['page'] or f is loc: continue\n                dy=loc['y']-f['y']\n                if -8<=dy<=125 and f['x']>=x0-35 and f['x']<loc['W']*.99:\n                    if any(_has(f['text'],x) for x in ALL_LABELS): continue\n                    near.append((max(0,dy),f['x'],f['text']))\n            near.sort(key=lambda z:(z[0],z[1]))\n            a=_address(' '.join(z[2] for z in near[:8]))\n        if a:d.update(project_street=a.get('street',''),project_zip=a.get('zip',''),project_city=a.get('city',''))\n"""


def _compile_text(text,name):
    p=BASE/name
    try:
        p.write_text(text,encoding='utf-8')
        py_compile.compile(str(p),doraise=True)
    finally:
        try:p.unlink()
        except Exception:pass


def patch_cards(text):
    if OLD_SAVE in text:
        return text.replace(OLD_SAVE,NEW_SAVE,1)
    if NEW_SAVE in text:
        return text
    raise RuntimeError('1.6.5: Speicherlogik in masterdata_v1604.py nicht gefunden.')


def patch_geometry(text):
    if MARK in text:
        return text
    if OLD_LOC not in text:
        raise RuntimeError('1.6.5: Bauort-Auswertung in masterdata_v1601.py nicht gefunden.')
    return text.replace(OLD_LOC,NEW_LOC,1)


def _candidate_db_files():
    out=[]
    local=os.environ.get('LOCALAPPDATA','')
    if local:
        root=Path(local)/'Engbers Projektzentrale'
        direct=root/'data'/'engbers_projekte.sqlite'
        if direct.exists():out.append(direct)
        if root.exists():
            try:
                for p in root.rglob('engbers_projekte.sqlite'):
                    if p not in out:out.append(p)
            except Exception:pass
    return out


def _folder_project_name(number,folder):
    try:name=Path(str(folder or '')).name.strip()
    except Exception:return ''
    if not name:return ''
    num=str(number or '').strip()
    if num:
        m=re.match(r'^'+re.escape(num)+r'\s*[.·_\-]*\s*(.+)$',name,re.I)
        if m:return m.group(1).strip()
    m=re.match(r'^\d{2}-\d{3}\s*[.·_\-]*\s*(.+)$',name)
    return m.group(1).strip() if m else ''


def repair_accidental_titles():
    repaired=[]
    for dbp in _candidate_db_files():
        try:
            con=sqlite3.connect(str(dbp));con.row_factory=sqlite3.Row
            cols={r['name'] for r in con.execute('PRAGMA table_info(projects)').fetchall()}
            if not {'id','number','title','folder'}.issubset(cols):
                con.close();continue
            mdcols={r['name'] for r in con.execute('PRAGMA table_info(project_masterdata)').fetchall()}
            if not {'project_id','project_title'}.issubset(mdcols):
                con.close();continue
            rows=con.execute('''SELECT p.id,p.number,p.title,p.folder,m.project_title
                                FROM projects p JOIN project_masterdata m ON m.project_id=p.id''').fetchall()
            for r in rows:
                current=str(r['title'] or '').strip(); master=str(r['project_title'] or '').strip()
                if not current or not master or current.casefold()!=master.casefold():continue
                restored=_folder_project_name(r['number'],r['folder'])
                if restored and restored.casefold()!=current.casefold():
                    con.execute('UPDATE projects SET title=? WHERE id=?',(restored,r['id']))
                    repaired.append(f"{r['number']}: {current} -> {restored}")
            con.commit();con.close()
        except Exception:
            try:con.close()
            except Exception:pass
    return repaired


def main():
    if not APP.exists() or not CARDS.exists() or not GEOM.exists():
        raise RuntimeError('1.6.5: erforderliche Programmdateien nicht gefunden.')
    app=APP.read_text(encoding='utf-8')
    if f'APP_VERSION = "{NEW}"' in app and MARK in app:
        return 0
    if f'APP_VERSION = "{OLD}"' not in app:
        raise RuntimeError('Update 1.6.5 erwartet Projektzentrale 1.6.4.')

    cards_old=CARDS.read_text(encoding='utf-8');geom_old=GEOM.read_text(encoding='utf-8')
    cards_new=patch_cards(cards_old);geom_new=patch_geometry(geom_old)
    app_new=app.replace(f'APP_VERSION = "{OLD}"',f'APP_VERSION = "{NEW}"',1)
    app_new=app_new.replace('Projektzentrale 1.6.4','Projektzentrale 1.6.5')
    anchor='PZ_MASTERDATA_CARDS_V1604'
    if anchor not in app_new:raise RuntimeError('1.6.5: 1.6.4-Kachelansicht nicht gefunden.')
    app_new=app_new.replace(anchor,anchor+'\n        # '+MARK,1)

    _compile_text(app_new,'app.py.1605.check')
    _compile_text(cards_new,'masterdata_v1604.py.1605.check')
    _compile_text(geom_new,'masterdata_v1601.py.1605.check')

    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for p in (APP,CARDS,GEOM):shutil.copy2(p,p.with_name(p.name+'.vor_1_6_5_'+stamp+'.bak'))
    tmp=APP.with_name('app.py.1605.tmp');tmp.write_text(app_new,encoding='utf-8');tmp.replace(APP)
    tmp=CARDS.with_name('masterdata_v1604.py.1605.tmp');tmp.write_text(cards_new,encoding='utf-8');tmp.replace(CARDS)
    tmp=GEOM.with_name('masterdata_v1601.py.1605.tmp');tmp.write_text(geom_new,encoding='utf-8');tmp.replace(GEOM)

    repaired=repair_accidental_titles()
    report=['OK: Projektzentrale 1.6.5 installiert.',
            'Projektname und Bauvorhaben-Bezeichnung sind jetzt getrennt.',
            'Bauort-Erkennung kombiniert Strasse sowie PLZ/Ort aus mehrzeiligen CAD-Plankoepfen.']
    if repaired:report.append('Automatisch reparierte Projektnamen: '+'; '.join(repaired))
    else:report.append('Automatische Projektnamen-Reparatur: kein passender Datensatz gefunden oder nicht erforderlich.')
    APP.with_name('patch_1605_report.txt').write_text('\n'.join(report)+'\n',encoding='utf-8')
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except SystemExit:raise
    except Exception:
        try:APP.with_name('patch_1605_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception:pass
        raise
