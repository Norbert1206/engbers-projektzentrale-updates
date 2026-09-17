from pathlib import Path
import runpy
import traceback

BASE=Path(__file__).resolve().parent
LOG=BASE/'update_1715_install.log'
ERR=BASE/'update_1715_error.txt'

def main():
    try:
        patch=BASE/'patch_1715.py'
        if not patch.exists(): raise RuntimeError('patch_1715.py fehlt im Programmordner.')
        ns=runpy.run_path(str(patch),run_name='pz_patch_1715')
        fn=ns.get('main')
        if not callable(fn): raise RuntimeError('patch_1715.py enthaelt keine main()-Funktion.')
        rc=fn()
        if rc not in (None,0): raise RuntimeError(f'patch_1715.py lieferte Rueckgabecode {rc}.')
        app=(BASE/'app.py').read_text(encoding='utf-8')
        mod=(BASE/'wordforms_v1700.py').read_text(encoding='utf-8')
        if 'APP_VERSION = "1.7.15"' not in app and "APP_VERSION = '1.7.15'" not in app: raise RuntimeError('Versionspruefung nach Installation fehlgeschlagen.')
        if 'PZ_PDF_SAVE_DIALOG_V1715' not in mod: raise RuntimeError('Funktionspruefung nach Installation fehlgeschlagen.')
        LOG.write_text('OK: Update 1.7.15 erfolgreich installiert.\n',encoding='utf-8')
        try: ERR.unlink()
        except Exception: pass
        return 0
    except Exception:
        text=traceback.format_exc()
        try: print(text)
        except Exception: pass
        try: ERR.write_text(text,encoding='utf-8')
        except Exception: pass
        try: LOG.write_text('FEHLER bei Update 1.7.15:\n'+text,encoding='utf-8')
        except Exception: pass
        return 1

if __name__=='__main__':
    raise SystemExit(main())
