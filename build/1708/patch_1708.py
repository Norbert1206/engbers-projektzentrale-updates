from pathlib import Path
import datetime
import py_compile
import shutil
import traceback

BASE=Path(__file__).resolve().parent
APP=BASE/'app.py'
MOD=BASE/'wordforms_v1700.py'
OLD='1.7.7'; NEW='1.7.8'
MARK='PZ_ADOBE_PDFMAKER_V1708'

NEW_EXPORT=r"""def _export_pdf_with_word(docx_path, pdf_path):
    # PZ_ADOBE_PDFMAKER_V1708
    # Oeffnet die DOCX ueber Windows/Word wie beim manuellen Doppelklick und
    # verwendet anschliessend das Acrobat PDFMaker Office COM Add-In.
    docx_path=Path(docx_path).resolve()
    pdf_path=Path(pdf_path).resolve()
    pdf_path.parent.mkdir(parents=True,exist_ok=True)
    if not docx_path.exists():
        return False,'Word-Datei wurde nicht gefunden.'

    script=r'''On Error Resume Next
Set a = WScript.Arguments
docx = a(0)
pdf = a(1)
Set fso = CreateObject("Scripting.FileSystemObject")
If fso.FileExists(pdf) Then
    Err.Clear
    fso.DeleteFile pdf, True
    If Err.Number <> 0 Then
        WScript.Echo "Die vorhandene PDF ist noch geöffnet oder gesperrt. Bitte PDF schließen und erneut ausfüllen."
        WScript.Quit 20
    End If
End If

' Genau wie ein Doppelklick: DOCX ueber die Windows-Dateizuordnung in Word oeffnen.
Set sh = CreateObject("WScript.Shell")
Err.Clear
sh.Run Chr(34) & docx & Chr(34), 1, False
If Err.Number <> 0 Then
    WScript.Echo "Word-Datei konnte über Windows nicht geöffnet werden: " & Err.Description
    WScript.Quit 21
End If

Set w = Nothing
For i = 1 To 80
    Err.Clear
    Set w = GetObject(, "Word.Application")
    If Err.Number = 0 And Not w Is Nothing Then Exit For
    WScript.Sleep 500
Next
If w Is Nothing Then
    WScript.Echo "Microsoft Word wurde nach dem Öffnen der Datei nicht gefunden."
    WScript.Quit 22
End If

Set d = Nothing
For i = 1 To 80
    Err.Clear
    For Each x In w.Documents
        If LCase(x.FullName) = LCase(docx) Then
            Set d = x
            Exit For
        End If
    Next
    If Not d Is Nothing Then Exit For
    WScript.Sleep 500
Next
If d Is Nothing Then
    WScript.Echo "Die geöffnete Word-Datei konnte in Word nicht eindeutig gefunden werden."
    WScript.Quit 23
End If

d.Activate
WScript.Sleep 500

Set pmkr = Nothing
For Each ad In w.COMAddIns
    desc = ""
    pid = ""
    Err.Clear
    desc = UCase(ad.Description)
    pid = UCase(ad.ProgId)
    If InStr(desc, "PDFMAKER") > 0 Or pid = "PDFMAKER.OFFICEADDIN" Then
        If Not ad.Connect Then
            ad.Connect = True
            WScript.Sleep 1200
        End If
        Err.Clear
        Set pmkr = ad.Object
        If Err.Number = 0 And Not pmkr Is Nothing Then Exit For
    End If
Next
If pmkr Is Nothing Then
    WScript.Echo "Acrobat PDFMaker Office COM Add-In wurde in Word nicht gefunden oder ist nicht aktiv."
    On Error Resume Next
    d.Close False
    WScript.Quit 24
End If

Set stng = Nothing
Err.Clear
pmkr.GetCurrentConversionSettings stng
If Err.Number <> 0 Or stng Is Nothing Then
    Err.Clear
    pmkr.GetDefaultConversionSettings stng
End If
If stng Is Nothing Then
    WScript.Echo "Acrobat PDFMaker-Konvertierungseinstellungen konnten nicht geladen werden."
    d.Close False
    WScript.Quit 25
End If

stng.OutputPDFFileName = pdf
stng.PromptForPDFFilename = False
stng.ShouldShowProgressDialog = False
stng.ViewPDFFile = False
stng.ConvertAllPages = True
Err.Clear
stng.AddLinks = True
stng.AddBookmarks = True
stng.AddTags = True
Err.Clear
pmkr.CreatePDFEx stng, 0
If Err.Number <> 0 Then
    WScript.Echo "Adobe PDFMaker konnte die Konvertierung nicht starten: " & Err.Description
    d.Close False
    WScript.Quit 26
End If

lastSize = -1
stable = 0
For i = 1 To 180
    If fso.FileExists(pdf) Then
        sz = fso.GetFile(pdf).Size
        If sz > 0 And sz = lastSize Then
            stable = stable + 1
        Else
            stable = 0
        End If
        lastSize = sz
        If stable >= 2 Then Exit For
    End If
    WScript.Sleep 500
Next
If Not fso.FileExists(pdf) Then
    WScript.Echo "Adobe PDFMaker hat keine PDF-Datei erzeugt."
    d.Close False
    WScript.Quit 27
End If
If fso.GetFile(pdf).Size <= 0 Then
    WScript.Echo "Adobe PDFMaker hat nur eine leere PDF-Datei erzeugt."
    d.Close False
    WScript.Quit 28
End If

On Error Resume Next
d.Close False
If w.Documents.Count = 0 Then w.Quit
WScript.Quit 0
'''
    tmp=None
    try:
        fd,tmp=tempfile.mkstemp(prefix='engbers_adobe_pdfmaker_',suffix='.vbs')
        os.close(fd)
        Path(tmp).write_text(script,encoding='utf-8-sig')
        cp=subprocess.run(
            ['cscript.exe','//nologo',tmp,str(docx_path),str(pdf_path)],
            capture_output=True,text=True,timeout=130,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)
        )
        if cp.returncode==0 and pdf_path.exists() and pdf_path.stat().st_size>0:
            return True,''
        detail=(cp.stdout or cp.stderr or '').strip()
        return False,(detail or f'Adobe PDFMaker Rückgabecode {cp.returncode}')
    except FileNotFoundError:
        return False,'Windows Script Host (cscript.exe) wurde nicht gefunden.'
    except subprocess.TimeoutExpired:
        return False,'Adobe PDFMaker hat nicht innerhalb von 130 Sekunden geantwortet.'
    except Exception as e:
        return False,str(e)
    finally:
        if tmp:
            try: Path(tmp).unlink()
            except Exception: pass
"""


def _patch_mod(mod):
    if MARK in mod:
        return mod
    start=mod.find('def _export_pdf_with_word(docx_path, pdf_path):')
    end=mod.find('\n\ndef open_wordforms(app):',start)
    if start<0 or end<0:
        raise RuntimeError('1.7.8: PDF-Exportfunktion wurde nicht gefunden.')
    return mod[:start]+NEW_EXPORT+mod[end:]


def main():
    if not APP.exists() or not MOD.exists():
        raise RuntimeError('1.7.8: app.py oder wordforms_v1700.py wurde nicht gefunden.')
    app=APP.read_text(encoding='utf-8')
    mod=MOD.read_text(encoding='utf-8')
    if f'APP_VERSION = "{NEW}"' in app and MARK in mod:
        return 0
    if f'APP_VERSION = "{OLD}"' not in app:
        raise RuntimeError('Update 1.7.8 erwartet Projektzentrale 1.7.7.')
    mod_new=_patch_mod(mod)
    app_new=app.replace(f'APP_VERSION = "{OLD}"',f'APP_VERSION = "{NEW}"',1).replace('Projektzentrale 1.7.7','Projektzentrale 1.7.8')
    if MARK not in mod_new:
        raise RuntimeError('1.7.8: PDFMaker-Marker fehlt.')
    chk1=APP.with_name('app.py.1708.check'); chk2=MOD.with_name('wordforms_v1700.py.1708.check')
    try:
        chk1.write_text(app_new,encoding='utf-8'); py_compile.compile(str(chk1),doraise=True)
        chk2.write_text(mod_new,encoding='utf-8'); py_compile.compile(str(chk2),doraise=True)
    finally:
        for p in (chk1,chk2):
            try:p.unlink()
            except Exception:pass
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for p in (APP,MOD): shutil.copy2(p,p.with_name(p.name+'.vor_1_7_8_'+stamp+'.bak'))
    t=APP.with_name('app.py.1708.tmp'); t.write_text(app_new,encoding='utf-8'); t.replace(APP)
    t=MOD.with_name('wordforms_v1700.py.1708.tmp'); t.write_text(mod_new,encoding='utf-8'); t.replace(MOD)
    APP.with_name('patch_1708_report.txt').write_text(
        'OK: Projektzentrale 1.7.8 installiert.\n'
        'PDF-Erzeugung verwendet jetzt Acrobat PDFMaker aus Microsoft Word.\n'
        'Die DOCX wird wie beim manuellen Öffnen über Windows gestartet; danach wird Adobe PDFMaker automatisiert.\n'
        'Word kann während der PDF-Erzeugung kurz sichtbar sein.\n',encoding='utf-8')
    return 0

if __name__=='__main__':
    try: raise SystemExit(main())
    except SystemExit: raise
    except Exception:
        try: APP.with_name('patch_1708_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception: pass
        raise
