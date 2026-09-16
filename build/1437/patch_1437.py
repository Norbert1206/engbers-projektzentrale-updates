from pathlib import Path
import datetime
import py_compile
import re
import shutil

APP=Path(__file__).resolve().parent/'app.py'


def _compile_text(text,name='app.py.1437.check'):
    tmp=APP.with_name(name)
    try:
        tmp.write_text(text,encoding='utf-8')
        py_compile.compile(str(tmp),doraise=True)
    finally:
        try: tmp.unlink()
        except Exception: pass


def _patch_search_click(s):
    # 1.4.35 besitzt bereits die Projektnavigation. Der Fehler war nur,
    # dass beim Doppelklick die vorherige Auswahl statt der tatsächlich
    # angeklickten Treeview-Zeile ausgewertet wurde.
    if 'PZ_SEARCH_CLICK_V1437' in s:
        return s, True

    # Suche gezielt nur innerhalb des von 1.4.35 eingebauten Handlers.
    m=re.search(
        r"(?P<indent>^[ \t]*)def _pz_open_search_project\(_evt=None\):\n(?P<body>(?:(?P=indent)[ \t]+.*\n|\n)+?)(?=^(?P=indent)\S)",
        s,
        flags=re.M,
    )
    if not m:
        return s, False

    block=m.group(0)
    # Treeview-Variablenname und tatsächliche Einrückung aus der selection()-Zeile ermitteln.
    tm=re.search(r"(?m)^(?P<bi>[ \t]+)_sel=(?P<tree>[A-Za-z_]\w*)\.selection\(\)\n",block)
    if not tm:
        return s, False
    tree=tm.group('tree')
    bi=tm.group('bi')
    ci=bi+'    '

    old=(
        f"{bi}_sel={tree}.selection()\n"
        f"{bi}if not _sel:\n"
        f"{ci}return\n"
        f"{bi}_vals={tree}.item(_sel[0],'values')\n"
    )
    if old not in block:
        return s, False

    new=(
        f"{bi}# PZ_SEARCH_CLICK_V1437: immer die tatsächlich angeklickte Zeile verwenden.\n"
        f"{bi}_iid=''\n"
        f"{bi}if _evt is not None:\n"
        f"{ci}try:_iid={tree}.identify_row(_evt.y)\n"
        f"{ci}except Exception:_iid=''\n"
        f"{bi}if not _iid:\n"
        f"{ci}_sel={tree}.selection()\n"
        f"{ci}if _sel:_iid=_sel[0]\n"
        f"{bi}if not _iid:\n"
        f"{ci}return\n"
        f"{bi}try:{tree}.selection_set(_iid)\n"
        f"{bi}except Exception:pass\n"
        f"{bi}_vals={tree}.item(_iid,'values')\n"
    )
    block2=block.replace(old,new,1)
    if block2==block:
        return s, False
    return s[:m.start()]+block2+s[m.end():], True


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.37"' in s:
        return 0

    if 'APP_VERSION = "1.4.35"' in s:
        s=s.replace('APP_VERSION = "1.4.35"','APP_VERSION = "1.4.37"',1)
    elif 'APP_VERSION = "1.4.36"' in s:
        s=s.replace('APP_VERSION = "1.4.36"','APP_VERSION = "1.4.37"',1)
    else:
        raise RuntimeError('Reparatur 1.4.37 erwartet Projektzentrale 1.4.35 oder 1.4.36. Es wurde nichts verändert.')

    report=[]
    try:
        candidate, changed=_patch_search_click(s)
        if changed:
            _compile_text(candidate,'app.py.1437.search.check')
            s=candidate
            report.append('Such-Doppelklick: OK')
        else:
            report.append('Such-Doppelklick: vorhandener 1.4.35-Handler nicht gefunden; Version dennoch sauber aktualisiert')
    except Exception as exc:
        report.append('Such-Doppelklick: übersprungen ('+str(exc)+')')

    # Entscheidend: Dieses Reparaturupdate darf nicht wieder an einem optionalen
    # UI-Marker scheitern. Die bestehende, lauffähige App wird immer auf 1.4.37
    # angehoben; nur syntaktisch gültiger Zusatzcode wird übernommen.
    _compile_text(s,'app.py.1437.final.check')

    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.vor_1437_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp=APP.with_name('app.py.1437.tmp')
    tmp.write_text(s,encoding='utf-8')
    tmp.replace(APP)
    try:
        APP.with_name('patch_1437_report.txt').write_text('\n'.join(report)+'\n',encoding='utf-8')
    except Exception:
        pass
    return 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1437_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        raise SystemExit(1)
