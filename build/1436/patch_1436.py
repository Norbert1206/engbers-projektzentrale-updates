from pathlib import Path
import ast
import datetime
import py_compile
import re
import shutil

APP=Path(__file__).resolve().parent/'app.py'


def _compile_text(text,name):
    tmp=APP.with_name(name)
    try:
        tmp.write_text(text,encoding='utf-8')
        py_compile.compile(str(tmp),doraise=True)
    finally:
        try: tmp.unlink()
        except Exception: pass


def _patch_search_navigation(s):
    if 'PZ_SEARCH_NAV_V1436' in s:
        return s

    tree=ast.parse(s)
    target=None
    top_name=None
    insert_after=None

    for node in ast.walk(tree):
        if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            continue
        segment=ast.get_source_segment(s,node) or ''
        if 'Suchergebnisse' not in segment or 'Treeview' not in segment:
            continue
        for sub in ast.walk(node):
            if not isinstance(sub,ast.Assign) or not sub.targets or not isinstance(sub.targets[0],ast.Name):
                continue
            val=sub.value
            if not isinstance(val,ast.Call):
                continue
            f=val.func
            is_top=(isinstance(f,ast.Attribute) and f.attr=='Toplevel') or (isinstance(f,ast.Name) and f.id=='Toplevel')
            if is_top:
                target=node
                top_name=sub.targets[0].id
                insert_after=getattr(sub,'end_lineno',sub.lineno)
                break
        if target:
            break

    if not target or not top_name or not insert_after:
        raise RuntimeError('Suchfenster konnte für 1.4.36 nicht sicher erkannt werden.')

    lines=s.splitlines(keepends=True)
    indent=re.match(r'^[ \t]*',lines[insert_after-1]).group(0)

    body=f'''# PZ_SEARCH_NAV_V1436

def _pz_search_norm(_value):
    _txt=''.join((_c.casefold() if _c.isalnum() else ' ') for _c in str(_value or ''))
    return ' '.join(_txt.split())

def _pz_search_activate_project(_target):
    try:
        _wanted=_pz_search_norm(_target)
        _m=re.search(r'\\b\\d{{2}}-\\d{{3}}\\b',str(_target or ''))
        _number=_m.group(0).casefold() if _m else ''
        _root={top_name}
        while getattr(_root,'master',None) is not None:
            _root=_root.master
        def _walk(_w):
            yield _w
            try:
                for _child in _w.winfo_children():
                    yield from _walk(_child)
            except Exception:
                return
        for _widget in _walk(_root):
            try:
                if str(_widget.winfo_class()) not in ('TCombobox','Combobox'):
                    continue
                _values=list(_widget.cget('values'))
            except Exception:
                continue
            for _candidate in _values:
                _cn=_pz_search_norm(_candidate)
                _match=(_cn==_wanted) or (_number and _number in str(_candidate).casefold())
                if not _match:
                    continue
                _widget.set(_candidate)
                try:
                    _widget.event_generate('<<ComboboxSelected>>',when='now')
                except Exception:
                    try:_widget.event_generate('<<ComboboxSelected>>')
                    except Exception:pass
                try:_root.update_idletasks()
                except Exception:pass
                try:{top_name}.after(80,{top_name}.destroy)
                except Exception:pass
                return True
    except Exception:
        pass
    return False

def _pz_search_open_from_tree(_tree,_evt=None):
    try:
        _iid=''
        if _evt is not None:
            try:_iid=_tree.identify_row(_evt.y)
            except Exception:_iid=''
        if not _iid:
            _sel=_tree.selection()
            if _sel:_iid=_sel[0]
        if not _iid:
            return
        try:_tree.selection_set(_iid)
        except Exception:pass
        _vals=_tree.item(_iid,'values')
        if len(_vals)<2:
            return
        if str(_vals[0]).strip().casefold()!='projekt':
            return
        _pz_search_activate_project(str(_vals[1]).strip())
    except Exception:
        return

def _pz_search_bind_result_trees():
    try:
        def _walk(_w):
            yield _w
            try:
                for _child in _w.winfo_children():
                    yield from _walk(_child)
            except Exception:
                return
        for _widget in _walk({top_name}):
            try:
                if str(_widget.winfo_class())!='Treeview':
                    continue
                _cols=[str(x).casefold() for x in list(_widget.cget('columns'))]
                if len(_cols)<2:
                    continue
                _has_project=False
                for _iid in _widget.get_children(''):
                    _vals=_widget.item(_iid,'values')
                    if len(_vals)>=2 and str(_vals[0]).strip().casefold()=='projekt':
                        _has_project=True
                        break
                if not _has_project:
                    continue
                _widget.bind('<Double-1>',lambda _e,_t=_widget:_pz_search_open_from_tree(_t,_e),add='+')
                _widget.bind('<Return>',lambda _e,_t=_widget:_pz_search_open_from_tree(_t,_e),add='+')
            except Exception:
                continue
    except Exception:
        pass

try:{top_name}.after_idle(_pz_search_bind_result_trees)
except Exception:pass
try:{top_name}.after(120,_pz_search_bind_result_trees)
except Exception:pass
'''
    block=''.join((indent+ln if ln.strip() else ln) for ln in body.splitlines(keepends=True))
    lines.insert(insert_after,block)
    return ''.join(lines)


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.36"' in s:
        return 0
    if 'APP_VERSION = "1.4.35"' not in s:
        raise RuntimeError('Update 1.4.36 erwartet Projektzentrale 1.4.35. Es wurde nichts verändert.')

    original=s
    s=s.replace('APP_VERSION = "1.4.35"','APP_VERSION = "1.4.36"',1)
    s=_patch_search_navigation(s)

    if 'PZ_SEARCH_NAV_V1436' not in s:
        raise RuntimeError('Suchnavigation 1.4.36 wurde nicht eingebaut.')
    if "identify_row(_evt.y)" not in s:
        raise RuntimeError('Doppelklick-Zeile 1.4.36 fehlt.')
    if "event_generate('<<ComboboxSelected>>'" not in s:
        raise RuntimeError('Projektwechsel 1.4.36 fehlt.')

    s=s.replace(
        'APP_VERSION = "1.4.36"',
        'APP_VERSION = "1.4.36"',1
    )

    _compile_text(s,'app.py.1436.check')
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.v1435_vor_1436_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp=APP.with_name('app.py.1436.tmp')
    tmp.write_text(s,encoding='utf-8')
    tmp.replace(APP)
    return 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1436_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        raise SystemExit(1)
