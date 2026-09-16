from pathlib import Path
import datetime
import py_compile
import shutil

APP=Path(__file__).resolve().parent/'app.py'

STATUS_UI = r'''        # 1.4.33: Bearbeitungsstatus direkt in der Positionsliste.
        # Bestehende mb-/Dateidaten bleiben unverändert; gelesen wird nur die
        # Projektzentrale-Metadatei .engbers_positionsakte.json.
        _position_status_values=('Offen','In Bearbeitung','Geprüft','Änderung erforderlich','Erledigt')

        def _position_status_row_folder(row):
            try:
                raw=(row or {}).get('_folder')
                if raw:
                    return Path(raw)
            except Exception:
                pass
            try:
                raw=(row or {}).get('_db')
                if raw:
                    db=Path(raw)
                    candidates=[db.parent]
                    candidates.extend(list(db.parents)[:5])
                    for cand in candidates:
                        try:
                            if cand.is_dir() and any(cand.glob('*.mbp')):
                                return cand
                        except Exception:
                            pass
            except Exception:
                pass
            try:
                raw=current_project.get('folder')
                if raw:
                    return Path(raw)
            except Exception:
                pass
            return None

        def _position_status_row_key(row):
            try:
                folder=_position_status_row_folder(row)
                fkey=str(folder.resolve()).casefold() if folder else ''
            except Exception:
                fkey=str(_position_status_row_folder(row) or '').casefold()
            return (fkey,str((row or {}).get('pos') or '').strip().upper())

        def _position_status_for_row(row):
            try:
                folder=_position_status_row_folder(row)
                pos=str((row or {}).get('pos') or '').strip()
                if not folder or not pos:
                    return 'Offen'
                status=str(_position_record_get(folder,pos).get('status') or 'Offen')
                return status if status in _position_status_values else 'Offen'
            except Exception:
                return 'Offen'

        # Zusätzliche Statusspalte rechts an die bestehende Positionsliste anhängen.
        try:
            _cols=list(ptr.cget('columns'))
            if 'pz_bearbeitung' not in _cols:
                _cols.append('pz_bearbeitung')
                ptr.configure(columns=tuple(_cols))
            ptr.heading('pz_bearbeitung',text='Bearbeitung')
            ptr.column('pz_bearbeitung',width=130,minwidth=105,stretch=False,anchor='w')
        except Exception:
            pass

        try:
            import tkinter as _tk
            _position_status_filter_var=_tk.StringVar(value='Alle')
        except Exception:
            _position_status_filter_var=None

        def _position_status_current_key():
            try:
                sel=ptr.selection()
                if sel:
                    row=item_rows.get(sel[0])
                    if row:
                        return _position_status_row_key(row)
            except Exception:
                pass
            return None

        def _position_status_reselect(key):
            if not key:
                return
            try:
                for iid,row in list(item_rows.items()):
                    if _position_status_row_key(row)!=key:
                        continue
                    if not ptr.exists(iid):
                        continue
                    try:
                        parent=ptr.parent(iid)
                        if not parent and iid not in ptr.get_children(''):
                            continue
                    except Exception:
                        pass
                    ptr.selection_set(iid)
                    ptr.focus(iid)
                    ptr.see(iid)
                    return
            except Exception:
                pass

        def _position_status_apply_to_tree():
            counts={x:0 for x in _position_status_values}
            wanted='Alle'
            try:
                if _position_status_filter_var is not None:
                    wanted=str(_position_status_filter_var.get() or 'Alle')
            except Exception:
                wanted='Alle'
            shown=0
            try:
                cols=list(ptr.cget('columns'))
                status_index=cols.index('pz_bearbeitung')
            except Exception:
                status_index=None
            for iid,row in list(item_rows.items()):
                try:
                    if not ptr.exists(iid):
                        continue
                except Exception:
                    continue
                status=_position_status_for_row(row)
                counts[status]=counts.get(status,0)+1
                if status_index is not None:
                    try:
                        vals=list(ptr.item(iid,'values'))
                        while len(vals)<=status_index:
                            vals.append('')
                        vals[status_index]=status
                        ptr.item(iid,values=tuple(vals))
                    except Exception:
                        pass
                if wanted!='Alle' and status!=wanted:
                    try: ptr.detach(iid)
                    except Exception: pass
                else:
                    shown+=1

            if wanted!='Alle':
                try:
                    for root_iid in list(ptr.get_children('')):
                        if root_iid in item_rows:
                            continue
                        try:
                            if not ptr.get_children(root_iid):
                                ptr.detach(root_iid)
                        except Exception:
                            pass
                except Exception:
                    pass

            try:
                project_name=current_project.get('name') or 'mb-Projekt'
                summary=(
                    f"Offen {counts.get('Offen',0)} · "
                    f"Bearb. {counts.get('In Bearbeitung',0)} · "
                    f"Geprüft {counts.get('Geprüft',0)} · "
                    f"Änderung {counts.get('Änderung erforderlich',0)} · "
                    f"Erledigt {counts.get('Erledigt',0)}"
                )
                pos_info.config(
                    text=f'{project_name} · {len(current_rows)} DB-Einträge gelesen · '
                         f'{shown} Positionszeilen sichtbar   | Status: {summary}',
                    fg=INK,
                )
            except Exception:
                pass
            return counts

        _rebuild_positions_1432_status = rebuild_positions
        def rebuild_positions(*_args):
            keep=_position_status_current_key()
            _rebuild_positions_1432_status(*_args)
            _position_status_apply_to_tree()
            _position_status_reselect(keep)

        def _position_status_filter_changed(_evt=None):
            try:
                rebuild_positions()
            except Exception:
                pass

        def _position_status_ui_refresh(folder,pos):
            """Refresh status column, counters and active status filter after a status change."""
            try:
                target=(str(Path(folder).resolve()).casefold(),str(pos or '').strip().upper())
            except Exception:
                target=(str(folder or '').casefold(),str(pos or '').strip().upper())
            try:
                rebuild_positions()
            except Exception:
                try:_position_status_apply_to_tree()
                except Exception:pass
            _position_status_reselect(target)

        # Statusfilter in die vorhandene Werkzeugzeile neben Filter/Suche einsetzen.
        try:
            if _position_status_filter_var is not None:
                _toolbar=pos_info.master
                _status_wrap=ttk.Frame(_toolbar)
                ttk.Label(_status_wrap,text='Status:').pack(side='left',padx=(0,4))
                _status_combo=ttk.Combobox(
                    _status_wrap,
                    textvariable=_position_status_filter_var,
                    values=('Alle',)+_position_status_values,
                    state='readonly',
                    width=20,
                )
                _status_combo.pack(side='left')
                _status_combo.bind('<<ComboboxSelected>>',_position_status_filter_changed)
                _mgr=str(pos_info.winfo_manager() or '')
                if _mgr=='pack':
                    _status_wrap.pack(side='right',padx=(8,10))
                elif _mgr=='grid':
                    _info=pos_info.grid_info()
                    _row=int(_info.get('row',0))
                    _cols_used=[]
                    for _w in _toolbar.grid_slaves():
                        try:_cols_used.append(int(_w.grid_info().get('column',0)))
                        except Exception:pass
                    _status_wrap.grid(row=_row,column=(max(_cols_used)+1 if _cols_used else 1),padx=(8,10),sticky='e')
                else:
                    _status_wrap.pack(side='right',padx=(8,10))
        except Exception:
            pass

        # Falls beim Start bereits Zeilen geladen sind, die neue Spalte sofort füllen.
        try:
            _position_status_apply_to_tree()
        except Exception:
            pass
'''


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.33"' in s:
        return 0
    if 'APP_VERSION = "1.4.32"' not in s:
        raise RuntimeError('Update 1.4.33 erwartet Projektzentrale 1.4.32. Es wurde nichts verändert.')
    original=s
    s=s.replace('APP_VERSION = "1.4.32"','APP_VERSION = "1.4.33"',1)

    marker="        ptr.bind('<<TreeviewSelect>>',position_selected)"
    if marker not in s:
        raise RuntimeError('1.4.33 Marker der Positionsliste fehlt.')
    s=s.replace(marker,STATUS_UI+'\n'+marker,1)

    old_same="""                if status==current:\n                    _position_update_bearbeitung_display(detail_text,status=status)\n                    return True\n"""
    new_same="""                if status==current:\n                    _position_update_bearbeitung_display(detail_text,status=status)\n                    try:_position_status_ui_refresh(folder,pos)\n                    except Exception:pass\n                    return True\n"""
    if old_same not in s:
        raise RuntimeError('1.4.33 Marker für unveränderten Status fehlt.')
    s=s.replace(old_same,new_same,1)

    old_saved="""                _position_update_bearbeitung_display(detail_text,status=status)\n                return True\n"""
    new_saved="""                _position_update_bearbeitung_display(detail_text,status=status)\n                try:_position_status_ui_refresh(folder,pos)\n                except Exception:pass\n                return True\n"""
    if old_saved not in s:
        raise RuntimeError('1.4.33 Marker für Status-Aktualisierung fehlt.')
    s=s.replace(old_saved,new_saved,1)

    s=s.replace(
        'Hinweis 1.4.32: Status und Positionsnotiz werden nach dem Speichern sofort im sichtbaren BEARBEITUNG-Block aktualisiert. Ein erneutes Anklicken der Position ist dafür nicht mehr nötig.',
        'Hinweis 1.4.33: Bearbeitungsstatus steht direkt als Spalte in der Positionsliste, kann separat gefiltert werden und wird oben mit Stückzahlen zusammengefasst. Statusänderungen aktualisieren Liste, Filter und Zähler sofort; die aktuelle Position bleibt soweit sichtbar ausgewählt.'
    )
    s=s.replace(
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb, Windows-Dateizuordnungen und Projektdateien werden read-only gelesen. Positionsakte 1.4.32 aktualisiert die sichtbare Status-/Notizanzeige unmittelbar nach dem Speichern; mb-Daten und Registry bleiben unverändert.',
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb, Windows-Dateizuordnungen und Projektdateien werden read-only gelesen. Positionsakte 1.4.33 ergänzt Statusspalte, Statusfilter und Statusübersicht; Status/Notiz bleiben ausschließlich Projektzentrale-Metadaten, mb-Daten und Registry unverändert.'
    )

    required=(
        'APP_VERSION = "1.4.33"',
        "ptr.heading('pz_bearbeitung',text='Bearbeitung')",
        "values=('Alle',)+_position_status_values",
        'def _position_status_apply_to_tree():',
        'def _position_status_ui_refresh(folder,pos):',
        'try:_position_status_ui_refresh(folder,pos)',
        '| Status: {summary}',
        "ptr.bind('<<TreeviewSelect>>',position_selected)",
    )
    if not all(x in s for x in required):
        raise RuntimeError('Patch-Ergebnis 1.4.33 unvollständig. Es wurde nichts verändert.')
    if s==original:
        raise RuntimeError('Keine Änderung erzeugt.')

    tmp=APP.with_name('app.py.1433.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.v1432_vor_1433_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp.replace(APP)
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1433_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        print('FEHLER:',e)
        raise SystemExit(1)
