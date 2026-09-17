from pathlib import Path
import datetime
import py_compile
import runpy
import shutil
import traceback

BASE=Path(__file__).resolve().parent
ORIG=BASE/'patch_1718.py'


def main():
    ns=runpy.run_path(str(ORIG),run_name='defs1718')
    APP=ns['APP']; MOD=ns['MOD']; OLD=ns['OLD']; NEW=ns['NEW']; MARK=ns['MARK']
    _version=ns['_version']; _set_version=ns['_set_version']; _replace_function=ns['_replace_function']
    new_func=ns['NEW_FUNC'].replace('"Druckausgabe speichern unter"-Dialog','Windows-Speicherdialog')

    if not APP.exists() or not MOD.exists():
        raise RuntimeError('1.7.18: app.py oder wordforms_v1700.py wurde nicht gefunden.')
    app=APP.read_text(encoding='utf-8'); mod=MOD.read_text(encoding='utf-8'); cur=_version(app)
    if cur==NEW and MARK in mod:
        return 0
    if cur!=OLD:
        raise RuntimeError(f'Update 1.7.18 erwartet Projektzentrale {OLD}; gefunden: {cur or "unbekannt"}.')

    app_new=_set_version(app)
    mod_new=_replace_function(mod,'_export_pdf_with_word',new_func)
    if MARK not in mod_new:
        raise RuntimeError('1.7.18: PrintToFile-Marker fehlt nach dem Patch.')
    active_start=mod_new.find(MARK)
    active_end=mod_new.find('\ndef ',active_start)
    active=mod_new[active_start:active_end if active_end>0 else len(mod_new)]
    for required in ('GetActiveObject','Microsoft Print to PDF','OutputFileName=$PdfPath','PrintToFile=$true','$doc.PrintOut'):
        if required not in active:
            raise RuntimeError('1.7.18: erwarteter direkter PrintToFile-Baustein fehlt: '+required)
    for forbidden in ('SendWait(', 'FocusedElement','FileNameControlHost'):
        if forbidden in active:
            raise RuntimeError('1.7.18: alter Dialog-Automationsweg ist noch aktiv: '+forbidden)

    chk1=APP.with_name('app.py.1718.check')
    chk2=MOD.with_name('wordforms_v1700.py.1718.check')
    try:
        chk1.write_text(app_new,encoding='utf-8'); py_compile.compile(str(chk1),doraise=True)
        chk2.write_text(mod_new,encoding='utf-8'); py_compile.compile(str(chk2),doraise=True)
    finally:
        for p in (chk1,chk2):
            try:p.unlink()
            except Exception:pass

    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for p in (APP,MOD):
        shutil.copy2(p,p.with_name(p.name+'.vor_1_7_18_'+stamp+'.bak'))
    t=APP.with_name('app.py.1718.tmp'); t.write_text(app_new,encoding='utf-8'); t.replace(APP)
    t=MOD.with_name('wordforms_v1700.py.1718.tmp'); t.write_text(mod_new,encoding='utf-8'); t.replace(MOD)
    APP.with_name('patch_1718_report.txt').write_text(
        'OK: Projektzentrale 1.7.18 installiert.\n'
        'PDF-Erzeugung: Word PrintOut mit PrintToFile und festem OutputFileName; keine Dialog-Automation mehr.\n',
        encoding='utf-8')
    return 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        try: (BASE/'patch_1718_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception: pass
        raise
