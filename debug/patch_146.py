from pathlib import Path
import datetime
import py_compile
import shutil
import sys

APP=Path(__file__).resolve().parent/'app.py'

INSERT=r'''        # 1.4.6: Positionsakte 2.0 – bestehende Anzeige unangetastet lassen,
        # aber Zaehler eindeutiger machen und automatisch passende Projektdateien
        # zur markierten mb-Position finden. Alles rein lesend.
        _rebuild_positions_145 = rebuild_positions
        def rebuild_positions(*_args):
            _rebuild_positions_145(*_args)
            try:
                visible=sum(1 for iid in list(item_rows.keys()) if ptr.exists(iid))
                project_name=current_project.get('name') or 'mb-Projekt'
                pos_info.config(text=f'{project_name} · {len(current_rows)} DB-Einträge gelesen · {visible} Positionszeilen sichtbar',fg=INK)
            except Exception:
                pass

        _position_files_cache={'files':None}
        _position_match_cache={}
        def _position_candidate_files():
            if _position_files_cache['files'] is not None:
                return _position_files_cache['files']
            out=[]
            allowed={'.pdf','.doc','.docx','.xls','.xlsx','.xlsm','.dwg','.dxf','.ndw','.npl','.jpg','.jpeg','.png','.tif','.tiff','.eml','.msg','.txt'}
            try:
                for p in project_root.rglob('*'):
                    try:
                        if not p.is_file() or p.suffix.casefold() not in allowed:
                            continue
                        rel=p.relative_to(project_root)
                        low=str(rel).replace('\\','/').casefold()
                        # mb-interne Dateien sind Quelle, aber keine externe Positionsverknuepfung.
                        if '/mb-software/' in '/'+low+'/' or '/mbaec/' in '/'+low+'/':
                            continue
                        out.append((p,rel,low))
                    except (OSError,ValueError):
                        continue
            except OSError:
                pass
            _position_files_cache['files']=out
            return out

        def _position_file_matches(row):
            pos=str((row or {}).get('pos') or '').strip()
            if not pos:
                return []
            key=pos.casefold()
            if key in _position_match_cache:
                return _position_match_cache[key]
            exact=key.replace(' ','')
            compact=''.join(ch for ch in key if ch.isalnum())
            parts=[x for x in __import__('re').split(r'[^0-9a-zäöüß]+',key) if x]
            matches=[]
            for p,rel,low in _position_candidate_files():
                low_no_space=low.replace(' ','')
                norm=''.join(ch for ch in low if ch.isalnum())
                hit=False; score=0
                if exact and exact in low_no_space:
                    hit=True; score+=100
                if compact and len(compact)>=4 and compact in norm:
                    hit=True; score+=80
                if len(parts)>=2 and all(part in low for part in parts if len(part)>=2):
                    hit=True; score+=30
                if not hit:
                    continue
                if 'prüf' in low or 'pruef' in low:
                    cat='Prüfstatik'; score+=12
                elif any(x in low for x in ('plan','allplan','cad','.dwg','.dxf','.ndw','.npl')):
                    cat='Pläne / CAD'; score+=10
                elif any(x in low for x in ('nachweis','berechnung','statik','bemessung')):
                    cat='Eigene Nachweise'; score+=8
                else:
                    cat='Dokumente'
                try: ts=p.stat().st_mtime
                except OSError: ts=0
                matches.append((score,ts,cat,p,rel))
            matches.sort(key=lambda x:(-x[0],-x[1],str(x[4]).casefold()))
            result=matches[:12]
            _position_match_cache[key]=result
            return result

        _position_selected_145 = position_selected
        def position_selected(_evt=None):
            _position_selected_145(_evt)
            try:
                sel=ptr.selection()
                if not sel:return
                r=item_rows.get(sel[0])
                if not r:return
                lines=[]
                dbsrc=str(r.get('_db') or '').strip()
                if dbsrc:
                    try: dbsrc=str(Path(dbsrc).relative_to(project_root))
                    except Exception: pass
                    lines.append('\\nMB-QUELLE\\n'+dbsrc)
                matches=_position_file_matches(r)
                lines.append('\\n\\nVERKNÜPFTE PROJEKTDATEIEN · AUTOMATISCH')
                if matches:
                    for _score,_ts,cat,_p,rel in matches:
                        lines.append(f'• {cat}: {rel}')
                else:
                    lines.append('Noch keine Datei anhand der Positionsnummer eindeutig zuordenbar.')
                lines.append('\\nDie Zuordnung ist nur eine Lese-/Suchansicht; Originaldateien werden nicht verändert.')
                detail_text.config(state='normal')
                detail_text.insert('end',''.join(lines))
                detail_text.config(state='disabled')
            except Exception:
                try: detail_text.config(state='disabled')
                except Exception: pass
'''

def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.6"' in s:
        return 0
    if 'APP_VERSION = "1.4.5"' not in s:
        raise RuntimeError('Update 1.4.6 erwartet Projektzentrale 1.4.5. Es wurde nichts verändert.')
    s=s.replace('APP_VERSION = "1.4.5"','APP_VERSION = "1.4.6"',1)
    marker="        ptr.bind('<<TreeviewSelect>>',position_selected)"
    if marker not in s:
        raise RuntimeError('Marker der Positionsakte wurde nicht gefunden. Update nicht angewendet.')
    s=s.replace(marker,INSERT+'\n'+marker,1)
    s=s.replace('Hinweis 1.4.5: Universelle mb-Projekt- und BSPos-Erkennung; Auswahl eines Projekts zeigt dessen Positionen, ALLE zeigt die Gesamtakte. Originaldateien bleiben read-only.',
                'Hinweis 1.4.6: Positionsakte 2.0 ergänzt eindeutige DB-/Sichtbarkeitszähler und sucht passend zur mb-Position automatisch Projektdateien. Originaldateien bleiben read-only.')
    s=s.replace('Quelle: BSPos.mbdb wird im jeweiligen mb-Projekt automatisch gesucht · SQLite mode=ro · Originaldaten bleiben unverändert.',
                'Quelle: BSPos.mbdb wird je mb-Projekt automatisch gesucht · SQLite mode=ro. 1.4.6 verknüpft Positionsnummern zusätzlich rein lesend mit passenden Projektdateien.')
    required=('APP_VERSION = "1.4.6"','_position_file_matches','VERKNÜPFTE PROJEKTDATEIEN','_rebuild_positions_145')
    if not all(x in s for x in required):
        raise RuntimeError('Patch-Ergebnis unvollständig. Es wurde nichts verändert.')
    tmp=APP.with_name('app.py.146.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.v145_vor_146_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp.replace(APP)
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_146_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        print('FEHLER:',e)
        raise SystemExit(1)
