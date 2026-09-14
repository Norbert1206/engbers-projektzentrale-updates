from pathlib import Path
import datetime
import py_compile
import shutil

APP=Path(__file__).resolve().parent/'app.py'

OPEN_HELPER = r'''        def _mb_open_project_application(folder,app_name):
            """Open the mb project through its registered Windows handler and
            then select the matching application tab in ProjektManager.

            The project start itself uses the .mbp file association discovered
            in 1.4.17. The optional tab selection uses Windows UI Automation via
            built-in PowerShell/.NET only. If UI Automation is unavailable or mb
            changes its UI, the project is still opened normally and nothing is
            written to mb project/model data or the registry.
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

                def _select_tab():
                    # ProjektManager needs a moment to create its main window.
                    time.sleep(1.0)
                    wanted='MicroFe' if str(app_name).lower()=='microfe' else 'BauStatik'
                    env=os.environ.copy()
                    env['ENGBERS_MB_PROJECT']=lead.stem
                    env['ENGBERS_MB_APP']=wanted
                    ps=r"""
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$project=$env:ENGBERS_MB_PROJECT
$wanted=$env:ENGBERS_MB_APP
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
$cond=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::TabItem)
$tabs=$window.FindAll([System.Windows.Automation.TreeScope]::Descendants,$cond)
foreach($tab in $tabs) {
    $name=$tab.Current.Name
    $match=$false
    if($wanted -eq 'MicroFe') { $match=($name -like '*MicroFe*') }
    else { $match=($name -like '*BauStatik*') }
    if($match) {
        try {
            $p=$tab.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern)
            $p.Select()
            exit 0
        } catch {}
        try {
            $p=$tab.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
            $p.Invoke()
            exit 0
        } catch {}
        try { $tab.SetFocus(); exit 0 } catch {}
    }
}
exit 3
"""
                    try:
                        subprocess.run(
                            ['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-Command',ps],
                            env=env,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=15,
                            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),
                        )
                    except Exception:
                        # Safe fallback: project is already open in ProjektManager.
                        pass
                threading.Thread(target=_select_tab,daemon=True).start()
            except Exception:
                pass
'''


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.18"' in s:
        return 0
    if 'APP_VERSION = "1.4.17"' not in s:
        raise RuntimeError('Update 1.4.18 erwartet Projektzentrale 1.4.17. Es wurde nichts verändert.')
    original=s
    s=s.replace('APP_VERSION = "1.4.17"','APP_VERSION = "1.4.18"',1)

    marker='        def _detail_add_link(text,label,path,tag_index):'
    if marker not in s:
        raise RuntimeError('1.4.18 Marker für Positionsakte-Helfer fehlt.')
    if 'def _mb_open_project_application' not in s:
        s=s.replace(marker,OPEN_HELPER+'\n'+marker,1)

    # Keep the proven raw ProjektManager link as fallback, but add the smarter
    # action that opens the project and selects BauStatik/MicroFe automatically.
    old_action="""                if lead is not None:
                    n=_detail_add_link(detail_text,'• ProjektManager öffnen',lead,n)
                else:
                    n=_detail_add_link(detail_text,'• mb-Projektordner öffnen',folder,n)

                dbsrc=str(r.get('_db') or '').strip()
"""
    new_action="""                if lead is not None:
                    n=_detail_add_action(detail_text,f'• mb öffnen → {mb_app}',lambda f=folder,a=mb_app:_mb_open_project_application(f,a),n)
                    n=_detail_add_link(detail_text,'• ProjektManager öffnen (nur Projekt)',lead,n)
                else:
                    n=_detail_add_link(detail_text,'• mb-Projektordner öffnen',folder,n)

                dbsrc=str(r.get('_db') or '').strip()
"""
    if old_action not in s:
        raise RuntimeError('1.4.18 Marker für ProjektManager-Aktion fehlt.')
    s=s.replace(old_action,new_action,1)

    s=s.replace(
        'Hinweis 1.4.17: Die Startdiagnose steht jetzt direkt im sichtbaren Kopf der Positionsakte. Zusätzlich wird das registrierte Windows/mb-Startkommando für .mbp bzw. .mbdb read-only angezeigt; doppelte Positionszeilen wurden entfernt.',
        'Hinweis 1.4.18: mb-Projekte werden über den registrierten .mbp-Handler geöffnet. Danach wählt Windows UI Automation automatisch das zugehörige Register BauStatik oder MicroFe im ProjektManager. Fällt die Registerwahl aus, bleibt der normale Projektstart erhalten.'
    )
    s=s.replace(
        'Quelle: BSPos.mbdb, *.mbp und FEM/*.mbdb sowie Windows-Dateizuordnungen werden ausschließlich read-only gelesen. Positionsakte 1.4.17 zeigt Handler und Startkommando kompakt im sichtbaren Kopf; Registry und mb-Daten bleiben unverändert.',
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb und Windows-Dateizuordnungen werden read-only gelesen. Positionsakte 1.4.18 startet das .mbp über den registrierten Handler und nutzt UI Automation nur zur Registerwahl; mb-Daten und Registry bleiben unverändert.'
    )

    required=(
        'APP_VERSION = "1.4.18"',
        'def _mb_open_project_application',
        "os.startfile(str(lead))",
        "ENGBERS_MB_APP",
        "ControlType]::TabItem",
        "f'• mb öffnen → {mb_app}'",
        '• ProjektManager öffnen (nur Projekt)',
        'Startprüfung Modell (.mbdb)',
        'Startprüfung Projekt (.mbp)',
    )
    if not all(x in s for x in required):
        raise RuntimeError('Patch-Ergebnis 1.4.18 unvollständig. Es wurde nichts verändert.')
    if s==original:
        raise RuntimeError('Keine Änderung erzeugt.')

    tmp=APP.with_name('app.py.1418.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.v1417_vor_1418_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp.replace(APP)
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1418_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        print('FEHLER:',e)
        raise SystemExit(1)
