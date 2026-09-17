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
OLD='1.7.16'
NEW='1.7.17'
MARK='PZ_PDF_FOCUSED_FILENAME_V1717'

NEW_FUNC=r'''def _export_pdf_with_word(docx_path, pdf_path):
    # PZ_PDF_FOCUSED_FILENAME_V1717
    # Der PDF-Druck bleibt unveraendert. Im Windows-Speichern-Dialog wird nur
    # Alt+N verwendet; danach wird das bereits fokussierte Dateiname-Feld direkt
    # per UIAutomation ValuePattern mit dem VOLLSTAENDIGEN absoluten PDF-Pfad gesetzt.
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
try {
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class EngbersSaveWin32_1717 {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);
}
"@ -ErrorAction SilentlyContinue
} catch {}

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
function Set-DefaultPrinter([string]$name){
  $net=New-Object -ComObject WScript.Network
  $net.SetDefaultPrinter($name)
}
function Find-SaveDialog {
  $root=Root
  $wins=$root.FindAll([Windows.Automation.TreeScope]::Children,[Windows.Automation.Condition]::TrueCondition)
  foreach($w in $wins){
    try {
      $n=[string]$w.Current.Name
      if($n -match 'Druckausgabe speichern unter|Speichern unter|Save Print Output As|Save As'){
        return $w
      }
    } catch {}
  }
  return $null
}
function Activate-Dialog($w){
  if(-not $w){ return $false }
  try {
    $h=[IntPtr]([int64]$w.Current.NativeWindowHandle)
    if($h -ne [IntPtr]::Zero){
      try { [EngbersSaveWin32_1717]::ShowWindowAsync($h,9) | Out-Null } catch {}
      try { [EngbersSaveWin32_1717]::SetForegroundWindow($h) | Out-Null } catch {}
      try { $w.SetFocus() } catch {}
      Start-Sleep -Milliseconds 300
      return $true
    }
  } catch {}
  try { $w.SetFocus(); Start-Sleep -Milliseconds 300; return $true } catch {}
  return $false
}
function Set-FocusedValue([string]$value){
  $el=$null
  try { $el=[Windows.Automation.AutomationElement]::FocusedElement } catch {}
  if(-not $el){ return $false }
  try {
    $vp=$el.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern)
    $vp.SetValue($value)
    Start-Sleep -Milliseconds 150
    try {
      if(([string]$vp.Current.Value) -eq $value){ return $true }
    } catch { return $true }
  } catch {}

  # letzter Fallback: auf genau dem bereits fokussierten Feld einfuegen
  try {
    [System.Windows.Forms.Clipboard]::SetText($value)
    [System.Windows.Forms.SendKeys]::SendWait('^a')
    Start-Sleep -Milliseconds 80
    [System.Windows.Forms.SendKeys]::SendWait('^v')
    Start-Sleep -Milliseconds 180
    return $true
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

  $dlg=Wait-Until { Find-SaveDialog } 18000 250
  if(-not $dlg){ throw ('Der Speichern-Dialog des PDF-Druckers "'+$printer+'" wurde nicht gefunden.') }
  if(-not (Activate-Dialog $dlg)){ throw 'Der Windows-Speichern-Dialog konnte nicht aktiviert werden.' }

  # Das funktioniert auf dem Zielrechner bereits: Alt+N fokussiert sichtbar "Dateiname".
  [System.Windows.Forms.SendKeys]::SendWait('%n')
  Start-Sleep -Milliseconds 250

  # Vollstaendigen Pfad direkt ins fokussierte Dateiname-Feld schreiben.
  # Dadurch ist der im Dialog angezeigte alte Ordner voellig egal.
  if(-not (Set-FocusedValue $PdfPath)){
    throw ('Der vollstaendige PDF-Zielpfad konnte nicht in das fokussierte Dateiname-Feld geschrieben werden: '+$PdfPath)
  }
  Start-Sleep -Milliseconds 250
  [System.Windows.Forms.SendKeys]::SendWait('{ENTER}')

  $ok=Wait-Until {
    if(Test-Path -LiteralPath $PdfPath){
      try { if((Get-Item -LiteralPath $PdfPath).Length -gt 100){ return $true } } catch {}
    }
    return $false
  } 25000 300
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
            capture_output=True,text=True,timeout=45,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)
        )
        if cp.returncode==0 and pdf_path.exists() and pdf_path.stat().st_size>100:
            return True,''
        detail=(cp.stderr or cp.stdout or '').strip()
        return False,(detail or f'PDF-Druck Rueckgabecode {cp.returncode}')
    except FileNotFoundError:
        return False,'Windows PowerShell wurde nicht gefunden.'
    except subprocess.TimeoutExpired:
        return False,'Der PDF-Druck hat nicht innerhalb von 45 Sekunden geantwortet.'
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
    if n!=1: raise RuntimeError('1.7.17: APP_VERSION wurde in app.py nicht gefunden.')
    return out.replace('Projektzentrale 1.7.16','Projektzentrale 1.7.17')


def _replace_function(source,name,new_block):
    tree=ast.parse(source)
    lines=source.splitlines(keepends=True)
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name==name:
            start=sum(len(x) for x in lines[:node.lineno-1])
            end=sum(len(x) for x in lines[:node.end_lineno])
            return source[:start]+new_block.rstrip()+'\n\n'+source[end:]
    raise RuntimeError(f'1.7.17: Funktion {name} wurde nicht gefunden.')


def main():
    if not APP.exists() or not MOD.exists(): raise RuntimeError('1.7.17: app.py oder wordforms_v1700.py wurde nicht gefunden.')
    app=APP.read_text(encoding='utf-8'); mod=MOD.read_text(encoding='utf-8'); cur=_version(app)
    if cur==NEW and MARK in mod: return 0
    if cur!=OLD: raise RuntimeError(f'Update 1.7.17 erwartet Projektzentrale {OLD}; gefunden: {cur or "unbekannt"}.')
    app_new=_set_version(app); mod_new=_replace_function(mod,'_export_pdf_with_word',NEW_FUNC)
    if MARK not in mod_new: raise RuntimeError('1.7.17: Focused-Dateiname-Marker fehlt nach dem Patch.')
    active_start=mod_new.find(MARK); active_end=mod_new.find('\ndef ',active_start); active=mod_new[active_start:active_end if active_end>0 else len(mod_new)]
    for required in ('AutomationElement]::FocusedElement','ValuePattern','Set-FocusedValue $PdfPath',"SendWait('%n')",'Microsoft Print to PDF'):
        if required not in active: raise RuntimeError('1.7.17: erwarteter Focused-Dateiname-Baustein fehlt: '+required)
    if "SendWait('^l')" in active or 'Paste-Text $PdfDir' in active:
        raise RuntimeError('1.7.17: alter separater Ordner-Schritt ist noch aktiv.')
    chk1=APP.with_name('app.py.1717.check'); chk2=MOD.with_name('wordforms_v1700.py.1717.check')
    try:
        chk1.write_text(app_new,encoding='utf-8'); py_compile.compile(str(chk1),doraise=True)
        chk2.write_text(mod_new,encoding='utf-8'); py_compile.compile(str(chk2),doraise=True)
    finally:
        for p in (chk1,chk2):
            try:p.unlink()
            except Exception:pass
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for p in (APP,MOD): shutil.copy2(p,p.with_name(p.name+'.vor_1_7_17_'+stamp+'.bak'))
    t=APP.with_name('app.py.1717.tmp'); t.write_text(app_new,encoding='utf-8'); t.replace(APP)
    t=MOD.with_name('wordforms_v1700.py.1717.tmp'); t.write_text(mod_new,encoding='utf-8'); t.replace(MOD)
    APP.with_name('patch_1717_report.txt').write_text('OK: Projektzentrale 1.7.17 installiert.\nPDF-Speicherdialog: voller Zielpfad wird direkt in das bereits fokussierte Dateiname-Feld geschrieben.\n',encoding='utf-8')
    return 0

if __name__=='__main__':
    try: raise SystemExit(main())
    except SystemExit: raise
    except Exception:
        try: APP.with_name('patch_1717_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception: pass
        raise
