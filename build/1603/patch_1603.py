from pathlib import Path
import datetime, py_compile, shutil, traceback

APP=Path(__file__).resolve().parent/'app.py'
OLD='1.6.2'; NEW='1.6.3'
OLD_IMPORT='from masterdata_v1602 import open_masterdata'
NEW_IMPORT='from masterdata_v1603 import open_masterdata'
OLD_MARK='PZ_MASTERDATA_FITZ_V1602'
NEW_MARK='PZ_MASTERDATA_LOCAL_FITZ_V1603'


def main():
    if not APP.exists():
        raise RuntimeError('1.6.3: app.py wurde nicht gefunden.')
    s=APP.read_text(encoding='utf-8')
    if f'APP_VERSION = "{NEW}"' in s and NEW_IMPORT in s:
        return 0
    if f'APP_VERSION = "{OLD}"' not in s:
        raise RuntimeError('Update 1.6.3 erwartet Projektzentrale 1.6.2.')
    if OLD_IMPORT not in s or OLD_MARK not in s:
        raise RuntimeError('1.6.3: Stammdatenmodul aus 1.6.2 wurde nicht gefunden.')
    s=s.replace(OLD_IMPORT,NEW_IMPORT,1)
    s=s.replace(OLD_MARK,NEW_MARK,1)
    s=s.replace(f'APP_VERSION = "{OLD}"',f'APP_VERSION = "{NEW}"',1)
    s=s.replace('Projektzentrale 1.6.2','Projektzentrale 1.6.3')
    if NEW_IMPORT not in s or NEW_MARK not in s:
        raise RuntimeError('1.6.3: Sicherheitsprüfung fehlgeschlagen.')
    chk=APP.with_name('app.py.1603.check')
    try:
        chk.write_text(s,encoding='utf-8')
        py_compile.compile(str(chk),doraise=True)
    finally:
        try: chk.unlink()
        except Exception: pass
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name('app.py.vor_1_6_3_'+stamp+'.bak')
    shutil.copy2(APP,bak)
    tmp=APP.with_name('app.py.1603.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    tmp.replace(APP)
    APP.with_name('patch_1603_report.txt').write_text(
        'OK: Projektzentrale 1.6.3 installiert.\n'
        'Projektstammdaten: lokaler PyMuPDF-CAD-Reader aktiviert.\n'
        'Fehlende PDF-Engine wird nicht mehr still durch pypdf ersetzt.\n'
        'Backup: '+str(bak)+'\n',encoding='utf-8')
    return 0


if __name__=='__main__':
    try: raise SystemExit(main())
    except SystemExit: raise
    except Exception:
        try: APP.with_name('patch_1603_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception: pass
        raise
