from pathlib import Path
import datetime
import py_compile
import shutil

APP=Path(__file__).resolve().parent/'app.py'

MANUAL_HELPER = r'''        def _position_plan_scope(pos):
            """Map an mb position to the project-wide plan scope used for manual assignment."""
            try:
                import re
                parts=re.findall(r'[A-Z]+|[0-9]+',str(pos or '').upper())
                head=parts[0] if parts else ''
                if head=='E': return 'EG'
                if head=='1': return 'OG'
                if head=='F': return 'SOHLE'
                if head=='G': return 'GARAGE'
                return 'POSITION'
            except Exception:
                return 'POSITION'

        def _position_manual_plan_store(folder):
            try:
                return _position_project_root(folder)/'.engbers_positionsplaene.json'
            except Exception:
                return Path(folder)/'.engbers_positionsplaene.json'

        def _position_manual_plan_load(folder):
            try:
                import json
                store=_position_manual_plan_store(folder)
                if not store.exists(): return {'version':1,'plans':{}}
                data=json.loads(store.read_text(encoding='utf-8'))
                if not isinstance(data,dict): return {'version':1,'plans':{}}
                if not isinstance(data.get('plans'),dict): data['plans']={}
                return data
            except Exception:
                return {'version':1,'plans':{}}

        def _position_manual_plan_files(folder,pos):
            """Return a persistent, user-confirmed Positionsplan assignment for this floor."""
            try:
                base=_position_project_root(folder).resolve()
                scope=_position_plan_scope(pos)
                data=_position_manual_plan_load(folder)
                entry=data.get('plans',{}).get(scope)
                if not isinstance(entry,dict): return []
                rel=str(entry.get('path') or '').strip()
                if not rel: return []
                p=(base/rel).resolve()
                try: p.relative_to(base)
                except Exception: return []
                if not p.exists() or not p.is_file(): return []
                try: ts=p.stat().st_mtime
                except Exception: ts=0
                try: shown=str(p.relative_to(base))
                except Exception: shown=str(p)
                return [(1000,ts,'Pläne / CAD',p,shown+f'  [Positionsplan {scope} – dauerhaft zugeordnet]')]
            except Exception:
                return []

        def _position_assign_plan(folder,pos):
            """Let the user select one project file and store it as Positionsplan for the floor."""
            try:
                import json, datetime as _dt
                from tkinter import filedialog, messagebox
                base=_position_project_root(folder).resolve()
                scope=_position_plan_scope(pos)
                selected=filedialog.askopenfilename(
                    title=f'Positionsplan {scope} dauerhaft zuordnen',
                    initialdir=str(base),
                    filetypes=[
                        ('Plan-Dateien','*.pdf *.dwg *.dxf *.dgn *.ifc *.plt *.hpgl'),
                        ('PDF','*.pdf'),
                        ('Alle Dateien','*.*'),
                    ],
                )
                if not selected: return False
                p=Path(selected).resolve()
                try:
                    rel=p.relative_to(base)
                except Exception:
                    messagebox.showwarning('Positionsplan','Bitte eine Datei innerhalb des aktuellen Projektordners auswählen.')
                    return False
                data=_position_manual_plan_load(folder)
                data.setdefault('plans',{})[scope]={
                    'path':str(rel),
                    'assigned_at':_dt.datetime.now().isoformat(timespec='seconds'),
                }
                store=_position_manual_plan_store(folder)
                store.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                messagebox.showinfo('Positionsplan',f'Positionsplan {scope} wurde dauerhaft zugeordnet.\n\nPosition bitte einmal erneut anklicken.')
                return True
            except Exception as exc:
                try:
                    from tkinter import messagebox
                    messagebox.showwarning('Positionsplan',f'Zuordnung konnte nicht gespeichert werden:\n{exc}')
                except Exception:
                    pass
                return False

        def _position_remove_manual_plan(folder,pos):
            try:
                import json
                from tkinter import messagebox
                scope=_position_plan_scope(pos)
                data=_position_manual_plan_load(folder)
                plans=data.setdefault('plans',{})
                if scope not in plans: return False
                if not messagebox.askyesno('Positionsplan',f'Dauerhafte Zuordnung für Positionsplan {scope} entfernen?'):
                    return False
                plans.pop(scope,None)
                _position_manual_plan_store(folder).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                messagebox.showinfo('Positionsplan',f'Zuordnung für Positionsplan {scope} wurde entfernt.\n\nPosition bitte einmal erneut anklicken.')
                return True
            except Exception:
                return False
'''


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.29"' in s:
        return 0
    if 'APP_VERSION = "1.4.28"' not in s:
        raise RuntimeError('Update 1.4.29 erwartet Projektzentrale 1.4.28. Es wurde nichts verändert.')
    original=s
    s=s.replace('APP_VERSION = "1.4.28"','APP_VERSION = "1.4.29"',1)

    marker='        def _position_context_plan_files(folder,pos):'
    if marker not in s:
        raise RuntimeError('1.4.29 Marker für Plan-Helfer fehlt.')
    if 'def _position_assign_plan(folder,pos)' not in s:
        s=s.replace(marker,MANUAL_HELPER+'\n'+marker,1)

    old="""                matches.sort(key=lambda _h:((_h[0] if len(_h)>0 else 0),(_h[1] if len(_h)>1 else 0)),reverse=True)
                detail_text.insert('end',f'\\nVERKNÜPFTE PROJEKTDATEIEN ({len(matches)})\\n')
                if matches:
"""
    new="""                for _hit in _position_manual_plan_files(folder,r.get('pos')):
                    try:_key=str(Path(_hit[3]).resolve()).lower()
                    except Exception:_key=str(_hit[3]).lower()
                    _new_matches=[]
                    for _old_hit in matches:
                        try:_old_key=str(Path(_old_hit[3]).resolve()).lower()
                        except Exception:_old_key=str(_old_hit[3]).lower()
                        if _old_key!=_key: _new_matches.append(_old_hit)
                    matches=_new_matches
                    matches.append(_hit); _seen_files.add(_key)
                matches.sort(key=lambda _h:((_h[0] if len(_h)>0 else 0),(_h[1] if len(_h)>1 else 0)),reverse=True)
                detail_text.insert('end',f'\\nVERKNÜPFTE PROJEKTDATEIEN ({len(matches)})\\n')
                _scope=_position_plan_scope(r.get('pos'))
                _assign_tag='posplan_assign_'+str(abs(hash((str(folder),str(r.get('pos'))))))
                detail_text.insert('end',f'• Positionsplan {_scope} dauerhaft zuordnen … (Doppelklick)\\n',_assign_tag)
                detail_text.tag_config(_assign_tag,underline=True)
                detail_text.tag_bind(_assign_tag,'<Double-1>',lambda _e,_f=folder,_p=r.get('pos'):_position_assign_plan(_f,_p))
                if _position_manual_plan_files(folder,r.get('pos')):
                    _remove_tag='posplan_remove_'+str(abs(hash((str(folder),str(r.get('pos'))))))
                    detail_text.insert('end',f'• Zuordnung Positionsplan {_scope} entfernen … (Doppelklick)\\n',_remove_tag)
                    detail_text.tag_config(_remove_tag,underline=True)
                    detail_text.tag_bind(_remove_tag,'<Double-1>',lambda _e,_f=folder,_p=r.get('pos'):_position_remove_manual_plan(_f,_p))
                detail_text.insert('end','\\n')
                if matches:
"""
    if old not in s:
        raise RuntimeError('1.4.29 Marker für verknüpfte Projektdateien fehlt.')
    s=s.replace(old,new,1)

    s=s.replace(
        'Hinweis 1.4.28: Plan-Kandidaten werden robuster erkannt. Auch Schreibweisen wie Pos.-Plan, Pos Plan oder Positionsplan sowie Dateien in plan-/CAD-typischen Ordnern werden als mögliche Zuordnung angeboten. Exakte Treffer bleiben höher bewertet.',
        'Hinweis 1.4.29: Positionspläne können pro Geschoss einmal manuell und dauerhaft zugeordnet werden. Die Zuordnung wird projektbezogen in .engbers_positionsplaene.json gespeichert und anschließend allen Positionen des Geschosses angeboten; sie kann auch wieder entfernt werden.'
    )
    s=s.replace(
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb, Windows-Dateizuordnungen und Projektdateien werden ausschließlich read-only gelesen. Positionsakte 1.4.28 normalisiert Planbezeichnungen und bietet zusätzlich planartige Projektdateien als mögliche Zuordnung an; mb-Daten und Registry bleiben unverändert.',
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb, Windows-Dateizuordnungen und Projektdateien werden read-only gelesen. Positionsakte 1.4.29 kann zusätzlich eine vom Benutzer bestätigte Positionsplan-Zuordnung als eigene Projektzentrale-Metadatei im Projektordner speichern; mb-Daten und Registry bleiben unverändert.'
    )

    required=(
        'APP_VERSION = "1.4.29"',
        'def _position_assign_plan(folder,pos)',
        'def _position_manual_plan_files(folder,pos)',
        "'.engbers_positionsplaene.json'",
        'dauerhaft zuordnen … (Doppelklick)',
        "for _hit in _position_manual_plan_files(folder,r.get('pos'))",
        'def _position_remove_manual_plan(folder,pos)',
    )
    if not all(x in s for x in required):
        raise RuntimeError('Patch-Ergebnis 1.4.29 unvollständig. Es wurde nichts verändert.')
    if s==original:
        raise RuntimeError('Keine Änderung erzeugt.')

    tmp=APP.with_name('app.py.1429.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.v1428_vor_1429_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp.replace(APP)
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1429_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        print('FEHLER:',e)
        raise SystemExit(1)
