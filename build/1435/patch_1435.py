from pathlib import Path
import ast
import datetime
import py_compile
import re
import shutil

APP=Path(__file__).resolve().parent/'app.py'


def _compile_text(text, name='app.py.1435.check'):
    tmp=APP.with_name(name)
    try:
        tmp.write_text(text,encoding='utf-8')
        py_compile.compile(str(tmp),doraise=True)
    finally:
        try: tmp.unlink()
        except Exception: pass


def _patch_status(s):
    if "_position_status_display={'Offen':'Offen'" not in s:
        marker="        _position_status_values=('Offen','In Bearbeitung','Geprüft','Änderung erforderlich','Erledigt')\n"
        if marker in s:
            s=s.replace(marker,marker+"        _position_status_display={'Offen':'Offen','In Bearbeitung':'Bearbeitung','Geprüft':'Geprüft','Änderung erforderlich':'Änderung','Erledigt':'Erledigt'}\n",1)
    old="""        # Zusätzliche Statusspalte rechts an die bestehende Positionsliste anhängen.
        try:
            _cols=list(ptr.cget('columns'))
            if 'pz_bearbeitung' not in _cols:
                _cols.append('pz_bearbeitung')
                ptr.configure(columns=tuple(_cols))
            ptr.heading('pz_bearbeitung',text='Bearbeitung')
            ptr.column('pz_bearbeitung',width=130,minwidth=105,stretch=False,anchor='w')
        except Exception:
            pass
"""
    new="""        # 1.4.35: Bearbeitungsstatus kompakt direkt hinter der Positionsspalte.
        try:
            _cols=list(ptr.cget('columns'))
            if 'pz_bearbeitung' in _cols:
                _cols.remove('pz_bearbeitung')
            _insert_at=min(3,len(_cols))
            for _i,_col in enumerate(_cols):
                _name=str(_col).casefold()
                if 'pos' in _name and 'projekt' not in _name:
                    _insert_at=_i+1
                    break
            _cols.insert(_insert_at,'pz_bearbeitung')
            ptr.configure(columns=tuple(_cols))
            ptr.heading('pz_bearbeitung',text='Status')
            ptr.column('pz_bearbeitung',width=100,minwidth=88,stretch=False,anchor='w')
        except Exception:
            pass
"""
    if old in s:
        s=s.replace(old,new,1)
    # Ist 1.4.34 teilweise angewendet, nur Überschrift/Breite korrigieren.
    s=s.replace("ptr.heading('pz_bearbeitung',text='Bearbeitung')","ptr.heading('pz_bearbeitung',text='Status')")
    s=s.replace("ptr.column('pz_bearbeitung',width=130,minwidth=105,stretch=False,anchor='w')","ptr.column('pz_bearbeitung',width=100,minwidth=88,stretch=False,anchor='w')")
    if "_position_status_display={'Offen':'Offen'" in s:
        s=s.replace("vals[status_index]=status","vals[status_index]=_position_status_display.get(status,status)")
    return s


def _patch_search(s):
    if 'def _pz_open_search_project' in s:
        return s
    tree=ast.parse(s)
    funcs=[]
    for node in ast.walk(tree):
        if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            continue
        txt=ast.get_source_segment(s,node) or ''
        if 'Suchergebnisse' in txt and 'Treeview' in txt:
            funcs.append(node)
    funcs.sort(key=lambda n:(getattr(n,'end_lineno',n.lineno)-n.lineno,n.lineno))
    for fn in funcs:
        candidates=[]
        for sub in ast.walk(fn):
            if not isinstance(sub,ast.Assign) or not sub.targets or not isinstance(sub.targets[0],ast.Name):
                continue
            val=sub.value
            if not isinstance(val,ast.Call):
                continue
            f=val.func
            if (isinstance(f,ast.Attribute) and f.attr=='Treeview') or (isinstance(f,ast.Name) and f.id=='Treeview'):
                candidates.append((sub,sub.targets[0].id))
        if not candidates:
            continue
        assign,tree_name=candidates[-1]
        lines=s.splitlines(keepends=True)
        indent=re.match(r'^[ \t]*',lines[assign.lineno-1]).group(0)
        body=f'''def _pz_open_search_project(_evt=None):
    try:
        _sel={tree_name}.selection()
        if not _sel:
            return
        _vals={tree_name}.item(_sel[0],'values')
        if len(_vals)<2 or str(_vals[0]).strip().casefold()!='projekt':
            return
        _target=str(_vals[1]).strip()
        if not _target:
            return
        def _norm(_v):
            return ' '.join(''.join((_c.casefold() if _c.isalnum() else ' ') for _c in str(_v or '')).split())
        _top={tree_name}.winfo_toplevel()
        _root=_top
        while getattr(_root,'master',None) is not None:
            _root=_root.master
        def _walk(_w):
            yield _w
            try:
                for _c in _w.winfo_children():
                    yield from _walk(_c)
            except Exception:
                return
        _wanted=_norm(_target)
        for _w in _walk(_root):
            try:
                if str(_w.winfo_class()) not in ('TCombobox','Combobox'):
                    continue
                _values=list(_w.cget('values'))
            except Exception:
                continue
            for _candidate in _values:
                if _norm(_candidate)==_wanted:
                    _w.set(_candidate)
                    try:_w.event_generate('<<ComboboxSelected>>',when='now')
                    except Exception:_w.event_generate('<<ComboboxSelected>>')
                    try:_top.after(30,_top.destroy)
                    except Exception:pass
                    return 'break'
    except Exception:
        return

{tree_name}.bind('<Double-1>',_pz_open_search_project,add='+')
{tree_name}.bind('<Return>',_pz_open_search_project,add='+')
'''
        block=''.join((indent+ln if ln.strip() else ln) for ln in body.splitlines(keepends=True))
        lines.insert(getattr(assign,'end_lineno',assign.lineno),block)
        return ''.join(lines)
    return s


STATIK_PDF = r'''        # 1.4.35: Statik-PDF Schnellzugriff. Nur lesender Zugriff auf vorhandene PDFs.
        try:
            _statik_pdf_paths={}
            def _statik_pdf_folder():
                try:
                    _root=Path(current_project.get('folder') or '')
                except Exception:
                    _root=Path('.')
                try:
                    for _c in _root.iterdir():
                        if _c.is_dir() and ''.join(x for x in _c.name.casefold() if x.isalnum())=='statikpdf':
                            return _c
                except Exception:
                    pass
                return _root/'Statik PDF'
            def _statik_pdf_open(_evt=None):
                try:
                    _sel=_statik_pdf_tree.selection()
                    if _sel and _sel[0] in _statik_pdf_paths:
                        self.open_external_path(_statik_pdf_paths[_sel[0]])
                except Exception:
                    pass
            def _statik_pdf_open_folder():
                try:
                    _folder=_statik_pdf_folder()
                    if not _folder.exists():
                        from tkinter import messagebox as _mbx
                        if not _mbx.askyesno('Statik PDF','Der Ordner „Statik PDF“ ist noch nicht vorhanden.\n\nSoll er im aktuellen Projekt angelegt werden?'):
                            return
                        _folder.mkdir(parents=True,exist_ok=True)
                    self.open_external_path(_folder)
                    _statik_pdf_refresh()
                except Exception:
                    pass
            def _statik_pdf_refresh():
                try:
                    for _iid in _statik_pdf_tree.get_children(''):
                        _statik_pdf_tree.delete(_iid)
                    _statik_pdf_paths.clear()
                    _folder=_statik_pdf_folder()
                    _files=[]
                    if _folder.exists():
                        for _p in _folder.rglob('*.pdf'):
                            try:
                                if _p.is_file(): _files.append(_p)
                            except Exception: pass
                    def _mt(_p):
                        try:return _p.stat().st_mtime
                        except Exception:return 0
                    _files.sort(key=lambda p:(_mt(p),p.name.casefold()),reverse=True)
                    for _p in _files:
                        try:_changed=datetime.datetime.fromtimestamp(_p.stat().st_mtime).strftime('%d.%m.%Y %H:%M')
                        except Exception:_changed='—'
                        try:
                            _sub=str(_p.relative_to(_folder).parent)
                            if _sub=='.':_sub='—'
                        except Exception:_sub='—'
                        _iid=_statik_pdf_tree.insert('', 'end', values=(_p.name,_changed,_sub))
                        _statik_pdf_paths[_iid]=_p
                    _statik_pdf_info.config(text=(f'{len(_files)} PDF-Datei(en) · Doppelklick öffnet das Original' if _folder.exists() else 'Ordner „Statik PDF“ noch nicht vorhanden'))
                except Exception:
                    pass
            _statik_pdf_box=ttk.LabelFrame(content,text='STATIK PDF · SCHNELLZUGRIFF')
            _statik_pdf_box.pack(fill='x',pady=(0,10))
            _statik_pdf_tools=ttk.Frame(_statik_pdf_box); _statik_pdf_tools.pack(fill='x',padx=8,pady=(6,3))
            _statik_pdf_info=ttk.Label(_statik_pdf_tools,text='Statik-PDF wird geladen …'); _statik_pdf_info.pack(side='left',fill='x',expand=True)
            ttk.Button(_statik_pdf_tools,text='Aktualisieren',command=_statik_pdf_refresh).pack(side='right',padx=(6,0))
            ttk.Button(_statik_pdf_tools,text='Ordner öffnen',command=_statik_pdf_open_folder).pack(side='right')
            _statik_pdf_tree=ttk.Treeview(_statik_pdf_box,columns=('datei','geaendert','ordner'),show='headings',height=3)
            _statik_pdf_tree.heading('datei',text='Datei'); _statik_pdf_tree.heading('geaendert',text='Geändert'); _statik_pdf_tree.heading('ordner',text='Unterordner')
            _statik_pdf_tree.column('datei',width=480,minwidth=220,stretch=True); _statik_pdf_tree.column('geaendert',width=125,minwidth=110,stretch=False); _statik_pdf_tree.column('ordner',width=240,minwidth=120,stretch=True)
            _statik_pdf_tree.pack(fill='x',padx=8,pady=(0,7))
            _statik_pdf_tree.bind('<Double-1>',_statik_pdf_open); _statik_pdf_tree.bind('<Return>',_statik_pdf_open)
            _statik_pdf_refresh()
        except Exception:
            pass

'''


def _patch_pdf(s):
    if 'STATIK PDF · SCHNELLZUGRIFF' in s:
        return s
    marker='        # Baugrund / Bodengutachten:'
    if marker in s:
        return s.replace(marker,STATIK_PDF+marker,1)
    # Fallback: direkt vor dem Baugrund-LabelFrame einfügen.
    m=re.search(r'(?m)^[ \t]*[A-Za-z_]\w*\s*=\s*ttk\.LabelFrame\([^\n]*BAUGRUND / BODENGUTACHTEN[^\n]*\)',s)
    if m:
        return s[:m.start()]+STATIK_PDF+s[m.start():]
    return s


def _apply_feature(name, source, fn, report):
    try:
        candidate=fn(source)
        if candidate==source:
            report.append(name+': nicht verändert / Marker nicht gefunden')
            return source
        _compile_text(candidate,f'app.py.1435.{name}.check')
        report.append(name+': OK')
        return candidate
    except Exception as exc:
        report.append(name+': übersprungen ('+str(exc)+')')
        return source


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.35"' in s:
        return 0
    if 'APP_VERSION = "1.4.34"' in s:
        s=s.replace('APP_VERSION = "1.4.34"','APP_VERSION = "1.4.35"',1)
    elif 'APP_VERSION = "1.4.33"' in s:
        s=s.replace('APP_VERSION = "1.4.33"','APP_VERSION = "1.4.35"',1)
    else:
        raise RuntimeError('Reparatur 1.4.35 erwartet Projektzentrale 1.4.33 oder 1.4.34. Es wurde nichts verändert.')

    report=[]
    s=_apply_feature('Status',s,_patch_status,report)
    s=_apply_feature('Suche',s,_patch_search,report)
    s=_apply_feature('StatikPDF',s,_patch_pdf,report)
    _compile_text(s,'app.py.1435.final.check')

    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.vor_1435_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp=APP.with_name('app.py.1435.tmp')
    tmp.write_text(s,encoding='utf-8')
    tmp.replace(APP)
    try:
        APP.with_name('patch_1435_report.txt').write_text('\n'.join(report)+'\n',encoding='utf-8')
    except Exception:
        pass
    return 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1435_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        raise SystemExit(1)
