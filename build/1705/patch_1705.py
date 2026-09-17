from pathlib import Path
import datetime
import py_compile
import shutil
import traceback

BASE=Path(__file__).resolve().parent
APP=BASE/'app.py'
MOD=BASE/'wordforms_v1700.py'
OLD='1.7.4'
NEW='1.7.5'
MARK='PZ_PDF_EXPORT_RETRY_V1705'

NEW_EXPORT=r"""def _export_pdf_with_word(docx_path, pdf_path):
    # PZ_PDF_EXPORT_RETRY_V1705
    # Robust: zuerst in eine temporaere PDF exportieren, danach atomar ersetzen.
    # Dadurch bleibt eine vorhandene PDF erhalten, falls Word beim Export scheitert.
    docx_path=Path(docx_path).resolve()
    pdf_path=Path(pdf_path).resolve()
    pdf_path.parent.mkdir(parents=True,exist_ok=True)
    if not docx_path.exists():
        return False,'Word-Datei wurde nicht gefunden.'

    script='''On Error Resume Next
Set a = WScript.Arguments
Err.Clear
Set w = CreateObject("Word.Application")
If Err.Number <> 0 Then WScript.Echo "Word konnte nicht gestartet werden: " & Err.Description : WScript.Quit 2
w.Visible = False
w.DisplayAlerts = 0
Err.Clear
Set d = w.Documents.Open(a(0), False, True, False)
If Err.Number <> 0 Then WScript.Echo "Word-Datei konnte nicht geoeffnet werden: " & Err.Description : w.Quit : WScript.Quit 3
Err.Clear
d.ExportAsFixedFormat a(1), 17
If Err.Number <> 0 Then WScript.Echo "PDF-Export durch Word fehlgeschlagen: " & Err.Description : d.Close False : w.Quit : WScript.Quit 4
d.Close False
w.Quit
Set d = Nothing
Set w = Nothing
WScript.Quit 0
'''
    last_err=''
    for attempt in range(1,4):
        tmp_vbs=None
        tmp_pdf=None
        try:
            fd,tmp_vbs=tempfile.mkstemp(prefix='engbers_word_pdf_',suffix='.vbs')
            os.close(fd)
            Path(tmp_vbs).write_text(script,encoding='utf-8-sig')

            fd,tmp_pdf=tempfile.mkstemp(prefix=pdf_path.stem+'_pz_',suffix='.pdf',dir=str(pdf_path.parent))
            os.close(fd)
            try: Path(tmp_pdf).unlink()
            except Exception: pass

            cp=subprocess.run(
                ['cscript.exe','//nologo',tmp_vbs,str(docx_path),str(tmp_pdf)],
                capture_output=True,text=True,timeout=90,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)
            )
            if cp.returncode==0 and Path(tmp_pdf).exists() and Path(tmp_pdf).stat().st_size>0:
                try:
                    os.replace(tmp_pdf,pdf_path)
                    tmp_pdf=None
                    return True,''
                except PermissionError:
                    return False,'Die vorhandene PDF ist noch geoeffnet oder gesperrt. Bitte PDF schliessen und erneut ausfuellen.'
                except Exception as e:
                    return False,'Neue PDF wurde erzeugt, konnte aber nicht ersetzt werden: '+str(e)

            last_err=(cp.stdout or cp.stderr or f'Word-PDF-Export Rueckgabecode {cp.returncode}').strip()
        except subprocess.TimeoutExpired:
            last_err='Microsoft Word hat beim PDF-Export nicht innerhalb von 90 Sekunden geantwortet.'
        except Exception as e:
            last_err=str(e)
        finally:
            if tmp_vbs:
                try: Path(tmp_vbs).unlink()
                except Exception: pass
            if tmp_pdf:
                try: Path(tmp_pdf).unlink()
                except Exception: pass
        if attempt<3:
            time.sleep(0.8)
    return False,(last_err or 'Unbekannter Word-PDF-Fehler')
"""

OLD_MSG="        if made and len(pdf_made)!=len(made): msg.append('Bei mindestens einer Datei konnte Word kein PDF erzeugen; Statuszeile beachten.')"
NEW_MSG="""        if made and len(pdf_made)!=len(made):
            errs=[str(x.get('pdf_error','') or '').strip() for x in docs.values() if x.get('pdf_error')]
            detail=(errs[0] if errs else 'Unbekannter PDF-Fehler')
            msg.append('Bei mindestens einer Datei konnte Word kein PDF erzeugen.\\nGrund: '+detail)
""".rstrip()


def _patch_mod(mod):
    if MARK in mod:
        return mod
    if '\nimport time\n' not in mod:
        anchor='import tempfile\n'
        if anchor not in mod:
            raise RuntimeError('1.7.5: tempfile-Import wurde nicht gefunden.')
        mod=mod.replace(anchor,anchor+'import time\n',1)
    start=mod.find('def _export_pdf_with_word(docx_path, pdf_path):')
    end=mod.find('\n\ndef open_wordforms(app):',start)
    if start<0 or end<0:
        raise RuntimeError('1.7.5: PDF-Exportfunktion wurde nicht gefunden.')
    mod=mod[:start]+NEW_EXPORT+mod[end:]
    if OLD_MSG in mod:
        mod=mod.replace(OLD_MSG,NEW_MSG,1)
    return mod


def main():
    if not APP.exists() or not MOD.exists():
        raise RuntimeError('1.7.5: app.py oder wordforms_v1700.py wurde nicht gefunden.')
    app=APP.read_text(encoding='utf-8')
    mod=MOD.read_text(encoding='utf-8')
    if f'APP_VERSION = "{NEW}"' in app and MARK in mod:
        return 0
    if f'APP_VERSION = "{OLD}"' not in app:
        raise RuntimeError('Update 1.7.5 erwartet Projektzentrale 1.7.4.')

    mod_new=_patch_mod(mod)
    app_new=app.replace(f'APP_VERSION = "{OLD}"',f'APP_VERSION = "{NEW}"',1)
    app_new=app_new.replace('Projektzentrale 1.7.4','Projektzentrale 1.7.5')
    if MARK not in mod_new:
        raise RuntimeError('1.7.5: Sicherheitsmarker fehlt.')

    chk1=APP.with_name('app.py.1705.check'); chk2=MOD.with_name('wordforms_v1700.py.1705.check')
    try:
        chk1.write_text(app_new,encoding='utf-8'); py_compile.compile(str(chk1),doraise=True)
        chk2.write_text(mod_new,encoding='utf-8'); py_compile.compile(str(chk2),doraise=True)
    finally:
        for p in (chk1,chk2):
            try:p.unlink()
            except Exception:pass

    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for p in (APP,MOD): shutil.copy2(p,p.with_name(p.name+'.vor_1_7_5_'+stamp+'.bak'))
    t=APP.with_name('app.py.1705.tmp'); t.write_text(app_new,encoding='utf-8'); t.replace(APP)
    t=MOD.with_name('wordforms_v1700.py.1705.tmp'); t.write_text(mod_new,encoding='utf-8'); t.replace(MOD)
    APP.with_name('patch_1705_report.txt').write_text(
        'OK: Projektzentrale 1.7.5 installiert.\n'
        'PDF-Export robuster: temporaere PDF, danach sicheres Ersetzen.\n'
        'Word-PDF-Export wird bei voruebergehenden COM-Fehlern automatisch wiederholt.\n'
        'Ist die vorhandene PDF geoeffnet/gesperrt, wird jetzt ein klarer Hinweis angezeigt.\n',
        encoding='utf-8')
    return 0


if __name__=='__main__':
    try: raise SystemExit(main())
    except SystemExit: raise
    except Exception:
        try: APP.with_name('patch_1705_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception: pass
        raise
