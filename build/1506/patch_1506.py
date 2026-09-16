from pathlib import Path
import datetime
import py_compile
import shutil
import traceback

APP = Path(__file__).resolve().parent / 'app.py'
VERSION_OLD = '1.5.5'
VERSION_NEW = '1.5.6'
MARKER_OLD = 'PZ_PROJECT_EXPLORER_QUEUE_V1505'
MARKER_NEW = 'PZ_PROJECT_EXPLORER_SELECT_FIX_V1506'

OLD_SELECTED = '''        def selected(event=None):\n            iid = ''\n            try:\n                if event is not None: iid = tr.identify_row(event.y)\n            except Exception: iid = ''\n            if not iid:\n                try:\n                    sel = tr.selection(); iid = sel[0] if sel else ''\n                except Exception: iid = ''\n            if iid:\n                try: tr.selection_set(iid); tr.focus(iid)\n                except Exception: pass\n            return pathmap.get(iid), rootmap.get(iid), iid\n'''

NEW_SELECTED = '''        def selected(event=None):\n            # 1.5.6: Nur AUSLESEN, niemals die Treeview-Auswahl hier erneut setzen.\n            # refresh_detail wird durch <<TreeviewSelect>> aufgerufen; selection_set() an\n            # dieser Stelle hat erneut <<TreeviewSelect>> erzeugt und damit eine Endlosschleife.\n            iid = ''\n            try:\n                if event is not None: iid = tr.identify_row(event.y)\n            except Exception: iid = ''\n            if not iid:\n                try:\n                    sel = tr.selection(); iid = sel[0] if sel else ''\n                except Exception: iid = ''\n            return pathmap.get(iid), rootmap.get(iid), iid\n'''


def main():
    if not APP.exists():
        raise RuntimeError('1.5.6: app.py wurde nicht gefunden.')
    original = APP.read_text(encoding='utf-8')
    if f'APP_VERSION = "{VERSION_NEW}"' in original and MARKER_NEW in original:
        return 0
    if f'APP_VERSION = "{VERSION_OLD}"' not in original:
        raise RuntimeError('Update 1.5.6 erwartet Projektzentrale 1.5.5. Es wurde nichts verändert.')
    if MARKER_OLD not in original:
        raise RuntimeError('1.5.6: Projekt-Explorer aus 1.5.5 wurde nicht gefunden.')
    if OLD_SELECTED not in original:
        raise RuntimeError('1.5.6: Auswahlroutine aus 1.5.5 wurde nicht gefunden.')

    candidate = original.replace(OLD_SELECTED, NEW_SELECTED, 1)
    candidate = candidate.replace(MARKER_OLD, MARKER_NEW, 1)
    candidate = candidate.replace(f'APP_VERSION = "{VERSION_OLD}"', f'APP_VERSION = "{VERSION_NEW}"', 1)
    candidate = candidate.replace('Projektzentrale 1.5.5', 'Projektzentrale 1.5.6')

    if 'def selected(event=None):' not in candidate or MARKER_NEW not in candidate:
        raise RuntimeError('1.5.6: Sicherheitsprüfung fehlgeschlagen.')
    if OLD_SELECTED in candidate:
        raise RuntimeError('1.5.6: Alte rekursive Auswahlroutine ist noch vorhanden.')

    check = APP.with_name('app.py.1506.check')
    try:
        check.write_text(candidate, encoding='utf-8')
        py_compile.compile(str(check), doraise=True)
    finally:
        try: check.unlink()
        except Exception: pass

    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = APP.with_name('app.py.vor_1_5_6_' + stamp + '.bak')
    shutil.copy2(APP, backup)
    tmp = APP.with_name('app.py.1506.tmp')
    tmp.write_text(candidate, encoding='utf-8')
    py_compile.compile(str(tmp), doraise=True)
    tmp.replace(APP)
    APP.with_name('patch_1506_report.txt').write_text(
        'OK: Projektzentrale 1.5.6 installiert.\n'
        'Projekt-Explorer: rekursive Treeview-Auswahl entfernt; <<TreeviewSelect>> kann sich nicht mehr selbst auslösen.\n'
        'Backup: ' + str(backup) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        try:
            APP.with_name('patch_1506_error.txt').write_text(traceback.format_exc(), encoding='utf-8')
        except Exception:
            pass
        raise
