from pathlib import Path
import datetime
import py_compile
import shutil
import traceback

BASE=Path(__file__).resolve().parent
APP=BASE/'app.py'
GEOM=BASE/'masterdata_v1601.py'
OLD='1.6.7'; NEW='1.6.8'
MARK='PZ_MASTERDATA_ARCHITECT_BAUORT_V1608'

BLOCK=r'''

# PZ_MASTERDATA_ARCHITECT_BAUORT_V1608
# Allplan-/CAD-PDFs zerlegen den sichtbaren Bauort im Plankopf oft in mehrere
# Textfragmente. 1.6.8 setzt deshalb die komplette Zeile rechts neben
# "Bauort:" wieder zusammen, bevor die Adresse ausgewertet wird.
_parse_geometry_v1607 = _parse_geometry

_META_WORDS_V1608=('planteil','plannummer','plan-nr','datum','gedruckt','maßstab','massstab','bauherr','anschrift','entwurfsverfasser','architekt')


def _pz_same_addr_v1608(a, street, zip_code, city):
    def n(v):
        return re.sub(r'\s+',' ',str(v or '').strip()).casefold()
    return bool(a and n(a.get('street'))==n(street) and n(a.get('zip'))==n(zip_code) and n(a.get('city'))==n(city))


def _pz_inline_after_location_v1608(text):
    low=text.casefold()
    for term in LABELS['location']:
        pos=low.find(term)
        if pos>=0:
            rest=text[pos+len(term):].lstrip(' :.-–—')
            if rest:
                return _clean(rest)
    return ''


def _pz_architect_bauort_v1608(frags,d):
    """Bauort direkt aus dem Plankopf lesen, auch wenn er in Fragmente zerlegt ist."""
    for lab in _find(frags,LABELS['location']):
        texts=[]

        # 1) Wert steckt bereits im selben Fragment hinter "Bauort:".
        inline=_pz_inline_after_location_v1608(lab['text'])
        if inline:
            texts.append(inline)

        # 2) Sichtbar gleiche Zeile: ALLE Fragmente rechts vom Label zusammensetzen.
        tol=max(8.0,min(24.0,float(lab.get('font') or 12.0)*1.35))
        same=[]
        for f in frags:
            if f is lab or f['page']!=lab['page']:
                continue
            if f['x'] <= lab['x']+1:
                continue
            if f['x']-lab['x'] > lab['W']*.52:
                continue
            if abs(f['y']-lab['y']) > tol:
                continue
            low=f['text'].casefold()
            if any(_has(low,k) for k in ALL_LABELS):
                continue
            if any(k in low for k in _META_WORDS_V1608):
                continue
            same.append(f)
        same.sort(key=lambda f:f['x'])
        same_text=_clean(' '.join(f['text'] for f in same))
        if same_text:
            texts.append(same_text)

        # 3) Wenn Straße und PLZ/Ort optisch zweizeilig sind, die direkt darunter
        #    liegende Zeile in derselben Wertespalte dazunehmen.
        x0=(same[0]['x'] if same else None)
        if x0 is None:
            _,x0=_right(frags,lab,LABELS['location'])
        below=[]
        if x0 is not None:
            for f in frags:
                if f is lab or f['page']!=lab['page']:
                    continue
                dy=lab['y']-f['y']
                if not (2 <= dy <= 55):
                    continue
                if abs(f['x']-x0) > lab['W']*.10:
                    continue
                low=f['text'].casefold()
                if any(_has(low,k) for k in ALL_LABELS):
                    continue
                if any(k in low for k in _META_WORDS_V1608):
                    continue
                below.append((dy,f['x'],f['text']))
            below.sort(key=lambda z:(z[0],z[1]))
        below_texts=[z[2] for z in below[:3]]

        tries=[]
        tries.extend(texts)
        if same_text and below_texts:
            tries.append(_clean(same_text+' '+' '.join(below_texts)))
        for t in texts:
            for b in below_texts:
                tries.append(_clean(t+' '+b))

        for candidate in tries:
            a=_address(candidate)
            if not a:
                continue
            # Niemals die Bauherrenanschrift als Bauort akzeptieren.
            if _pz_same_addr_v1608(a,d.get('client_street',''),d.get('client_zip',''),d.get('client_city','')):
                continue
            return a
    return {}


def _parse_geometry(frags):
    d=_parse_geometry_v1607(frags)
    # 1.6.7 ist bewusst konservativ. 1.6.8 fuellt die Bauadresse nur dann wieder,
    # wenn sie am expliziten Label Bauort/Grundstueck im Plankopf gelesen wird.
    if not d.get('project_street'):
        a=_pz_architect_bauort_v1608(frags,d)
        if a:
            d['project_street']=a.get('street','')
            d['project_zip']=a.get('zip','')
            d['project_city']=a.get('city','')
    return d
'''


def _compile_text(text,name):
    p=BASE/name
    try:
        p.write_text(text,encoding='utf-8')
        py_compile.compile(str(p),doraise=True)
    finally:
        try:p.unlink()
        except Exception:pass


def main():
    if not APP.exists() or not GEOM.exists():
        raise RuntimeError('1.6.8: erforderliche Programmdateien nicht gefunden.')
    app=APP.read_text(encoding='utf-8')
    geom=GEOM.read_text(encoding='utf-8')
    if f'APP_VERSION = "{NEW}"' in app and MARK in geom:
        return 0
    if f'APP_VERSION = "{OLD}"' not in app:
        raise RuntimeError('Update 1.6.8 erwartet Projektzentrale 1.6.7.')
    geom_new=geom if MARK in geom else geom.rstrip()+BLOCK+'\n'
    app_new=app.replace(f'APP_VERSION = "{OLD}"',f'APP_VERSION = "{NEW}"',1)
    app_new=app_new.replace('Projektzentrale 1.6.7','Projektzentrale 1.6.8')
    _compile_text(app_new,'app.py.1608.check')
    _compile_text(geom_new,'masterdata_v1601.py.1608.check')
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for p in (APP,GEOM):
        shutil.copy2(p,p.with_name(p.name+'.vor_1_6_8_'+stamp+'.bak'))
    tmp=APP.with_name('app.py.1608.tmp');tmp.write_text(app_new,encoding='utf-8');tmp.replace(APP)
    tmp=GEOM.with_name('masterdata_v1601.py.1608.tmp');tmp.write_text(geom_new,encoding='utf-8');tmp.replace(GEOM)
    APP.with_name('patch_1608_report.txt').write_text(
        'OK: Projektzentrale 1.6.8 installiert.\n'
        'Bauort wird direkt aus dem Architekten-Plankopf gelesen, auch bei getrennten Allplan-Textfragmenten.\n'
        'Die Bauherrenadresse bleibt als Bauort ausgeschlossen.\n',encoding='utf-8')
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except SystemExit:raise
    except Exception:
        try:APP.with_name('patch_1608_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception:pass
        raise
