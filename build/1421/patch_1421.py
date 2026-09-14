from pathlib import Path
import datetime
import py_compile
import shutil

APP=Path(__file__).resolve().parent/'app.py'


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.21"' in s:
        return 0
    if 'APP_VERSION = "1.4.20"' not in s:
        raise RuntimeError('Update 1.4.21 erwartet Projektzentrale 1.4.20. Es wurde nichts verändert.')
    original=s
    s=s.replace('APP_VERSION = "1.4.20"','APP_VERSION = "1.4.21"',1)

    # 1.4.20 could stop after a UIA Selection/Invoke call that technically
    # succeeded although mb did not actually open the model. 1.4.21 makes the
    # physical double-click on the matched visible model title the PRIMARY
    # action. This mirrors the user's proven manual action exactly.
    old_decl='''    [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, UIntPtr extra);\n}\n\"@'''
    new_decl='''    [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, UIntPtr extra);\n    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);\n}\n\"@'''
    if old_decl not in s:
        raise RuntimeError('1.4.21 Marker für Maus-Helfer fehlt.')
    s=s.replace(old_decl,new_decl,1)

    start=s.find('function Try-OpenElement($el) {')
    end=s.find('for($round=0; $round -lt 12; $round++) {',start)
    if start < 0 or end < 0:
        raise RuntimeError('1.4.21 Marker für MicroFe-Modellöffnung fehlt.')

    new_func=r'''function Try-OpenElement($el) {
    # PRIMARY PATH: physically double-click the visible UIA element. mb's
    # model cards are custom controls and may report Selection/Invoke success
    # without opening the model. A real double-click is the proven user action.
    try {
        try {
            $hwnd=[IntPtr]$window.Current.NativeWindowHandle
            if($hwnd -ne [IntPtr]::Zero) {
                [EngbersMouse]::SetForegroundWindow($hwnd) | Out-Null
                Start-Sleep -Milliseconds 120
            }
        } catch { try { $window.SetFocus() } catch {} }

        $r=$el.Current.BoundingRectangle
        if($r.Width -gt 1 -and $r.Height -gt 1) {
            $x=[int]($r.Left + ($r.Width / 2.0))
            $y=[int]($r.Top + ($r.Height / 2.0))
            [EngbersMouse]::SetCursorPos($x,$y) | Out-Null
            Start-Sleep -Milliseconds 140
            for($k=0; $k -lt 2; $k++) {
                [EngbersMouse]::mouse_event(0x0002,0,0,0,[UIntPtr]::Zero)
                Start-Sleep -Milliseconds 35
                [EngbersMouse]::mouse_event(0x0004,0,0,0,[UIntPtr]::Zero)
                if($k -eq 0) { Start-Sleep -Milliseconds 105 }
            }
            return $true
        }
    } catch {}

    # Fallback only when no usable screen rectangle is exposed.
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

'''
    s=s[:start]+new_func+s[end:]

    s=s.replace(
        'Hinweis 1.4.20: Die MicroFe-Modellkarte wird nach der UI-Automation-Suche zusätzlich über ihre sichtbare Bildschirmposition doppelt angeklickt, falls mb für die Karte keine Invoke-/Selection-Aktion bereitstellt. BauStatik bleibt zunächst auf dem richtigen Register.',
        'Hinweis 1.4.21: Bei MicroFe wird die gefundene sichtbare Modellbezeichnung jetzt zuerst per echtem Doppelklick geöffnet. UI-Automation-Invoke/Selection dient nur noch als Fallback, weil mb diese Aktionen teils bestätigt, ohne das Modell tatsächlich zu öffnen.'
    )
    s=s.replace(
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb und Windows-Dateizuordnungen werden read-only gelesen. Positionsakte 1.4.20 nutzt UI Automation und als Fallback einen Doppelklick auf die gefundene MicroFe-Modellkarte; mb-Daten und Registry bleiben unverändert.',
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb und Windows-Dateizuordnungen werden read-only gelesen. Positionsakte 1.4.21 verwendet für MicroFe primär den sichtbaren Doppelklick auf die gefundene Modellbezeichnung; mb-Daten und Registry bleiben unverändert.'
    )

    required=(
        'APP_VERSION = "1.4.21"',
        'SetForegroundWindow',
        'PRIMARY PATH: physically double-click',
        '[EngbersMouse]::SetCursorPos',
        '[EngbersMouse]::mouse_event',
        'function Try-OpenElement($el)',
        "m=posid:_mb_open_project_application(f,a,m)",
        '• ProjektManager öffnen (nur Projekt)',
    )
    if not all(x in s for x in required):
        raise RuntimeError('Patch-Ergebnis 1.4.21 unvollständig. Es wurde nichts verändert.')
    if s==original:
        raise RuntimeError('Keine Änderung erzeugt.')

    tmp=APP.with_name('app.py.1421.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.v1420_vor_1421_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp.replace(APP)
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1421_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        print('FEHLER:',e)
        raise SystemExit(1)
