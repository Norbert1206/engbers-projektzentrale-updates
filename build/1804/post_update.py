from pathlib import Path
import runpy
import traceback

BASE=Path(__file__).resolve().parent
LOG=BASE/'update_1804_install.log'
ERR=BASE/'update_1804_error.txt'

def main():
    try:
        patch=BASE/'patch_1804.py'
        if not patch.exists():
            raise RuntimeError('patch_1804.py fehlt im Programmordner.')
        ns=runpy.run_path(str(patch),run_name='pz_patch_1804')
        fn=ns.get('main')
        if not callable(fn):
            raise RuntimeError('patch_1804.py enthaelt keine main()-Funktion.')
        rc=fn()
        if rc not in (None,0):
            raise RuntimeError(f'patch_1804.py lieferte Rueckgabecode {rc}.')
        app=(BASE/'app.py').read_text(encoding='utf-8')
        mod=(BASE/'wordforms_v1700.py').read_text(encoding='utf-8')
        if 'APP_VERSION = "1.8.4"' not in app and "APP_VERSION = '1.8.4'" not in app:
            raise RuntimeError('Versionspruefung nach Installation fehlgeschlagen.')
        if 'PZ_SASV_PDF_ONLY_STAMP_V1804' not in mod:
            raise RuntimeError('Funktionspruefung nach Installation fehlgeschlagen.')
        LOG.write_text('OK: Update 1.8.4 erfolgreich installiert.\n',encoding='utf-8')
        try: ERR.unlink()
        except Exception: pass
        return 0
    except Exception:
        text=traceback.format_exc()
        try: ERR.write_text(text,encoding='utf-8')
        except Exception: pass
        try: LOG.write_text('FEHLER bei Update 1.8.4:\n'+text,encoding='utf-8')
        except Exception: pass
        return 1

if __name__=='__main__':
    raise SystemExit(main())
