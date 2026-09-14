from pathlib import Path
import datetime
import py_compile
import shutil

APP=Path(__file__).resolve().parent/'app.py'


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.20"' in s:
        return 0
    if 'APP_VERSION = "1.4.19"' not in s:
        raise RuntimeError('Update 1.4.20 erwartet Projektzentrale 1.4.19. Es wurde nichts verändert.')
    original=s
    s=s.replace('APP_VERSION = "1.4.19"','APP_VERSION = "1.4.20"',1)

    old_add="""Add-Type -AssemblyName System.Windows.Forms
$project=$env:ENGBERS_MB_PROJECT
"""
    new_add="""Add-Type -AssemblyName System.Windows.Forms
Add-Type @\"\nusing System;\nusing System.Runtime.InteropServices;\npublic static class EngbersMouse {\n    [DllImport(\"user32.dll\")] public static extern bool SetCursorPos(int X, int Y);\n    [DllImport(\"user32.dll\")] public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, UIntPtr extra);\n}\n\"@
$project=$env:ENGBERS_MB_PROJECT
"""
    if old_add not in s:
        raise RuntimeError('1.4.20 Marker für UI-Automation-Initialisierung fehlt.')
    s=s.replace(old_add,new_add,1)

    old_func="""function Try-OpenElement($el) {
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
"""
    new_func="""function Try-OpenElement($el) {
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

    # mb exposes the visible model title, but the surrounding card does not
    # always publish Invoke/Selection patterns. In that case use the UIA
    # bounding rectangle of the *matched title itself* and perform the same
    # double-click the user would do. No project/model data is modified.
    try {
        $r=$el.Current.BoundingRectangle
        if($r.Width -gt 1 -and $r.Height -gt 1) {
            try { $window.SetFocus() } catch {}
            $x=[int]($r.Left + ($r.Width / 2.0))
            $y=[int]($r.Top + ($r.Height / 2.0))
            [EngbersMouse]::SetCursorPos($x,$y) | Out-Null
            Start-Sleep -Milliseconds 120
            for($k=0; $k -lt 2; $k++) {
                [EngbersMouse]::mouse_event(0x0002,0,0,0,[UIntPtr]::Zero)
                [EngbersMouse]::mouse_event(0x0004,0,0,0,[UIntPtr]::Zero)
                if($k -eq 0) { Start-Sleep -Milliseconds 110 }
            }
            return $true
        }
    } catch {}
    return $false
}
"""
    if old_func not in s:
        raise RuntimeError('1.4.20 Marker für MicroFe-Modellöffnung fehlt.')
    s=s.replace(old_func,new_func,1)

    s=s.replace(
        'Hinweis 1.4.19: Nach dem Projektstart und der Registerwahl sucht Windows UI Automation bei MicroFe zusätzlich die Modellkarte der ausgewählten Position (z.B. E.01.D) und öffnet sie best-effort. BauStatik bleibt zunächst auf dem richtigen Register.',
        'Hinweis 1.4.20: Die MicroFe-Modellkarte wird nach der UI-Automation-Suche zusätzlich über ihre sichtbare Bildschirmposition doppelt angeklickt, falls mb für die Karte keine Invoke-/Selection-Aktion bereitstellt. BauStatik bleibt zunächst auf dem richtigen Register.'
    )
    s=s.replace(
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb und Windows-Dateizuordnungen werden read-only gelesen. Positionsakte 1.4.19 nutzt UI Automation zusätzlich zur best-effort Auswahl der MicroFe-Modellkarte; mb-Daten und Registry bleiben unverändert.',
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb und Windows-Dateizuordnungen werden read-only gelesen. Positionsakte 1.4.20 nutzt UI Automation und als Fallback einen Doppelklick auf die gefundene MicroFe-Modellkarte; mb-Daten und Registry bleiben unverändert.'
    )

    required=(
        'APP_VERSION = "1.4.20"',
        'public static class EngbersMouse',
        '[EngbersMouse]::SetCursorPos',
        '[EngbersMouse]::mouse_event',
        'BoundingRectangle',
        "m=posid:_mb_open_project_application(f,a,m)",
        '• ProjektManager öffnen (nur Projekt)',
    )
    if not all(x in s for x in required):
        raise RuntimeError('Patch-Ergebnis 1.4.20 unvollständig. Es wurde nichts verändert.')
    if s==original:
        raise RuntimeError('Keine Änderung erzeugt.')

    tmp=APP.with_name('app.py.1420.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.v1419_vor_1420_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp.replace(APP)
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1420_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        print('FEHLER:',e)
        raise SystemExit(1)
