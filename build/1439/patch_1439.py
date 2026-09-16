from pathlib import Path
import datetime
import py_compile
import re
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

    marker="def _pz_1438_open_project(_evt=None):"
    start=s.find(marker)
    if start<0:
        return s, False
    end=s.find("def _pz_1438_bind_project_open():",start)
    if end<0:
        return s, False
    block=s[start:end]

    # Preserve the real indentation from the installed app. The search function
    # is nested, therefore hard-coded spaces are intentionally avoided here.
    pat=re.compile(
        r"(?P<indent>^[ \t]*)if _pz_1438_activate_project\(str\(_vals\[1\]\)\.strip\(\)\):\n"
        r"(?P=indent)[ \t]+try:(?P<top>[A-Za-z_]\w*)\.after\(70,(?P=top)\.destroy\)\n"
        r"(?P=indent)[ \t]+except Exception:pass\n"
        r"(?P=indent)[ \t]+return 'break'\n",
        flags=re.M,
    )
    m=pat.search(block)
    if not m:
        return s, False
    indent=m.group('indent')
    top=m.group('top')
    child=indent+'    '

    new=(
        indent+"# PZ_SEARCH_ORDER_V1439: Suchfenster zuerst schließen, dann Projekt wechseln.\n"
        +indent+"# Damit ist ein modales wait_window/grab beendet, bevor der Projektwähler reagiert.\n"
        +indent+"_target=str(_vals[1]).strip()\n"
        +indent+"try:\n"
        +child+f"_main={top}\n"
        +child+"while getattr(_main,'master',None) is not None:\n"
        +child+"    _main=_main.master\n"
        +indent+"except Exception:\n"
        +child+"_main=None\n"
        +indent+f"try:{top}.destroy()\n"
        +indent+"except Exception:pass\n"
        +indent+"def _pz_1439_switch_after_close():\n"
        +child+"try:\n"
        +child+"    _ok=_pz_1438_activate_project(_target)\n"
        +child+"    if not _ok:\n"
        +child+"        try:\n"
        +child+"            from tkinter import messagebox as _pz_mbx\n"
        +child+"            _pz_mbx.showwarning('Projekt öffnen','Der Projekttreffer wurde erkannt, aber der Projektwähler konnte nicht umgeschaltet werden.')\n"
        +child+"        except Exception:pass\n"
        +child+"except Exception:\n"
        +child+"    pass\n"
        +indent+"try:\n"
        +child+"if _main is not None:\n"
        +child+"    _main.after(120,_pz_1439_switch_after_close)\n"
        +child+"else:\n"
        +child+"    _pz_1439_switch_after_close()\n"
        +indent+"except Exception:\n"
        +child+"_pz_1439_switch_after_close()\n"
        +indent+"return 'break'\n"
    )
    block2=block[:m.start()]+new+block[m.end():]
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
