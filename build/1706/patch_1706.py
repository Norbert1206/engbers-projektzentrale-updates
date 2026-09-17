from pathlib import Path
import datetime
import py_compile
import shutil
import traceback

BASE=Path(__file__).resolve().parent
APP=BASE/'app.py'
MOD=BASE/'wordforms_v1700.py'
OLD='1.7.5'
NEW='1.7.6'
MARK='PZ_PDF_POWERSHELL_WORD_V1706'

NEW_EXPORT=r"""def _export_pdf_with_word(docx_path, pdf_path):
    # PZ_PDF_POWERSHELL_WORD_V1706
    # Export ueber PowerShell + Word-COM statt VBScript/cscript.
    # Erst temporaere PDF, danach atomar an Zielstelle ersetzen.
    docx_path=Path(docx_path).resolve()
    pdf_path=Path(pdf_path).resolve()
    pdf_path.parent.mkdir(parents=True,exist_ok=True)
    if not docx_path.exists():
        return False,'Word-Datei wurde nicht gefunden.'

    ps=r'''param(
    [Parameter(Mandatory=$true)][string]$DocxPath,
    [Parameter(Mandatory=$true)][string]$PdfPath
)
$ErrorActionPreference = 'Stop'
$word = $null
$doc = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $doc = $word.Documents.Open($DocxPath, $false, $true, $false)
    $doc.ExportAsFixedFormat($PdfPath, 17)
    exit 0
}
catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
finally {
    if ($doc -ne $null) {
        try { $doc.Close($false) } catch {}
        try { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($doc) } catch {}
    }
    if ($word -ne $null) {
        try { $word.Quit() } catch {}
        try { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($word) } catch {}
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
'''
    last_err=''
    for attempt in range(1,4):
        tmp_ps1=None
        tmp_pdf=None
        try:
            fd,tmp_ps1=tempfile.mkstemp(prefix='engbers_word_pdf_',suffix='.ps1')
            os.close(fd)
            Path(tmp_ps1).write_text(ps,encoding='utf-8-sig')

            fd,tmp_pdf=tempfile.mkstemp(prefix=pdf_path.stem+'_pz_',suffix='.pdf',dir=str(pdf_path.parent))
            os.close(fd)
            try: Path(tmp_pdf).unlink()
            except Exception: pass

            cmd=[
                'powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass',
                '-File',tmp_ps1,'-DocxPath',str(docx_path),'-PdfPath',str(tmp_pdf)
            ]
            cp=subprocess.run(
                cmd,capture_output=True,text=True,timeout=120,
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

            detail=(cp.stderr or cp.stdout or '').strip()
            last_err=detail or f'PowerShell-Word-PDF-Export Rueckgabecode {cp.returncode}'
        except FileNotFoundError:
            return False,'Windows PowerShell wurde nicht gefunden.'
        except subprocess.TimeoutExpired:
            last_err='Microsoft Word hat beim PDF-Export nicht innerhalb von 120 Sekunden geantwortet.'
        except Exception as e:
            last_err=str(e)
        finally:
            if tmp_ps1:
                try: Path(tmp_ps1).unlink()
                except Exception: pass
            if tmp_pdf:
                try: Path(tmp_pdf).unlink()
                except Exception: pass
        if attempt<3:
            time.sleep(0.8)
    return False,(last_err or 'Unbekannter PowerShell-Word-PDF-Fehler')
"""


def _patch_mod(mod):
    if MARK in mod:
        return mod
    start=mod.find('def _export_pdf_with_word(docx_path, pdf_path):')
    end=mod.find('\n\ndef open_wordforms(app):',start)
    if start<0 or end<0:
        raise RuntimeError('1.7.6: PDF-Exportfunktion wurde nicht gefunden.')
    return mod[:start]+NEW_EXPORT+mod[end:]


def main():
    if not APP.exists() or not MOD.exists():
        raise RuntimeError('1.7.6: app.py oder wordforms_v1700.py wurde nicht gefunden.')
    app=APP.read_text(encoding='utf-8')
    mod=MOD.read_text(encoding='utf-8')
    if f'APP_VERSION = "{NEW}"' in app and MARK in mod:
        return 0
    if f'APP_VERSION = "{OLD}"' not in app:
        raise RuntimeError('Update 1.7.6 erwartet Projektzentrale 1.7.5.')

    mod_new=_patch_mod(mod)
    app_new=app.replace(f'APP_VERSION = "{OLD}"',f'APP_VERSION = "{NEW}"',1)
    app_new=app_new.replace('Projektzentrale 1.7.5','Projektzentrale 1.7.6')
    if MARK not in mod_new:
        raise RuntimeError('1.7.6: Sicherheitsmarker fehlt.')

    chk1=APP.with_name('app.py.1706.check'); chk2=MOD.with_name('wordforms_v1700.py.1706.check')
    try:
        chk1.write_text(app_new,encoding='utf-8'); py_compile.compile(str(chk1),doraise=True)
        chk2.write_text(mod_new,encoding='utf-8'); py_compile.compile(str(chk2),doraise=True)
    finally:
        for p in (chk1,chk2):
            try:p.unlink()
            except Exception:pass

    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for p in (APP,MOD): shutil.copy2(p,p.with_name(p.name+'.vor_1_7_6_'+stamp+'.bak'))
    t=APP.with_name('app.py.1706.tmp'); t.write_text(app_new,encoding='utf-8'); t.replace(APP)
    t=MOD.with_name('wordforms_v1700.py.1706.tmp'); t.write_text(mod_new,encoding='utf-8'); t.replace(MOD)
    APP.with_name('patch_1706_report.txt').write_text(
        'OK: Projektzentrale 1.7.6 installiert.\n'
        'PDF-Export fuer Word-Bescheinigungen nutzt jetzt PowerShell + Microsoft Word-COM.\n'
        'VBScript/cscript wird nicht mehr verwendet.\n'
        'Export erfolgt zuerst in temporaere PDF und wird danach sicher ersetzt.\n',
        encoding='utf-8')
    return 0


if __name__=='__main__':
    try: raise SystemExit(main())
    except SystemExit: raise
    except Exception:
        try: APP.with_name('patch_1706_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception: pass
        raise
