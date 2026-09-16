from pathlib import Path
import datetime, py_compile, shutil, traceback

APP=Path(__file__).resolve().parent/'app.py'
OLD='1.6.0'; NEW='1.6.1'
OLD_IMPORT='from masterdata_v1600 import open_masterdata'
NEW_IMPORT='from masterdata_v1601 import open_masterdata'
OLD_MARK='PZ_MASTERDATA_PLANS_V1600'
NEW_MARK='PZ_MASTERDATA_GEOMETRY_V1601'

def main():
    if not APP.exists():
        raise RuntimeError('1.6.1: app.py wurde nicht gefunden.')
    s=APP.read_text(encoding='utf-8')
    if f'APP_VERSION = "{NEW}"' in s and NEW_IMPORT in s:
        return 0
    if f'APP_VERSION = "{OLD}"' not in s:
        raise RuntimeError('Update 1.6.1 erwartet Projektzentrale 1.6.0.')
    if OLD_IMPORT not in s or OLD_MARK not in s:
        raise RuntimeError('1.6.1: Stammdatenmodul aus 1.6.0 wurde nicht gefunden.')
    s=s.replace(OLD_IMPORT,NEW_IMPORT,1)
    s=s.replace(OLD_MARK,NEW_MARK,1)
    s=s.replace(f'APP_VERSION = "{OLD}"',f'APP_VERSION = "{NEW}"',1)
    s=s.replace('Projektzentrale 1.6.0','Projektzentrale 1.6.1')
    if NEW_IMPORT not in s or NEW_MARK not in s:
        raise RuntimeError('1.6.1: Sicherheitsprüfung fehlgeschlagen.')
    chk=APP.with_name('app.py.1601.check')
    try:
        chk.write_text(s,encoding='utf-8')
        py_compile.compile(str(chk),doraise=True)
    finally:
        try:chk.unlink()
        except Exception:pass
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name('app.py.vor_1_6_1_'+stamp+'.bak')
    shutil.copy2(APP,bak)
    tmp=APP.with_name('app.py.1601.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    tmp.replace(APP)
    APP.with_name('patch_1601_report.txt').write_text(
        'OK: Projektzentrale 1.6.1 installiert.\n'
        'Projektstammdaten: geometrische Plankopf-Auswertung aktiviert.\n'
        'Architektenplaene haben Vorrang; Statik-Titelseiten ergaenzen nur fehlende Werte.\n'
        'Backup: '+str(bak)+'\n',encoding='utf-8')
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except SystemExit:raise
    except Exception:
        try:APP.with_name('patch_1601_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception:pass
        raise
