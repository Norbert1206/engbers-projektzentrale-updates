from pathlib import Path
import datetime
import py_compile
import shutil
import traceback

BASE=Path(__file__).resolve().parent
APP=BASE/'app.py'
MOD=BASE/'wordforms_v1700.py'
OLD='1.7.6'
NEW='1.7.7'
MARK='PZ_PDF_EXPORT_SAFE_DOCX_V1707'

NEW_EXPORT=r"""def _field_result_text(ff, parents):
    fld=parents.get(ff)
    begin=_ancestor(fld,'r',parents)
    p=_ancestor(begin,'p',parents)
    if begin is None or p is None:
        return ''
    children=list(p)
    try:
        bi=children.index(begin)
    except ValueError:
        return ''
    sep_i=end_i=None
    for i,el in enumerate(children[bi:],bi):
        fc=el.find('.//'+Q('fldChar'))
        if fc is None:
            continue
        typ=fc.get(Q('fldCharType'))
        if typ=='separate' and sep_i is None:
            sep_i=i
        elif typ=='end' and sep_i is not None:
            end_i=i
            break
    if sep_i is None or end_i is None:
        return ''
    return ''.join(_txt(el) for el in children[sep_i+1:end_i])


def _make_export_safe_docx(src):
    # PZ_PDF_EXPORT_SAFE_DOCX_V1707
    # Fuer den PDF-Export werden nur die alten Text-Formularfelder in einer
    # temporaeren Kopie in normalen Text umgewandelt. Die Projekt-DOCX selbst
    # bleibt unveraendert und behaelt ihre Formularfelder fuer spaetere Updates.
    src=Path(src).resolve()
    with zipfile.ZipFile(src,'r') as zin:
        root=ET.fromstring(zin.read('word/document.xml'))
        parents={c:p for p in root.iter() for c in p}
        fields=list(root.iter(Q('ffData')))
        flattened=0
        for ff in fields:
            if ff.find(Q('checkBox')) is not None:
                continue
            value=_field_result_text(ff,parents)
            if _flatten(ff,value,parents):
                flattened+=1
        new_xml=ET.tostring(root,encoding='utf-8',xml_declaration=True)
        fd,tmp=tempfile.mkstemp(prefix='engbers_pdf_export_',suffix='.docx')
        os.close(fd)
        try:
            with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    content=new_xml if item.filename=='word/document.xml' else zin.read(item.filename)
                    zout.writestr(item,content)
            with zipfile.ZipFile(tmp,'r') as chk:
                if chk.testzip() is not None:
                    raise RuntimeError('Export-Zwischendatei ist kein gueltiges DOCX-Archiv.')
            return Path(tmp),flattened
        except Exception:
            try: Path(tmp).unlink()
            except Exception: pass
            raise


def _export_pdf_with_word(docx_path, pdf_path):
    docx_path=Path(docx_path).resolve()
    pdf_path=Path(pdf_path).resolve()
    pdf_path.parent.mkdir(parents=True,exist_ok=True)
    if not docx_path.exists():
        return False,'Word-Datei wurde nicht gefunden.'

    export_docx=None
    try:
        export_docx,_=_make_export_safe_docx(docx_path)
    except Exception as e:
        return False,'PDF-Export-Zwischendatei konnte nicht erstellt werden: '+str(e)

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
    try:
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
                    '-File',tmp_ps1,'-DocxPath',str(export_docx),'-PdfPath',str(tmp_pdf)
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
    finally:
        if export_docx:
            try: Path(export_docx).unlink()
            except Exception: pass
"""


def _patch_mod(mod):
    if MARK in mod:
        return mod
    start=mod.find('def _export_pdf_with_word(docx_path, pdf_path):')
    end=mod.find('\n\ndef open_wordforms(app):',start)
    if start<0 or end<0:
        raise RuntimeError('1.7.7: PDF-Exportfunktion wurde nicht gefunden.')
    return mod[:start]+NEW_EXPORT+mod[end:]


def main():
    if not APP.exists() or not MOD.exists():
        raise RuntimeError('1.7.7: app.py oder wordforms_v1700.py wurde nicht gefunden.')
    app=APP.read_text(encoding='utf-8')
    mod=MOD.read_text(encoding='utf-8')
    if f'APP_VERSION = "{NEW}"' in app and MARK in mod:
        return 0
    if f'APP_VERSION = "{OLD}"' not in app:
        raise RuntimeError('Update 1.7.7 erwartet Projektzentrale 1.7.6.')

    mod_new=_patch_mod(mod)
    app_new=app.replace(f'APP_VERSION = "{OLD}"',f'APP_VERSION = "{NEW}"',1)
    app_new=app_new.replace('Projektzentrale 1.7.6','Projektzentrale 1.7.7')
    if MARK not in mod_new:
        raise RuntimeError('1.7.7: Sicherheitsmarker fehlt.')

    chk1=APP.with_name('app.py.1707.check'); chk2=MOD.with_name('wordforms_v1700.py.1707.check')
    try:
        chk1.write_text(app_new,encoding='utf-8'); py_compile.compile(str(chk1),doraise=True)
        chk2.write_text(mod_new,encoding='utf-8'); py_compile.compile(str(chk2),doraise=True)
    finally:
        for p in (chk1,chk2):
            try:p.unlink()
            except Exception:pass

    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for p in (APP,MOD): shutil.copy2(p,p.with_name(p.name+'.vor_1_7_7_'+stamp+'.bak'))
    t=APP.with_name('app.py.1707.tmp'); t.write_text(app_new,encoding='utf-8'); t.replace(APP)
    t=MOD.with_name('wordforms_v1700.py.1707.tmp'); t.write_text(mod_new,encoding='utf-8'); t.replace(MOD)
    APP.with_name('patch_1707_report.txt').write_text(
        'OK: Projektzentrale 1.7.7 installiert.\n'
        'Projekt-DOCX behaelt ihre Formularfelder.\n'
        'Fuer den PDF-Export wird nur temporaer eine flache Export-DOCX erzeugt und danach geloescht.\n'
        'PowerShell + Microsoft Word-COM exportiert nur diese Export-Zwischendatei.\n',
        encoding='utf-8')
    return 0


if __name__=='__main__':
    try: raise SystemExit(main())
    except SystemExit: raise
    except Exception:
        try: APP.with_name('patch_1707_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception: pass
        raise
