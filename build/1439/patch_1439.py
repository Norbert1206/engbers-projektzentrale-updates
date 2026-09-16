from pathlib import Path
import datetime
import py_compile
import shutil

APP=Path(__file__).resolve().parent/'app.py'


def _compile_text(text,name='app.py.1439.check'):
    tmp=APP.with_name(name)
    try:
        tmp.write_text(text,encoding='utf-8')
        py_compile.compile(str(tmp),doraise=True)
    finally:
        try: tmp.unlink()
        except Exception: pass


def _patch_search_order(s):
    if 'PZ_SEARCH_ORDER_V1439' in s:
        return s, True

    old="""        if _pz_1438_activate_project(str(_vals[1]).strip()):
            try:{TOP}.after(70,{TOP}.destroy)
            except Exception:pass
            return 'break'
"""

    # top-level variable is generated into the installed app. Detect it from the
    # existing 1.4.38 function body instead of guessing names.
    marker="def _pz_1438_open_project(_evt=None):"
    start=s.find(marker)
    if start<0:
        return s, False
    end=s.find("def _pz_1438_bind_project_open():",start)
    if end<0:
        return s, False
    block=s[start:end]

    # Find the concrete Toplevel variable from the current destroy call.
    import re
    m=re.search(r"try:(?P<top>[A-Za-z_]\w*)\.after\(70,(?P=top)\.destroy\)",block)
    if not m:
        return s, False
    top=m.group('top')
    concrete=old.replace('{TOP}',top)
    if concrete not in block:
        return s, False

    new=f"""        # PZ_SEARCH_ORDER_V1439: Suchfenster zuerst schließen, dann Projekt wechseln.
        # Damit ist ein evtl. modales wait_window/grab vollständig beendet, bevor
        # der Projektwähler sein <<ComboboxSelected>> verarbeitet.
        _target=str(_vals[1]).strip()
        try:
            _main={top}
            while getattr(_main,'master',None) is not None:
                _main=_main.master
        except Exception:
            _main=None
        try:{top}.destroy()
        except Exception:pass
        def _pz_1439_switch_after_close():
            try:
                _pz_1438_activate_project(_target)
            except Exception:
                pass
        try:
            if _main is not None:
                _main.after(120,_pz_1439_switch_after_close)
            else:
                _pz_1439_switch_after_close()
        except Exception:
            _pz_1439_switch_after_close()
        return 'break'
"""
    block2=block.replace(concrete,new,1)
    return s[:start]+block2+s[end:], True


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.39"' in s:
        return 0
    if 'APP_VERSION = "1.4.38"' not in s:
        raise RuntimeError('Update 1.4.39 erwartet Projektzentrale 1.4.38. Es wurde nichts verändert.')

    s=s.replace('APP_VERSION = "1.4.38"','APP_VERSION = "1.4.39"',1)
    candidate,ok=_patch_search_order(s)
    if not ok:
        raise RuntimeError('1.4.39 konnte den vorhandenen Suchhandler aus 1.4.38 nicht sicher erkennen. Es wurde nichts verändert.')
    s=candidate

    if 'PZ_SEARCH_ORDER_V1439' not in s:
        raise RuntimeError('Suchkorrektur 1.4.39 fehlt.')
    if '.after(120,_pz_1439_switch_after_close)' not in s:
        raise RuntimeError('Verzögerter Projektwechsel 1.4.39 fehlt.')

    _compile_text(s,'app.py.1439.final.check')
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.v1438_vor_1439_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp=APP.with_name('app.py.1439.tmp')
    tmp.write_text(s,encoding='utf-8')
    tmp.replace(APP)
    return 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1439_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        raise SystemExit(1)
