from pathlib import Path
import datetime
import py_compile
import re
import shutil

APP=Path(__file__).resolve().parent/'app.py'


def _compile_text(text,name='app.py.1441.check'):
    tmp=APP.with_name(name)
    try:
        tmp.write_text(text,encoding='utf-8')
        py_compile.compile(str(tmp),doraise=True)
    finally:
        try: tmp.unlink()
        except Exception: pass


def _patch_search_direct(s):
    if 'PZ_SEARCH_DIRECT_V1441' in s:
        return s, True

    marker='def _pz_1438_open_project(_evt=None):'
    start=s.find(marker)
    if start < 0:
        return s, False
    end=s.find('def _pz_1438_bind_project_open():', start)
    if end < 0:
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
        r'try:(?P<top>[A-Za-z_]\w*)\.destroy\(\)',
        r'(?P<top>[A-Za-z_]\w*)\.after\(70,(?P=top)\.destroy\)',
    ):
        m=re.search(pat,block)
        if m:
            top=m.group('top')
            break
    if not top:
        # In 1.4.40 the Toplevel variable is also used while climbing to _main.
        m=re.search(r'_main=(?P<top>[A-Za-z_]\w*)\n',block)
        if m:
            top=m.group('top')
    if not top:
        return s, False

    line_start=s.rfind('\n',0,start)+1
    indent=re.match(r'^[ \t]*',s[line_start:start]).group(0)

    body=f'''def _pz_1438_open_project(_evt=None):
    # PZ_SEARCH_DIRECT_V1441
    # Direkter Projektwechsel über die bereits vorhandenen App-Attribute
    # self.project_map / self.project_var / self.project_id. Kein Suchen des
    # Projektwählers in der Widget-Hierarchie mehr.
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

        def _norm(_value):
            _txt=''.join((_c.casefold() if _c.isalnum() else ' ') for _c in str(_value or ''))
            return ' '.join(_txt.split())

        _wanted=_norm(_target)
        _m=re.search(r'\\b\\d{{2}}-\\d{{3}}\\b',_target)
        _number=_m.group(0).casefold() if _m else ''
        _label=None
        _pid=None
        try:
            _items=list(getattr(self,'project_map',{{}}).items())
        except Exception:
            _items=[]
        for _candidate,_candidate_pid in _items:
            _cn=_norm(_candidate)
            if _cn==_wanted or (_number and _number in str(_candidate).casefold()):
                _label=_candidate
                _pid=_candidate_pid
                if _cn==_wanted:
                    break
        if _label is None:
            try:
                self.refresh_project_combo()
                _items=list(getattr(self,'project_map',{{}}).items())
            except Exception:
                _items=[]
            for _candidate,_candidate_pid in _items:
                _cn=_norm(_candidate)
                if _cn==_wanted or (_number and _number in str(_candidate).casefold()):
                    _label=_candidate
                    _pid=_candidate_pid
                    if _cn==_wanted:
                        break
        if _label is None or _pid is None:
            try:
                from tkinter import messagebox as _mbx
                _mbx.showwarning('Projektsuche',f'Das gefundene Projekt konnte nicht in der Projektliste aufgelöst werden.\\n\\nZiel: {{_target}}')
            except Exception:
                pass
            return 'break'

        # Aktuellen Fachbereich merken, damit z.B. Statik -> Statik erhalten bleibt.
        _active_label=None
        try:
            for _nav_label,_button in getattr(self,'nav_buttons',{{}}).items():
                try:
                    if str(_button.cget('bg')).casefold()==str(DARK2).casefold():
                        _active_label=_nav_label
                        break
                except Exception:
                    continue
        except Exception:
            _active_label=None

        try:{top}.destroy()
        except Exception:pass

        def _switch_project_direct():
            try:
                self.project_id=_pid
                try:self.project_var.set(_label)
                except Exception:pass
                try:self.refresh_project_combo()
                except Exception:pass
                if _active_label and _active_label in getattr(self,'nav_buttons',{{}}):
                    try:self.nav_buttons[_active_label].invoke()
                    except Exception:self.show_dashboard()
                else:
                    self.show_dashboard()
            except Exception as _exc:
                try:
                    from tkinter import messagebox as _mbx
                    _mbx.showwarning('Projektsuche',f'Der direkte Projektwechsel konnte nicht ausgeführt werden.\\n\\n{{_exc}}')
                except Exception:
                    pass
        try:self.after(80,_switch_project_direct)
        except Exception:_switch_project_direct()
        return 'break'
    except Exception as _exc:
        try:
            from tkinter import messagebox as _mbx
            _mbx.showwarning('Projektsuche',f'Der Projekttreffer konnte nicht geöffnet werden.\\n\\n{{_exc}}')
        except Exception:
            pass
        return

'''
    new_block=''.join((indent+ln if ln.strip() else ln) for ln in body.splitlines(keepends=True))
    return s[:start]+new_block+s[end:], True


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    original=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.41"' in original:
        return 0

    previous=None
    for _v in ('1.4.40','1.4.39','1.4.38'):
        if f'APP_VERSION = "{_v}"' in original:
            previous=_v
            break
    if previous is None:
        raise RuntimeError('Update 1.4.41 erwartet Projektzentrale 1.4.38 bis 1.4.40. Es wurde nichts verändert.')

    # Erst Kernkorrektur anwenden und prüfen. Die Versionsnummer wird absichtlich
    # erst danach geändert, damit ein Fehlschlag nicht als installiert erscheint.
    candidate,changed=_patch_search_direct(original)
    if not changed or 'PZ_SEARCH_DIRECT_V1441' not in candidate:
        raise RuntimeError('1.4.41 konnte den vorhandenen Suchhandler nicht sicher erkennen. Die installierte Version bleibt unverändert.')
    _compile_text(candidate,'app.py.1441.search.check')

    candidate=candidate.replace(f'APP_VERSION = "{previous}"','APP_VERSION = "1.4.41"',1)
    _compile_text(candidate,'app.py.1441.final.check')

    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.vor_1441_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp=APP.with_name('app.py.1441.tmp')
    tmp.write_text(candidate,encoding='utf-8')
    tmp.replace(APP)
    try:
        APP.with_name('patch_1441_report.txt').write_text(
            f'Ausgangsversion: {previous}\nProjektsuche: direkter Wechsel über self.project_map/project_id eingebaut\n',
            encoding='utf-8')
    except Exception:
        pass
    return 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1441_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        raise SystemExit(1)
