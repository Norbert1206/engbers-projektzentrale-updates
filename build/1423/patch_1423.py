from pathlib import Path
import datetime
import py_compile
import shutil

APP=Path(__file__).resolve().parent/'app.py'


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.23"' in s:
        return 0
    if 'APP_VERSION = "1.4.22"' not in s:
        raise RuntimeError('Update 1.4.23 erwartet Projektzentrale 1.4.22. Es wurde nichts verändert.')
    original=s
    s=s.replace('APP_VERSION = "1.4.22"','APP_VERSION = "1.4.23"',1)

    start=s.find('function Click-UiaElement($el,$double=$false) {')
    end=s.find('for($round=0; $round -lt 12; $round++) {',start)
    if start < 0 or end < 0:
        raise RuntimeError('1.4.23 Marker für MicroFe-Modellöffnung fehlt.')

    new_func=r'''function Click-Point($x,$y,$double=$false) {
    try {
        [EngbersMouse]::SetCursorPos([int]$x,[int]$y) | Out-Null
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

function Get-CardElement($el) {
    # The title text itself is often a tiny child. Walk upwards and choose the
    # smallest plausible card-sized ancestor, but never the whole workspace.
    $cur=$el
    $best=$null
    $bestArea=[double]::MaxValue
    for($j=0; $j -lt 8 -and $null -ne $cur; $j++) {
        try {
            $r=$cur.Current.BoundingRectangle
            $area=[double]$r.Width*[double]$r.Height
            if($r.Width -ge 180 -and $r.Width -le 700 -and $r.Height -ge 80 -and $r.Height -le 450 -and $area -lt $bestArea) {
                $best=$cur
                $bestArea=$area
            }
        } catch {}
        try { $cur=$walker.GetParent($cur) } catch { $cur=$null }
    }
    if($null -ne $best) { return $best }
    return $el
}

function Click-UiaElement($el,$double=$false) {
    try {
        $r=$el.Current.BoundingRectangle
        if($r.Width -le 1 -or $r.Height -le 1) { return $false }
        return (Click-Point ($r.Left + ($r.Width/2.0)) ($r.Top + ($r.Height/2.0)) $double)
    } catch { return $false }
}

function Try-PhysicalUseButton() {
    # Do not trust InvokePattern success here: mb can acknowledge Invoke without
    # doing anything. Physically click the visible ribbon command instead.
    try {
        $all2=$window.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
        foreach($b in $all2) {
            $bn=$b.Current.Name
            if($bn -ne 'Verwenden') { continue }
            try {
                $r=$b.Current.BoundingRectangle
                if($r.Width -gt 5 -and $r.Height -gt 5) {
                    return (Click-Point ($r.Left + ($r.Width/2.0)) ($r.Top + ($r.Height/2.0)) $false)
                }
            } catch {}
        }
    } catch {}
    return $false
}

function MicroFe-WindowOpened() {
    try {
        $wins=$root.FindAll([System.Windows.Automation.TreeScope]::Children,[System.Windows.Automation.Condition]::TrueCondition)
        foreach($w in $wins) {
            $n=$w.Current.Name
            if([string]::IsNullOrWhiteSpace($n)) { continue }
            if($n -like '*MicroFe*' -and $n -notlike '*ProjektManager*') { return $true }
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

        $card=Get-CardElement $el

        # PRIMARY PATH: click the actual card surface, then physically click
        # the native ProjectManager command Verwenden. Only report success if
        # a MicroFe window really appears.
        if(Click-UiaElement $card $false) {
            Start-Sleep -Milliseconds 300
            if(Try-PhysicalUseButton) {
                for($v=0; $v -lt 20; $v++) {
                    Start-Sleep -Milliseconds 250
                    if(MicroFe-WindowOpened) { return $true }
                }
            }
        }

        # SECOND PATH: physical double-click on the whole card, not the title.
        if(Click-UiaElement $card $true) {
            for($v=0; $v -lt 20; $v++) {
                Start-Sleep -Milliseconds 250
                if(MicroFe-WindowOpened) { return $true }
            }
        }
    } catch {}

    # Last-resort UI Automation patterns. These are intentionally last because
    # mb may report them as successful without opening the model.
    $cur=$el
    for($j=0; $j -lt 7 -and $null -ne $cur; $j++) {
        try {
            $p=$cur.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
            $p.Invoke()
            Start-Sleep -Milliseconds 600
            if(MicroFe-WindowOpened) { return $true }
        } catch {}
        try {
            $p=$cur.GetCurrentPattern([System.Windows.Automation.LegacyIAccessiblePattern]::Pattern)
            $p.DoDefaultAction()
            Start-Sleep -Milliseconds 600
            if(MicroFe-WindowOpened) { return $true }
        } catch {}
        try { $cur=$walker.GetParent($cur) } catch { $cur=$null }
    }
    return $false
}

'''
    s=s[:start]+new_func+s[end:]

    # Give the custom cards more time to appear after switching the register.
    s=s.replace('for($round=0; $round -lt 12; $round++) {','for($round=0; $round -lt 28; $round++) {',1)

    s=s.replace(
        'Hinweis 1.4.22: Bei MicroFe wird die gefundene Modellkarte zuerst ausgewählt und anschließend der native ProjektManager-Befehl „Verwenden“ ausgelöst. Doppelklick und UI-Automation bleiben als Fallback erhalten.',
        'Hinweis 1.4.23: Bei MicroFe wird jetzt die tatsächliche Kartenfläche statt nur der Titelzeile angeklickt. Anschließend wird „Verwenden“ physisch angeklickt und erst nach Erkennen eines geöffneten MicroFe-Fensters Erfolg gemeldet.'
    )
    s=s.replace(
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb und Windows-Dateizuordnungen werden read-only gelesen. Positionsakte 1.4.22 wählt die MicroFe-Modellkarte und startet sie über den ProjektManager-Befehl „Verwenden“; mb-Daten und Registry bleiben unverändert.',
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb und Windows-Dateizuordnungen werden read-only gelesen. Positionsakte 1.4.23 klickt die gefundene MicroFe-Kartenfläche und den sichtbaren ProjektManager-Befehl „Verwenden“ physisch; mb-Daten und Registry bleiben unverändert.'
    )

    required=(
        'APP_VERSION = "1.4.23"',
        'function Get-CardElement($el)',
        'function Try-PhysicalUseButton()',
        'function MicroFe-WindowOpened()',
        '$card=Get-CardElement $el',
        'for($round=0; $round -lt 28; $round++)',
        'function Try-OpenElement($el)',
        "m=posid:_mb_open_project_application(f,a,m)",
    )
    if not all(x in s for x in required):
        raise RuntimeError('Patch-Ergebnis 1.4.23 unvollständig. Es wurde nichts verändert.')
    if s==original:
        raise RuntimeError('Keine Änderung erzeugt.')

    tmp=APP.with_name('app.py.1423.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.v1422_vor_1423_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp.replace(APP)
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1423_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        print('FEHLER:',e)
        raise SystemExit(1)
