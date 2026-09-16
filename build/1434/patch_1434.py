from pathlib import Path
import ast
import datetime
import py_compile
import re
import shutil

APP=Path(__file__).resolve().parent/'app.py'


STATIK_PDF_BODY = r'''# 1.4.34: Statik-PDF als direkter Schnellzugriff in der Statik.
# Gesucht wird projektbezogen und rekursiv in einem Ordner "Statik PDF"
# (Schreibweisen mit Leerzeichen/Bindestrich werden ebenfalls erkannt).
def _statik_pdf_resolve_folder():
    try:
        for _child in project_root.iterdir():
            try:
                if not _child.is_dir():
                    continue
                _norm=''.join(_ch for _ch in _child.name.casefold() if _ch.isalnum())
                if _norm=='statikpdf':
                    return _child
            except Exception:
                continue
    except Exception:
        pass
    return project_root/'Statik PDF'

_statik_pdf_paths={}

def _statik_pdf_open_selected(_evt=None):
    try:
        _sel=_statik_pdf_tree.selection()
        if not _sel:
            return
        _p=_statik_pdf_paths.get(_sel[0])
        if _p:
            self.open_external_path(_p)
    except Exception:
        pass

def _statik_pdf_open_folder():
    try:
        from tkinter import messagebox as _mbx
        _folder=_statik_pdf_resolve_folder()
        if not _folder.exists():
            if not _mbx.askyesno('Statik PDF','Der Ordner "Statik PDF" ist noch nicht vorhanden.\n\nSoll er im aktuellen Projekt angelegt werden?'):
                return
            _folder.mkdir(parents=True,exist_ok=True)
            _statik_pdf_refresh()
        self.open_external_path(_folder)
    except Exception as _exc:
        try:
            from tkinter import messagebox as _mbx
            _mbx.showwarning('Statik PDF',f'Der Ordner konnte nicht geöffnet werden:\n{_exc}')
        except Exception:
            pass

def _statik_pdf_refresh():
    try:
        for _iid in _statik_pdf_tree.get_children(''):
            _statik_pdf_tree.delete(_iid)
        _statik_pdf_paths.clear()
        _folder=_statik_pdf_resolve_folder()
        if not _folder.exists():
            _statik_pdf_info.config(text='Ordner "Statik PDF" noch nicht vorhanden · über „Ordner öffnen“ bei Bedarf anlegen')
            return
        _files=[]
        try:
            for _p in _folder.rglob('*'):
                try:
                    if _p.is_file() and _p.suffix.casefold()=='.pdf':
                        _files.append(_p)
                except OSError:
                    continue
        except OSError:
            pass
        def _mtime(_p):
            try:return _p.stat().st_mtime
            except Exception:return 0
        _files.sort(key=lambda _p:(_mtime(_p),_p.name.casefold()),reverse=True)
        for _p in _files:
            try:_changed=datetime.datetime.fromtimestamp(_p.stat().st_mtime).strftime('%d.%m.%Y %H:%M')
            except Exception:_changed='—'
            try:
                _rel=_p.relative_to(_folder)
                _sub=str(_rel.parent)
                if _sub=='.':_sub='—'
            except Exception:
                _sub='—'
            _iid=_statik_pdf_tree.insert('', 'end', values=(_p.name,_changed,_sub))
            _statik_pdf_paths[_iid]=_p
        _statik_pdf_info.config(text=f'{len(_files)} PDF-Datei(en) · Doppelklick öffnet das Original')
    except Exception:
        pass

_statik_pdf_box=ttk.LabelFrame(__PARENT__,text='STATIK PDF · SCHNELLZUGRIFF')
_statik_pdf_box.pack(fill='x',pady=(0,10))
_statik_pdf_tools=ttk.Frame(_statik_pdf_box)
_statik_pdf_tools.pack(fill='x',padx=8,pady=(6,3))
_statik_pdf_info=ttk.Label(_statik_pdf_tools,text='Statik-PDF wird geladen …')
_statik_pdf_info.pack(side='left',fill='x',expand=True)
ttk.Button(_statik_pdf_tools,text='Aktualisieren',command=_statik_pdf_refresh).pack(side='right',padx=(6,0))
ttk.Button(_statik_pdf_tools,text='Ordner öffnen',command=_statik_pdf_open_folder).pack(side='right')
_statik_pdf_list=ttk.Frame(_statik_pdf_box)
_statik_pdf_list.pack(fill='x',padx=8,pady=(0,7))
_statik_pdf_tree=ttk.Treeview(_statik_pdf_list,columns=('datei','geaendert','ordner'),show='headings',height=3)
_statik_pdf_tree.heading('datei',text='Datei')
_statik_pdf_tree.heading('geaendert',text='Geändert')
_statik_pdf_tree.heading('ordner',text='Unterordner')
_statik_pdf_tree.column('datei',width=470,minwidth=220,stretch=True)
_statik_pdf_tree.column('geaendert',width=125,minwidth=110,stretch=False)
_statik_pdf_tree.column('ordner',width=260,minwidth=120,stretch=True)
_statik_pdf_scroll=ttk.Scrollbar(_statik_pdf_list,orient='vertical',command=_statik_pdf_tree.yview)
_statik_pdf_tree.configure(yscrollcommand=_statik_pdf_scroll.set)
_statik_pdf_tree.pack(side='left',fill='x',expand=True)
_statik_pdf_scroll.pack(side='right',fill='y')
_statik_pdf_tree.bind('<Double-1>',_statik_pdf_open_selected)
_statik_pdf_tree.bind('<Return>',_statik_pdf_open_selected)
_statik_pdf_refresh()

'''


def _patch_status_ui(s):
    values="        _position_status_values=('Offen','In Bearbeitung','Geprüft','Änderung erforderlich','Erledigt')\n"
    if values not in s:
        raise RuntimeError('1.4.34 Marker für Statuswerte fehlt.')
    display=(
        values+
        "        _position_status_display={'Offen':'Offen','In Bearbeitung':'Bearbeitung','Geprüft':'Geprüft','Änderung erforderlich':'Änderung','Erledigt':'Erledigt'}\n"
    )
    s=s.replace(values,display,1)

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
    new="""        # Bearbeitungsstatus kompakt direkt hinter der Positionsspalte anzeigen.
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
    if old not in s:
        raise RuntimeError('1.4.34 Marker für Statusspalte fehlt.')
    s=s.replace(old,new,1)

    old_cell="                        vals[status_index]=status\n"
    new_cell="                        vals[status_index]=_position_status_display.get(status,status)\n"
    if old_cell not in s:
        raise RuntimeError('1.4.34 Marker für Statuszelle fehlt.')
    s=s.replace(old_cell,new_cell,1)

    s=s.replace("                    width=20,\n","                    width=18,\n",1)
    return s


def _patch_search_navigation(s):
    if 'def _pz_open_search_project' in s:
        return s
    tree=ast.parse(s)
    funcs=[]
    for node in ast.walk(tree):
        if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            continue
        found=False
        for sub in ast.walk(node):
            if isinstance(sub,ast.Constant) and isinstance(sub.value,str) and 'Suchergebnisse' in sub.value:
                found=True; break
        if found:
            funcs.append(node)
    funcs.sort(key=lambda n:((getattr(n,'end_lineno',n.lineno)-n.lineno),n.lineno))
    target_func=None; assign=None; tree_name=None
    for fn in funcs:
        candidates=[]
        for sub in ast.walk(fn):
            val=None; name=None
            if isinstance(sub,ast.Assign) and sub.targets:
                val=sub.value
                if isinstance(sub.targets[0],ast.Name): name=sub.targets[0].id
            elif isinstance(sub,ast.AnnAssign):
                val=sub.value
                if isinstance(sub.target,ast.Name): name=sub.target.id
            if not name or not isinstance(val,ast.Call):
                continue
            f=val.func
            is_tree=(isinstance(f,ast.Attribute) and f.attr=='Treeview') or (isinstance(f,ast.Name) and f.id=='Treeview')
            if is_tree:
                candidates.append((sub,name))
        if candidates:
            target_func=fn; assign,tree_name=candidates[0]; break
    if target_func is None or assign is None or not tree_name:
        raise RuntimeError('1.4.34 Suchfenster/Treeview konnte nicht sicher erkannt werden.')

    lines=s.splitlines(keepends=True)
    line=lines[assign.lineno-1]
    indent=re.match(r'^[ \t]*',line).group(0)
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
        def _norm(_value):
            _txt=''.join((_ch.casefold() if _ch.isalnum() else ' ') for _ch in str(_value or ''))
            return ' '.join(_txt.split())
        _top={tree_name}.winfo_toplevel()
        _main=getattr(_top,'master',None) or _top
        while getattr(_main,'master',None) is not None:
            _main=_main.master
        def _walk(_w):
            yield _w
            try:
                for _child in _w.winfo_children():
                    yield from _walk(_child)
            except Exception:
                return
        _wanted=_norm(_target)
        for _widget in _walk(_main):
            try:
                if str(_widget.winfo_class()) not in ('TCombobox','Combobox'):
                    continue
                _values=list(_widget.cget('values'))
            except Exception:
                continue
            for _candidate in _values:
                if _norm(_candidate)!=_wanted:
                    continue
                _widget.set(_candidate)
                try:
                    _widget.event_generate('<<ComboboxSelected>>',when='now')
                except Exception:
                    _widget.event_generate('<<ComboboxSelected>>')
                try:_top.after(20,_top.destroy)
                except Exception:pass
                return 'break'
    except Exception:
        return

{tree_name}.bind('<Double-1>',_pz_open_search_project,add='+')
{tree_name}.bind('<Return>',_pz_open_search_project,add='+')
'''
    block=''.join((indent+ln if ln.strip() else ln) for ln in body.splitlines(keepends=True))
    insert_index=getattr(assign,'end_lineno',assign.lineno)
    lines.insert(insert_index,block)
    return ''.join(lines)


def _patch_statik_pdf(s):
    if 'STATIK PDF · SCHNELLZUGRIFF' in s:
        return s
    marker='        # Baugrund / Bodengutachten:'
    pos=s.find(marker)
    if pos<0:
        raise RuntimeError('1.4.34 Marker vor Baugrund/Bodengutachten fehlt.')
    tail=s[pos:pos+1600]
    m=re.search(r'(?m)^(?P<indent>[ \t]*)(?P<var>[A-Za-z_]\w*)\s*=\s*ttk\.LabelFrame\((?P<parent>[^,\n]+),',tail)
    if not m:
        raise RuntimeError('1.4.34 Elternbereich der Statik konnte nicht sicher erkannt werden.')
    indent=re.match(r'^[ \t]*',marker).group(0)
    parent=m.group('parent').strip()
    body=STATIK_PDF_BODY.replace('__PARENT__',parent)
    block=''.join((indent+ln if ln.strip() else ln) for ln in body.splitlines(keepends=True))
    return s[:pos]+block+s[pos:]


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.34"' in s:
        return 0
    if 'APP_VERSION = "1.4.33"' not in s:
        raise RuntimeError('Update 1.4.34 erwartet Projektzentrale 1.4.33. Es wurde nichts verändert.')
    original=s
    s=s.replace('APP_VERSION = "1.4.33"','APP_VERSION = "1.4.34"',1)

    s=_patch_status_ui(s)
    s=_patch_search_navigation(s)
    s=_patch_statik_pdf(s)

    s=s.replace(
        'Hinweis 1.4.33: Bearbeitungsstatus steht direkt als Spalte in der Positionsliste, kann separat gefiltert werden und wird oben mit Stückzahlen zusammengefasst. Statusänderungen aktualisieren Liste, Filter und Zähler sofort; die aktuelle Position bleibt soweit sichtbar ausgewählt.',
        'Hinweis 1.4.34: Statusspalte kompakter direkt bei der Position; Projekttreffer der globalen Suche öffnen per Doppelklick das gefundene Projekt. In Statik steht zusätzlich der Projektordner Statik PDF als direkter PDF-Schnellzugriff bereit.'
    )
    s=s.replace(
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb, Windows-Dateizuordnungen und Projektdateien werden read-only gelesen. Positionsakte 1.4.33 ergänzt Statusspalte, Statusfilter und Statusübersicht; Status/Notiz bleiben ausschließlich Projektzentrale-Metadaten, mb-Daten und Registry unverändert.',
        'Quelle: mb-Daten und Projektdateien bleiben unverändert. Projektzentrale 1.4.34 ergänzt eine kompakte Statusansicht, Projektnavigation aus der Suche und einen read-only PDF-Schnellzugriff auf den Projektordner Statik PDF.'
    )

    required=(
        'APP_VERSION = "1.4.34"',
        "ptr.heading('pz_bearbeitung',text='Status')",
        "_position_status_display={'Offen':'Offen'",
        'def _pz_open_search_project',
        "event_generate('<<ComboboxSelected>>'",
        'STATIK PDF · SCHNELLZUGRIFF',
        'def _statik_pdf_refresh():',
        "_p.suffix.casefold()=='.pdf'",
        "text='Ordner öffnen'",
    )
    if not all(x in s for x in required):
        raise RuntimeError('Patch-Ergebnis 1.4.34 unvollständig. Es wurde nichts verändert.')
    if s==original:
        raise RuntimeError('Keine Änderung erzeugt.')

    tmp=APP.with_name('app.py.1434.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.v1433_vor_1434_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp.replace(APP)
    return 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1434_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        print('FEHLER:',e)
        raise SystemExit(1)
