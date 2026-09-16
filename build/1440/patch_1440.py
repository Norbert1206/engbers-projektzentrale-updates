from pathlib import Path
import datetime
import py_compile
import re
import shutil

APP=Path(__file__).resolve().parent/'app.py'


def _compile_text(text,name='app.py.1440.check'):
    tmp=APP.with_name(name)
    try:
        tmp.write_text(text,encoding='utf-8')
        py_compile.compile(str(tmp),doraise=True)
    finally:
        try: tmp.unlink()
        except Exception: pass


def _patch_search(s):
    if 'PZ_SEARCH_NAV_V1440' in s:
        return s, True

    marker='def _pz_1438_open_project(_evt=None):'
    start=s.find(marker)
    if start<0:
        return s, False
    end=s.find('def _pz_1438_bind_project_open():',start)
    if end<0:
        return s, False
    block=s[start:end]

    tm=re.search(r'(?P<tree>[A-Za-z_]\w*)\.identify_row\(_evt\.y\)',block)
    if not tm:
        tm=re.search(r'(?P<tree>[A-Za-z_]\w*)\.selection\(\)',block)
    if not tm:
        return s, False
    tree=tm.group('tree')

    top=None
    for pat in (
        r'(?P<top>[A-Za-z_]\w*)\.after\(70,(?P=top)\.destroy\)',
        r'try:(?P<top>[A-Za-z_]\w*)\.destroy\(\)',
    ):
        m=re.search(pat,block)
        if m:
            top=m.group('top'); break
    if not top:
        return s, False

    line_start=s.rfind('\n',0,start)+1
    end_line_start=s.rfind('\n',0,end)+1
    indent=s[line_start:start]
    body=f'''def _pz_1438_open_project(_evt=None):
    # PZ_SEARCH_NAV_V1440
    # Suchfenster vollständig schließen und erst danach den Projektwähler
    # im Hauptfenster setzen. Die Suche nach dem Wähler ist absichtlich
    # generisch und nicht auf einen bestimmten Combobox-Klassennamen begrenzt.
    try:
        _iid=''
        if _evt is not None:
            try:_iid={tree}.identify_row(_evt.y)
            except Exception:_iid=''
        if not _iid:
            try:
                _sel={tree}.selection()
                if _sel:_iid=_sel[0]
            except Exception:
                _iid=''
        if not _iid:
            return
        try:{tree}.selection_set(_iid)
        except Exception:pass
        _vals={tree}.item(_iid,'values')
        if len(_vals)<2 or str(_vals[0]).strip().casefold()!='projekt':
            return
        _target=str(_vals[1]).strip()
        if not _target:
            return

        try:
            _main={top}
            while getattr(_main,'master',None) is not None:
                _main=_main.master
        except Exception:
            _main=None

        def _norm(_value):
            _txt=''.join((_c.casefold() if _c.isalnum() else ' ') for _c in str(_value or ''))
            return ' '.join(_txt.split())

        try:{top}.destroy()
        except Exception:pass

        def _switch_project():
            try:
                if _main is None:
                    raise RuntimeError('Hauptfenster nicht gefunden')
                _wanted=_norm(_target)
                _m=re.search(r'\\b\\d{{2}}-\\d{{3}}\\b',_target)
                _number=_m.group(0).casefold() if _m else ''
                def _walk(_w):
                    yield _w
                    try:
                        for _child in _w.winfo_children():
                            yield from _walk(_child)
                    except Exception:
                        return
                _best=None
                for _widget in _walk(_main):
                    try:
                        _values=list(_widget.cget('values'))
                    except Exception:
                        continue
                    if not _values:
                        continue
                    for _idx,_candidate in enumerate(_values):
                        _cn=_norm(_candidate)
                        _score=0
                        if _cn==_wanted:
                            _score=100
                        elif _number and _number in str(_candidate).casefold():
                            _score=90
                        elif _wanted and (_wanted in _cn or _cn in _wanted):
                            _score=60
                        if _score and (_best is None or _score>_best[0]):
                            _best=(_score,_widget,_idx,_candidate)
                if _best is None:
                    try:
                        from tkinter import messagebox as _mbx
                        _mbx.showwarning('Projektsuche',f'Projekttreffer erkannt, aber der Projektwähler konnte nicht gefunden werden.\\n\\nZiel: {{_target}}')
                    except Exception:
                        pass
                    return
                _,_widget,_idx,_candidate=_best
                try:_widget.current(_idx)
                except Exception:
                    try:_widget.set(_candidate)
                    except Exception:pass
                try:_widget.event_generate('<<ComboboxSelected>>',when='now')
                except Exception:
                    try:_widget.event_generate('<<ComboboxSelected>>')
                    except Exception:pass
                try:_main.update_idletasks()
                except Exception:pass
            except Exception as _exc:
                try:
                    from tkinter import messagebox as _mbx
                    _mbx.showwarning('Projektsuche',f'Der Projektwechsel konnte nicht ausgeführt werden.\\n\\n{{_exc}}')
                except Exception:
                    pass
        try:
            if _main is not None:
                _main.after(120,_switch_project)
            else:
                _switch_project()
        except Exception:
            _switch_project()
        return 'break'
    except Exception:
        return

'''
    new_block=''.join((indent+ln if ln.strip() else ln) for ln in body.splitlines(keepends=True))
    return s[:line_start]+new_block+s[end_line_start:], True


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.40"' in s:
        return 0

    previous=None
    for _v in ('1.4.39','1.4.38'):
        if f'APP_VERSION = "{_v}"' in s:
            previous=_v
            s=s.replace(f'APP_VERSION = "{_v}"','APP_VERSION = "1.4.40"',1)
            break
    if previous is None:
        raise RuntimeError('Reparatur 1.4.40 erwartet Projektzentrale 1.4.38 oder 1.4.39. Es wurde nichts verändert.')

    report=[f'Ausgangsversion: {previous}']
    try:
        candidate,changed=_patch_search(s)
        if changed:
            _compile_text(candidate,'app.py.1440.search.check')
            s=candidate
            report.append('Projektsuche/Doppelklick: 1.4.40-Korrektur eingebaut')
        else:
            report.append('Projektsuche/Doppelklick: vorhandener Suchhandler nicht erkannt; Versionsreparatur trotzdem ausgeführt')
    except Exception as exc:
        report.append('Projektsuche/Doppelklick: übersprungen ('+str(exc)+')')

    _compile_text(s,'app.py.1440.final.check')
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.vor_1440_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp=APP.with_name('app.py.1440.tmp')
    tmp.write_text(s,encoding='utf-8')
    tmp.replace(APP)
    try:
        APP.with_name('patch_1440_report.txt').write_text('\n'.join(report)+'\n',encoding='utf-8')
    except Exception:
        pass
    return 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1440_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        raise SystemExit(1)
