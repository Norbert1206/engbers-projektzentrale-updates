import json, re
from pathlib import Path
import masterdata_v1600 as _base

FIELDS=_base.FIELDS
_OLD_SCORE=_base._score
_OLD_PARSE=_base._parse

LABELS={
 'project':('bauvorhaben','baumaßnahme','baumassnahme','bauprojekt'),
 'location':('bauort','grundstück','grundstueck'),
 'client':('bauherr','bauherrschaft','auftraggeber'),
 'client_addr':('anschrift',),
 'architect':('architekt','entwurfsverfasser','planverfasser'),
 'engineer':('tragwerksplanung','tragwerksplaner'),
}
ALL_LABELS=tuple(sorted(set(sum((list(v) for v in LABELS.values()),[]))))
MAGIC='__PZ_GEOMETRY_V1601__'

def _clean(s):
    s=(s or '').replace('\x00','')
    for a,b in (('\\ü','ü'),('\\ö','ö'),('\\ä','ä'),('\\Ü','Ü'),('\\Ö','Ö'),('\\Ä','Ä')):
        s=s.replace(a,b)
    return re.sub(r'\s+',' ',s).strip(' \t|;')

def _point(cm,tm):
    x,y=tm[4],tm[5]
    return x*cm[0]+y*cm[2]+cm[4],x*cm[1]+y*cm[3]+cm[5]

def _geometry(path,max_pages=6):
    frags=[];raw_chars=0
    Reader=None
    try:
        from pypdf import PdfReader as Reader
    except Exception:
        try:from PyPDF2 import PdfReader as Reader
        except Exception:Reader=None
    if Reader:
        try:
            r=Reader(str(path),strict=False)
            for pi,p in enumerate(list(r.pages)[:max_pages]):
                try:W=float(p.mediabox.width);H=float(p.mediabox.height)
                except Exception:W,H=1000.0,1000.0
                def visitor(text,cm,tm,font_dict,font_size):
                    nonlocal raw_chars
                    t=_clean(text)
                    if not t or len(t)>1500:return
                    raw_chars+=len(t)
                    try:x,y=_point(cm,tm)
                    except Exception:x,y=0.0,0.0
                    if abs(x)<0.01 and abs(y)<1.0:return
                    frags.append({'page':pi,'x':float(x),'y':float(y),'text':t,'font':float(font_size or 0),'W':W,'H':H})
                try:p.extract_text(visitor_text=visitor)
                except TypeError:p.extract_text()
                except Exception:pass
        except Exception:pass
    if not frags:
        try:
            import fitz
            d=fitz.open(str(path))
            for pi in range(min(len(d),max_pages)):
                page=d[pi];W=float(page.rect.width);H=float(page.rect.height)
                words=page.get_text('words') or [];groups={}
                for w in words:
                    try:groups.setdefault((w[5],w[6]),[]).append(w)
                    except Exception:pass
                for ws in groups.values():
                    ws=sorted(ws,key=lambda z:z[0]);t=_clean(' '.join(str(z[4]) for z in ws))
                    if not t:continue
                    raw_chars+=len(t);ytop=min(float(z[1]) for z in ws)
                    frags.append({'page':pi,'x':min(float(z[0]) for z in ws),'y':H-ytop,'text':t,'font':12.0,'W':W,'H':H})
            d.close()
        except Exception:pass
    return frags,raw_chars

def _has(text,term):
    return re.search(r'(?<!\w)'+re.escape(term)+r'(?!\w)',text.casefold()) is not None

def _find(frags,terms,exclude=()):
    out=[]
    for f in frags:
        low=f['text'].casefold()
        if any(_has(low,t) for t in terms) and not any(_has(low,t) for t in exclude):out.append(f)
    return out

def _right(frags,label,terms):
    low=label['text'].casefold()
    for term in terms:
        pos=low.find(term)
        if pos>=0:
            rest=label['text'][pos+len(term):].lstrip(' :.-–—')
            if rest and not any(rest.casefold().startswith(x) for x in ALL_LABELS):return _clean(rest),label['x']+1
    tol=max(3.0,min(12.0,label['font']*.40))
    same=[f for f in frags if f['page']==label['page'] and f is not label and f['x']>label['x']+2 and f['x']-label['x']<label['W']*.38 and abs(f['y']-label['y'])<=tol and not any(_has(f['text'],x) for x in ALL_LABELS)]
    same.sort(key=lambda f:f['x'])
    if same:return same[0]['text'],same[0]['x']
    return '',None

def _best(frags,terms,exclude=()):
    opts=[]
    for lab in _find(frags,terms,exclude):
        val,x=_right(frags,lab,terms)
        score=(100 if val else 0)+(16 if lab['x']>lab['W']*.50 else 0)+(14 if lab['y']<lab['H']*.38 else 0)
        if lab['x']<0 or lab['y']<0 or lab['x']>lab['W']*1.2 or lab['y']>lab['H']*1.2:score-=100
        opts.append((score,lab,val,x))
    return max(opts,key=lambda z:z[0]) if opts else (0,None,'',None)

def _below(frags,label,x_hint=None,max_lines=5,depth=100):
    if not label:return []
    x0=x_hint if x_hint is not None else label['x']+10;a=[]
    for f in frags:
        if f['page']!=label['page'] or f is label:continue
        dy=label['y']-f['y']
        if 2<=dy<=depth and f['x']>=x0-30 and f['x']<label['W']*.99:
            if any(_has(f['text'],x) for x in ALL_LABELS):continue
            a.append((dy,f['x'],f))
    a.sort(key=lambda z:(z[0],z[1]))
    return [x[2] for x in a[:max_lines]]

ADDR_FULL=re.compile(r'(?P<street>[A-ZÄÖÜa-zäöüß][A-ZÄÖÜa-zäöüß0-9 .,/\'’\-]{2,90}?\s+\d{1,4}[a-zA-Z]?)\s*[,;]?\s+(?P<zip>\d{5})\s+(?P<city>[A-ZÄÖÜa-zäöüß][A-ZÄÖÜa-zäöüß .\'’\-]{1,60})',re.I)
ADDR_PART=re.compile(r'(?P<street>[A-ZÄÖÜa-zäöüß][A-ZÄÖÜa-zäöüß0-9 .,/\'’\-]{2,90}?\s+\d{1,4}[a-zA-Z]?)\s*,\s*(?P<city>[A-ZÄÖÜa-zäöüß][A-ZÄÖÜa-zäöüß .\'’\-]{1,60})$',re.I)
MAIL=re.compile(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}')
PHONE=re.compile(r'(?:tel(?:efon)?\.?|fon|mobil)\s*[:.]?\s*([+0-9][0-9 /()\-]{5,})',re.I)

def _address(s):
    s=_clean(s);m=ADDR_FULL.search(s)
    if m:return {'street':m.group('street').strip(' ,;'),'zip':m.group('zip'),'city':m.group('city').strip(' ,;')}
    m=ADDR_PART.search(s)
    if m:return {'street':m.group('street').strip(' ,;'),'zip':'','city':m.group('city').strip(' ,;')}
    return {}

def _contacts(lines):
    j=' | '.join(x['text'] if isinstance(x,dict) else str(x) for x in lines)
    p=PHONE.search(j);m=MAIL.search(j)
    return (p.group(1).strip(' ,;') if p else '',m.group(0) if m else '')

def _parse_geometry(frags):
    d={}
    _,lab,val,x=_best(frags,LABELS['project'])
    if lab and val:
        parts=[val]
        for f in _below(frags,lab,x,max_lines=2,depth=65):
            if _address(f['text']):continue
            if x is not None and abs(f['x']-x)<lab['W']*.10 and len(f['text'])>3:parts.append(f['text'])
        d['project_title']=_clean(' '.join(parts))
    _,loc,lval,lx=_best(frags,LABELS['location'])
    if loc:
        txt=lval or ' '.join(f['text'] for f in _below(frags,loc,lx,max_lines=2,depth=60));a=_address(txt)
        if a:d.update(project_street=a['street'],project_zip=a['zip'],project_city=a['city'])
    _,cl,cval,cx=_best(frags,LABELS['client'],exclude=('entwurfsverfasser','planverfasser','architekt'))
    if cl and cval:d['client_name']=cval
    addr_labs=_find(frags,LABELS['client_addr'])
    if cl and addr_labs:
        al=min(addr_labs,key=lambda f:abs(f['y']-cl['y'])+abs(f['x']-cl['x'])*.2)
        aval,ax=_right(frags,al,LABELS['client_addr'])
        if not aval:aval=' '.join(f['text'] for f in _below(frags,al,ax,max_lines=2,depth=55))
        a=_address(aval)
        if a:d.update(client_street=a['street'],client_zip=a['zip'],client_city=a['city'])
    elif cl:
        for f in _below(frags,cl,cx,max_lines=4,depth=75):
            a=_address(f['text'])
            if a:d.update(client_street=a['street'],client_zip=a['zip'],client_city=a['city']);break
    if cl:
        near=[f for f in frags if f['page']==cl['page'] and abs(f['x']-(cx or cl['x']))<cl['W']*.28 and 0<=cl['y']-f['y']<=85]
        ph,em=_contacts(near)
        if ph:d['client_phone']=ph
        if em:d['client_email']=em
    _,al,av,ax=_best(frags,LABELS['architect'])
    if al:
        if av and len(av)>3 and not any(k in av.casefold() for k in ('büro','buero','bauunternehmen','architektur')) and len(av.split())>=2:d['architect_name']=av
        near=_below(frags,al,ax,max_lines=8,depth=150)
        for f in near:
            a=_address(f['text'])
            if a:d.update(architect_street=a['street'],architect_zip=a['zip'],architect_city=a['city']);break
        ph,em=_contacts(near)
        if ph:d['architect_phone']=ph
        if em:d['architect_email']=em
    excluded={(d.get('project_street','').casefold(),d.get('project_zip','')),(d.get('client_street','').casefold(),d.get('client_zip',''))}
    ac=[]
    for f in frags:
        a=_address(f['text'])
        if not a or (a['street'].casefold(),a['zip']) in excluded:continue
        near=[g for g in frags if g['page']==f['page'] and abs(g['x']-f['x'])<f['W']*.22 and abs(g['y']-f['y'])<145]
        cue=' '.join(g['text'].casefold() for g in near)
        score=(20 if f['x']>f['W']*.52 else 0)+(20 if f['y']<f['H']*.42 else 0)
        if any(k in cue for k in ('architektur','architekt','planungsbüro','planungsbuero','ing.-büro','ing.-buero')):score+=90
        if 'engbers ingenieurbau' in cue or 'tragwerksplanung' in cue:score-=100
        ac.append((score,f,a,near))
    if ac and not d.get('architect_street'):
        score,f,a,near=max(ac,key=lambda z:z[0])
        if score>=30:
            d.update(architect_street=a['street'],architect_zip=a['zip'],architect_city=a['city'])
            ph,em=_contacts(near)
            if ph:d['architect_phone']=ph
            if em:d['architect_email']=em
            upper=[g for g in near if 0<g['y']-f['y']<105 and g['x']>=f['x']-f['W']*.10];useful=[]
            for g in sorted(upper,key=lambda z:z['y'],reverse=True):
                t=g['text'];low=t.casefold()
                if _address(t) or PHONE.search(t) or MAIL.search(t) or any(_has(low,k) for k in ALL_LABELS):continue
                if any(k in low for k in ('datum','plannummer','gedruckt','planteil')):continue
                useful.append(t)
            for t in useful:
                if re.search(r'\b(dipl\.?-?ing|architekt(?:in)?\b)',t,re.I) and 'büro' not in t.casefold():d.setdefault('architect_name',t);break
            firms=[t for t in useful if len(t)<80 and not re.fullmatch(r'[\d .,/+\-]+',t)]
            if firms:d['architect_firm']=min(firms,key=len)
    _,el,ev,ex=_best(frags,LABELS['engineer'])
    if el:
        if ev:d['engineer_name']=ev
        near=_below(frags,el,ex,max_lines=7,depth=120)
        for f in near:
            a=_address(f['text'])
            if a:d.update(engineer_street=a['street'],engineer_zip=a['zip'],engineer_city=a['city']);break
        ph,em=_contacts(near)
        if ph:d['engineer_phone']=ph
        if em:d['engineer_email']=em
    return d

def _score(path,root):
    s,why=_OLD_SCORE(path,root)
    try:rel=str(path.relative_to(root)).casefold().replace('\\','/')
    except Exception:rel=str(path).casefold().replace('\\','/')
    txt=path.name.casefold()+' '+rel
    if any(k in txt for k in ('statische berechnung','statischer nachweis','statik pdf','/statik/')):
        if s<24:s=24
        why=(why+', Statik-Ergänzung').strip(', ')
    return s,why

def _pdf_text(path,max_pages=6):
    fr,n=_geometry(path,max_pages)
    if not fr:return ''
    data=_parse_geometry(fr)
    return MAGIC+json.dumps({'data':data,'chars':n},ensure_ascii=False)

def _parse(text):
    if isinstance(text,str) and text.startswith(MAGIC):
        try:return json.loads(text[len(MAGIC):]).get('data',{})
        except Exception:return {}
    return _OLD_PARSE(text)

def open_masterdata(app):
    _base._score=_score
    _base._pdf_text=_pdf_text
    _base._parse=_parse
    return _base.open_masterdata(app)
