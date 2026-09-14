from pathlib import Path
import datetime
import py_compile
import shutil

APP=Path(__file__).resolve().parent/'app.py'

APP_HELPER = r'''        _mb_application_cache={}

        def _mb_application_for_position(folder,row):
            """Classify a position by real project data, without changing mb files.

            A BauStatik position that is backed by a MicroFe/FEM model is recognised
            through FEM/*.mbdb -> FEMWerteTabelle/ModellName. Everything else remains
            a BauStatik position. The scan is cached per mb project folder.
            """
            try:
                import sqlite3
                folder=Path(folder)
                pos=str((row or {}).get('pos') or '').strip()
                if not pos:
                    return 'BauStatik'
                key=str(folder.resolve()).casefold()
                names=_mb_application_cache.get(key)
                if names is None:
                    names=set()
                    fem=folder/'FEM'
                    if fem.exists():
                        for db in fem.rglob('*.mbdb'):
                            try:
                                uri='file:'+db.resolve().as_posix()+'?mode=ro'
                                con=sqlite3.connect(uri,uri=True,timeout=0.25)
                                try:
                                    tab=con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='FEMWerteTabelle' LIMIT 1").fetchone()
                                    if not tab:
                                        continue
                                    for rec in con.execute("SELECT strWert FROM FEMWerteTabelle WHERE lower(strName)=lower('ModellName')"):
                                        if rec and rec[0] not in (None,''):
                                            names.add(str(rec[0]).strip().casefold())
                                finally:
                                    con.close()
                            except Exception:
                                pass
                    _mb_application_cache[key]=names
                return 'MicroFe' if pos.casefold() in names else 'BauStatik'
            except Exception:
                return 'BauStatik'
'''


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.11"' in s:
        return 0
    if 'APP_VERSION = "1.4.10"' not in s:
        raise RuntimeError('Update 1.4.11 erwartet Projektzentrale 1.4.10. Es wurde nichts verändert.')
    original=s
    s=s.replace('APP_VERSION = "1.4.10"','APP_VERSION = "1.4.11"',1)

    # Application classification belongs next to the existing Positionsakte link helpers.
    marker='        def _detail_add_link(text,label,path,tag_index):'
    if marker not in s:
        raise RuntimeError('1.4.11 Marker für Positionsakte-Helfer fehlt.')
    if 'def _mb_application_for_position' not in s:
        s=s.replace(marker,APP_HELPER+'\n'+marker,1)

    # BauStatik.exe cannot be used standalone: mb itself requires the ProjektManager.
    old_action="""                if lead is not None:\n                    n=_detail_add_link(detail_text,'• ProjektManager öffnen',lead,n)\n                else:\n                    n=_detail_add_link(detail_text,'• mb-Projektordner öffnen',folder,n)\n                n=_detail_add_action(detail_text,'• BauStatik direkt öffnen',lambda f=folder:_open_baustatik_project(f),n)\n\n                dbsrc=str(r.get('_db') or '').strip()\n"""
    new_action="""                if lead is not None:\n                    n=_detail_add_link(detail_text,'• ProjektManager öffnen',lead,n)\n                else:\n                    n=_detail_add_link(detail_text,'• mb-Projektordner öffnen',folder,n)\n\n                dbsrc=str(r.get('_db') or '').strip()\n"""
    if old_action not in s:
        raise RuntimeError('1.4.11 Marker für direkten BauStatik-Start fehlt.')
    s=s.replace(old_action,new_action,1)

    # Show the responsible mb application based on real project content.
    old_meta="""                detail_text.insert('end',f'mb-Projekt: {projekt}\\nmb-Modul: {modul}\\nFachgruppe: {gruppe}\\nBerechnungsstatus: {status}\\n')\n\n                detail_text.insert('end','\\nDIREKT ÖFFNEN · DOPPELKLICK\\n')\n"""
    new_meta="""                mb_app=_mb_application_for_position(folder,r)\n                detail_text.insert('end',f'mb-Projekt: {projekt}\\nmb-Modul: {modul}\\nmb-Anwendung: {mb_app}\\nFachgruppe: {gruppe}\\nBerechnungsstatus: {status}\\n')\n                if mb_app=='MicroFe':\n                    detail_text.insert('end','Startweg: ProjektManager → MicroFe (bzw. aus BauStatik)\\n')\n                else:\n                    detail_text.insert('end','Startweg: ProjektManager → BauStatik\\n')\n\n                detail_text.insert('end','\\nÖFFNEN · DOPPELKLICK\\n')\n"""
    if old_meta not in s:
        raise RuntimeError('1.4.11 Marker für Positions-Metadaten fehlt.')
    s=s.replace(old_meta,new_meta,1)

    s=s.replace(
        'Hinweis 1.4.10: BauStatik-Suche erweitert: Windows-Registry, Program-Files-Varianten und Unterordner wie x64/bin werden automatisch geprüft. Bei Sonderinstallationen kann BauStatik.exe einmal manuell gewählt werden. Alles read-only.',
        'Hinweis 1.4.11: mb-konformer Startweg: BauStatik wird nicht mehr standalone gestartet, da mb die Oberfläche ausschließlich aus dem ProjektManager öffnet. MicroFe-Modelle werden anhand der FEM-Projektdaten automatisch erkannt. Alles read-only.'
    )
    s=s.replace(
        'Quelle: BSPos.mbdb wird je mb-Projekt automatisch gesucht · SQLite mode=ro. Positionsakte 1.4.10 startet ProjektManager oder BauStatik getrennt; BauStatik wird robust über Registry und Installationsordner gesucht.',
        'Quelle: BSPos.mbdb und FEM/*.mbdb werden je mb-Projekt ausschließlich read-only gelesen. Positionsakte 1.4.11 erkennt BauStatik/MicroFe und öffnet mb-konform über den ProjektManager.'
    )

    required=(
        'APP_VERSION = "1.4.11"',
        'def _mb_application_for_position',
        "return 'MicroFe' if pos.casefold() in names else 'BauStatik'",
        "mb-Anwendung: {mb_app}",
        'Startweg: ProjektManager → MicroFe',
        'ÖFFNEN · DOPPELKLICK',
        '• ProjektManager öffnen',
    )
    if not all(x in s for x in required):
        raise RuntimeError('Patch-Ergebnis 1.4.11 unvollständig. Es wurde nichts verändert.')
    # Direct launch must no longer be exposed in the UI.
    if "_detail_add_action(detail_text,'• BauStatik direkt öffnen'" in s:
        raise RuntimeError('Direkter BauStatik-Start ist noch in der Oberfläche aktiv.')
    if s==original:
        raise RuntimeError('Keine Änderung erzeugt.')

    tmp=APP.with_name('app.py.1411.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.v1410_vor_1411_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp.replace(APP)
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1411_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        print('FEHLER:',e)
        raise SystemExit(1)
