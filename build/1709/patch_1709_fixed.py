from pathlib import Path
import datetime
import py_compile
import shutil
import traceback

BASE=Path(__file__).resolve().parent
APP=BASE/'app.py'
MOD=BASE/'wordforms_v1700.py'
OLD='1.7.8'; NEW='1.7.9'
MARK='PZ_ADOBE_UI_AUTOMATION_V1709'

NEW_EXPORT=r"""def _export_pdf_with_word(docx_path, pdf_path):
    # PZ_ADOBE_UI_AUTOMATION_V1709
    # Bildet den bewaehrten manuellen Ablauf nach:
    # Word sichtbar oeffnen -> Datei -> Als Adobe PDF speichern -> Speichern.
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

    ps=r'''param(
 [Parameter(Mandatory=$true)][string]$DocxPath,
 [Parameter(Mandatory=$true)][string]$PdfPath
)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms

function Wait-Until([scriptblock]$Test,[int]$TimeoutMs=15000,[int]$SleepMs=250){
  $sw=[Diagnostics.Stopwatch]::StartNew()
  while($sw.ElapsedMilliseconds -lt $TimeoutMs){
    $r=& $Test
    if($r){ return $r }
    Start-Sleep -Milliseconds $SleepMs
  }
  return $null
}
function Get-Root(){ [Windows.Automation.AutomationElement]::RootElement }
function Find-ByName($root,[string[]]$names,$ctype=$null){
  if(-not $root){ return $null }
  foreach($nm in $names){
    $c1=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::NameProperty,$nm)
    if($ctype){
      $c2=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty,$ctype)
      $cond=New-Object Windows.Automation.AndCondition($c1,$c2)
    } else { $cond=$c1 }
    $el=$root.FindFirst([Windows.Automation.TreeScope]::Descendants,$cond)
    if($el){ return $el }
  }
  return $null
}
function Invoke-El($el){
  if(-not $el){ return $false }
  try {
    $p=$el.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern)
    $p.Invoke(); return $true
  } catch {}
  try { $el.SetFocus(); [System.Windows.Forms.SendKeys]::SendWait('{ENTER}'); return $true } catch {}
  return $false
}

Start-Process -FilePath $DocxPath
$wordProc=Wait-Until {
  Get-Process WINWORD -ErrorAction SilentlyContinue | Sort-Object StartTime -Descending | Select-Object -First 1
} 20000
if(-not $wordProc){ throw 'Microsoft Word wurde nach dem Oeffnen der Datei nicht gefunden.' }
$wordProc.WaitForInputIdle() | Out-Null
Start-Sleep -Milliseconds 900
$wordProc.Refresh()
$hwnd=$wordProc.MainWindowHandle
if($hwnd -eq 0){
  $wordProc=Wait-Until {
    Get-Process WINWORD -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
  } 10000
  if(-not $wordProc){ throw 'Word-Fenster wurde nicht gefunden.' }
  $hwnd=$wordProc.MainWindowHandle
}
$wordWin=[Windows.Automation.AutomationElement]::FromHandle([IntPtr]$hwnd)
try { $wordWin.SetFocus() } catch {}
Start-Sleep -Milliseconds 400

[System.Windows.Forms.SendKeys]::SendWait('%f')
Start-Sleep -Milliseconds 900

$wordWin=[Windows.Automation.AutomationElement]::FromHandle([IntPtr]$hwnd)
$adobe=Wait-Until {
  Find-ByName $wordWin @('Als Adobe PDF speichern','Save as Adobe PDF')
} 12000
if(-not $adobe){ throw 'Der Word-Befehl "Als Adobe PDF speichern" wurde nicht gefunden.' }
if(-not (Invoke-El $adobe)){ throw 'Der Word-Befehl "Als Adobe PDF speichern" konnte nicht ausgefuehrt werden.' }

$dlg=Wait-Until {
  $root=Get-Root
  $all=$root.FindAll([Windows.Automation.TreeScope]::Children,[Windows.Automation.Condition]::TrueCondition)
  foreach($w in $all){
    try {
      $n=$w.Current.Name
      if($n -match 'Speichern|Save|Adobe PDF'){
        $edit=$w.FindFirst([Windows.Automation.TreeScope]::Descendants,
          (New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Edit)))
        if($edit){ return $w }
      }
    } catch {}
  }
  return $null
} 20000
if(-not $dlg){ throw 'Der Adobe-Speichern-Dialog wurde nicht gefunden.' }

$edit=$null
try {
  $cond=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::AutomationIdProperty,'1001')
  $edit=$dlg.FindFirst([Windows.Automation.TreeScope]::Descendants,$cond)
} catch {}
if(-not $edit){
  $edits=$dlg.FindAll([Windows.Automation.TreeScope]::Descendants,
    (New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Edit)))
  if($edits.Count -gt 0){ $edit=$edits.Item($edits.Count-1) }
}
if(-not $edit){ throw 'Das Dateiname-Feld im Adobe-Speichern-Dialog wurde nicht gefunden.' }
try {
  $vp=$edit.GetCurrentPattern([Windows.Automation.ValuePattern]::Pattern)
  $vp.SetValue($PdfPath)
} catch {
  $edit.SetFocus(); [System.Windows.Forms.SendKeys]::SendWait('^a'); [System.Windows.Forms.SendKeys]::SendWait($PdfPath)
}
Start-Sleep -Milliseconds 300

$save=Find-ByName $dlg @('Speichern','Save') [Windows.Automation.ControlType]::Button
if(-not $save){ throw 'Der Speichern-Button wurde nicht gefunden.' }
if(-not (Invoke-El $save)){ throw 'Speichern konnte nicht ausgeloest werden.' }

$ok=Wait-Until {
  if(Test-Path -LiteralPath $PdfPath){
    try { if((Get-Item -LiteralPath $PdfPath).Length -gt 100){ return $true } } catch {}
  }
  return $false
} 60000 500
if(-not $ok){ throw 'Adobe PDFMaker hat keine fertige PDF-Datei erzeugt.' }
exit 0
'''
    tmp=None
    try:
        fd,tmp=tempfile.mkstemp(prefix='engbers_adobe_ui_',suffix='.ps1')
        os.close(fd)
        Path(tmp).write_text(ps,encoding='utf-8-sig')
        cp=subprocess.run(
            ['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',tmp,
             '-DocxPath',str(docx_path),'-PdfPath',str(pdf_path)],
            capture_output=True,text=True,timeout=100,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)
        )
        if cp.returncode==0 and pdf_path.exists() and pdf_path.stat().st_size>0:
            return True,''
        detail=(cp.stderr or cp.stdout or '').strip()
        return False,(detail or f'Adobe-UI-Automatik Rueckgabecode {cp.returncode}')
    except FileNotFoundError:
        return False,'Windows PowerShell wurde nicht gefunden.'
    except subprocess.TimeoutExpired:
        return False,'Die Adobe-PDF-Erzeugung hat nicht innerhalb von 100 Sekunden geantwortet.'
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
        raise RuntimeError('1.7.9: PDF-Exportfunktion wurde nicht gefunden.')
    return mod[:start]+NEW_EXPORT+mod[end:]


def main():
    if not APP.exists() or not MOD.exists():
        raise RuntimeError('1.7.9: app.py oder wordforms_v1700.py wurde nicht gefunden.')
    app=APP.read_text(encoding='utf-8')
    mod=MOD.read_text(encoding='utf-8')
    if f'APP_VERSION = "{NEW}"' in app and MARK in mod:
        return 0
    if f'APP_VERSION = "{OLD}"' not in app:
        raise RuntimeError('Update 1.7.9 erwartet Projektzentrale 1.7.8.')
    mod_new=_patch_mod(mod)
    app_new=app.replace(f'APP_VERSION = "{OLD}"',f'APP_VERSION = "{NEW}"',1).replace('Projektzentrale 1.7.8','Projektzentrale 1.7.9')
    if MARK not in mod_new:
        raise RuntimeError('1.7.9: UI-Automationsmarker fehlt.')
    chk1=APP.with_name('app.py.1709.check'); chk2=MOD.with_name('wordforms_v1700.py.1709.check')
    try:
        chk1.write_text(app_new,encoding='utf-8'); py_compile.compile(str(chk1),doraise=True)
        chk2.write_text(mod_new,encoding='utf-8'); py_compile.compile(str(chk2),doraise=True)
    finally:
        for p in (chk1,chk2):
            try:p.unlink()
            except Exception:pass
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for p in (APP,MOD): shutil.copy2(p,p.with_name(p.name+'.vor_1_7_9_'+stamp+'.bak'))
    t=APP.with_name('app.py.1709.tmp'); t.write_text(app_new,encoding='utf-8'); t.replace(APP)
    t=MOD.with_name('wordforms_v1700.py.1709.tmp'); t.write_text(mod_new,encoding='utf-8'); t.replace(MOD)
    APP.with_name('patch_1709_report.txt').write_text(
        'OK: Projektzentrale 1.7.9 installiert.\n'
        'PDF-Erzeugung klickt den sichtbaren Word-Befehl Als Adobe PDF speichern per Windows UI Automation.\n'
        'Keine direkte PDFMaker-COM-Schnittstelle mehr.\n',encoding='utf-8')
    return 0

if __name__=='__main__':
    try: raise SystemExit(main())
    except SystemExit: raise
    except Exception:
        try: APP.with_name('patch_1709_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception: pass
        raise
