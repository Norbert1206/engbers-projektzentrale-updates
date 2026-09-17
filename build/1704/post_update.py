from pathlib import Path
import re
import runpy

BASE=Path(__file__).resolve().parent
APP=BASE/'app.py'


def current_version():
    try:
        text=APP.read_text(encoding='utf-8')
    except Exception:
        return ''
    m=re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']',text)
    return m.group(1).strip() if m else ''


def run_patch(name):
    p=BASE/name
    if not p.exists():
        raise RuntimeError(f'Kumulatives Update: {name} fehlt im Paket.')
    ns=runpy.run_path(str(p),run_name=name.replace('.py',''))
    fn=ns.get('main')
    if not callable(fn):
        raise RuntimeError(f'Kumulatives Update: {name} enthält keine main()-Funktion.')
    rc=fn()
    if rc not in (None,0):
        raise RuntimeError(f'Kumulatives Update: {name} lieferte Rückgabecode {rc}.')


v=current_version()
if v=='1.7.1':
    run_patch('patch_1702.py')
    v=current_version()
if v=='1.7.2':
    run_patch('patch_1703.py')
    v=current_version()
if v=='1.7.3':
    run_patch('patch_1704.py')
    v=current_version()
if v!='1.7.4':
    raise RuntimeError(f'Kumulatives Update 1.7.4 konnte nicht abgeschlossen werden. Aktueller Stand: {v or "unbekannt"}')
