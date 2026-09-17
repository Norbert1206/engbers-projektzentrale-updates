from pathlib import Path
import ast
import datetime
import py_compile
import re
import shutil
import traceback

BASE=Path(__file__).resolve().parent
APP=BASE/'app.py'
MOD=BASE/'wordforms_v1700.py'
OLD='1.7.17'
NEW='1.7.18'
MARK='PZ_WORD_DIRECT_PRINTTOFILE_V1718'

NEW_FUNC=r'''def _export_pdf_with_word(docx_path, pdf_path):
    # PZ_WORD_DIRECT_PRINTTOFILE_V1718
    # Kein Windows-Speicherdialog mehr: Word wird normal geoeffnet, das bereits
    # geoeffnete Dokument wird per COM gefunden und direkt mit PrintToFile=True
    # und OutputFileName=<voller PDF-Pfad> auf Microsoft Print to PDF ausgegeben.
    docx_path=Path(docx_path).resolve()
    pdf_path=Path(pdf_path).resolve()
    pdf_path.parent.mkdir(parents=True,exist_ok=True)
    if not docx_path.exists():
        return False,'Word-Datei wurde nicht gefunden.'
    try:
        if pdf_path.exists():
            pdf_path.unlink()
    except PermissionError:
        return False,'Die vorhandene PDF ist noch geoeffnet oder gesperrt. Bitte PDF schliessen und erneut ausfuellen.'
    except Exception as e:
        return False,'Vorhandene PDF konnte nicht entfernt werden: '+str(e)

    ps=r"""param(
 [Parameter(Mandatory=$true)][string]$DocxPath,
 [Parameter(Mandatory=$true)][string]$PdfPath
)
$ErrorActionPreference='Stop'
$DocxPath=[IO.Path]::GetFullPath($DocxPath)
$PdfPath=[IO.Path]::GetFullPath($PdfPath)

function Wait-Until([scriptblock]$Test,[int]$TimeoutMs=12000,[int]$SleepMs=250){
  $sw=[Diagnostics.Stopwatch]::StartNew()
  while($sw.ElapsedMilliseconds -lt $TimeoutMs){
    try { $r=& $Test } catch { $r=$null }
    if($r){ return $r }
    Start-Sleep -Milliseconds $SleepMs
  }
  return $null
}
function Set-DefaultPrinter([string]$name){
  $net=New-Object -ComObject WScript.Network
  $net.SetDefaultPrinter($name)
}
function Get-TargetWordDocument([string]$fullName){
  try { $word=[Runtime.InteropServices.Marshal]::GetActiveObject('Word.Application') } catch { return $null }
  try {
    for($i=1; $i -le $word.Documents.Count; $i++){
      $d=$word.Documents.Item($i)
      try {
        $fn=[IO.Path]::GetFullPath([string]$d.FullName)
        if($fn -ieq $fullName){ return @{Word=$word; Doc=$d} }
      } catch {}
    }
  } catch {}
  return $null
}

$printer='Microsoft Print to PDF'
$printers=@(Get-CimInstance Win32_Printer | Select-Object -ExpandProperty Name)
if($printers -notcontains $printer){
  throw 'Der Windows-Drucker "Microsoft Print to PDF" wurde nicht gefunden.'
}

$oldDefault=$null
try { $oldDefault=(Get-CimInstance Win32_Printer | Where-Object {$_.Default} | Select-Object -First 1).Name } catch {}
$word=$null
$doc=$null
$oldWordPrinter=$null
try {
  Set-DefaultPrinter $printer
  Start-Sleep -Milliseconds 500

  # Wichtig: normal ueber Windows/Word oeffnen. Dieser Weg funktioniert auf dem Zielrechner.
  Start-Process -FilePath $DocxPath | Out-Null
  $pair=Wait-Until { Get-TargetWordDocument $DocxPath } 12000 250
  if(-not $pair){ throw 'Das in Word geoeffnete Dokument konnte nicht per Word-COM gefunden werden.' }
  $word=$pair.Word
  $doc=$pair.Doc

  try { $oldWordPrinter=[string]$word.ActivePrinter } catch {}
  try { $word.ActivePrinter=$printer } catch {
    # Word kann den System-Standarddrucker erst nach kurzer Verzoegerung uebernehmen.
    Start-Sleep -Milliseconds 600
    try { $word.ActivePrinter=$printer } catch {
      throw ('Microsoft Print to PDF konnte in Word nicht als aktiver Drucker gesetzt werden. Aktiver Word-Drucker: '+[string]$word.ActivePrinter)
    }
  }

  # Word PrintOut hat einen eigenen dateibasierten Druckweg. Dadurch erscheint KEIN
  # "Druckausgabe speichern unter"-Dialog. Die Ausgabe geht direkt nach $PdfPath.
  $Background=$false
  $Append=$false
  $Range=0
  $OutputFileName=$PdfPath
  $From=[Type]::Missing
  $To=[Type]::Missing
  $Item=0
  $Copies=1
  $Pages=[Type]::Missing
  $PageType=[Type]::Missing
  $PrintToFile=$true
  $Collate=$true
  $ActivePrinterMacGX=[Type]::Missing
  $ManualDuplexPrint=$false
  $PrintZoomColumn=[Type]::Missing
  $PrintZoomRow=[Type]::Missing
  $PrintZoomPaperWidth=[Type]::Missing
  $PrintZoomPaperHeight=[Type]::Missing

  $doc.PrintOut(
    [ref]$Background,[ref]$Append,[ref]$Range,[ref]$OutputFileName,
    [ref]$From,[ref]$To,[ref]$Item,[ref]$Copies,[ref]$Pages,[ref]$PageType,
    [ref]$PrintToFile,[ref]$Collate,[ref]$ActivePrinterMacGX,[ref]$ManualDuplexPrint,
    [ref]$PrintZoomColumn,[ref]$PrintZoomRow,[ref]$PrintZoomPaperWidth,[ref]$PrintZoomPaperHeight)

  $ok=Wait-Until {
    if(Test-Path -LiteralPath $PdfPath){
      try { if((Get-Item -LiteralPath $PdfPath).Length -gt 100){ return $true } } catch {}
    }
    return $false
  } 20000 300
  if(-not $ok){ throw ('Word hat beim direkten PrintToFile keine PDF erzeugt: '+$PdfPath) }

  # Nur das fuer den Druck geoeffnete Dokument schliessen; andere Word-Dokumente bleiben offen.
  try { $doc.Close($false) } catch {}
  exit 0
}
finally {
  if($word -and $oldWordPrinter){ try { $word.ActivePrinter=$oldWordPrinter } catch {} }
  if($oldDefault){ try { Set-DefaultPrinter $oldDefault } catch {} }
}
"""
    tmp=None
    try:
        fd,tmp=tempfile.mkstemp(prefix='engbers_word_printtofile_',suffix='.ps1')
        os.close(fd)
        Path(tmp).write_text(ps,encoding='utf-8-sig')
        cp=subprocess.run(
            ['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',tmp,
             '-DocxPath',str(docx_path),'-PdfPath',str(pdf_path)],
            capture_output=True,text=True,timeout=40,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)
        )
        if cp.returncode==0 and pdf_path.exists() and pdf_path.stat().st_size>100:
            return True,''
        detail=(cp.stderr or cp.stdout or '').strip()
        return False,(detail or f'Word-PrintToFile Rueckgabecode {cp.returncode}')
    except FileNotFoundError:
        return False,'Windows PowerShell wurde nicht gefunden.'
    except subprocess.TimeoutExpired:
        return False,'Word-PrintToFile hat nicht innerhalb von 40 Sekunden geantwortet.'
    except Exception as e:
        return False,'Word-PrintToFile konnte nicht ausgefuehrt werden: '+str(e)
    finally:
        if tmp:
            try:Path(tmp).unlink()
            except Exception:pass
'''


def _version(text):
    m=re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']',text)
    return m.group(1).strip() if m else ''


def _set_version(text):
    out,n=re.subn(r'(APP_VERSION\s*=\s*)["\'][^"\']+["\']',lambda m:m.group(1)+'"'+NEW+'"',text,count=1)
    if n!=1: raise RuntimeError('1.7.18: APP_VERSION wurde in app.py nicht gefunden.')
    return out.replace('Projektzentrale 1.7.17','Projektzentrale 1.7.18')


def _replace_function(source,name,new_block):
    tree=ast.parse(source)
    lines=source.splitlines(keepends=True)
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name==name:
            start=sum(len(x) for x in lines[:node.lineno-1])
            end=sum(len(x) for x in lines[:node.end_lineno])
            return source[:start]+new_block.rstrip()+'\n\n'+source[end:]
    raise RuntimeError(f'1.7.18: Funktion {name} wurde nicht gefunden.')


def main():
    if not APP.exists() or not MOD.exists(): raise RuntimeError('1.7.18: app.py oder wordforms_v1700.py wurde nicht gefunden.')
    app=APP.read_text(encoding='utf-8'); mod=MOD.read_text(encoding='utf-8'); cur=_version(app)
    if cur==NEW and MARK in mod: return 0
    if cur!=OLD: raise RuntimeError(f'Update 1.7.18 erwartet Projektzentrale {OLD}; gefunden: {cur or "unbekannt"}.')
    app_new=_set_version(app); mod_new=_replace_function(mod,'_export_pdf_with_word',NEW_FUNC)
    if MARK not in mod_new: raise RuntimeError('1.7.18: PrintToFile-Marker fehlt nach dem Patch.')
    active_start=mod_new.find(MARK); active_end=mod_new.find('\ndef ',active_start); active=mod_new[active_start:active_end if active_end>0 else len(mod_new)]
    for required in ('GetActiveObject','Microsoft Print to PDF','OutputFileName=$PdfPath','PrintToFile=$true','$doc.PrintOut'):
        if required not in active: raise RuntimeError('1.7.18: erwarteter direkter PrintToFile-Baustein fehlt: '+required)
    for forbidden in ('Druckausgabe speichern unter','SendWait(', 'FocusedElement','FileNameControlHost'):
        if forbidden in active: raise RuntimeError('1.7.18: alter Speicherdialog-Weg ist noch aktiv: '+forbidden)
    chk1=APP.with_name('app.py.1718.check'); chk2=MOD.with_name('wordforms_v1700.py.1718.check')
    try:
        chk1.write_text(app_new,encoding='utf-8'); py_compile.compile(str(chk1),doraise=True)
        chk2.write_text(mod_new,encoding='utf-8'); py_compile.compile(str(chk2),doraise=True)
    finally:
        for p in (chk1,chk2):
            try:p.unlink()
            except Exception:pass
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for p in (APP,MOD): shutil.copy2(p,p.with_name(p.name+'.vor_1_7_18_'+stamp+'.bak'))
    t=APP.with_name('app.py.1718.tmp'); t.write_text(app_new,encoding='utf-8'); t.replace(APP)
    t=MOD.with_name('wordforms_v1700.py.1718.tmp'); t.write_text(mod_new,encoding='utf-8'); t.replace(MOD)
    APP.with_name('patch_1718_report.txt').write_text('OK: Projektzentrale 1.7.18 installiert.\nPDF-Erzeugung: Word PrintOut mit PrintToFile und festem OutputFileName; kein Windows-Speicherdialog mehr.\n',encoding='utf-8')
    return 0

if __name__=='__main__':
    try: raise SystemExit(main())
    except SystemExit: raise
    except Exception:
        try: APP.with_name('patch_1718_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception: pass
        raise
