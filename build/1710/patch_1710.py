from pathlib import Path
import datetime
import py_compile
import shutil
import traceback

BASE=Path(__file__).resolve().parent
APP=BASE/'app.py'
MOD=BASE/'wordforms_v1700.py'
OLD='1.7.9'; NEW='1.7.10'
MARK='PZ_ADOBE_UI_GLOBAL_SEARCH_V1710'

OLD_BLOCK=r'''$wordWin=[Windows.Automation.AutomationElement]::FromHandle([IntPtr]$hwnd)
$adobe=Wait-Until {
  Find-ByName $wordWin @('Als Adobe PDF speichern','Save as Adobe PDF')
} 12000
if(-not $adobe){ throw 'Der Word-Befehl "Als Adobe PDF speichern" wurde nicht gefunden.' }
if(-not (Invoke-El $adobe)){ throw 'Der Word-Befehl "Als Adobe PDF speichern" konnte nicht ausgefuehrt werden.' }'''

NEW_BLOCK=r'''# PZ_ADOBE_UI_GLOBAL_SEARCH_V1710
# Der Word-Backstage-Bereich ist technisch nicht immer Kind des normalen Word-Fensters.
# Deshalb im gesamten Desktop-UI-Baum suchen.
$adobe=Wait-Until {
  $root=Get-Root
  $el=Find-ByName $root @('Als Adobe PDF speichern','Save as Adobe PDF')
  if($el){ return $el }
  try {
    $all=$root.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition)
    foreach($e in $all){
      try {
        $n=[string]$e.Current.Name
        if($n -and ($n -like '*Adobe PDF*')){ return $e }
      } catch {}
    }
  } catch {}
  return $null
} 15000
if(-not $adobe){ throw 'Der Word-Befehl "Als Adobe PDF speichern" wurde im gesamten Windows-UI nicht gefunden.' }
if(-not (Invoke-El $adobe)){ throw 'Der Word-Befehl "Als Adobe PDF speichern" wurde gefunden, konnte aber nicht ausgefuehrt werden.' }'''


def _patch_mod(mod):
    if MARK in mod:
        return mod
    if OLD_BLOCK not in mod:
        raise RuntimeError('1.7.10: Adobe-Menuesuche aus 1.7.9 wurde nicht gefunden.')
    return mod.replace(OLD_BLOCK,NEW_BLOCK,1)


def main():
    if not APP.exists() or not MOD.exists():
        raise RuntimeError('1.7.10: app.py oder wordforms_v1700.py wurde nicht gefunden.')
    app=APP.read_text(encoding='utf-8')
    mod=MOD.read_text(encoding='utf-8')
    if f'APP_VERSION = "{NEW}"' in app and MARK in mod:
        return 0
    if f'APP_VERSION = "{OLD}"' not in app:
        raise RuntimeError('Update 1.7.10 erwartet Projektzentrale 1.7.9.')
    mod_new=_patch_mod(mod)
    app_new=app.replace(f'APP_VERSION = "{OLD}"',f'APP_VERSION = "{NEW}"',1).replace('Projektzentrale 1.7.9','Projektzentrale 1.7.10')
    if MARK not in mod_new:
        raise RuntimeError('1.7.10: Global-UI-Suchmarker fehlt.')
    chk1=APP.with_name('app.py.1710.check'); chk2=MOD.with_name('wordforms_v1700.py.1710.check')
    try:
        chk1.write_text(app_new,encoding='utf-8'); py_compile.compile(str(chk1),doraise=True)
        chk2.write_text(mod_new,encoding='utf-8'); py_compile.compile(str(chk2),doraise=True)
    finally:
        for p in (chk1,chk2):
            try:p.unlink()
            except Exception:pass
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for p in (APP,MOD): shutil.copy2(p,p.with_name(p.name+'.vor_1_7_10_'+stamp+'.bak'))
    t=APP.with_name('app.py.1710.tmp'); t.write_text(app_new,encoding='utf-8'); t.replace(APP)
    t=MOD.with_name('wordforms_v1700.py.1710.tmp'); t.write_text(mod_new,encoding='utf-8'); t.replace(MOD)
    APP.with_name('patch_1710_report.txt').write_text(
        'OK: Projektzentrale 1.7.10 installiert.\n'
        'Adobe-PDF-Menuesuche erfolgt jetzt im gesamten Windows-UI-Baum statt nur im normalen Word-Fenster.\n'
        'Zusaetzlich wird als Fallback nach allen UI-Elementen mit Adobe PDF im Namen gesucht.\n',encoding='utf-8')
    return 0

if __name__=='__main__':
    try: raise SystemExit(main())
    except SystemExit: raise
    except Exception:
        try: APP.with_name('patch_1710_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception: pass
        raise
