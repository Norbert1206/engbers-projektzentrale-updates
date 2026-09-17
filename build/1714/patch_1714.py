from pathlib import Path
import datetime
import py_compile
import re
import shutil
import traceback

BASE = Path(__file__).resolve().parent
APP = BASE / 'app.py'
MOD = BASE / 'wordforms_v1700.py'
OLD = '1.7.13'
NEW = '1.7.14'
OLD_MARK = '# PZ_ADOBE_DIRECT_BACKSTAGE_V1713'
NEW_MARK = '# PZ_ADOBE_BACKSTAGE_KEYS_CLICK_V1714'
DIALOG_MARK = '$dlg=Wait-Until {'

NEW_BLOCK = r'''# PZ_ADOBE_BACKSTAGE_KEYS_CLICK_V1714
# Backstage robust oeffnen: 1) echtes Alt+F, 2) UIAutomation, 3) physischer Klick auf Datei.
# Nach JEDEM Versuch wird geprueft, ob "Als Adobe PDF speichern" wirklich sichtbar ist.
try {
  Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Threading;
public static class EngbersWin32_1714 {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo);
  public static void AltF(){
    keybd_event(0x12,0,0,UIntPtr.Zero); Thread.Sleep(70);
    keybd_event(0x46,0,0,UIntPtr.Zero); Thread.Sleep(70);
    keybd_event(0x46,0,2,UIntPtr.Zero); Thread.Sleep(40);
    keybd_event(0x12,0,2,UIntPtr.Zero);
  }
  public static void Click(int x,int y){
    SetCursorPos(x,y); Thread.Sleep(80);
    mouse_event(0x0002,0,0,0,UIntPtr.Zero); Thread.Sleep(60);
    mouse_event(0x0004,0,0,0,UIntPtr.Zero);
  }
}
"@ -ErrorAction SilentlyContinue
} catch {}

$wordProc.Refresh()
$hwnd=$wordProc.MainWindowHandle
if($hwnd -eq 0){
  $wordProc=Wait-Until {
    Get-Process WINWORD -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
  } 8000
  if(-not $wordProc){ throw 'Word-Fenster wurde nicht gefunden.' }
  $hwnd=$wordProc.MainWindowHandle
}

# Word sicher aktivieren.
try {
  $wsh=New-Object -ComObject WScript.Shell
  [void]$wsh.AppActivate([int]$wordProc.Id)
} catch {}
try { [EngbersWin32_1714]::ShowWindowAsync([IntPtr]$hwnd,9) | Out-Null } catch {}
try { [EngbersWin32_1714]::SetForegroundWindow([IntPtr]$hwnd) | Out-Null } catch {}
Start-Sleep -Milliseconds 450

function Find-AdobeInWordWindows {
  $root=Get-Root
  $pidCond=New-Object Windows.Automation.PropertyCondition(
    [Windows.Automation.AutomationElement]::ProcessIdProperty,[int]$wordProc.Id)
  $wins=$root.FindAll([Windows.Automation.TreeScope]::Children,$pidCond)
  foreach($w in $wins){
    try {
      $el=Find-ByName $w @('Als Adobe PDF speichern','Save as Adobe PDF')
      if($el){ return $el }
    } catch {}
  }
  try {
    $main=[Windows.Automation.AutomationElement]::FromHandle([IntPtr]$hwnd)
    $el=Find-ByName $main @('Als Adobe PDF speichern','Save as Adobe PDF')
    if($el){ return $el }
  } catch {}
  return $null
}

# Versuch 1: echtes Windows-Tastaturereignis Alt+F an das aktive Word-Fenster.
$adobe=$null
try { [EngbersWin32_1714]::AltF() } catch {
  try { [System.Windows.Forms.SendKeys]::SendWait('%f') } catch {}
}
Start-Sleep -Milliseconds 900
$adobe=Wait-Until { Find-AdobeInWordWindows } 2500 200

# Versuch 2: Datei-Element per mehreren UIAutomation-Patterns wirklich ausloesen.
if(-not $adobe){
  try {
    [void]$wsh.AppActivate([int]$wordProc.Id)
    [void][EngbersWin32_1714]::SetForegroundWindow([IntPtr]$hwnd)
  } catch {}
  Start-Sleep -Milliseconds 250
  try {
    $wordWin=[Windows.Automation.AutomationElement]::FromHandle([IntPtr]$hwnd)
    $fileTab=Find-ByName $wordWin @('Datei','File')
    if($fileTab){
      $done=$false
      try {
        $p=$fileTab.GetCurrentPattern([Windows.Automation.SelectionItemPattern]::Pattern)
        $p.Select(); $done=$true
      } catch {}
      if(-not $done){
        try {
          $p=$fileTab.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern)
          $p.Invoke(); $done=$true
        } catch {}
      }
      if(-not $done){
        try {
          $p=$fileTab.GetCurrentPattern([Windows.Automation.LegacyIAccessiblePattern]::Pattern)
          $p.DoDefaultAction(); $done=$true
        } catch {}
      }
      if(-not $done){
        try { $fileTab.SetFocus(); [System.Windows.Forms.SendKeys]::SendWait('{ENTER}') } catch {}
      }
    }
  } catch {}
  Start-Sleep -Milliseconds 900
  $adobe=Wait-Until { Find-AdobeInWordWindows } 2500 200
}

# Versuch 3: wenn Word den Ribbon-Reiter per UIAutomation nicht ausloest,
# den sichtbaren Datei-Reiter anhand seiner echten Bildschirmposition anklicken.
if(-not $adobe){
  try {
    [void]$wsh.AppActivate([int]$wordProc.Id)
    [void][EngbersWin32_1714]::SetForegroundWindow([IntPtr]$hwnd)
    Start-Sleep -Milliseconds 250
    $wordWin=[Windows.Automation.AutomationElement]::FromHandle([IntPtr]$hwnd)
    $fileTab=Find-ByName $wordWin @('Datei','File')
    if($fileTab){
      $r=$fileTab.Current.BoundingRectangle
      if($r.Width -gt 4 -and $r.Height -gt 4){
        $cx=[int]($r.Left + ($r.Width/2))
        $cy=[int]($r.Top + ($r.Height/2))
        [EngbersWin32_1714]::Click($cx,$cy)
      }
    }
  } catch {}
  Start-Sleep -Milliseconds 1000
  $adobe=Wait-Until { Find-AdobeInWordWindows } 3000 200
}

if(-not (Get-Process -Id $wordProc.Id -ErrorAction SilentlyContinue)){
  throw 'Microsoft Word wurde waehrend der PDF-Erzeugung geschlossen.'
}
if(-not $adobe){
  throw 'Word wurde aktiviert, aber der Datei-Bereich mit "Als Adobe PDF speichern" konnte auch per Alt+F, UIAutomation und direktem Klick nicht geoeffnet werden.'
}
if(-not (Invoke-El $adobe)){
  throw '"Als Adobe PDF speichern" wurde gefunden, konnte aber nicht angeklickt werden.'
}
Start-Sleep -Milliseconds 500

'''


def _version(text):
    m = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']', text)
    return m.group(1).strip() if m else ''


def _set_version(text):
    out, n = re.subn(r'(APP_VERSION\s*=\s*)["\'][^"\']+["\']',
                     lambda m: m.group(1) + '"' + NEW + '"', text, count=1)
    if n != 1:
        raise RuntimeError('1.7.14: APP_VERSION wurde in app.py nicht gefunden.')
    out = out.replace('Projektzentrale 1.7.13', 'Projektzentrale 1.7.14')
    return out


def _patch_mod(mod):
    if NEW_MARK in mod:
        return mod
    s = mod.find(OLD_MARK)
    if s < 0:
        raise RuntimeError('1.7.14: Adobe-Backstage-Marker aus 1.7.13 wurde nicht gefunden.')
    e = mod.find(DIALOG_MARK, s)
    if e < 0:
        raise RuntimeError('1.7.14: Beginn des Adobe-Speichern-Dialogs wurde nicht gefunden.')
    return mod[:s] + NEW_BLOCK + mod[e:]


def main():
    if not APP.exists() or not MOD.exists():
        raise RuntimeError('1.7.14: app.py oder wordforms_v1700.py wurde nicht gefunden.')
    app = APP.read_text(encoding='utf-8')
    mod = MOD.read_text(encoding='utf-8')
    cur = _version(app)
    if cur == NEW and NEW_MARK in mod:
        return 0
    if cur != OLD:
        raise RuntimeError(f'Update 1.7.14 erwartet Projektzentrale {OLD}; gefunden: {cur or "unbekannt"}.')

    app_new = _set_version(app)
    mod_new = _patch_mod(mod)
    if NEW_MARK not in mod_new:
        raise RuntimeError('1.7.14: neuer Backstage-Marker fehlt nach dem Patch.')

    active = mod_new[mod_new.find(NEW_MARK):mod_new.find(DIALOG_MARK, mod_new.find(NEW_MARK))]
    for required in ('EngbersWin32_1714', 'AltF()', 'SelectionItemPattern', 'LegacyIAccessiblePattern', 'BoundingRectangle', '::Click('):
        if required not in active:
            raise RuntimeError('1.7.14: erwarteter robuster Datei-Mechanismus fehlt: ' + required)

    chk1 = APP.with_name('app.py.1714.check')
    chk2 = MOD.with_name('wordforms_v1700.py.1714.check')
    try:
        chk1.write_text(app_new, encoding='utf-8')
        py_compile.compile(str(chk1), doraise=True)
        chk2.write_text(mod_new, encoding='utf-8')
        py_compile.compile(str(chk2), doraise=True)
    finally:
        for p in (chk1, chk2):
            try: p.unlink()
            except Exception: pass

    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for p in (APP, MOD):
        shutil.copy2(p, p.with_name(p.name + '.vor_1_7_14_' + stamp + '.bak'))
    t = APP.with_name('app.py.1714.tmp'); t.write_text(app_new, encoding='utf-8'); t.replace(APP)
    t = MOD.with_name('wordforms_v1700.py.1714.tmp'); t.write_text(mod_new, encoding='utf-8'); t.replace(MOD)
    APP.with_name('patch_1714_report.txt').write_text(
        'OK: Projektzentrale 1.7.14 installiert.\n'
        'Adobe-PDF: Datei/Backstage wird jetzt dreistufig per Alt+F, UIAutomation und direktem Klick geoeffnet.\n',
        encoding='utf-8')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        try: APP.with_name('patch_1714_error.txt').write_text(traceback.format_exc(), encoding='utf-8')
        except Exception: pass
        raise
