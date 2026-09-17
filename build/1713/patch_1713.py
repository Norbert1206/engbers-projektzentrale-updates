from pathlib import Path
import datetime
import py_compile
import re
import shutil
import traceback

BASE = Path(__file__).resolve().parent
APP = BASE / 'app.py'
MOD = BASE / 'wordforms_v1700.py'
OLD = '1.7.12'
NEW = '1.7.13'
OLD_MARK = '# PZ_WORD_FOCUS_BACKSTAGE_V1711'
NEW_MARK = '# PZ_ADOBE_DIRECT_BACKSTAGE_V1713'
DIALOG_MARK = '$dlg=Wait-Until {'

NEW_BLOCK = r'''# PZ_ADOBE_DIRECT_BACKSTAGE_V1713
# Word per Win32 wirklich in den Vordergrund holen; danach Backstage per Alt+F.
# Es wird NICHT mehr der komplette Desktop-UI-Baum rekursiv durchsucht.
try {
  Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class EngbersWin32 {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);
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

try { [EngbersWin32]::ShowWindowAsync([IntPtr]$hwnd,9) | Out-Null } catch {}
try { [EngbersWin32]::SetForegroundWindow([IntPtr]$hwnd) | Out-Null } catch {}
Start-Sleep -Milliseconds 500
[System.Windows.Forms.SendKeys]::SendWait('%f')
Start-Sleep -Milliseconds 900

if(-not (Get-Process -Id $wordProc.Id -ErrorAction SilentlyContinue)){
  throw 'Microsoft Word wurde waehrend der PDF-Erzeugung geschlossen.'
}

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
  return $null
}

$adobe=Wait-Until { Find-AdobeInWordWindows } 6000 250
if(-not $adobe){
  # Einmaliger Fallback: sichtbaren Datei-Reiter per UIAutomation anklicken und erneut suchen.
  try {
    $wordWin=[Windows.Automation.AutomationElement]::FromHandle([IntPtr]$hwnd)
    $fileTab=Find-ByName $wordWin @('Datei','File')
    if($fileTab){ [void](Invoke-El $fileTab) }
  } catch {}
  Start-Sleep -Milliseconds 700
  $adobe=Wait-Until { Find-AdobeInWordWindows } 6000 250
}
if(-not $adobe){
  throw 'Der Word-Bereich "Als Adobe PDF speichern" wurde nach dem Oeffnen von Datei nicht gefunden.'
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
        raise RuntimeError('1.7.13: APP_VERSION wurde in app.py nicht gefunden.')
    out = out.replace('Projektzentrale 1.7.12', 'Projektzentrale 1.7.13')
    return out


def _patch_mod(mod):
    if NEW_MARK in mod:
        return mod
    s = mod.find(OLD_MARK)
    if s < 0:
        raise RuntimeError('1.7.13: Word-/Backstage-Marker aus 1.7.12 wurde nicht gefunden.')
    e = mod.find(DIALOG_MARK, s)
    if e < 0:
        raise RuntimeError('1.7.13: Beginn des Adobe-Speichern-Dialogs wurde nicht gefunden.')
    return mod[:s] + NEW_BLOCK + mod[e:]


def main():
    if not APP.exists() or not MOD.exists():
        raise RuntimeError('1.7.13: app.py oder wordforms_v1700.py wurde nicht gefunden.')
    app = APP.read_text(encoding='utf-8')
    mod = MOD.read_text(encoding='utf-8')
    cur = _version(app)
    if cur == NEW and NEW_MARK in mod:
        return 0
    if cur != OLD:
        raise RuntimeError(f'Update 1.7.13 erwartet Projektzentrale {OLD}; gefunden: {cur or "unbekannt"}.')

    app_new = _set_version(app)
    mod_new = _patch_mod(mod)
    if NEW_MARK not in mod_new:
        raise RuntimeError('1.7.13: neuer Backstage-Marker fehlt nach dem Patch.')
    if '# PZ_ADOBE_UI_GLOBAL_SEARCH_V1710' in mod_new:
        # Die alte globale rekursive Suche muss aus dem aktiven Exportblock verschwunden sein.
        active = mod_new[mod_new.find(NEW_MARK):mod_new.find(DIALOG_MARK, mod_new.find(NEW_MARK))]
        if '# PZ_ADOBE_UI_GLOBAL_SEARCH_V1710' in active:
            raise RuntimeError('1.7.13: alte globale Desktop-Suche ist noch aktiv.')

    chk1 = APP.with_name('app.py.1713.check')
    chk2 = MOD.with_name('wordforms_v1700.py.1713.check')
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
        shutil.copy2(p, p.with_name(p.name + '.vor_1_7_13_' + stamp + '.bak'))
    t = APP.with_name('app.py.1713.tmp'); t.write_text(app_new, encoding='utf-8'); t.replace(APP)
    t = MOD.with_name('wordforms_v1700.py.1713.tmp'); t.write_text(mod_new, encoding='utf-8'); t.replace(MOD)
    APP.with_name('patch_1713_report.txt').write_text(
        'OK: Projektzentrale 1.7.13 installiert.\n'
        'Adobe-PDF: Word wird per Win32 aktiviert; keine rekursive globale Desktop-Suche mehr.\n',
        encoding='utf-8')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        try: APP.with_name('patch_1713_error.txt').write_text(traceback.format_exc(), encoding='utf-8')
        except Exception: pass
        raise
