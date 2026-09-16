from pathlib import Path
import datetime
import py_compile
import shutil
import traceback

BASE=Path(__file__).resolve().parent
APP=BASE/'app.py'
GEOM=BASE/'masterdata_v1601.py'
OLD='1.6.6'; NEW='1.6.7'
MARK='PZ_MASTERDATA_CONSERVATIVE_V1607'

SAFE_BLOCK=r'''

# PZ_MASTERDATA_CONSERVATIVE_V1607
# Stammdaten nur uebernehmen, wenn sie fachlich eindeutig zugeordnet werden koennen.
_parse_geometry_v1606 = _parse_geometry

_BAD_PROJECT_TITLE_LABEL = re.compile(
    r'\s+(?:Planteil|Plannummer|Plan-Nr\.?|Datum|gedruckt|Bauherr|Anschrift|'
    r'Entwurfsverfasser|Planverfasser|Architekt|Bauort|Grundst(?:ue|ü)ck)\s*:',
    re.I)


def _same_address(a, street, zip_code, city):
    def n(v):
        return re.sub(r'\s+',' ',str(v or '').strip()).casefold()
    return bool(a and n(a.get('street'))==n(street) and n(a.get('zip'))==n(zip_code) and n(a.get('city'))==n(city))


def _explicit_project_address(frags, client_street='', client_zip='', client_city=''):
    """Nur explizit mit Bauort/Grundstueck beschriftete Anschriften akzeptieren."""
    for loc in _find(frags, LABELS['location']):
        val, x = _right(frags, loc, LABELS['location'])
        texts=[]
        if val:
            texts.append(val)
        # Nur eng unterhalb/rechts des Bauort-Labels lesen; keine fremden Plankopf-Bloecke.
        below=_below(frags,loc,x,max_lines=3,depth=75)
        for f in below:
            if x is not None and abs(f['x']-x) <= loc['W']*.12:
                texts.append(f['text'])
        candidates=[]
        candidates.extend(texts)
        for i in range(len(texts)):
            candidates.append(' '.join(texts[i:i+2]))
            candidates.append(' '.join(texts[i:i+3]))
        for candidate in candidates:
            a=_address(candidate)
            if not a:
                continue
            if _same_address(a,client_street,client_zip,client_city):
                continue
            return a
    return {}


def _parse_geometry(frags):
    d=_parse_geometry_v1606(frags)

    # Bauvorhaben-Bezeichnung an der naechsten Plankopf-Beschriftung abschneiden.
    title=_clean(d.get('project_title',''))
    m=_BAD_PROJECT_TITLE_LABEL.search(title)
    if m:
        title=title[:m.start()].strip(' .,:;-')
    d['project_title']=title

    # Den grosszuegigen 1.6.6-Fallback bewusst verwerfen. Eine Bauadresse wird
    # nur akzeptiert, wenn sie explizit bei Bauort/Grundstueck gefunden wurde.
    a=_explicit_project_address(
        frags,
        d.get('client_street',''),d.get('client_zip',''),d.get('client_city',''))
    if a:
        d['project_street']=a.get('street','')
        d['project_zip']=a.get('zip','')
        d['project_city']=a.get('city','')
    else:
        d['project_street']=''
        d['project_zip']=''
        d['project_city']=''
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
        raise RuntimeError('1.6.7: erforderliche Programmdateien nicht gefunden.')
    app=APP.read_text(encoding='utf-8')
    geom=GEOM.read_text(encoding='utf-8')
    if f'APP_VERSION = "{NEW}"' in app and MARK in geom:
        return 0
    if f'APP_VERSION = "{OLD}"' not in app:
        raise RuntimeError('Update 1.6.7 erwartet Projektzentrale 1.6.6.')
    if MARK in geom:
        geom_new=geom
    else:
        geom_new=geom.rstrip()+SAFE_BLOCK+'\n'
    app_new=app.replace(f'APP_VERSION = "{OLD}"',f'APP_VERSION = "{NEW}"',1)
    app_new=app_new.replace('Projektzentrale 1.6.6','Projektzentrale 1.6.7')
    _compile_text(app_new,'app.py.1607.check')
    _compile_text(geom_new,'masterdata_v1601.py.1607.check')
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for p in (APP,GEOM):
        shutil.copy2(p,p.with_name(p.name+'.vor_1_6_7_'+stamp+'.bak'))
    tmp=APP.with_name('app.py.1607.tmp');tmp.write_text(app_new,encoding='utf-8');tmp.replace(APP)
    tmp=GEOM.with_name('masterdata_v1601.py.1607.tmp');tmp.write_text(geom_new,encoding='utf-8');tmp.replace(GEOM)
    APP.with_name('patch_1607_report.txt').write_text(
        'OK: Projektzentrale 1.6.7 installiert.\n'
        'Bauvorhaben-Bezeichnung wird von Planteil/Datum/Plannummer getrennt.\n'
        'Bauvorhaben-Adresse wird nur noch aus explizit beschriftetem Bauort/Grundstueck uebernommen.\n'
        'Bauherrenadresse kann nicht mehr als Bauvorhaben-Adresse uebernommen werden.\n',encoding='utf-8')
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except SystemExit:raise
    except Exception:
        try:APP.with_name('patch_1607_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception:pass
        raise
