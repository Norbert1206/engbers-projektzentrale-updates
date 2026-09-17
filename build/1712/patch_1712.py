from pathlib import Path
import datetime
import py_compile
import re
import shutil
import traceback

BASE = Path(__file__).resolve().parent
APP = BASE / 'app.py'
MOD = BASE / 'wordforms_v1700.py'
NEW = '1.7.12'
MARK = 'PZ_WORD_FOCUS_BACKSTAGE_V1711'

OLD_START = "# 2) Datei-Backstage oeffnen\n[System.Windows.Forms.SendKeys]::SendWait('%f')\nStart-Sleep -Milliseconds 900\n\n# 3) Adobe-Menueintrag wirklich anklicken\n"
OLD_END = "# 4) Auf Speichern-Dialog warten"

NEW_BLOCK = r'''# 2) Exakt das Word-Fenster der aktuellen DOCX finden und aktivieren
# PZ_WORD_FOCUS_BACKSTAGE_V1711
$docName=[IO.Path]::GetFileNameWithoutExtension($DocxPath)
$targetWin=Wait-Until {
  $root=Get-Root
  $wins=$root.FindAll([Windows.Automation.TreeScope]::Children,[Windows.Automation.Condition]::TrueCondition)
  foreach($w in $wins){
    try {
      $n=[string]$w.Current.Name
      if($n -and $n -like "*$docName*" -and $n -match 'Word') { return $w }
    } catch {}
  }
  return $null
} 15000
if(-not $targetWin){
  try { $targetWin=[Windows.Automation.AutomationElement]::FromHandle([IntPtr]$hwnd) } catch {}
}
if(-not $targetWin){ throw 'Das Word-Fenster mit der Bescheinigung wurde nicht gefunden.' }
try { $targetWin.SetFocus() } catch {}
Start-Sleep -Milliseconds 500

$fileTab=Find-ByName $targetWin @('Datei','File')
if($fileTab){
  if(-not (Invoke-El $fileTab)){
    try { $fileTab.SetFocus(); [System.Windows.Forms.SendKeys]::SendWait('{ENTER}') } catch {}
  }
} else {
  [System.Windows.Forms.SendKeys]::SendWait('%f')
}
Start-Sleep -Milliseconds 1200

if(-not (Get-Process -Id $wordProc.Id -ErrorAction SilentlyContinue)){
  throw 'Microsoft Word wurde waehrend der PDF-Erzeugung geschlossen.'
}

# 3) Adobe-Menueintrag im gesamten Desktop suchen
'''


def _version(text):
    m = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']', text)
    return m.group(1).strip() if m else ''


def _set_version(text, version):
    out, n = re.subn(r'(APP_VERSION\s*=\s*)["\'][^"\']+["\']',
                     lambda m: m.group(1) + '"' + version + '"', text, count=1)
    if n != 1:
        raise RuntimeError('1.7.12: APP_VERSION wurde in app.py nicht gefunden.')
    for old in ('Projektzentrale 1.7.10', 'Projektzentrale 1.7.11'):
        out = out.replace(old, 'Projektzentrale 1.7.12')
    return out


def _patch_mod(mod):
    if MARK in mod:
        return mod
    s = mod.find(OLD_START)
    if s < 0:
        raise RuntimeError('1.7.12: Start des Word-Backstage-Blocks aus 1.7.10 wurde nicht gefunden.')
    e = mod.find(OLD_END, s)
    if e < 0:
        raise RuntimeError('1.7.12: Ende des Word-Backstage-Blocks wurde nicht gefunden.')
    return mod[:s] + NEW_BLOCK + mod[s + len(OLD_START):e] + mod[e:]


def main():
    if not APP.exists() or not MOD.exists():
        raise RuntimeError('1.7.12: app.py oder wordforms_v1700.py wurde nicht gefunden.')

    app = APP.read_text(encoding='utf-8')
    mod = MOD.read_text(encoding='utf-8')
    cur = _version(app)

    if cur == NEW and MARK in mod:
        return 0
    if cur not in ('1.7.10', '1.7.11', '1.7.12'):
        raise RuntimeError(f'Update 1.7.12 erwartet 1.7.10 oder 1.7.11; gefunden: {cur or "unbekannt"}.')

    mod_new = _patch_mod(mod)
    app_new = _set_version(app, NEW)
    if MARK not in mod_new:
        raise RuntimeError('1.7.12: Fokus-/Backstage-Fix fehlt nach dem Patch.')

    chk1 = APP.with_name('app.py.1712.check')
    chk2 = MOD.with_name('wordforms_v1700.py.1712.check')
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
        shutil.copy2(p, p.with_name(p.name + '.vor_1_7_12_' + stamp + '.bak'))

    t = APP.with_name('app.py.1712.tmp')
    t.write_text(app_new, encoding='utf-8')
    t.replace(APP)
    t = MOD.with_name('wordforms_v1700.py.1712.tmp')
    t.write_text(mod_new, encoding='utf-8')
    t.replace(MOD)

    APP.with_name('patch_1712_report.txt').write_text(
        'OK: Projektzentrale 1.7.12 installiert.\n'
        'Update-Ausfuehrung repariert; Word-Fenster wird fuer Adobe-PDF gezielt aktiviert.\n',
        encoding='utf-8')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        try:
            APP.with_name('patch_1712_error.txt').write_text(traceback.format_exc(), encoding='utf-8')
        except Exception:
            pass
        raise
