from pathlib import Path
import datetime
import py_compile
import shutil
import traceback

BASE=Path(__file__).resolve().parent
APP=BASE/'app.py'
OLD='1.7.3'
NEW='1.7.4'
MARK='PZ_CUMULATIVE_BRIDGE_V1704'


def main():
    if not APP.exists():
        raise RuntimeError('1.7.4: app.py wurde nicht gefunden.')
    app=APP.read_text(encoding='utf-8')
    if f'APP_VERSION = "{NEW}"' in app:
        return 0
    if f'APP_VERSION = "{OLD}"' not in app:
        raise RuntimeError('Update 1.7.4 erwartet nach den Brückenschritten Projektzentrale 1.7.3.')
    app_new=app.replace(f'APP_VERSION = "{OLD}"',f'APP_VERSION = "{NEW}"',1)
    app_new=app_new.replace('Projektzentrale 1.7.3','Projektzentrale 1.7.4')
    chk=APP.with_name('app.py.1704.check')
    try:
        chk.write_text(app_new,encoding='utf-8')
        py_compile.compile(str(chk),doraise=True)
    finally:
        try: chk.unlink()
        except Exception: pass
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(APP,APP.with_name(APP.name+'.vor_1_7_4_'+stamp+'.bak'))
    tmp=APP.with_name('app.py.1704.tmp')
    tmp.write_text(app_new,encoding='utf-8')
    tmp.replace(APP)
    APP.with_name('patch_1704_report.txt').write_text(
        'OK: Projektzentrale 1.7.4 installiert.\n'
        'Kumulatives Brückenupdate: Installationen ab 1.7.1 werden automatisch auf den aktuellen Stand gebracht.\n'
        'Word-Bescheinigungen bleiben im direkten Bearbeitungsmodus aus 1.7.3.\n',
        encoding='utf-8')
    return 0


if __name__=='__main__':
    try: raise SystemExit(main())
    except SystemExit: raise
    except Exception:
        try: APP.with_name('patch_1704_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception: pass
        raise
