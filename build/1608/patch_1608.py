from pathlib import Path
import datetime
import py_compile
import shutil
import traceback

BASE=Path(__file__).resolve().parent
APP=BASE/'app.py'
GEOM=BASE/'masterdata_v1601.py'
OLD='1.6.7'; NEW='1.6.8'
MARK='PZ_MASTERDATA_SAFE_PROJECT_ADDRESS_FALLBACK_V1608'

BLOCK=r'''

# PZ_MASTERDATA_SAFE_PROJECT_ADDRESS_FALLBACK_V1608
# Sichere Ergaenzung fuer Statik-/Titelblaetter:
# Bauvorhaben -> Bezeichnung -> Adresse direkt darunter in derselben Textspalte.
_parse_geometry_v1607 = _parse_geometry

_META_WORDS_V1608=('planteil','plannummer','plan-nr','datum','gedruckt','maßstab','massstab','bauherr','anschrift','entwurfsverfasser','architekt')


def _pz_same_addr_v1608(a, street, zip_code, city):
    def n(v):
        return re.sub(r'\s+',' ',str(v or '').strip()).casefold()
    return bool(a and n(a.get('street'))==n(street) and n(a.get('zip'))==n(zip_code) and n(a.get('city'))==n(city))


def _pz_project_address_below_title_v1608(frags, d):
    """Adresse nur unmittelbar unter dem Bauvorhaben-Wert in derselben Spalte akzeptieren."""
    for lab in _find(frags,LABELS['project']):
        val,x=_right(frags,lab,LABELS['project'])
        if not val or x is None:
            continue
        cands=[]
        for f in frags:
            if f is lab or f['page']!=lab['page']:
                continue
            dy=lab['y']-f['y']
            if not (2 <= dy <= 58):
                continue
            if abs(f['x']-x) > lab['W']*.085:
                continue
            low=f['text'].casefold()
            if any(_has(low,k) for k in ALL_LABELS):
                continue
            if any(k in low for k in _META_WORDS_V1608):
                continue
            cands.append((dy,f['x'],f['text']))
        cands.sort(key=lambda z:(z[0],z[1]))
        texts=[z[2] for z in cands[:4]]
        tries=[]
        tries.extend(texts)
        for i in range(len(texts)):
            tries.append(' '.join(texts[i:i+2]))
        for text in tries:
            a=_address(text)
            if not a:
                continue
            if _pz_same_addr_v1608(a,d.get('client_street',''),d.get('client_zip',''),d.get('client_city','')):
                continue
            return a
    return {}


def _parse_geometry(frags):
    d=_parse_geometry_v1607(frags)
    if not d.get('project_street'):
        a=_pz_project_address_below_title_v1608(frags,d)
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
        'Fehlende Bauvorhaben-Adresse darf jetzt aus einer eindeutigen Adresszeile direkt unter dem Bauvorhaben ergaenzt werden.\n'
        'Die Bauherrenadresse wird dabei explizit ausgeschlossen.\n',encoding='utf-8')
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except SystemExit:raise
    except Exception:
        try:APP.with_name('patch_1608_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception:pass
        raise
