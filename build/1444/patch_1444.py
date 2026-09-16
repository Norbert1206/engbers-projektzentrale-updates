from pathlib import Path
import datetime, py_compile, shutil
import patch_1444_ui, patch_1444_positions
APP=Path(__file__).resolve().parent/'app.py'
def compile_text(text,name):
    p=APP.with_name(name)
    try:p.write_text(text,encoding='utf-8'); py_compile.compile(str(p),doraise=True)
    finally:
        try:p.unlink()
        except Exception:pass
def main():
    if not APP.exists():raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.44"' in s:return 0
    if 'APP_VERSION = "1.4.43"' not in s:raise RuntimeError('Update 1.4.44 erwartet exakt Projektzentrale 1.4.43. Es wurde nichts verändert.')
    s=patch_1444_ui.apply(s); s=patch_1444_positions.apply(s)
    need=('PZ_STATIK_PDF_NAV_V1444','PZ_STATIK_PDF_ROOT_V1444','def _position_layout_1444()',"win.title('Kategorie wählen')",'PZ_SEARCH_DOCUMENT_OPEN_V1444')
    miss=[x for x in need if x not in s]
    if miss:raise RuntimeError('1.4.44 unvollständig: '+', '.join(miss))
    compile_text(s,'app.py.1444.features.check'); s=s.replace('APP_VERSION = "1.4.43"','APP_VERSION = "1.4.44"',1); compile_text(s,'app.py.1444.final.check')
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S'); shutil.copy2(APP,APP.with_name(f'app.py.vor_1444_{stamp}.bak'))
    tmp=APP.with_name('app.py.1444.tmp'); tmp.write_text(s,encoding='utf-8'); tmp.replace(APP)
    try:APP.with_name('patch_1444_report.txt').write_text('Ausgangsversion: 1.4.43\nPositionsliste kompakt + Statusdarstellung korrigiert\nStatusfilter kombiniert\nPositionsdatei-Kategorie wählbar + Sofortaktualisierung\nStatik PDF: richtiger Projektordner + Sidebar-Unterpunkt\nGlobale Suche: Dokumenttreffer öffnen\n',encoding='utf-8')
    except Exception:pass
    return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1444_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        raise SystemExit(1)
