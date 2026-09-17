from pathlib import Path
import datetime
import py_compile
import shutil
import traceback

BASE=Path(__file__).resolve().parent
APP=BASE/'app.py'
MOD=BASE/'wordforms_v1700.py'
OLD='1.7.10'; NEW='1.7.11'
MARK='PZ_WORD_FOCUS_BACKSTAGE_V1711'

OLD_START="# 2) Datei-Backstage oeffnen\n[System.Windows.Forms.SendKeys]::SendWait('%f')\nStart-Sleep -Milliseconds 900\n\n# 3) Adobe-Menueintrag wirklich anklicken\n"
OLD_END="# 4) Auf Speichern-Dialog warten"

NEW_BLOCK=r'''# 2) Exakt das Word-Fenster der aktuellen DOCX finden und aktivieren
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
  # Fallback auf das zuvor gefundene Word-Fenster
  try { $targetWin=[Windows.Automation.AutomationElement]::FromHandle([IntPtr]$hwnd) } catch {}
}
if(-not $targetWin){ throw 'Das Word-Fenster mit der Bescheinigung wurde nicht gefunden.' }
try { $targetWin.SetFocus() } catch {}
Start-Sleep -Milliseconds 500

# Datei-Register gezielt anklicken; erst danach Alt+F als Fallback.
$fileTab=Find-ByName $targetWin @('Datei','File')
if($fileTab){
  if(-not (Invoke-El $fileTab)){
    try { $fileTab.SetFocus(); [System.Windows.Forms.SendKeys]::SendWait('{ENTER}') } catch {}
  }
} else {
  [System.Windows.Forms.SendKeys]::SendWait('%f')
}
Start-Sleep -Milliseconds 1200

# Pruefen, ob Word noch laeuft, bevor im Backstage gesucht wird.
if(-not (Get-Process -Id $wordProc.Id -ErrorAction SilentlyContinue)){
  throw 'Microsoft Word wurde waehrend der PDF-Erzeugung geschlossen.'
}

# 3) Adobe-Menueintrag im gesamten Desktop suchen
'''


def _patch_mod(mod):
    if MARK in mod:
        return mod
    s=mod.find(OLD_START)
    if s<0:
        raise RuntimeError('1.7.11: Start des Word-Backstage-Blocks wurde nicht gefunden.')
    e=mod.find(OLD_END,s)
    if e<0:
        raise RuntimeError('1.7.11: Ende des Word-Backstage-Blocks wurde nicht gefunden.')
    return mod[:s]+NEW_BLOCK+mod[s+len(OLD_START):e]+mod[e:]


def main():
    if not APP.exists() or not MOD.exists():
        raise RuntimeError('1.7.11: app.py oder wordforms_v1700.py wurde nicht gefunden.')
    app=APP.read_text(encoding='utf-8')
    mod=MOD.read_text(encoding='utf-8')
    if f'APP_VERSION = "{NEW}"' in app and MARK in mod:
        return 0
    if f'APP_VERSION = "{OLD}"' not in app:
        raise RuntimeError('Update 1.7.11 erwartet Projektzentrale 1.7.10.')
    mod_new=_patch_mod(mod)
    app_new=app.replace(f'APP_VERSION = "{OLD}"',f'APP_VERSION = "{NEW}"',1).replace('Projektzentrale 1.7.10','Projektzentrale 1.7.11')
    if MARK not in mod_new:
        raise RuntimeError('1.7.11: Fokusmarker fehlt.')
    chk1=APP.with_name('app.py.1711.check'); chk2=MOD.with_name('wordforms_v1700.py.1711.check')
    try:
        chk1.write_text(app_new,encoding='utf-8'); py_compile.compile(str(chk1),doraise=True)
        chk2.write_text(mod_new,encoding='utf-8'); py_compile.compile(str(chk2),doraise=True)
    finally:
        for p in (chk1,chk2):
            try:p.unlink()
            except Exception:pass
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for p in (APP,MOD): shutil.copy2(p,p.with_name(p.name+'.vor_1_7_11_'+stamp+'.bak'))
    t=APP.with_name('app.py.1711.tmp'); t.write_text(app_new,encoding='utf-8'); t.replace(APP)
    t=MOD.with_name('wordforms_v1700.py.1711.tmp'); t.write_text(mod_new,encoding='utf-8'); t.replace(MOD)
    APP.with_name('patch_1711_report.txt').write_text(
        'OK: Projektzentrale 1.7.11 installiert.\n'
        'Word-Fenster wird anhand des Dokumentnamens aktiviert; Datei wird gezielt geoeffnet.\n'
        'Schliessen von Word waehrend der PDF-Erzeugung wird sauber abgefangen.\n',encoding='utf-8')
    return 0

if __name__=='__main__':
    try: raise SystemExit(main())
    except SystemExit: raise
    except Exception:
        try: APP.with_name('patch_1711_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception: pass
        raise
