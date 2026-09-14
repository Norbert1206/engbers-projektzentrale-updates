from pathlib import Path
import datetime
import py_compile
import shutil

APP=Path(__file__).resolve().parent/'app.py'


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.22"' in s:
        return 0
    if 'APP_VERSION = "1.4.21"' not in s:
        raise RuntimeError('Update 1.4.22 erwartet Projektzentrale 1.4.21. Es wurde nichts verändert.')
    original=s
    s=s.replace('APP_VERSION = "1.4.21"','APP_VERSION = "1.4.22"',1)

    start=s.find('function Try-OpenElement($el) {')
    end=s.find('for($round=0; $round -lt 12; $round++) {',start)
    if start < 0 or end < 0:
        raise RuntimeError('1.4.22 Marker für MicroFe-Modellöffnung fehlt.')

    new_func=r'''function Click-UiaElement($el,$double=$false) {
    try {
        $r=$el.Current.BoundingRectangle
        if($r.Width -le 1 -or $r.Height -le 1) { return $false }
        $x=[int]($r.Left + ($r.Width / 2.0))
        $y=[int]($r.Top + ($r.Height / 2.0))
        [EngbersMouse]::SetCursorPos($x,$y) | Out-Null
        Start-Sleep -Milliseconds 120
        $count=1
        if($double) { $count=2 }
        for($k=0; $k -lt $count; $k++) {
            [EngbersMouse]::mouse_event(0x0002,0,0,0,[UIntPtr]::Zero)
            Start-Sleep -Milliseconds 35
            [EngbersMouse]::mouse_event(0x0004,0,0,0,[UIntPtr]::Zero)
            if($k -eq 0 -and $count -gt 1) { Start-Sleep -Milliseconds 105 }
        }
        return $true
    } catch { return $false }
}

function Try-UseButton() {
    # The ProjectManager ribbon exposes a real "Verwenden" command. Selecting
    # the model card first and then invoking this command mirrors the normal
    # ProjectManager workflow more reliably than a double-click on mb's custom
    # card surface.
    try {
        $all2=$window.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
        foreach($b in $all2) {
            $bn=$b.Current.Name
            if($bn -ne 'Verwenden') { continue }
            try {
                $p=$b.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
                $p.Invoke()
                return $true
            } catch {}
            try {
                $p=$b.GetCurrentPattern([System.Windows.Automation.LegacyIAccessiblePattern]::Pattern)
                $p.DoDefaultAction()
                return $true
            } catch {}
            if(Click-UiaElement $b $false) { return $true }
        }
    } catch {}
    return $false
}

function Try-OpenElement($el) {
    try {
        try {
            $hwnd=[IntPtr]$window.Current.NativeWindowHandle
            if($hwnd -ne [IntPtr]::Zero) {
                [EngbersMouse]::SetForegroundWindow($hwnd) | Out-Null
                Start-Sleep -Milliseconds 180
            }
        } catch { try { $window.SetFocus() } catch {} }

        # PRIMARY PATH: select the requested MicroFe card and use the ribbon
        # command "Verwenden". On the user's ProjectManager this is the native
        # command for opening the selected model.
        if(Click-UiaElement $el $false) {
            Start-Sleep -Milliseconds 350
            if(Try-UseButton) { return $true }
        }

        # SECOND PATH: try a physical double-click on the matched model title.
        if(Click-UiaElement $el $true) { return $true }
    } catch {}

    # Last-resort UI Automation patterns.
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
        'Hinweis 1.4.21: Bei MicroFe wird die gefundene sichtbare Modellbezeichnung jetzt zuerst per echtem Doppelklick geöffnet. UI-Automation-Invoke/Selection dient nur noch als Fallback, weil mb diese Aktionen teils bestätigt, ohne das Modell tatsächlich zu öffnen.',
        'Hinweis 1.4.22: Bei MicroFe wird die gefundene Modellkarte zuerst ausgewählt und anschließend der native ProjektManager-Befehl „Verwenden“ ausgelöst. Doppelklick und UI-Automation bleiben als Fallback erhalten.'
    )
    s=s.replace(
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb und Windows-Dateizuordnungen werden read-only gelesen. Positionsakte 1.4.21 verwendet für MicroFe primär den sichtbaren Doppelklick auf die gefundene Modellbezeichnung; mb-Daten und Registry bleiben unverändert.',
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb und Windows-Dateizuordnungen werden read-only gelesen. Positionsakte 1.4.22 wählt die MicroFe-Modellkarte und startet sie über den ProjektManager-Befehl „Verwenden“; mb-Daten und Registry bleiben unverändert.'
    )

    required=(
        'APP_VERSION = "1.4.22"',
        'function Click-UiaElement($el,$double=$false)',
        'function Try-UseButton()',
        "$bn -ne 'Verwenden'",
        'if(Click-UiaElement $el $false)',
        'if(Try-UseButton) { return $true }',
        'function Try-OpenElement($el)',
        "m=posid:_mb_open_project_application(f,a,m)",
        '• ProjektManager öffnen (nur Projekt)',
    )
    if not all(x in s for x in required):
        raise RuntimeError('Patch-Ergebnis 1.4.22 unvollständig. Es wurde nichts verändert.')
    if s==original:
        raise RuntimeError('Keine Änderung erzeugt.')

    tmp=APP.with_name('app.py.1422.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.v1421_vor_1422_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp.replace(APP)
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1422_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        print('FEHLER:',e)
        raise SystemExit(1)
