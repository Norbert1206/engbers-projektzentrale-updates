from pathlib import Path
import datetime
import py_compile
import shutil

APP=Path(__file__).resolve().parent/'app.py'


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.16"' in s:
        return 0
    if 'APP_VERSION = "1.4.15"' not in s:
        raise RuntimeError('Update 1.4.16 erwartet Projektzentrale 1.4.15. Es wurde nichts verändert.')
    original=s
    s=s.replace('APP_VERSION = "1.4.15"','APP_VERSION = "1.4.16"',1)

    # Fix the local cache introduced in 1.4.15. The helper is nested inside the
    # Statik page builder; using "global" there made the first cache read raise
    # NameError before the diagnostic could render. Use a closure-safe dict.
    old_head="""        _mb_windows_start_cache=None
        def _mb_windows_start_info():
"""
    new_head="""        _mb_windows_start_cache={}
        def _mb_windows_start_info():
"""
    if old_head not in s:
        raise RuntimeError('1.4.16 Marker für Startdiagnose-Cache fehlt.')
    s=s.replace(old_head,new_head,1)

    old_cache="""            global _mb_windows_start_cache
            if _mb_windows_start_cache is not None:
                return _mb_windows_start_cache
"""
    new_cache="""            if 'value' in _mb_windows_start_cache:
                return _mb_windows_start_cache['value']
"""
    if old_cache not in s:
        raise RuntimeError('1.4.16 Marker für fehlerhaften global-Cache fehlt.')
    s=s.replace(old_cache,new_cache,1)

    old_store="""            _mb_windows_start_cache=result
            return result
"""
    new_store="""            _mb_windows_start_cache['value']=result
            return result
"""
    if old_store not in s:
        raise RuntimeError('1.4.16 Marker für Cache-Speicherung fehlt.')
    s=s.replace(old_store,new_store,1)

    s=s.replace(
        'Hinweis 1.4.15: Zusätzlich wird read-only geprüft, welche Windows/mb-Dateizuordnung für Projektdateien (.mbp) und MicroFe-Modelldatenbanken (.mbdb) registriert ist. Damit kann der nächste Modellstart ohne geratenen Kommandozeilenparameter gebaut werden.',
        'Hinweis 1.4.16: Fehlerkorrektur der read-only Windows-Startdiagnose. Die Positionsakte zeigt wieder vollständig Anwendung, Modell/Modell-ID, Modellquelle und den registrierten Handler für .mbp bzw. .mbdb.'
    )
    s=s.replace(
        'Quelle: BSPos.mbdb, *.mbp und FEM/*.mbdb werden ausschließlich read-only gelesen. Positionsakte 1.4.15 ergänzt eine read-only Windows-Startdiagnose für .mbp/.mbdb; es werden keine Registry-Werte verändert.',
        'Quelle: BSPos.mbdb, *.mbp und FEM/*.mbdb sowie Windows-Dateizuordnungen werden ausschließlich read-only gelesen. Positionsakte 1.4.16 korrigiert die Handler-Diagnose; Registry und mb-Daten bleiben unverändert.'
    )

    required=(
        'APP_VERSION = "1.4.16"',
        "_mb_windows_start_cache={}",
        "if 'value' in _mb_windows_start_cache",
        "_mb_windows_start_cache['value']=result",
        'Startprüfung Modell (.mbdb)',
        'Startprüfung Projekt (.mbp)',
        'def _mb_model_for_position',
    )
    if not all(x in s for x in required):
        raise RuntimeError('Patch-Ergebnis 1.4.16 unvollständig. Es wurde nichts verändert.')
    if s==original:
        raise RuntimeError('Keine Änderung erzeugt.')

    tmp=APP.with_name('app.py.1416.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.v1415_vor_1416_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp.replace(APP)
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1416_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        print('FEHLER:',e)
        raise SystemExit(1)
