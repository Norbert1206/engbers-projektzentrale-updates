from pathlib import Path
import datetime
import py_compile
import shutil

APP=Path(__file__).resolve().parent/'app.py'

OPEN_HELPER = r'''        def _mb_open_project_application(folder,app_name,model_hint=''):
            """Open the mb project, select the application tab and, for MicroFe,
            try to open the concrete model card matching the selected position.

            The project itself is still opened only through the registered .mbp
            Windows handler. UI Automation is best-effort and read-only with
            respect to mb project/model data and the registry.
            """
            try:
                import os, subprocess, threading, time
                from pathlib import Path
                base=Path(folder)
                mbps=sorted(base.glob('*.mbp'))
                if not mbps:
                    try:
                        from tkinter import messagebox
                        messagebox.showwarning('mb-Projekt','Keine .mbp-Projektdatei gefunden.')
                    except Exception:
                        pass
                    return
                lead=mbps[0]
                try:
                    os.startfile(str(lead))
                except Exception as exc:
                    try:
                        from tkinter import messagebox
                        messagebox.showwarning('mb-Projekt',f'Projekt konnte nicht geöffnet werden:\n{exc}')
                    except Exception:
                        pass
                    return

                def _select_tab_and_model():
                    time.sleep(1.0)
                    wanted='MicroFe' if str(app_name).lower()=='microfe' else 'BauStatik'
                    env=os.environ.copy()
                    env['ENGBERS_MB_PROJECT']=lead.stem
                    env['ENGBERS_MB_APP']=wanted
                    env['ENGBERS_MB_MODEL']=str(model_hint or '').strip()
                    ps=r"""
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms
$project=$env:ENGBERS_MB_PROJECT
$wanted=$env:ENGBERS_MB_APP
$model=$env:ENGBERS_MB_MODEL
$root=[System.Windows.Automation.AutomationElement]::RootElement
$window=$null
for($i=0; $i -lt 48 -and $null -eq $window; $i++) {
    $wins=$root.FindAll([System.Windows.Automation.TreeScope]::Children,[System.Windows.Automation.Condition]::TrueCondition)
    foreach($w in $wins) {
        $name=$w.Current.Name
        if($name -and $name -like '*ProjektManager*' -and ($project -eq '' -or $name -like ('*'+$project+'*'))) {
            $window=$w
            break
        }
    }
    if($null -eq $window) { Start-Sleep -Milliseconds 250 }
}
if($null -eq $window) { exit 2 }

$tabCond=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::TabItem)
$tabs=$window.FindAll([System.Windows.Automation.TreeScope]::Descendants,$tabCond)
$tabFound=$false
foreach($tab in $tabs) {
    $name=$tab.Current.Name
    $match=$false
    if($wanted -eq 'MicroFe') { $match=($name -like '*MicroFe*') }
    else { $match=($name -like '*BauStatik*') }
    if($match) {
        try {
            $p=$tab.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern)
            $p.Select()
            $tabFound=$true
            break
        } catch {}
        try {
            $p=$tab.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
            $p.Invoke()
            $tabFound=$true
            break
        } catch {}
        try { $tab.SetFocus(); $tabFound=$true; break } catch {}
    }
}
if(-not $tabFound) { exit 3 }

# BauStatik stays at the correct register for now. Its position lives inside
# the BauStatik model and will be handled in a later step.
if($wanted -ne 'MicroFe' -or [string]::IsNullOrWhiteSpace($model)) { exit 0 }

Start-Sleep -Milliseconds 700
$walker=[System.Windows.Automation.TreeWalker]::ControlViewWalker
function Try-OpenElement($el) {
    $cur=$el
    for($j=0; $j -lt 7 -and $null -ne $cur; $j++) {
        try {
            $p=$cur.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
            $p.Invoke()
            return $true
        } catch {}
        try {
            $p=$cur.GetCurrentPattern([System.Windows.Automation.LegacyIAccessiblePattern]::Pattern)
            $p.DoDefaultAction()
            return $true
        } catch {}
        try {
            $p=$cur.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern)
            $p.Select()
            $cur.SetFocus()
            [System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
            return $true
        } catch {}
        try { $cur=$walker.GetParent($cur) } catch { $cur=$null }
    }
    return $false
}

for($round=0; $round -lt 12; $round++) {
    $all=$window.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
    foreach($el in $all) {
        $name=$el.Current.Name
        if([string]::IsNullOrWhiteSpace($name)) { continue }
        $n=$name.Trim()
        if($n -eq $model -or $n -like ($model+' *')) {
            if(Try-OpenElement $el) { exit 0 }
        }
    }
    Start-Sleep -Milliseconds 250
}
exit 4
"""
                    try:
                        subprocess.run(
                            ['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-Command',ps],
                            env=env,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=20,
                            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),
                        )
                    except Exception:
                        pass
                threading.Thread(target=_select_tab_and_model,daemon=True).start()
            except Exception:
                pass
'''


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.19"' in s:
        return 0
    if 'APP_VERSION = "1.4.18"' not in s:
        raise RuntimeError('Update 1.4.19 erwartet Projektzentrale 1.4.18. Es wurde nichts verändert.')
    original=s
    s=s.replace('APP_VERSION = "1.4.18"','APP_VERSION = "1.4.19"',1)

    start=s.find('        def _mb_open_project_application(folder,app_name):')
    end=s.find('        def _detail_add_link(text,label,path,tag_index):',start)
    if start < 0 or end < 0:
        raise RuntimeError('1.4.19 Marker für mb-Starthelfer fehlt.')
    s=s[:start]+OPEN_HELPER+'\n'+s[end:]

    old="n=_detail_add_action(detail_text,f'• mb öffnen → {mb_app}',lambda f=folder,a=mb_app:_mb_open_project_application(f,a),n)"
    new="n=_detail_add_action(detail_text,f'• mb öffnen → {mb_app}',lambda f=folder,a=mb_app,m=posid:_mb_open_project_application(f,a,m),n)"
    if old not in s:
        raise RuntimeError('1.4.19 Marker für mb-Aktion fehlt.')
    s=s.replace(old,new,1)

    s=s.replace(
        'Hinweis 1.4.18: mb-Projekte werden über den registrierten .mbp-Handler geöffnet. Danach wählt Windows UI Automation automatisch das zugehörige Register BauStatik oder MicroFe im ProjektManager. Fällt die Registerwahl aus, bleibt der normale Projektstart erhalten.',
        'Hinweis 1.4.19: Nach dem Projektstart und der Registerwahl sucht Windows UI Automation bei MicroFe zusätzlich die Modellkarte der ausgewählten Position (z.B. E.01.D) und öffnet sie best-effort. BauStatik bleibt zunächst auf dem richtigen Register.'
    )
    s=s.replace(
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb und Windows-Dateizuordnungen werden read-only gelesen. Positionsakte 1.4.18 startet das .mbp über den registrierten Handler und nutzt UI Automation nur zur Registerwahl; mb-Daten und Registry bleiben unverändert.',
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb und Windows-Dateizuordnungen werden read-only gelesen. Positionsakte 1.4.19 nutzt UI Automation zusätzlich zur best-effort Auswahl der MicroFe-Modellkarte; mb-Daten und Registry bleiben unverändert.'
    )

    required=(
        'APP_VERSION = "1.4.19"',
        "def _mb_open_project_application(folder,app_name,model_hint='')",
        "env['ENGBERS_MB_MODEL']",
        'function Try-OpenElement($el)',
        "m=posid:_mb_open_project_application(f,a,m)",
        "if($wanted -ne 'MicroFe'",
        '• ProjektManager öffnen (nur Projekt)',
    )
    if not all(x in s for x in required):
        raise RuntimeError('Patch-Ergebnis 1.4.19 unvollständig. Es wurde nichts verändert.')
    if s==original:
        raise RuntimeError('Keine Änderung erzeugt.')

    tmp=APP.with_name('app.py.1419.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.v1418_vor_1419_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp.replace(APP)
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1419_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        print('FEHLER:',e)
        raise SystemExit(1)
