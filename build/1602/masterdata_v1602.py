import json
import masterdata_v1601 as _prev

FIELDS=_prev.FIELDS
MAGIC='__PZ_FITZ_GEOMETRY_V1602__'


def _geometry(path,max_pages=6):
    """CAD/Allplan PDFs: prefer PyMuPDF word coordinates; pypdf only as fallback."""
    frags=[]
    raw_chars=0
    try:
        import fitz
        d=fitz.open(str(path))
        for pi in range(min(len(d),max_pages)):
            page=d[pi]
            W=float(page.rect.width); H=float(page.rect.height)
            words=page.get_text('words') or []
            groups={}
            for w in words:
                try:
                    # PyMuPDF: x0,y0,x1,y1,text,block_no,line_no,word_no
                    groups.setdefault((int(w[5]),int(w[6])),[]).append(w)
                except Exception:
                    pass
            for ws in groups.values():
                ws=sorted(ws,key=lambda z:(float(z[0]),int(z[7]) if len(z)>7 else 0))
                text=_prev._clean(' '.join(str(z[4]) for z in ws))
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
    # Only when PyMuPDF is unavailable / cannot read the PDF do we use the 1.6.1 reader.
    return _prev._geometry(path,max_pages)


def _pdf_text(path,max_pages=6):
    fr,n=_geometry(path,max_pages)
    if not fr:
        return ''
    data=_prev._parse_geometry(fr)
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
    # UI/database remain the proven 1.6.0 implementation; only the reader/parser is replaced.
    _prev._base._score=_score
    _prev._base._pdf_text=_pdf_text
    _prev._base._parse=_parse
    return _prev._base.open_masterdata(app)
