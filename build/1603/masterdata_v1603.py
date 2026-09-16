import importlib
import json
import sys
from pathlib import Path
from tkinter import messagebox
import masterdata_v1602 as _prev

FIELDS=_prev.FIELDS
MAGIC='__PZ_LOCAL_FITZ_V1603__'
BASE=Path(__file__).resolve().parent
VENDOR=BASE/'_vendor'
_ENGINE=None
_ENGINE_SOURCE=''
_ENGINE_ERROR=''


def _load_fitz():
    global _ENGINE,_ENGINE_SOURCE,_ENGINE_ERROR
    if _ENGINE is not None:
        return _ENGINE
    if VENDOR.exists():
        v=str(VENDOR)
        if v not in sys.path:
            sys.path.insert(0,v)
    errors=[]
    for name in ('pymupdf','fitz'):
        try:
            mod=importlib.import_module(name)
            _ENGINE=mod
            _ENGINE_SOURCE=('lokal' if VENDOR.exists() and str(VENDOR) in str(getattr(mod,'__file__','')) else 'system')
            _ENGINE_ERROR=''
            return mod
        except Exception as e:
            errors.append(f'{name}: {e}')
    _ENGINE_ERROR=' | '.join(errors)
    return None


def engine_status():
    mod=_load_fitz()
    if mod is None:
        return False,_ENGINE_ERROR or 'PyMuPDF konnte nicht geladen werden.'
    try:
        ver=getattr(mod,'__version__','') or getattr(mod,'VersionBind','') or ''
    except Exception:
        ver=''
    return True,('PyMuPDF aktiv'+(f' ({ver})' if ver else '')+f' · Quelle: {_ENGINE_SOURCE}')


def _geometry(path,max_pages=6):
    """Allplan/CAD-PDFs immer mit lokalem PyMuPDF lesen; kein stiller Rueckfall bei fehlender Engine."""
    fitz=_load_fitz()
    if fitz is None:
        return [],0
    frags=[]
    raw_chars=0
    try:
        d=fitz.open(str(path))
        for pi in range(min(len(d),max_pages)):
            page=d[pi]
            W=float(page.rect.width); H=float(page.rect.height)
            words=page.get_text('words') or []
            groups={}
            for w in words:
                try:
                    groups.setdefault((int(w[5]),int(w[6])),[]).append(w)
                except Exception:
                    pass
            for ws in groups.values():
                ws=sorted(ws,key=lambda z:(float(z[0]),int(z[7]) if len(z)>7 else 0))
                text=_prev._prev._clean(' '.join(str(z[4]) for z in ws))
                if not text or len(text)>1500:
                    continue
                raw_chars+=len(text)
                x=min(float(z[0]) for z in ws)
                ytop=min(float(z[1]) for z in ws)
                frags.append({'page':pi,'x':x,'y':H-ytop,'text':text,'font':12.0,'W':W,'H':H})
        d.close()
        if frags:
            return frags,raw_chars
    except Exception:
        pass
    # Engine ist vorhanden, aber diese einzelne PDF konnte mit fitz nicht ausgewertet werden.
    # Erst dann darf der alte Reader als Datei-Fallback ran.
    return _prev._prev._geometry(path,max_pages)


def _pdf_text(path,max_pages=6):
    fr,n=_geometry(path,max_pages)
    if not fr:
        return ''
    data=_prev._prev._parse_geometry(fr)
    return MAGIC+json.dumps({'data':data,'chars':n},ensure_ascii=False)


def _parse(text):
    if isinstance(text,str) and text.startswith(MAGIC):
        try:
            return json.loads(text[len(MAGIC):]).get('data',{})
        except Exception:
            return {}
    return _prev._parse(text)


def _score(path,root):
    return _prev._score(path,root)


def open_masterdata(app):
    ok,info=engine_status()
    if not ok:
        messagebox.showerror(
            'CAD-PDF-Reader fehlt',
            'PyMuPDF konnte nicht geladen werden.\n\n'
            'Die Stammdatenerkennung wird deshalb NICHT mit einer unzuverlaessigen Ersatzmethode gestartet.\n\n'
            'Bitte unter Sicherung / Update erneut nach Updates suchen.\n\nDetails: '+info,
            parent=app)
        return None
    # 1.6.2 als UI-Basis weiterverwenden, aber Reader/Parser gezielt ersetzen.
    _prev._geometry=_geometry
    _prev._pdf_text=_pdf_text
    _prev._parse=_parse
    return _prev.open_masterdata(app)
