from pathlib import Path
import ast
import datetime
import py_compile
import re
import shutil

APP=Path(__file__).resolve().parent/'app.py'


def _compile_text(text,name='app.py.1442.check'):
    tmp=APP.with_name(name)
    try:
        tmp.write_text(text,encoding='utf-8')
        py_compile.compile(str(tmp),doraise=True)
    finally:
        try: tmp.unlink()
        except Exception: pass


def _patch_search_end_binding(s):
    if 'PZ_SEARCH_DIRECT_V1442' in s:
        return s, True

    tree=ast.parse(s)
    targets=[]
    for node in ast.walk(tree):
        if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            continue
        seg=ast.get_source_segment(s,node) or ''
        if 'Suchergebnisse' not in seg or 'Treeview' not in seg:
            continue
        trees=[]
        for sub in ast.walk(node):
            if not isinstance(sub,ast.Assign) or not sub.targets or not isinstance(sub.targets[0],ast.Name):
                continue
            val=sub.value
            if not isinstance(val,ast.Call):
                continue
            f=val.func
            if (isinstance(f,ast.Attribute) and f.attr=='Treeview') or (isinstance(f,ast.Name) and f.id=='Treeview'):
                trees.append((sub,sub.targets[0].id))
        if trees:
            trees.sort(key=lambda x:x[0].lineno)
            targets.append((node,trees[-1][1]))
    if not targets:
        return s, False
    targets.sort(key=lambda x:(getattr(x[0],'end_lineno',x[0].lineno)-x[0].lineno,x[0].lineno))
    fn,tree_name=targets[0]

    lines=s.splitlines(keepends=True)
    # Body-Einrückung aus einer vorhandenen Zeile innerhalb der Funktion ableiten.
    fn_indent=re.match(r'^[ \t]*',lines[fn.lineno-1]).group(0)
    body_indent=fn_indent+'    '
    for ln in lines[fn.lineno:getattr(fn,'end_lineno',fn.lineno)]:
        if ln.strip():
            ind=re.match(r'^[ \t]*',ln).group(0)
            if len(ind)>len(fn_indent):
                body_indent=ind
                break

    body=f'''# PZ_SEARCH_DIRECT_V1442
# Diese Bindung wird bewusst ganz am Ende der Suchfunktion gesetzt und ersetzt
# ältere Doubleclick-Bindungen. Projektwechsel erfolgt direkt über project_map.
def _pz_1442_norm(_value):
    _txt=''.join((_c.casefold() if _c.isalnum() else ' ') for _c in str(_value or ''))
    return ' '.join(_txt.split())

def _pz_1442_open_project(_evt=None):
    try:
        _iid=''
        if _evt is not None:
            try:_iid={tree_name}.identify_row(_evt.y)
            except Exception:_iid=''
        if not _iid:
            try:
                _sel={tree_name}.selection()
                if _sel:_iid=_sel[0]
            except Exception:_iid=''
        if not _iid:
            return
        try:{tree_name}.selection_set(_iid)
        except Exception:pass
        _vals={tree_name}.item(_iid,'values')
        if len(_vals)<2 or str(_vals[0]).strip().casefold()!='projekt':
            return
        _target=str(_vals[1]).strip()
        if not _target:
            return

        _wanted=_pz_1442_norm(_target)
        _m=re.search(r'\\b\\d{{2}}-\\d{{3}}\\b',_target)
        _number=_m.group(0).casefold() if _m else ''

        def _resolve():
            try:_items=list(getattr(self,'project_map',{{}}).items())
            except Exception:_items=[]
            _best=None
            for _a,_b in _items:
                # Üblicher Fall: label -> project_id
                _an=_pz_1442_norm(_a)
                _score=0
                if _an==_wanted:_score=100
                elif _number and _number in str(_a).casefold():_score=90
                elif _wanted and (_wanted in _an or _an in _wanted):_score=60
                if _score and (_best is None or _score>_best[0]):
                    _best=(_score,_a,_b)
                # Fallback für eventuell umgekehrte Maps.
                if isinstance(_b,str):
                    _bn=_pz_1442_norm(_b)
                    _score2=0
                    if _bn==_wanted:_score2=100
                    elif _number and _number in _b.casefold():_score2=90
                    if _score2 and (_best is None or _score2>_best[0]):
                        _best=(_score2,_b,_a)
            return (_best[1],_best[2]) if _best else (None,None)

        _label,_pid=_resolve()
        if _label is None:
            try:self.refresh_project_combo()
            except Exception:pass
            _label,_pid=_resolve()
        if _label is None or _pid is None:
            try:
                from tkinter import messagebox as _mbx
                _mbx.showwarning('Projektsuche',f'Das gefundene Projekt konnte nicht in der internen Projektliste aufgelöst werden.\\n\\nZiel: {{_target}}')
            except Exception:pass
            return 'break'

        _top={tree_name}.winfo_toplevel()
        try:_top.destroy()
        except Exception:pass

        def _switch():
            try:
                try:self.project_var.set(_label)
                except Exception:pass
                self.project_id=_pid
                # Für maximale Stabilität zunächst immer die Projektübersicht laden.
                self.show_dashboard()
            except Exception as _exc:
                try:
                    from tkinter import messagebox as _mbx
                    _mbx.showwarning('Projektsuche',f'Der Projektwechsel konnte nicht ausgeführt werden.\\n\\n{{_exc}}')
                except Exception:pass
        try:self.after(60,_switch)
        except Exception:_switch()
        return 'break'
    except Exception as _exc:
        try:
            from tkinter import messagebox as _mbx
            _mbx.showwarning('Projektsuche',f'Der Projekttreffer konnte nicht geöffnet werden.\\n\\n{{_exc}}')
        except Exception:pass
        return 'break'

try:
    {tree_name}.bind('<Double-1>',_pz_1442_open_project)
    {tree_name}.bind('<Return>',_pz_1442_open_project)
except Exception:
    pass
'''
    block=''.join((body_indent+ln if ln.strip() else ln) for ln in body.splitlines(keepends=True))
    insert_index=getattr(fn,'end_lineno',fn.lineno)
    lines.insert(insert_index,block)
    return ''.join(lines), True


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    original=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.42"' in original:
        return 0

    previous=None
    for _v in ('1.4.41','1.4.40','1.4.39','1.4.38'):
        if f'APP_VERSION = "{_v}"' in original:
            previous=_v
            break
    if previous is None:
        raise RuntimeError('Update 1.4.42 erwartet Projektzentrale 1.4.38 bis 1.4.41. Es wurde nichts verändert.')

    candidate,ok=_patch_search_end_binding(original)
    if not ok or 'PZ_SEARCH_DIRECT_V1442' not in candidate:
        raise RuntimeError('1.4.42 konnte das globale Suchfenster nicht sicher erkennen. Die installierte Version bleibt unverändert.')
    _compile_text(candidate,'app.py.1442.search.check')

    candidate=candidate.replace(f'APP_VERSION = "{previous}"','APP_VERSION = "1.4.42"',1)
    _compile_text(candidate,'app.py.1442.final.check')

    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.vor_1442_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp=APP.with_name('app.py.1442.tmp')
    tmp.write_text(candidate,encoding='utf-8')
    tmp.replace(APP)
    try:
        APP.with_name('patch_1442_report.txt').write_text(
            f'Ausgangsversion: {previous}\nGlobale Suche: finale direkte Projektbindung am Ende der Suchfunktion eingebaut\n',
            encoding='utf-8')
    except Exception:pass
    return 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1442_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        raise SystemExit(1)
