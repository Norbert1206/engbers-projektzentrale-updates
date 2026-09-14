from pathlib import Path
import datetime
import py_compile
import shutil

APP=Path(__file__).resolve().parent/'app.py'


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.17"' in s:
        return 0
    if 'APP_VERSION = "1.4.16"' not in s:
        raise RuntimeError('Update 1.4.17 erwartet Projektzentrale 1.4.16. Es wurde nichts verändert.')
    original=s
    s=s.replace('APP_VERSION = "1.4.16"','APP_VERSION = "1.4.17"',1)

    # 1.4.16 renders the extended model data again, but the important start
    # diagnostic sits below the visible area of the compact Positionsakte.
    # Move handler + command to the top and remove duplicated Position/Bezeichnung
    # lines (those are already rendered directly above this block).
    old="""                start_info=_mb_windows_start_info()
                if str(mb_app).lower()=='microfe':
                    start_probe=f'Startprüfung Modell (.mbdb): {start_info.get(\"model_handler\") or \"nicht registriert\"}\\n'
                else:
                    start_probe=f'Startprüfung Projekt (.mbp): {start_info.get(\"project_handler\") or \"nicht registriert\"}\\n'
                detail_text.insert('end',f'Position: {posid}\\nBezeichnung: {bez}\\n\\nmb-Projekt: {projekt}\\nmb-Modul: {modul}\\nmb-Anwendung: {mb_app}\\nmb-Modell: {model_name}\\n{model_id_line}Modellquelle: {model_source}\\nFachgruppe: {gruppe}\\nBerechnungsstatus: {status}\\n{start_probe}')
"""
    new="""                start_info=_mb_windows_start_info()
                if str(mb_app).lower()=='microfe':
                    start_probe=f'Startprüfung Modell (.mbdb): {start_info.get(\"model_handler\") or \"nicht registriert\"}\\n'
                    start_command=start_info.get('model_command') or '—'
                else:
                    start_probe=f'Startprüfung Projekt (.mbp): {start_info.get(\"project_handler\") or \"nicht registriert\"}\\n'
                    start_command=start_info.get('project_command') or '—'
                detail_text.insert('end',f'mb-Projekt: {projekt}\\nmb-Modul: {modul}\\nmb-Anwendung: {mb_app}\\n{start_probe}Startkommando: {start_command}\\nmb-Modell: {model_name}\\n{model_id_line}Modellquelle: {model_source}\\nFachgruppe: {gruppe}\\nBerechnungsstatus: {status}\\n')
"""
    if old not in s:
        raise RuntimeError('1.4.17 Marker für Positionsakte-Startdiagnose fehlt.')
    s=s.replace(old,new,1)

    s=s.replace(
        'Hinweis 1.4.16: Fehlerkorrektur der read-only Windows-Startdiagnose. Die Positionsakte zeigt wieder vollständig Anwendung, Modell/Modell-ID, Modellquelle und den registrierten Handler für .mbp bzw. .mbdb.',
        'Hinweis 1.4.17: Die Startdiagnose steht jetzt direkt im sichtbaren Kopf der Positionsakte. Zusätzlich wird das registrierte Windows/mb-Startkommando für .mbp bzw. .mbdb read-only angezeigt; doppelte Positionszeilen wurden entfernt.'
    )
    s=s.replace(
        'Quelle: BSPos.mbdb, *.mbp und FEM/*.mbdb sowie Windows-Dateizuordnungen werden ausschließlich read-only gelesen. Positionsakte 1.4.16 korrigiert die Handler-Diagnose; Registry und mb-Daten bleiben unverändert.',
        'Quelle: BSPos.mbdb, *.mbp und FEM/*.mbdb sowie Windows-Dateizuordnungen werden ausschließlich read-only gelesen. Positionsakte 1.4.17 zeigt Handler und Startkommando kompakt im sichtbaren Kopf; Registry und mb-Daten bleiben unverändert.'
    )

    required=(
        'APP_VERSION = "1.4.17"',
        "start_command=start_info.get('model_command') or '—'",
        "start_command=start_info.get('project_command') or '—'",
        'Startkommando: {start_command}',
        'Startprüfung Modell (.mbdb)',
        'Startprüfung Projekt (.mbp)',
        'mb-Modell: {model_name}',
    )
    if not all(x in s for x in required):
        raise RuntimeError('Patch-Ergebnis 1.4.17 unvollständig. Es wurde nichts verändert.')
    if s==original:
        raise RuntimeError('Keine Änderung erzeugt.')

    tmp=APP.with_name('app.py.1417.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.v1416_vor_1417_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp.replace(APP)
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1417_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        print('FEHLER:',e)
        raise SystemExit(1)
