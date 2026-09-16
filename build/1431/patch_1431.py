from pathlib import Path
import datetime
import py_compile
import shutil

APP=Path(__file__).resolve().parent/'app.py'

STATUS_HELPER = r'''        def _position_set_status(folder,pos):
            """Choose a position status with direct buttons and save silently.

            1.4.31 removes the extra success confirmation dialog. Only real
            errors still produce a warning. The detail pane reflects the new
            value the next time the position is selected/refreshed.
            """
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
                if status==current: return True
                if not _position_record_update(folder,pos,status=status):
                    messagebox.showwarning('Positionsstatus','Der Status konnte nicht gespeichert werden.')
                    return False
                return True
            except Exception:
                return False
'''


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.31"' in s:
        return 0
    if 'APP_VERSION = "1.4.30"' not in s:
        raise RuntimeError('Update 1.4.31 erwartet Projektzentrale 1.4.30. Es wurde nichts verändert.')
    original=s
    s=s.replace('APP_VERSION = "1.4.30"','APP_VERSION = "1.4.31"',1)

    start=s.find('        def _position_set_status(folder,pos):')
    end=s.find('        def _position_edit_note(folder,pos):',start)
    if start<0 or end<0:
        raise RuntimeError('1.4.31 Marker für Positionsstatus fehlt.')
    s=s[:start]+STATUS_HELPER+'\n'+s[end:]

    # Also remove the unnecessary success popup after saving a note. Errors stay visible.
    s=s.replace(
        "                messagebox.showinfo('Positionsnotiz','Notiz wurde gespeichert.\\n\\nPosition bitte einmal erneut anklicken.')\n                return True",
        "                return True",
        1,
    )

    s=s.replace(
        'Hinweis 1.4.30: Die Positionsakte speichert zusätzlich Bearbeitungsstatus, kurze Positionsnotiz und manuelle Dateiverknüpfungen je exakter mb-Position. Dateien bleiben an ihrem Originalort; gespeichert werden nur projektbezogene Verweise in .engbers_positionsakte.json.',
        'Hinweis 1.4.31: Der Bearbeitungsstatus wird nun direkt über fünf Schaltflächen gewählt. Die unnötige Bestätigung nach Status- oder Notizspeicherung entfällt; nur Fehler werden noch gemeldet. Positionsakte und Dateiverknüpfungen bleiben unverändert erhalten.'
    )
    s=s.replace(
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb, Windows-Dateizuordnungen und Projektdateien werden read-only gelesen. Positionsakte 1.4.30 speichert Status, Notiz und manuelle Dateiverknüpfungen ausschließlich in einer eigenen Projektzentrale-Metadatei; mb-Daten und Registry bleiben unverändert.',
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb, Windows-Dateizuordnungen und Projektdateien werden read-only gelesen. Positionsakte 1.4.31 vereinfacht die Status-/Notizbedienung; gespeichert wird weiterhin ausschließlich in der Projektzentrale-Metadatei, mb-Daten und Registry bleiben unverändert.'
    )

    required=(
        'APP_VERSION = "1.4.31"',
        'def _position_set_status(folder,pos)',
        "options=('Offen','In Bearbeitung','Geprüft','Änderung erforderlich','Erledigt')",
        "tk.Button(outer,text=label,width=30,anchor='w'",
        "if status==current: return True",
        "messagebox.showwarning('Positionsstatus','Der Status konnte nicht gespeichert werden.')",
        'def _position_edit_note(folder,pos)',
        'def _position_record_store(folder)',
    )
    if not all(x in s for x in required):
        raise RuntimeError('Patch-Ergebnis 1.4.31 unvollständig. Es wurde nichts verändert.')
    if s==original:
        raise RuntimeError('Keine Änderung erzeugt.')

    tmp=APP.with_name('app.py.1431.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.v1430_vor_1431_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp.replace(APP)
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1431_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        print('FEHLER:',e)
        raise SystemExit(1)
