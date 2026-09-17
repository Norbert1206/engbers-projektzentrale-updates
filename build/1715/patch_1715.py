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
OLD='1.7.14'
NEW='1.7.15'
MARK='PZ_PDF_SAVE_DIALOG_V1715'

NEW_FUNC=r'''def _export_pdf_with_word(docx_path, pdf_path):
    # PZ_PDF_SAVE_DIALOG_V1715
    # PDF-Drucker wie in 1.7.14; verbessert ist ausschliesslich der Windows-Speichern-Dialog.
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
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms

function Wait-Until([scriptblock]$Test,[int]$TimeoutMs=12000,[int]$SleepMs=200){
  $sw=[Diagnostics.Stopwatch]::StartNew()
  while($sw.ElapsedMilliseconds -lt $TimeoutMs){
    try { $r=& $Test } catch { $r=$null }
    if($r){ return $r }
    Start-Sleep -Milliseconds $SleepMs
  }
  return $null
}
function Root(){ [Windows.Automation.AutomationElement]::RootElement }
function Find-ByName($root,[string[]]$names,$ctype=$null){
  if(-not $root){ return $null }
  foreach($nm in $names){
    $c1=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::NameProperty,$nm)
    if($ctype){
      $c2=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty,$ctype)
      $cond=New-Object Windows.Automation.AndCondition($c1,$c2)
    } else { $cond=$c1 }
    try { $el=$root.FindFirst([Windows.Automation.TreeScope]::Descendants,$cond) } catch { $el=$null }
    if($el){ return $el }
  }
  return $null
}
function Invoke-El($el){
  if(-not $el){ return $false }
  try { $p=$el.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern); $p.Invoke(); return $true } catch {}
  try { $p=$el.GetCurrentPattern([Windows.Automation.LegacyIAccessiblePattern]::Pattern); $p.DoDefaultAction(); return $true } catch {}
  return $false
}
function Set-DefaultPrinter([string]$name){
  $net=New-Object -ComObject WScript.Network
  $net.SetDefaultPrinter($name)
}
function Find-FileNameEdit($w){
  if(-not $w){ return $null }

  # Windows 10/11 Common Item Dialog: Dateiname-Bereich heisst oft FileNameControlHost.
  foreach($id in @('FileNameControlHost','1001','1148')){
    try {
      $cond=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::AutomationIdProperty,$id)
      $host=$w.FindFirst([Windows.Automation.TreeScope]::Descendants,$cond)
      if($host){
        if($host.Current.ControlType -eq [Windows.Automation.ControlType]::Edit){ return $host }
        $ec=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Edit)
        $e=$host.FindFirst([Windows.Automation.TreeScope]::Descendants,$ec)
        if($e){ return $e }
      }
    } catch {}
  }

  # Fallback fuer unterschiedliche Windows-Builds: das Dateiname-Feld ist im Speichern-Dialog
  # das unterste sichtbare Edit-Control. Suchfeld/Adressleiste liegen deutlich weiter oben.
  try {
    $ec=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Edit)
    $edits=$w.FindAll([Windows.Automation.TreeScope]::Descendants,$ec)
    $best=$null; $bestTop=-1
    foreach($e in $edits){
      try {
        $r=$e.Current.BoundingRectangle
        $n=[string]$e.Current.Name
        $aid=[string]$e.Current.AutomationId
        if($r.Width -gt 120 -and $r.Height -gt 10 -and $r.Top -gt $bestTop){
          if($n -notmatch 'Suchen|Search' -and $aid -notmatch 'Search'){
            $best=$e; $bestTop=$r.Top
          }
        }
      } catch {}
    }
    if($best){ return $best }
  } catch {}
  return $null
}
function Find-SaveDialog {
  $root=Root
  $wins=$root.FindAll([Windows.Automation.TreeScope]::Children,[Windows.Automation.Condition]::TrueCondition)
  foreach($w in $wins){
    try {
      $n=[string]$w.Current.Name
      if($n -match 'Druckausgabe speichern unter|Speichern unter|Save Print Output As|Save As|PDF'){
        $edit=Find-FileNameEdit $w
        $save=Find-ByName $w @('Speichern','Save') [Windows.Automation.ControlType]::Button
        if($edit -and $save){ return @{Window=$w; Edit=$edit; Save=$save} }
      }
    } catch {}
  }
  return $null
}
function Set-FileName($edit,[string]$value){
  if(-not $edit){ return $false }
  try {
    $vp=$edit.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern)
    $vp.SetValue($value)
    Start-Sleep -Milliseconds 150
    $now=[string]$vp.Current.Value
    if($now -eq $value){ return $true }
  } catch {}

  # Tastatur-Fallback nur auf das bereits eindeutig gefundene Dateiname-Feld.
  try {
    $edit.SetFocus()
    Start-Sleep -Milliseconds 120
    [System.Windows.Forms.SendKeys]::SendWait('^a')
    Start-Sleep -Milliseconds 80
    [System.Windows.Forms.Clipboard]::SetText($value)
    [System.Windows.Forms.SendKeys]::SendWait('^v')
    Start-Sleep -Milliseconds 180
    try {
      $vp=$edit.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern)
      if(([string]$vp.Current.Value) -eq $value){ return $true }
    } catch { return $true }
  } catch {}
  return $false
}

$DocxPath=[IO.Path]::GetFullPath($DocxPath)
$PdfPath=[IO.Path]::GetFullPath($PdfPath)
$oldDefault=$null
try { $oldDefault=(Get-CimInstance Win32_Printer | Where-Object {$_.Default} | Select-Object -First 1).Name } catch {}

try {
  $printers=@(Get-CimInstance Win32_Printer | Select-Object -ExpandProperty Name)
  $printer=$null
  if($printers -contains 'Microsoft Print to PDF'){
    $printer='Microsoft Print to PDF'
  } elseif($printers -contains 'Adobe PDF'){
    $printer='Adobe PDF'
  } else {
    $printer=$printers | Where-Object { $_ -like '*Adobe PDF*' -or $_ -like '*Print to PDF*' } | Select-Object -First 1
  }
  if(-not $printer){ throw 'Es wurde weder Microsoft Print to PDF noch Adobe PDF gefunden.' }

  Set-DefaultPrinter $printer
  Start-Sleep -Milliseconds 700
  Start-Process -FilePath $DocxPath -Verb Print | Out-Null

  $info=Wait-Until { Find-SaveDialog } 18000 250
  if(-not $info){ throw ('Der Speichern-Dialog des PDF-Druckers "'+$printer+'" wurde nicht gefunden.') }

  if(-not (Set-FileName $info.Edit $PdfPath)){
    throw ('Der Zielpfad konnte nicht in das Feld "Dateiname" eingetragen werden: '+$PdfPath)
  }
  Start-Sleep -Milliseconds 250

  if(-not (Invoke-El $info.Save)){ throw 'Der Speichern-Button des PDF-Druckers konnte nicht ausgeloest werden.' }

  $ok=Wait-Until {
    if(Test-Path -LiteralPath $PdfPath){
      try { if((Get-Item -LiteralPath $PdfPath).Length -gt 100){ return $true } } catch {}
    }
    return $false
  } 30000 300
  if(-not $ok){ throw ('Der PDF-Drucker hat die erwartete Datei nicht erzeugt: '+$PdfPath) }
  exit 0
}
finally {
  if($oldDefault){ try { Set-DefaultPrinter $oldDefault } catch {} }
}
"""
    tmp=None
    try:
        fd,tmp=tempfile.mkstemp(prefix='engbers_pdf_print_',suffix='.ps1')
        os.close(fd)
        Path(tmp).write_text(ps,encoding='utf-8-sig')
        cp=subprocess.run(
            ['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',tmp,
             '-DocxPath',str(docx_path),'-PdfPath',str(pdf_path)],
            capture_output=True,text=True,timeout=55,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)
        )
        if cp.returncode==0 and pdf_path.exists() and pdf_path.stat().st_size>100:
            return True,''
        detail=(cp.stderr or cp.stdout or '').strip()
        return False,(detail or f'PDF-Druck Rueckgabecode {cp.returncode}')
    except FileNotFoundError:
        return False,'Windows PowerShell wurde nicht gefunden.'
    except subprocess.TimeoutExpired:
        return False,'Der PDF-Druck hat nicht innerhalb von 55 Sekunden geantwortet.'
    except Exception as e:
        return False,'PDF-Druck konnte nicht ausgefuehrt werden: '+str(e)
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
    if n!=1: raise RuntimeError('1.7.15: APP_VERSION wurde in app.py nicht gefunden.')
    return out.replace('Projektzentrale 1.7.14','Projektzentrale 1.7.15')


def _replace_function(source,name,new_block):
    tree=ast.parse(source)
    lines=source.splitlines(keepends=True)
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name==name:
            start=sum(len(x) for x in lines[:node.lineno-1])
            end=sum(len(x) for x in lines[:node.end_lineno])
            return source[:start]+new_block.rstrip()+'\n\n'+source[end:]
    raise RuntimeError(f'1.7.15: Funktion {name} wurde nicht gefunden.')


def main():
    if not APP.exists() or not MOD.exists(): raise RuntimeError('1.7.15: app.py oder wordforms_v1700.py wurde nicht gefunden.')
    app=APP.read_text(encoding='utf-8'); mod=MOD.read_text(encoding='utf-8'); cur=_version(app)
    if cur==NEW and MARK in mod: return 0
    if cur!=OLD: raise RuntimeError(f'Update 1.7.15 erwartet Projektzentrale {OLD}; gefunden: {cur or "unbekannt"}.')
    app_new=_set_version(app); mod_new=_replace_function(mod,'_export_pdf_with_word',NEW_FUNC)
    if MARK not in mod_new: raise RuntimeError('1.7.15: Speicherdialog-Marker fehlt nach dem Patch.')
    active_start=mod_new.find(MARK); active_end=mod_new.find('\ndef ',active_start); active=mod_new[active_start:active_end if active_end>0 else len(mod_new)]
    for required in ('FileNameControlHost','Find-FileNameEdit','Set-FileName','Druckausgabe speichern unter','Microsoft Print to PDF'):
        if required not in active: raise RuntimeError('1.7.15: erwarteter Speicherdialog-Baustein fehlt: '+required)
    chk1=APP.with_name('app.py.1715.check'); chk2=MOD.with_name('wordforms_v1700.py.1715.check')
    try:
        chk1.write_text(app_new,encoding='utf-8'); py_compile.compile(str(chk1),doraise=True)
        chk2.write_text(mod_new,encoding='utf-8'); py_compile.compile(str(chk2),doraise=True)
    finally:
        for p in (chk1,chk2):
            try:p.unlink()
            except Exception:pass
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for p in (APP,MOD): shutil.copy2(p,p.with_name(p.name+'.vor_1_7_15_'+stamp+'.bak'))
    t=APP.with_name('app.py.1715.tmp'); t.write_text(app_new,encoding='utf-8'); t.replace(APP)
    t=MOD.with_name('wordforms_v1700.py.1715.tmp'); t.write_text(mod_new,encoding='utf-8'); t.replace(MOD)
    APP.with_name('patch_1715_report.txt').write_text('OK: Projektzentrale 1.7.15 installiert.\nPDF-Druck: Windows-Dateiname-Feld wird gezielt erkannt und der vollstaendige Zielpfad vor Speichern verifiziert.\n',encoding='utf-8')
    return 0

if __name__=='__main__':
    try: raise SystemExit(main())
    except SystemExit: raise
    except Exception:
        try: APP.with_name('patch_1715_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception: pass
        raise
