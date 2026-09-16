from pathlib import Path
import datetime
import py_compile
import shutil
import traceback

BASE=Path(__file__).resolve().parent
APP=BASE/'app.py'
GEOM=BASE/'masterdata_v1601.py'
OLD='1.6.8'; NEW='1.6.9'
MARK='PZ_MASTERDATA_EXPLICIT_BAUORT_NO_HOUSENO_V1609'

BLOCK=r'''

# PZ_MASTERDATA_EXPLICIT_BAUORT_NO_HOUSENO_V1609
# Ein explizit beschrifteter Bauort darf auch ohne Hausnummer gespeichert werden,
# z.B. "Bauort: Bayernstr. 48429 Rheine".
_parse_geometry_v1608 = _parse_geometry

_PZ_BAUORT_FLEX_V1609 = re.compile(
    r'^(?P<street>.+?)\s*[,;]?\s+(?P<zip>\d{5})\s+(?P<city>[A-ZÄÖÜa-zäöüß][A-ZÄÖÜa-zäöüß .\'’\-]{1,60})$',
    re.I)


def _pz_norm_v1609(v):
    return re.sub(r'\s+',' ',str(v or '').strip()).casefold()


def _pz_same_address_v1609(a, street, zip_code, city):
    return bool(
        a and
        _pz_norm_v1609(a.get('street')) == _pz_norm_v1609(street) and
        _pz_norm_v1609(a.get('zip')) == _pz_norm_v1609(zip_code) and
        _pz_norm_v1609(a.get('city')) == _pz_norm_v1609(city)
    )


def _pz_flexible_explicit_address_v1609(text):
    text=_clean(text).strip(' ,;:-')
    # Label ggf. noch im zusammengesetzten Text entfernen.
    text=re.sub(r'^\s*(?:bauort|grundst(?:ue|ü)ck)\s*:\s*','',text,flags=re.I)
    m=_PZ_BAUORT_FLEX_V1609.match(text)
    if not m:
        return {}
    street=m.group('street').strip(' ,;:-')
    zip_code=m.group('zip').strip()
    city=m.group('city').strip(' ,;:-')
    # Ein nackter Ort/sonstiger Metatext vor der PLZ soll nicht als Straße gelten.
    if len(street) < 3 or street.casefold() in ('bauort','grundstück','grundstueck'):
        return {}
    return {'street':street,'zip':zip_code,'city':city}


def _pz_explicit_bauort_v1609(frags, d):
    """Liest nur die explizit beschriftete Bauort-Zeile und erlaubt Straßen ohne Hausnummer."""
    for lab in _find(frags,LABELS['location']):
        pieces=[]
        low=lab['text'].casefold()
        # Text rechts vom Label im selben Fragment, falls vorhanden.
        for term in LABELS['location']:
            pos=low.find(term)
            if pos >= 0:
                rest=lab['text'][pos+len(term):].lstrip(' :.-–—')
                if rest:
                    pieces.append((lab['x']+1.0,rest))
                break

        tol=max(4.0,min(16.0,float(lab.get('font') or 10.0)*0.75))
        for f in frags:
            if f is lab or f.get('page') != lab.get('page'):
                continue
            if f.get('x',0) <= lab.get('x',0)+2:
                continue
            if f.get('x',0)-lab.get('x',0) > lab.get('W',1000.0)*0.52:
                continue
            if abs(float(f.get('y',0))-float(lab.get('y',0))) > tol:
                continue
            txt=_clean(f.get('text',''))
            if not txt:
                continue
            # Keine benachbarten Feldbezeichnungen in die Bauort-Zeile mischen.
            if any(_has(txt.casefold(),k) for k in ALL_LABELS):
                continue
            pieces.append((float(f.get('x',0)),txt))

        if not pieces:
            continue
        # Doppelte Fragmente entfernen, aber X-Reihenfolge bewahren.
        ordered=[]; seen=set()
        for x,txt in sorted(pieces,key=lambda z:z[0]):
            key=(round(x,1),txt.casefold())
            if key in seen:
                continue
            seen.add(key); ordered.append(txt)
        joined=_clean(' '.join(ordered))
        a=_pz_flexible_explicit_address_v1609(joined)
        if not a:
            continue
        if _pz_same_address_v1609(a,d.get('client_street',''),d.get('client_zip',''),d.get('client_city','')):
            continue
        return a
    return {}


def _parse_geometry(frags):
    d=_parse_geometry_v1608(frags)
    a=_pz_explicit_bauort_v1609(frags,d)
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
        raise RuntimeError('1.6.9: erforderliche Programmdateien nicht gefunden.')
    app=APP.read_text(encoding='utf-8')
    geom=GEOM.read_text(encoding='utf-8')
    if f'APP_VERSION = "{NEW}"' in app and MARK in geom:
        return 0
    if f'APP_VERSION = "{OLD}"' not in app:
        raise RuntimeError('Update 1.6.9 erwartet Projektzentrale 1.6.8.')
    geom_new=geom if MARK in geom else geom.rstrip()+BLOCK+'\n'
    app_new=app.replace(f'APP_VERSION = "{OLD}"',f'APP_VERSION = "{NEW}"',1)
    app_new=app_new.replace('Projektzentrale 1.6.8','Projektzentrale 1.6.9')
    _compile_text(app_new,'app.py.1609.check')
    _compile_text(geom_new,'masterdata_v1601.py.1609.check')
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for p in (APP,GEOM):
        shutil.copy2(p,p.with_name(p.name+'.vor_1_6_9_'+stamp+'.bak'))
    tmp=APP.with_name('app.py.1609.tmp');tmp.write_text(app_new,encoding='utf-8');tmp.replace(APP)
    tmp=GEOM.with_name('masterdata_v1601.py.1609.tmp');tmp.write_text(geom_new,encoding='utf-8');tmp.replace(GEOM)
    APP.with_name('patch_1609_report.txt').write_text(
        'OK: Projektzentrale 1.6.9 installiert.\n'
        'Explizit beschrifteter Bauort wird jetzt auch ohne Hausnummer erkannt.\n'
        'Beispiel: Bayernstr. 48429 Rheine -> Straße Bayernstr., PLZ 48429, Ort Rheine.\n'
        'Die Bauherrenadresse bleibt als Bauort ausgeschlossen.\n',encoding='utf-8')
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except SystemExit:raise
    except Exception:
        try:APP.with_name('patch_1609_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception:pass
        raise
