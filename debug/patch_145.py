from pathlib import Path
import datetime
import py_compile
import re
import shutil
import sys

APP = Path(__file__).resolve().parent / 'app.py'


def replace_nested_function(src, name, new_block):
    pat = re.compile(rf'(?ms)^        def {re.escape(name)}\([^\n]*\):\n.*?(?=^        def |^    def |\Z)')
    m = pat.search(src)
    if not m:
        raise RuntimeError(f'Marker/Funktion {name} wurde nicht gefunden.')
    return src[:m.start()] + new_block.rstrip() + '\n\n' + src[m.end():]


GENERIC_READER = r'''        # 1.4.5: universelle, rein lesende mb-Projekt-/Positionsauswertung.
        # Der reale Projektordner ist die Identität. BSPos.mbdb wird nicht mehr an
        # einer einzigen festen Stelle erwartet; auch leicht abweichende Schemata
        # werden anhand ihrer Spalten erkannt. Keine mb-Datei wird geschrieben.
        def _mb_find_databases(folder):
            import sqlite3 as _sqlite3  # noqa: F401 - dokumentiert SQLite-Abhängigkeit lokal
            folder=Path(folder)
            found=[]; seen=set()
            preferred=(folder/'STATIK'/'BSPos.mbdb', folder/'Statik'/'BSPos.mbdb',
                       folder/'statik'/'BSPos.mbdb', folder/'BSPos.mbdb')
            for db in preferred:
                try:
                    if db.is_file():
                        key=str(db.resolve()).casefold()
                        if key not in seen: seen.add(key); found.append(db)
                except OSError:
                    pass
            try:
                for db in folder.rglob('*'):
                    try:
                        if not db.is_file() or db.name.casefold()!='bspos.mbdb': continue
                        key=str(db.resolve()).casefold()
                        if key not in seen: seen.add(key); found.append(db)
                    except OSError:
                        continue
            except OSError:
                pass
            return found

        def _mb_pick(data,*names):
            low={str(k).casefold():v for k,v in data.items()}
            for name in names:
                if name.casefold() in low: return low[name.casefold()]
            return None

        def _mb_group(pos,desc,module):
            p=(pos or '').strip().casefold(); d=(desc or '').strip().casefold(); m=(module or '').strip().casefold()
            section_names={'erdgeschoss','obergeschoss','dachgeschoss','gründung','gruendung','keller','carport','fundamente','dach'}
            if m.startswith('s960') or p in section_names:
                return 'Gliederung'
            if m.startswith(('s030','s031','s037')) or p.startswith('ws') or 'last' in p or 'last' in d:
                return 'Lasten / Grundlagen'
            if (m.startswith(('s009','s010','s011','s014')) or p in {'tb','vorbemerkung','s1'} or
                'titelblatt' in d or 'schlussseite' in d or 'bodengutachten' in d or 'grundlagen' in d):
                return 'Dokumente / Grundlagen'
            return 'Tragwerkspositionen'

        def _mb_find_position_table(con):
            names=[r[0] for r in con.execute("select name from sqlite_master where type in ('table','view')")]
            exact=next((n for n in names if str(n).casefold()=='bspositionen'),None)
            if exact: return exact
            best=None; bestscore=0
            for table in names:
                try:
                    cols=[r[1] for r in con.execute('pragma table_info("'+str(table).replace('"','""')+'")')]
                except Exception:
                    continue
                lc={str(c).casefold() for c in cols}; score=0
                if any(c in lc for c in ('strnameposition','nameposition','posname','position','positionsname')): score+=4
                if any(c in lc for c in ('strbeschreibungposition','beschreibungposition','beschreibung','bezeichnung','description')): score+=2
                if any(c in lc for c in ('strprogposition','progposition','programm','modul','program')): score+=2
                if any(c in lc for c in ('stridposition','idposition','posuuid','uuid','id')): score+=1
                if score>bestscore: bestscore=score; best=table
            return best if bestscore>=4 else None

        def read_mb_positions(folder):
            import sqlite3
            rows=[]; errors=[]; usable_db=False
            dbs=_mb_find_databases(folder)
            if not dbs:
                return [], 'Keine BSPos.mbdb im mb-Projekt gefunden.'
            for db in dbs:
                con=None
                try:
                    con=sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True)
                    con.row_factory=sqlite3.Row
                    table=_mb_find_position_table(con)
                    if not table:
                        errors.append(f'{db.name}: keine Positionstabelle erkannt'); continue
                    usable_db=True
                    sql='select * from "'+str(table).replace('"','""')+'"'
                    for rr in con.execute(sql):
                        data=dict(rr)
                        pos=_mb_pick(data,'strNamePosition','NamePosition','PosName','Position','Positionsname','Name')
                        desc=_mb_pick(data,'strBeschreibungPosition','BeschreibungPosition','Beschreibung','Bezeichnung','Description','Text')
                        module=_mb_pick(data,'strProgPosition','ProgPosition','Programm','Modul','Program','Module')
                        rid=_mb_pick(data,'strIDPosition','IDPosition','PosUUID','UUID','ID','PositionID')
                        order=_mb_pick(data,'PosOrder','Reihenfolge','nIndex','Index','Sortierung','Order')
                        results=_mb_pick(data,'Ergebnisse','Ergebnis','nErgebnisse','Result','Results')
                        locked=_mb_pick(data,'IstGesperrt','Gesperrt','Locked','IsLocked')
                        calc=_mb_pick(data,'Berechnungsstatus','CalcStatus','Status','CalculationStatus')
                        if not str(pos or '').strip() and not str(desc or '').strip(): continue
                        row={
                            'id':str(rid or ''), 'uuid':str(rid or ''),
                            'pos':str(pos or '').strip(), 'desc':str(desc or '').strip(),
                            'module':str(module or '').strip(),
                            'group':_mb_group(str(pos or ''),str(desc or ''),str(module or '')),
                            'order':order if order is not None else 0,
                            'row_order':order if order is not None else 0,
                            'results':results if results is not None else 0,
                            'locked':locked if locked is not None else 0,
                            'calc_status':calc if calc is not None else 0,
                            'status':calc if calc is not None else 0,
                            'art':'Position','type':'Position','_db':str(db)
                        }
                        rows.append(row)
                except Exception as e:
                    errors.append(f'{db.name}: {e}')
                finally:
                    try:
                        if con is not None: con.close()
                    except Exception:
                        pass
            uniq=[]; seen=set()
            for row in rows:
                key=('id',row['id'].casefold()) if row.get('id') else ('data',row['pos'].casefold(),row['desc'].casefold(),row['module'].casefold())
                if key in seen: continue
                seen.add(key); uniq.append(row)
            def _sortkey(row):
                try: order=float(row.get('order',0))
                except Exception: order=1e12
                return (order,row.get('pos','').casefold(),row.get('desc','').casefold())
            uniq.sort(key=_sortkey)
            if uniq: return uniq, (' · '.join(errors) if errors and not usable_db else None)
            if errors: return [], ' · '.join(errors)
            return [], None

        def read_mb_position_detail(folder,r):
            import sqlite3
            detail={'file_refs':0,'auswertung_types':[],'version':'','berechnet_mit':'','berechnung':'','calculation':'',
                    'output':'','ausgabe':'','output_len':0,'ausgabe_len':0,'db':''}
            db=None
            try:
                raw=r.get('_db') if isinstance(r,dict) else None
                if raw:
                    cand=Path(raw)
                    if cand.is_file(): db=cand
            except Exception:
                db=None
            if db is None:
                dbs=_mb_find_databases(folder)
                if dbs: db=dbs[0]
            if db is None:
                return detail,'Keine BSPos.mbdb gefunden.'
            detail['db']=str(db)
            pid=str((r or {}).get('id') or (r or {}).get('uuid') or '')
            if not pid:
                return detail,None
            con=None
            try:
                con=sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True); con.row_factory=sqlite3.Row
                tables={str(x[0]).casefold():x[0] for x in con.execute("select name from sqlite_master where type in ('table','view')")}
                def _qtable(name): return tables.get(name.casefold())
                t=_qtable('BSBerechnung')
                if t:
                    try:
                        rr=con.execute('select * from "'+str(t).replace('"','""')+'" where strIDPosition=? limit 1',(pid,)).fetchone()
                        if rr:
                            d=dict(rr); detail['version']=str(_mb_pick(d,'Version','Versionsnummer') or '')
                            detail['berechnet_mit']=str(_mb_pick(d,'BerechnetMit','Programmversion') or '')
                            detail['berechnung']=detail['berechnet_mit']; detail['calculation']=detail['berechnet_mit']
                    except Exception: pass
                t=_qtable('BSAuswertung')
                if t:
                    try:
                        vals=[]
                        for rr in con.execute('select * from "'+str(t).replace('"','""')+'" where strIDPosition=?',(pid,)):
                            typ=_mb_pick(dict(rr),'Typ','Type','Auswertungstyp')
                            if typ is not None and typ not in vals: vals.append(typ)
                        detail['auswertung_types']=vals
                    except Exception: pass
                t=_qtable('BSDateireferenzen')
                if t:
                    try:
                        detail['file_refs']=int(con.execute('select count(*) from "'+str(t).replace('"','""')+'" where strIDPosition=?',(pid,)).fetchone()[0])
                    except Exception: pass
                t=_qtable('BSPositionsausgaben')
                if t:
                    try:
                        candidates=[]
                        for rr in con.execute('select * from "'+str(t).replace('"','""')+'" where strIDPosition=?',(pid,)):
                            val=_mb_pick(dict(rr),'Ausgabe','Output','Text','Inhalt')
                            if val is not None:
                                if isinstance(val,bytes):
                                    try: val=val.decode('utf-8','replace')
                                    except Exception: val=str(val)
                                candidates.append(str(val))
                        if candidates:
                            out=max(candidates,key=len); detail['output']=out; detail['ausgabe']=out
                            detail['output_len']=len(out); detail['ausgabe_len']=len(out)
                    except Exception: pass
                return detail,None
            except Exception as e:
                return detail,str(e)
            finally:
                try:
                    if con is not None: con.close()
                except Exception: pass
'''

PROJECT_AUGMENT = r'''        # 1.4.5: vorhandene Erkennung ergänzen. Direkte Unterordner eines
        # mb-Software-Ordners gelten jeweils als eigenständiges mb-Projekt, sobald
        # eine .mbp-Leitdatei oder eine BSPos.mbdb vorhanden ist.
        try:
            _seen_mb=set()
            for _e in mb_projects:
                try: _seen_mb.add(str(Path(_e[0]).resolve()).casefold())
                except Exception: _seen_mb.add(str(Path(_e[0])).casefold())
            _mb_roots=[]; _root_seen=set()
            for _e in list(mb_projects):
                try:
                    _parent=Path(_e[0]).parent
                    _norm=''.join(ch for ch in _parent.name.casefold() if ch.isalnum())
                    if _norm in {'mbsoftware','mbaec'}:
                        _k=str(_parent.resolve()).casefold()
                        if _k not in _root_seen: _root_seen.add(_k); _mb_roots.append(_parent)
                except Exception:
                    pass
            if project_root.exists():
                try:
                    for _cand in project_root.rglob('*'):
                        try:
                            if not _cand.is_dir(): continue
                            _norm=''.join(ch for ch in _cand.name.casefold() if ch.isalnum())
                            if _norm not in {'mbsoftware','mbaec'}: continue
                            _k=str(_cand.resolve()).casefold()
                            if _k not in _root_seen: _root_seen.add(_k); _mb_roots.append(_cand)
                        except OSError:
                            continue
                except OSError:
                    pass
            for _mbroot in _mb_roots:
                try: _children=sorted((x for x in _mbroot.iterdir() if x.is_dir()),key=lambda x:x.name.casefold())
                except OSError: continue
                for _folder in _children:
                    try: _key=str(_folder.resolve()).casefold()
                    except Exception: _key=str(_folder).casefold()
                    if _key in _seen_mb: continue
                    try: _leads=sorted(_folder.glob('*.mbp'),key=lambda x:x.name.casefold())
                    except OSError: _leads=[]
                    _dbs=[]
                    try:
                        for _db in _folder.rglob('*'):
                            try:
                                if _db.is_file() and _db.name.casefold()=='bspos.mbdb': _dbs.append(_db); break
                            except OSError: continue
                    except OSError: pass
                    if not _leads and not _dbs: continue
                    _lead=None
                    for _x in _leads:
                        if _x.stem.casefold()==_folder.name.casefold(): _lead=_x; break
                    if _lead is None and _leads: _lead=_leads[0]
                    _lead_name=_lead.name if _lead else '—'
                    _stamp=_lead or (_dbs[0] if _dbs else None)
                    try: _changed=datetime.datetime.fromtimestamp(_stamp.stat().st_mtime).strftime('%d.%m.%Y %H:%M') if _stamp else '—'
                    except OSError: _changed='—'
                    try: _rel=str(_folder.relative_to(project_root))
                    except Exception: _rel=str(_folder)
                    mb_projects.append((_folder,_folder.name,_lead_name,_changed,_rel,'mb-Projekt erkannt'))
                    _seen_mb.add(_key)
            mb_projects.sort(key=lambda e:str(e[0]).casefold())
        except Exception:
            # Die bereits vorhandene Erkennung bleibt im Fehlerfall vollständig erhalten.
            pass

'''

OPEN_FUNCTION = r'''        def open_mb_project():
            r=selected_position.get('row')
            folder=(r or {}).get('_folder') or current_project.get('folder')
            if not folder:
                try: messagebox.showinfo('mb AEC','Bitte zuerst ein konkretes mb-Projekt oder eine Position auswählen.')
                except Exception: pass
                return
            folder=Path(folder)
            leads=[]
            try: leads=sorted(folder.glob('*.mbp'),key=lambda x:x.name.casefold())
            except OSError: leads=[]
            preferred=next((x for x in leads if x.stem.casefold()==folder.name.casefold()),None)
            if preferred is None and leads: preferred=leads[0]
            if preferred is None:
                try:
                    deep=sorted(folder.rglob('*.mbp'),key=lambda x:(len(x.parts),x.name.casefold()))
                    preferred=deep[0] if deep else None
                except OSError:
                    preferred=None
            if preferred is not None:
                self.open_external_path(preferred)
            else:
                self.open_external_path(folder)
'''

SELECT_FUNCTION = r'''            def select_mb_project(_evt=None):
                sel=tr.selection()
                if not sel:return
                iid=sel[0]; target=item_paths.get(iid)
                if item_names.get(iid)=='ALLE mb-PROJEKTE': load_all_positions()
                elif target: load_positions(target,item_names.get(iid,target.name))
'''


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.5"' in s:
        return 0
    source_version=None
    for v in ('1.4.4','1.4.3'):
        if f'APP_VERSION = "{v}"' in s:
            source_version=v; break
    if not source_version:
        raise RuntimeError('Update 1.4.5 erwartet Projektzentrale 1.4.3 oder 1.4.4. Es wurde nichts verändert.')

    # Version zuerst nur im Arbeitstext ändern; geschrieben wird erst nach py_compile.
    s=s.replace(f'APP_VERSION = "{source_version}"','APP_VERSION = "1.4.5"',1)

    marker="current_rows=[]; item_rows={}; current_project={'folder':None,'name':'ALLE mb-PROJEKTE'}; selected_position={'row':None}"
    if marker not in s:
        raise RuntimeError('Marker der mb-Positionsakte fehlt. Update nicht angewendet.')
    s=s.replace(marker, GENERIC_READER + '\n        ' + marker, 1)

    # Direkte Unterordner in mb-Software als eigenständige Projekte ergänzen.
    aug_marker='        # Baugrund / Bodengutachten:'
    if aug_marker not in s:
        raise RuntimeError('Marker vor Baugrundakte fehlt. Update nicht angewendet.')
    s=s.replace(aug_marker, PROJECT_AUGMENT + aug_marker, 1)

    # Reales Quellprojekt öffnen, nicht aus Namen raten.
    s=replace_nested_function(s,'open_mb_project',OPEN_FUNCTION)

    # In 1.4.4 war die Auswahl absichtlich immer Gesamtakte; für Diagnose und
    # tägliche Arbeit zeigt 1.4.5 bei Auswahl wieder genau dieses mb-Projekt.
    try:
        s=replace_nested_function(s,'select_mb_project',SELECT_FUNCTION)
    except RuntimeError:
        # Manche Zwischenstände definieren select_mb_project tiefer im if-Block;
        # dort wird unten zusätzlich per Textmarker korrigiert.
        pass

    forced="""            def select_mb_project(_evt=None):\n                sel=tr.selection()\n                if not sel:return\n                iid=sel[0]; target=item_paths.get(iid)\n                # 1.4.4: In einer verknüpften Projektakte zeigt die Positionsakte\n                # grundsätzlich alle mb-Positionen der Gesamtakte. Die Auswahl oben\n                # dient nur noch der Herkunft/Öffnung des mb-Projekts.\n                load_all_positions()\n"""
    if forced in s:
        s=s.replace(forced,SELECT_FUNCTION,1)

    # Sichtbarkeit: "ALLE" zählt nicht als echtes Projekt, braucht aber eine zusätzliche Zeile.
    s=s.replace("tr=ttk.Treeview(b_mb,columns=cols,show='headings',height=max(2,min(len(mb_projects),5)))",
                "tr=ttk.Treeview(b_mb,columns=cols,show='headings',height=max(3,min(len(mb_projects)+1,6)))",1)

    # Versionshinweise aktualisieren, ohne auf deren Vorhandensein angewiesen zu sein.
    s=s.replace('Hinweis 1.4.4: Positionsakte zeigt in einer verknüpften Projektakte standardmäßig immer alle mb-Positionen der Gesamtakte. Originaldateien bleiben read-only.',
                'Hinweis 1.4.5: Universelle mb-Projekt- und BSPos-Erkennung; Auswahl eines Projekts zeigt dessen Positionen, ALLE zeigt die Gesamtakte. Originaldateien bleiben read-only.')
    s=s.replace('Hinweis 1.4.3: Positionsakte kann alle mb-Projekte der verknüpften Gesamtakte gemeinsam anzeigen. Originaldateien bleiben read-only.',
                'Hinweis 1.4.5: Universelle mb-Projekt- und BSPos-Erkennung; Auswahl eines Projekts zeigt dessen Positionen, ALLE zeigt die Gesamtakte. Originaldateien bleiben read-only.')
    s=s.replace('Quelle: STATIK/BSPos.mbdb · SQLite mode=ro. 1.4.4 zeigt standardmäßig alle Positionen aus allen mb-Projekten der verknüpften Gesamtakte gemeinsam; mb-Daten bleiben read-only.',
                'Quelle: BSPos.mbdb wird im jeweiligen mb-Projekt automatisch gesucht · SQLite mode=ro · Originaldaten bleiben unverändert.')
    s=s.replace('Quelle: STATIK/BSPos.mbdb · SQLite mode=ro. 1.4.3 zeigt auf Wunsch alle Positionen aus allen mb-Projekten der verknüpften Gesamtakte gemeinsam; mb-Daten bleiben read-only.',
                'Quelle: BSPos.mbdb wird im jeweiligen mb-Projekt automatisch gesucht · SQLite mode=ro · Originaldaten bleiben unverändert.')

    # Sicherheitsprüfung gegen versehentliche Teilpatches.
    required=('APP_VERSION = "1.4.5"','def _mb_find_databases(folder):','def read_mb_positions(folder):',
              'def read_mb_position_detail(folder,r):','def open_mb_project():')
    if not all(x in s for x in required):
        raise RuntimeError('Patch-Ergebnis unvollständig. Es wurde nichts verändert.')

    tmp=APP.with_name('app.py.145.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.v{source_version.replace(".","")}_vor_145_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp.replace(APP)
    return 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:
            (Path(__file__).resolve().parent/'patch_145_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:
            pass
        print('FEHLER:',e)
        raise SystemExit(1)
