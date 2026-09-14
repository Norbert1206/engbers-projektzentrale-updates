from pathlib import Path
import datetime
import py_compile
import shutil

APP=Path(__file__).resolve().parent/'app.py'

EXACT_HELPER = r'''        def _position_file_is_exact(pos,rel):
            """Match a project file to exactly one mb position.

            The position and candidate path are split into alpha/numeric components.
            This keeps common spellings such as E.01.D, E01D, E_01_D and
            'Pos E01 D' compatible, but E.01.D no longer matches E.01.DS-1.
            """
            try:
                import re
                def parts(value):
                    return re.findall(r'[A-Z]+|[0-9]+',str(value or '').upper())
                wanted=parts(pos)
                have=parts(rel)
                if not wanted or len(have)<len(wanted):
                    return False
                n=len(wanted)
                return any(have[i:i+n]==wanted for i in range(len(have)-n+1))
            except Exception:
                return False
'''


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.12"' in s:
        return 0
    if 'APP_VERSION = "1.4.11"' not in s:
        raise RuntimeError('Update 1.4.12 erwartet Projektzentrale 1.4.11. Es wurde nichts verändert.')
    original=s
    s=s.replace('APP_VERSION = "1.4.11"','APP_VERSION = "1.4.12"',1)

    # Exact position/file assignment. Insert beside the existing Positionsakte helpers.
    marker='        def _detail_add_link(text,label,path,tag_index):'
    if marker not in s:
        raise RuntimeError('1.4.12 Marker für Positionsakte-Helfer fehlt.')
    if 'def _position_file_is_exact' not in s:
        s=s.replace(marker,EXACT_HELPER+'\n'+marker,1)

    # 1.4.8+ computed broad candidates. Filter them directly before they are shown,
    # so a short position such as E.01.D cannot inherit files of E.01.DS-1 etc.
    old_matches="""                detail_text.insert('end',f'\\nVERKNÜPFTE PROJEKTDATEIEN ({len(matches)})\\n')
                if matches:
"""
    new_matches="""                matches=[hit for hit in matches if _position_file_is_exact(r.get('pos'), hit[4] if len(hit)>4 else hit[3])]
                detail_text.insert('end',f'\\nVERKNÜPFTE PROJEKTDATEIEN ({len(matches)})\\n')
                if matches:
"""
    if old_matches not in s:
        raise RuntimeError('1.4.12 Marker für verknüpfte Projektdateien fehlt.')
    s=s.replace(old_matches,new_matches,1)

    # Put the actual position and designation at the top of the right-hand file.
    old_meta="""                mb_app=_mb_application_for_position(folder,r)
                detail_text.insert('end',f'mb-Projekt: {projekt}\\nmb-Modul: {modul}\\nmb-Anwendung: {mb_app}\\nFachgruppe: {gruppe}\\nBerechnungsstatus: {status}\\n')
"""
    new_meta="""                mb_app=_mb_application_for_position(folder,r)
                posid=str(r.get('pos') or '').strip() or '—'
                detail_text.insert('end',f'Position: {posid}\\nBezeichnung: {bez}\\n\\nmb-Projekt: {projekt}\\nmb-Modul: {modul}\\nmb-Anwendung: {mb_app}\\nFachgruppe: {gruppe}\\nBerechnungsstatus: {status}\\n')
"""
    if old_meta not in s:
        raise RuntimeError('1.4.12 Marker für Positions-Metadaten fehlt.')
    s=s.replace(old_meta,new_meta,1)

    s=s.replace(
        'Hinweis 1.4.11: mb-konformer Startweg: BauStatik wird nicht mehr standalone gestartet, da mb die Oberfläche ausschließlich aus dem ProjektManager öffnet. MicroFe-Modelle werden anhand der FEM-Projektdaten automatisch erkannt. Alles read-only.',
        'Hinweis 1.4.12: Positionsakte mit exakter Positionszuordnung. E.01.D wird nicht mehr mit E.01.DS-1 usw. verwechselt; Schreibweisen wie E01D und E_01_D bleiben kompatibel. BauStatik/MicroFe-Erkennung bleibt read-only.'
    )
    s=s.replace(
        'Quelle: BSPos.mbdb und FEM/*.mbdb werden je mb-Projekt ausschließlich read-only gelesen. Positionsakte 1.4.11 erkennt BauStatik/MicroFe und öffnet mb-konform über den ProjektManager.',
        'Quelle: BSPos.mbdb und FEM/*.mbdb werden je mb-Projekt ausschließlich read-only gelesen. Positionsakte 1.4.12 erkennt BauStatik/MicroFe und ordnet Projektdateien nur bei exakter Positionskennung zu.'
    )

    required=(
        'APP_VERSION = "1.4.12"',
        'def _position_file_is_exact',
        "matches=[hit for hit in matches if _position_file_is_exact",
        "Position: {posid}",
        "Bezeichnung: {bez}",
        'Startweg: ProjektManager → MicroFe',
    )
    if not all(x in s for x in required):
        raise RuntimeError('Patch-Ergebnis 1.4.12 unvollständig. Es wurde nichts verändert.')
    if s==original:
        raise RuntimeError('Keine Änderung erzeugt.')

    tmp=APP.with_name('app.py.1412.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.v1411_vor_1412_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp.replace(APP)
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1412_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        print('FEHLER:',e)
        raise SystemExit(1)
