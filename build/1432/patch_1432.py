from pathlib import Path
import datetime
import py_compile
import shutil

APP=Path(__file__).resolve().parent/'app.py'

REFRESH_HELPERS = r'''        def _position_update_bearbeitung_display(detail_text,status=None,note=None):
            """Update the visible BEARBEITUNG block immediately after saving."""
            if detail_text is None:
                return
            try:
                old_state=str(detail_text.cget('state'))
            except Exception:
                old_state='normal'
            try:
                if old_state=='disabled':
                    detail_text.config(state='normal')
                start=detail_text.search('BEARBEITUNG','1.0','end')
                if not start:
                    return
                if status is not None:
                    idx=detail_text.search('Status:',start,'end')
                    if idx:
                        detail_text.delete(idx,f'{idx} lineend')
                        detail_text.insert(idx,'Status: '+str(status))
                if note is not None:
                    idx=detail_text.search('Notiz:',start,'end')
                    if idx:
                        detail_text.delete(idx,f'{idx} lineend')
                        detail_text.insert(idx,'Notiz: '+(str(note) if str(note).strip() else '—'))
            except Exception:
                pass
            finally:
                try:
                    if old_state=='disabled':
                        detail_text.config(state='disabled')
                except Exception:
                    pass

        def _position_set_status(folder,pos,detail_text=None):
            """Choose a position status with direct buttons and refresh the visible status immediately."""
            try:
                import tkinter as tk
                from tkinter import messagebox
                current=_position_record_get(folder,pos).get('status') or 'Offen'
                options=('Offen','In Bearbeitung','Geprüft','Änderung erforderlich','Erledigt')
                chosen={'value':None}

                master=getattr(tk,'_default_root',None)
                dlg=tk.Toplevel(master) if master is not None else tk.Toplevel()
                dlg.title('Positionsstatus')
                dlg.resizable(False,False)
                try:
                    if master is not None: dlg.transient(master)
                except Exception:
                    pass

                outer=tk.Frame(dlg,padx=16,pady=14)
                outer.pack(fill='both',expand=True)
                tk.Label(outer,text='Bearbeitungsstatus für '+str(pos),anchor='w').pack(fill='x',pady=(0,4))
                tk.Label(outer,text='Aktuell: '+str(current),anchor='w').pack(fill='x',pady=(0,10))

                def _choose(value):
                    chosen['value']=value
                    try: dlg.destroy()
                    except Exception: pass

                for value in options:
                    label=('✓  ' if value==current else '   ')+value
                    tk.Button(outer,text=label,width=30,anchor='w',command=lambda v=value:_choose(v)).pack(fill='x',pady=2)

                tk.Button(outer,text='Abbrechen',width=30,command=lambda:_choose(None)).pack(fill='x',pady=(10,0))
                try:
                    dlg.protocol('WM_DELETE_WINDOW',lambda:_choose(None))
                    dlg.grab_set()
                    dlg.focus_force()
                    dlg.wait_window()
                except Exception:
                    pass

                status=chosen.get('value')
                if not status: return False
                if status==current:
                    _position_update_bearbeitung_display(detail_text,status=status)
                    return True
                if not _position_record_update(folder,pos,status=status):
                    messagebox.showwarning('Positionsstatus','Der Status konnte nicht gespeichert werden.')
                    return False
                _position_update_bearbeitung_display(detail_text,status=status)
                return True
            except Exception:
                return False

        def _position_edit_note(folder,pos,detail_text=None):
            try:
                from tkinter import simpledialog, messagebox
                current=_position_record_get(folder,pos).get('note') or ''
                note=simpledialog.askstring('Positionsnotiz',f'Kurze Notiz zu Position {pos}:',initialvalue=current)
                if note is None: return False
                note=' '.join(str(note).split())[:500]
                if not _position_record_update(folder,pos,note=note):
                    messagebox.showwarning('Positionsnotiz','Die Notiz konnte nicht gespeichert werden.')
                    return False
                _position_update_bearbeitung_display(detail_text,note=note)
                return True
            except Exception:
                return False
'''


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.32"' in s:
        return 0
    if 'APP_VERSION = "1.4.31"' not in s:
        raise RuntimeError('Update 1.4.32 erwartet Projektzentrale 1.4.31. Es wurde nichts verändert.')
    original=s
    s=s.replace('APP_VERSION = "1.4.31"','APP_VERSION = "1.4.32"',1)

    start=s.find('        def _position_set_status(folder,pos):')
    end=s.find('        def _position_context_plan_files(folder,pos):',start)
    if start<0 or end<0:
        raise RuntimeError('1.4.32 Marker für Status-/Notiz-Helfer fehlt.')
    # Replace both status + note helpers as one block; the context-plan helper follows directly afterwards.
    s=s[:start]+REFRESH_HELPERS+'\n'+s[end:]

    old_status="detail_text.tag_bind(_status_tag,'<Double-1>',lambda _e,_f=folder,_p=r.get('pos'):_position_set_status(_f,_p))"
    new_status="detail_text.tag_bind(_status_tag,'<Double-1>',lambda _e,_f=folder,_p=r.get('pos'),_t=detail_text:_position_set_status(_f,_p,_t))"
    if old_status not in s:
        raise RuntimeError('1.4.32 Marker für Status-Aktion fehlt.')
    s=s.replace(old_status,new_status,1)

    old_note="detail_text.tag_bind(_note_tag,'<Double-1>',lambda _e,_f=folder,_p=r.get('pos'):_position_edit_note(_f,_p))"
    new_note="detail_text.tag_bind(_note_tag,'<Double-1>',lambda _e,_f=folder,_p=r.get('pos'),_t=detail_text:_position_edit_note(_f,_p,_t))"
    if old_note not in s:
        raise RuntimeError('1.4.32 Marker für Notiz-Aktion fehlt.')
    s=s.replace(old_note,new_note,1)

    s=s.replace(
        'Hinweis 1.4.31: Der Bearbeitungsstatus wird nun direkt über fünf Schaltflächen gewählt. Die unnötige Bestätigung nach Status- oder Notizspeicherung entfällt; nur Fehler werden noch gemeldet. Positionsakte und Dateiverknüpfungen bleiben unverändert erhalten.',
        'Hinweis 1.4.32: Status und Positionsnotiz werden nach dem Speichern sofort im sichtbaren BEARBEITUNG-Block aktualisiert. Ein erneutes Anklicken der Position ist dafür nicht mehr nötig.'
    )
    s=s.replace(
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb, Windows-Dateizuordnungen und Projektdateien werden read-only gelesen. Positionsakte 1.4.31 vereinfacht die Status-/Notizbedienung; gespeichert wird weiterhin ausschließlich in der Projektzentrale-Metadatei, mb-Daten und Registry bleiben unverändert.',
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb, Windows-Dateizuordnungen und Projektdateien werden read-only gelesen. Positionsakte 1.4.32 aktualisiert die sichtbare Status-/Notizanzeige unmittelbar nach dem Speichern; mb-Daten und Registry bleiben unverändert.'
    )

    required=(
        'APP_VERSION = "1.4.32"',
        'def _position_update_bearbeitung_display(detail_text,status=None,note=None)',
        'def _position_set_status(folder,pos,detail_text=None)',
        'def _position_edit_note(folder,pos,detail_text=None)',
        '_position_update_bearbeitung_display(detail_text,status=status)',
        '_position_update_bearbeitung_display(detail_text,note=note)',
        "_position_set_status(_f,_p,_t)",
        "_position_edit_note(_f,_p,_t)",
        'def _position_context_plan_files(folder,pos)',
    )
    if not all(x in s for x in required):
        raise RuntimeError('Patch-Ergebnis 1.4.32 unvollständig. Es wurde nichts verändert.')
    if s==original:
        raise RuntimeError('Keine Änderung erzeugt.')

    tmp=APP.with_name('app.py.1432.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.v1431_vor_1432_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp.replace(APP)
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1432_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        print('FEHLER:',e)
        raise SystemExit(1)
