from pathlib import Path
import ast
import datetime
import py_compile
import re
import shutil

APP=Path(__file__).resolve().parent/'app.py'


def _compile_text(text,name='app.py.1438.check'):
    tmp=APP.with_name(name)
    try:
        tmp.write_text(text,encoding='utf-8')
        py_compile.compile(str(tmp),doraise=True)
    finally:
        try: tmp.unlink()
        except Exception: pass


def _patch_search_navigation(s):
    if 'PZ_SEARCH_NAV_V1438' in s:
        return s, True
    tree=ast.parse(s)
    targets=[]
    for node in ast.walk(tree):
        if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            continue
        seg=ast.get_source_segment(s,node) or ''
        if 'Suchergebnisse' not in seg or 'Treeview' not in seg:
            continue
        top_assign=None; top_name=None; tree_assign=None; tree_name=None
        for sub in ast.walk(node):
            if not isinstance(sub,ast.Assign) or not sub.targets or not isinstance(sub.targets[0],ast.Name):
                continue
            val=sub.value
            if not isinstance(val,ast.Call):
                continue
            f=val.func
            if ((isinstance(f,ast.Attribute) and f.attr=='Toplevel') or (isinstance(f,ast.Name) and f.id=='Toplevel')) and top_assign is None:
                top_assign=sub; top_name=sub.targets[0].id
            if (isinstance(f,ast.Attribute) and f.attr=='Treeview') or (isinstance(f,ast.Name) and f.id=='Treeview'):
                tree_assign=sub; tree_name=sub.targets[0].id
        if top_assign is not None and tree_assign is not None:
            targets.append((node,top_assign,top_name,tree_assign,tree_name))
    if not targets:
        return s, False
    targets.sort(key=lambda x:(getattr(x[0],'end_lineno',x[0].lineno)-x[0].lineno,x[0].lineno))
    _fn,_ta,top_name,tree_assign,tree_name=targets[0]
    lines=s.splitlines(keepends=True)
    insert_after=getattr(tree_assign,'end_lineno',tree_assign.lineno)
    indent=re.match(r'^[ \t]*',lines[tree_assign.lineno-1]).group(0)
    body=f'''# PZ_SEARCH_NAV_V1438
# Der Handler wird nach dem Aufbau des Suchfensters erneut gebunden. Dadurch
# kann eine spätere Standardbindung den Projektdoppelklick nicht mehr überschreiben.
def _pz_1438_norm(_value):
    _txt=''.join((_c.casefold() if _c.isalnum() else ' ') for _c in str(_value or ''))
    return ' '.join(_txt.split())

def _pz_1438_activate_project(_target):
    try:
        _wanted=_pz_1438_norm(_target)
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
        _best=None
        for _widget in _walk(_root):
            try:
                if str(_widget.winfo_class()) not in ('TCombobox','Combobox'):
                    continue
                _values=list(_widget.cget('values'))
            except Exception:
                continue
            for _idx,_candidate in enumerate(_values):
                _cn=_pz_1438_norm(_candidate)
                _score=0
                if _cn==_wanted:
                    _score=100
                elif _number and _number in str(_candidate).casefold():
                    _score=90
                elif _wanted and _wanted in _cn:
                    _score=60
                if _score and (_best is None or _score>_best[0]):
                    _best=(_score,_widget,_idx,_candidate)
        if _best is None:
            return False
        _,_widget,_idx,_candidate=_best
        try:_widget.current(_idx)
        except Exception:_widget.set(_candidate)
        try:_widget.event_generate('<<ComboboxSelected>>',when='now')
        except Exception:
            try:_widget.event_generate('<<ComboboxSelected>>')
            except Exception:pass
        try:_root.update_idletasks()
        except Exception:pass
        return True
    except Exception:
        return False

def _pz_1438_open_project(_evt=None):
    try:
        _iid=''
        if _evt is not None:
            try:_iid={tree_name}.identify_row(_evt.y)
            except Exception:_iid=''
        if not _iid:
            _sel={tree_name}.selection()
            if _sel:_iid=_sel[0]
        if not _iid:
            return
        try:{tree_name}.selection_set(_iid)
        except Exception:pass
        _vals={tree_name}.item(_iid,'values')
        if len(_vals)<2 or str(_vals[0]).strip().casefold()!='projekt':
            return
        if _pz_1438_activate_project(str(_vals[1]).strip()):
            try:{top_name}.after(70,{top_name}.destroy)
            except Exception:pass
            return 'break'
    except Exception:
        return

def _pz_1438_bind_project_open():
    try:
        {tree_name}.bind('<Double-1>',_pz_1438_open_project)
        {tree_name}.bind('<Return>',_pz_1438_open_project)
    except Exception:
        pass

try:{top_name}.after_idle(_pz_1438_bind_project_open)
except Exception:pass
try:{top_name}.after(150,_pz_1438_bind_project_open)
except Exception:pass
'''
    block=''.join((indent+ln if ln.strip() else ln) for ln in body.splitlines(keepends=True))
    lines.insert(insert_after,block)
    return ''.join(lines), True


def _patch_position_layout(s):
    if 'PZ_POSITION_LAYOUT_V1438' in s:
        return s, True
    patterns=(
        "            ptr.column('pz_bearbeitung',width=100,minwidth=88,stretch=False,anchor='w')\n",
        "            ptr.column('pz_bearbeitung',width=130,minwidth=105,stretch=False,anchor='w')\n",
    )
    marker=None
    for p in patterns:
        if p in s:
            marker=p; break
    if marker is None:
        return s, False
    block="""            # PZ_POSITION_LAYOUT_V1438: Positionsliste ohne notwendiges horizontales Scrollen.\n            try:\n                _pz_cols=list(ptr.cget('columns'))\n                _pz_order=('gruppe','mb_projekt','pos','pz_bearbeitung','bezeichnung','modul','kennwert')\n                _pz_display=[_c for _c in _pz_order if _c in _pz_cols]\n                _pz_display.extend([_c for _c in _pz_cols if _c not in _pz_display])\n                ptr.configure(displaycolumns=tuple(_pz_display))\n                _pz_widths={\n                    'gruppe':(132,95,False),\n                    'mb_projekt':(112,88,False),\n                    'pos':(82,72,False),\n                    'pz_bearbeitung':(96,86,False),\n                    'bezeichnung':(285,180,True),\n                    'modul':(82,70,False),\n                    'kennwert':(68,58,False),\n                }\n                for _col,(_width,_min,_stretch) in _pz_widths.items():\n                    if _col in _pz_cols:\n                        ptr.column(_col,width=_width,minwidth=_min,stretch=_stretch)\n                if 'pz_bearbeitung' in _pz_cols:\n                    ptr.heading('pz_bearbeitung',text='Status')\n                try:ptr.xview_moveto(0)\n                except Exception:pass\n            except Exception:\n                pass\n"""
    s=s.replace(marker,marker+block,1)
    return s, True


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.38"' in s:
        return 0
    previous=None
    for _v in ('1.4.37','1.4.36','1.4.35'):
        if f'APP_VERSION = "{_v}"' in s:
            previous=_v
            s=s.replace(f'APP_VERSION = "{_v}"','APP_VERSION = "1.4.38"',1)
            break
    if previous is None:
        raise RuntimeError('Update 1.4.38 erwartet Projektzentrale 1.4.35 bis 1.4.37. Es wurde nichts verändert.')

    report=[]
    try:
        candidate,ok=_patch_search_navigation(s)
        if ok:
            _compile_text(candidate,'app.py.1438.search.check')
            s=candidate; report.append('Projektsuche/Doppelklick: OK')
        else:
            report.append('Projektsuche/Doppelklick: Suchfenster nicht sicher erkannt; übersprungen')
    except Exception as exc:
        report.append('Projektsuche/Doppelklick: übersprungen ('+str(exc)+')')

    try:
        candidate,ok=_patch_position_layout(s)
        if ok:
            _compile_text(candidate,'app.py.1438.layout.check')
            s=candidate; report.append('Positionsliste kompakt: OK')
        else:
            report.append('Positionsliste kompakt: Statusspalten-Marker nicht gefunden; übersprungen')
    except Exception as exc:
        report.append('Positionsliste kompakt: übersprungen ('+str(exc)+')')

    # Der Versionswechsel selbst darf von optionalen UI-Erweiterungen nicht blockiert werden.
    _compile_text(s,'app.py.1438.final.check')
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.vor_1438_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp=APP.with_name('app.py.1438.tmp')
    tmp.write_text(s,encoding='utf-8')
    tmp.replace(APP)
    try:
        APP.with_name('patch_1438_report.txt').write_text('\n'.join(report)+'\n',encoding='utf-8')
    except Exception:
        pass
    return 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1438_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        raise SystemExit(1)
