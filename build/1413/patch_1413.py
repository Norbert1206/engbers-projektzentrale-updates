from pathlib import Path
import datetime
import py_compile
import shutil

APP=Path(__file__).resolve().parent/'app.py'

MODEL_HELPER = r'''        _mb_model_cache={}
        def _mb_model_for_position(folder,r):
            """Identify the concrete mb model behind a position, read-only.

            MicroFe: finds the FEM database that really contains the selected
            position and uses its filename as stable model identifier.
            BauStatik: uses the project .mbp/BSPos container and tries to read a
            descriptive project/model title only from clearly named metadata
            fields. No mb file is ever modified.
            """
            try:
                import re, sqlite3
                from pathlib import Path
                base=Path(folder)
                pos=str(r.get('pos') or '').strip()
                app=_mb_application_for_position(folder,r)
                key=(str(base).lower(),pos.upper(),str(app))
                if key in _mb_model_cache:
                    return _mb_model_cache[key]

                def _q(name):
                    return '"'+str(name).replace('"','""')+'"'

                def _db_open_ro(db):
                    return sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True)

                def _clean(value):
                    if value is None:
                        return ''
                    txt=' '.join(str(value).replace('\x00',' ').split()).strip()
                    if len(txt)<3 or len(txt)>180:
                        return ''
                    if txt.lower() in {'none','null','true','false'}:
                        return ''
                    return txt

                def _db_title(db):
                    """Return only high-confidence model/project metadata."""
                    try:
                        con=_db_open_ro(db)
                        tables=[x[0] for x in con.execute("select name from sqlite_master where type='table'")]
                        strong=('modellname','modelname','projektbezeichnung','projectname','projekttitel','projecttitle','modeltitle')
                        weak=('bezeichnung','name','titel','title')
                        for table in tables:
                            try:
                                cols=[x[1] for x in con.execute(f'pragma table_info({_q(table)})')]
                            except Exception:
                                continue
                            tl=re.sub(r'[^a-z0-9]','',str(table).lower())
                            for col in cols:
                                cl=re.sub(r'[^a-z0-9]','',str(col).lower())
                                ok=any(k in cl for k in strong)
                                if not ok and ('projekt' in tl or 'project' in tl or 'modell' in tl or 'model' in tl):
                                    ok=any(k in cl for k in weak)
                                if not ok:
                                    continue
                                try:
                                    vals=con.execute(f'SELECT {_q(col)} FROM {_q(table)} WHERE {_q(col)} IS NOT NULL LIMIT 8').fetchall()
                                except Exception:
                                    continue
                                for row in vals:
                                    txt=_clean(row[0] if row else '')
                                    if txt and not _position_file_is_exact(pos,txt):
                                        con.close()
                                        return txt
                        con.close()
                    except Exception:
                        pass
                    return ''

                def _db_has_position(db):
                    if not pos:
                        return False
                    try:
                        con=_db_open_ro(db)
                        tables=[x[0] for x in con.execute("select name from sqlite_master where type='table'")]
                        for table in tables:
                            try:
                                info=con.execute(f'pragma table_info({_q(table)})').fetchall()
                            except Exception:
                                continue
                            # Prefer likely position columns, then textual/typeless columns.
                            cols=[]
                            for c in info:
                                name=c[1]; typ=str(c[2] or '').upper(); low=str(name).lower()
                                if any(k in low for k in ('pos','position','bez','name')) or any(k in typ for k in ('CHAR','TEXT','CLOB')) or not typ:
                                    cols.append(name)
                            for col in cols[:12]:
                                try:
                                    rows=con.execute(f'SELECT {_q(col)} FROM {_q(table)} WHERE CAST({_q(col)} AS TEXT) LIKE ? LIMIT 30',(f'%{pos}%',)).fetchall()
                                except Exception:
                                    continue
                                for row in rows:
                                    if row and _position_file_is_exact(pos,row[0]):
                                        con.close()
                                        return True
                        con.close()
                    except Exception:
                        pass
                    return False

                result={'name':'—','source':'—','app':app,'confidence':'fallback'}

                if str(app).lower()=='microfe':
                    fem=base/'FEM'
                    dbs=sorted(fem.glob('*.mbdb')) if fem.exists() else []
                    chosen=None
                    for db in dbs:
                        if _db_has_position(db):
                            chosen=db
                            break
                    if chosen is None and len(dbs)==1:
                        chosen=dbs[0]
                    if chosen is not None:
                        title=_db_title(chosen)
                        result={
                            'name':title or chosen.stem,
                            'source':str(chosen.relative_to(base)) if chosen.is_relative_to(base) else str(chosen),
                            'app':app,
                            'confidence':'position' if _db_has_position(chosen) else 'single',
                        }
                else:
                    # BauStatik positions live in BSPos.mbdb; the .mbp is the
                    # model/project container opened by the mb ProjectManager.
                    bs=base/'BSPos.mbdb'
                    mbps=sorted(base.glob('*.mbp'))
                    title=''
                    if bs.exists():
                        title=_db_title(bs)
                    source=bs if bs.exists() else (mbps[0] if mbps else None)
                    if not title and mbps:
                        # Conservative text metadata lookup; no guessing from random binary strings.
                        try:
                            raw=mbps[0].read_bytes()[:2_000_000]
                            texts=[]
                            for enc in ('utf-8','utf-16','cp1252'):
                                try:texts.append(raw.decode(enc,errors='ignore'))
                                except Exception:pass
                            pat=re.compile(r'(?i)(?:Projektbezeichnung|ProjectName|ModelName|ModellName|ProjektTitel|ProjectTitle)\s*[=:>]\s*["\']?([^"\'\r\n<>]{3,180})')
                            for txt in texts:
                                m=pat.search(txt)
                                if m:
                                    cand=_clean(m.group(1))
                                    if cand:
                                        title=cand; break
                        except Exception:
                            pass
                    fallback=mbps[0].stem if mbps else base.name
                    result={
                        'name':title or fallback,
                        'source':str(source.relative_to(base)) if source is not None and source.is_relative_to(base) else (str(source) if source else '—'),
                        'app':app,
                        'confidence':'metadata' if title else 'container',
                    }

                _mb_model_cache[key]=result
                return result
            except Exception:
                return {'name':'—','source':'—','app':'—','confidence':'error'}
'''


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.13"' in s:
        return 0
    if 'APP_VERSION = "1.4.12"' not in s:
        raise RuntimeError('Update 1.4.13 erwartet Projektzentrale 1.4.12. Es wurde nichts verändert.')
    original=s
    s=s.replace('APP_VERSION = "1.4.12"','APP_VERSION = "1.4.13"',1)

    marker='        def _detail_add_link(text,label,path,tag_index):'
    if marker not in s:
        raise RuntimeError('1.4.13 Marker für Positionsakte-Helfer fehlt.')
    if 'def _mb_model_for_position' not in s:
        s=s.replace(marker,MODEL_HELPER+'\n'+marker,1)

    old_meta="""                mb_app=_mb_application_for_position(folder,r)
                posid=str(r.get('pos') or '').strip() or '—'
                detail_text.insert('end',f'Position: {posid}\\nBezeichnung: {bez}\\n\\nmb-Projekt: {projekt}\\nmb-Modul: {modul}\\nmb-Anwendung: {mb_app}\\nFachgruppe: {gruppe}\\nBerechnungsstatus: {status}\\n')
"""
    new_meta="""                mb_app=_mb_application_for_position(folder,r)
                posid=str(r.get('pos') or '').strip() or '—'
                mb_model=_mb_model_for_position(folder,r)
                model_name=mb_model.get('name') or '—'
                model_source=mb_model.get('source') or '—'
                detail_text.insert('end',f'Position: {posid}\\nBezeichnung: {bez}\\n\\nmb-Projekt: {projekt}\\nmb-Modul: {modul}\\nmb-Anwendung: {mb_app}\\nmb-Modell: {model_name}\\nModellquelle: {model_source}\\nFachgruppe: {gruppe}\\nBerechnungsstatus: {status}\\n')
"""
    if old_meta not in s:
        raise RuntimeError('1.4.13 Marker für Positions-Metadaten fehlt.')
    s=s.replace(old_meta,new_meta,1)

    s=s.replace(
        'Hinweis 1.4.12: Positionsakte mit exakter Positionszuordnung. E.01.D wird nicht mehr mit E.01.DS-1 usw. verwechselt; Schreibweisen wie E01D und E_01_D bleiben kompatibel. BauStatik/MicroFe-Erkennung bleibt read-only.',
        'Hinweis 1.4.13: Positionsakte erkennt zusätzlich die konkrete mb-Modellquelle. MicroFe-Positionen werden der passenden FEM-Datenbank zugeordnet; BauStatik zeigt den Projekt-/Modellcontainer. Alle mb-Daten bleiben read-only.'
    )
    s=s.replace(
        'Quelle: BSPos.mbdb und FEM/*.mbdb werden je mb-Projekt ausschließlich read-only gelesen. Positionsakte 1.4.12 erkennt BauStatik/MicroFe und ordnet Projektdateien nur bei exakter Positionskennung zu.',
        'Quelle: BSPos.mbdb, *.mbp und FEM/*.mbdb werden ausschließlich read-only gelesen. Positionsakte 1.4.13 zeigt Anwendung, Modellkennung und Modellquelle je Position; Dateizuordnung bleibt positionsgenau.'
    )

    required=(
        'APP_VERSION = "1.4.13"',
        'def _mb_model_for_position',
        "mb_model=_mb_model_for_position(folder,r)",
        "mb-Modell: {model_name}",
        "Modellquelle: {model_source}",
        'Startweg: ProjektManager → MicroFe',
        'def _position_file_is_exact',
    )
    if not all(x in s for x in required):
        raise RuntimeError('Patch-Ergebnis 1.4.13 unvollständig. Es wurde nichts verändert.')
    if s==original:
        raise RuntimeError('Keine Änderung erzeugt.')

    tmp=APP.with_name('app.py.1413.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.v1412_vor_1413_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp.replace(APP)
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1413_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        print('FEHLER:',e)
        raise SystemExit(1)
