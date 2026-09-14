from pathlib import Path
import datetime
import py_compile
import shutil

APP=Path(__file__).resolve().parent/'app.py'

OPEN_HELPER = r'''        def _mb_open_project_application(folder,app_name,model_hint=''):
            """Open the mb project and select BauStatik/MicroFe in ProjektManager.

            Deliberately stops at the application register. The concrete model/position
            is opened by the user in mb. This is the stable workflow proven in 1.4.18.
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
                        pass
                threading.Thread(target=_select_tab,daemon=True).start()
            except Exception:
                pass
'''

FILE_HELPER = r'''        _position_project_files_cache={}
        def _position_project_files(folder,pos):
            """Find project files whose path contains exactly the selected position.

            The complete project tree is scanned read-only. Common spelling variants
            are handled by _position_file_is_exact, so E.01.D does not inherit
            E.01.DS-1 files. Results use the existing Positionsakte tuple format:
            (score, mtime, category, absolute_path, relative_path).
            """
            try:
                import os
                from pathlib import Path
                base=Path(folder)
                wanted=str(pos or '').strip()
                if not wanted or not base.exists():
                    return []
                key=(str(base).lower(),wanted.upper())
                cached=_position_project_files_cache.get(key)
                if cached is not None:
                    return list(cached)

                allowed={
                    '.pdf','.doc','.docx','.rtf','.odt',
                    '.xls','.xlsx','.xlsm','.xlsb','.ods','.csv',
                    '.dwg','.dxf','.dgn','.ifc','.plt','.hpgl',
                    '.jpg','.jpeg','.png','.tif','.tiff','.bmp',
                    '.txt','.xml','.zip','.skp','.c4d'
                }
                skip_dirs={
                    'fem','__pycache__','.git','.svn','$recycle.bin',
                    'backup','backups','sicherung','sicherungen'
                }
                cad_ext={'.dwg','.dxf','.dgn','.ifc','.plt','.hpgl','.skp','.c4d'}
                sheet_ext={'.xls','.xlsx','.xlsm','.xlsb','.ods','.csv'}
                office_ext={'.doc','.docx','.rtf','.odt'}
                result=[]
                scanned=0

                for root,dirs,files in os.walk(base):
                    dirs[:]=[d for d in dirs if d.lower() not in skip_dirs and not d.startswith('.')]
                    for fn in files:
                        scanned+=1
                        if scanned>30000:
                            break
                        if fn.startswith('~$') or fn.startswith('.'):
                            continue
                        p=Path(root)/fn
                        ext=p.suffix.lower()
                        if ext not in allowed:
                            continue
                        try:
                            rel=str(p.relative_to(base))
                        except Exception:
                            rel=str(p)
                        if not _position_file_is_exact(wanted,rel):
                            continue

                        low=rel.lower()
                        if any(x in low for x in ('prüf','pruef','prüfer','pruefer')):
                            cat='Prüfstatik'
                        elif ext in cad_ext or any(x in low for x in ('plan','pläne','plaene','cad','bewehr','schalplan','positionsplan')):
                            cat='Pläne / CAD'
                        elif ext in sheet_ext or ext in office_ext or any(x in low for x in ('nachweis','berechnung','bemessung','statik')):
                            cat='Eigene Nachweise'
                        else:
                            cat='Dokumente'

                        score=100
                        try:
                            if _position_file_is_exact(wanted,p.name):
                                score+=30
                            if ext=='.pdf':
                                score+=5
                            ts=p.stat().st_mtime
                        except Exception:
                            ts=0
                        result.append((score,ts,cat,p,rel))
                    if scanned>30000:
                        break

                result.sort(key=lambda x:(x[0],x[1]),reverse=True)
                _position_project_files_cache[key]=list(result)
                return result
            except Exception:
                return []
'''


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.25"' in s:
        return 0
    if 'APP_VERSION = "1.4.24"' not in s:
        raise RuntimeError('Update 1.4.25 erwartet Projektzentrale 1.4.24. Es wurde nichts verändert.')
    original=s
    s=s.replace('APP_VERSION = "1.4.24"','APP_VERSION = "1.4.25"',1)

    # Remove the experimental MicroFe card-click/debug logic and keep the stable
    # project + application-register start only.
    start=s.find('        def _mb_open_project_application(')
    end=s.find('        def _detail_add_link(text,label,path,tag_index):',start)
    if start<0 or end<0:
        raise RuntimeError('1.4.25 Marker für mb-Starthelfer fehlt.')
    s=s[:start]+OPEN_HELPER+'\n'+FILE_HELPER+'\n'+s[end:]

    old_filter="matches=[hit for hit in matches if _position_file_is_exact(r.get('pos'), hit[4] if len(hit)>4 else hit[3])]"
    new_filter="""matches=[hit for hit in matches if _position_file_is_exact(r.get('pos'), hit[4] if len(hit)>4 else hit[3])]
                _seen_files=set()
                for _hit in matches:
                    try:_seen_files.add(str(Path(_hit[3]).resolve()).lower())
                    except Exception:_seen_files.add(str(_hit[3]).lower())
                for _hit in _position_project_files(folder,r.get('pos')):
                    try:_key=str(Path(_hit[3]).resolve()).lower()
                    except Exception:_key=str(_hit[3]).lower()
                    if _key not in _seen_files:
                        matches.append(_hit); _seen_files.add(_key)
                matches.sort(key=lambda _h:((_h[0] if len(_h)>0 else 0),(_h[1] if len(_h)>1 else 0)),reverse=True)"""
    if old_filter not in s:
        raise RuntimeError('1.4.25 Marker für Dateizuordnung fehlt.')
    s=s.replace(old_filter,new_filter,1)

    s=s.replace(
        'Hinweis 1.4.24: MicroFe-Start protokolliert nun die tatsächlich sichtbaren UI-Elemente und Klickziele. Bei einem Fehlschlag wird auf dem Desktop Engbers_MB_MicroFe_Debug.txt erzeugt; mb-Daten und Registry bleiben unverändert.',
        'Hinweis 1.4.25: Die Positionsakte durchsucht jetzt zusätzlich den gesamten Projektordner nach Dateien mit exakt passender Positionskennung und ordnet sie automatisch den Gruppen Prüfstatik, Pläne/CAD, Eigene Nachweise oder Dokumente zu. Der mb-Start endet stabil im richtigen BauStatik-/MicroFe-Register.'
    )
    s=s.replace(
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb und Windows-Dateizuordnungen werden read-only gelesen. Positionsakte 1.4.24 protokolliert beim MicroFe-Start sichtbare UI-Elemente und Klickziele in eine Desktop-Diagnosedatei; mb-Daten und Registry bleiben unverändert.',
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb, Windows-Dateizuordnungen und Projektdateien werden ausschließlich read-only gelesen. Positionsakte 1.4.25 ergänzt eine rekursive, positionsgenaue Dateizuordnung; mb-Daten und Registry bleiben unverändert.'
    )

    required=(
        'APP_VERSION = "1.4.25"',
        "def _mb_open_project_application(folder,app_name,model_hint='')",
        'def _position_project_files(folder,pos)',
        "cat='Prüfstatik'",
        "cat='Pläne / CAD'",
        "cat='Eigene Nachweise'",
        "for _hit in _position_project_files(folder,r.get('pos'))",
        '• ProjektManager öffnen (nur Projekt)',
    )
    if not all(x in s for x in required):
        raise RuntimeError('Patch-Ergebnis 1.4.25 unvollständig. Es wurde nichts verändert.')
    if s==original:
        raise RuntimeError('Keine Änderung erzeugt.')

    tmp=APP.with_name('app.py.1425.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.v1424_vor_1425_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp.replace(APP)
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1425_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        print('FEHLER:',e)
        raise SystemExit(1)
