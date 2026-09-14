from pathlib import Path
import datetime
import py_compile
import shutil

APP=Path(__file__).resolve().parent/'app.py'


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.24"' in s:
        return 0
    if 'APP_VERSION = "1.4.23"' not in s:
        raise RuntimeError('Update 1.4.24 erwartet Projektzentrale 1.4.23. Es wurde nichts verändert.')
    original=s
    s=s.replace('APP_VERSION = "1.4.23"','APP_VERSION = "1.4.24"',1)

    start=s.find('function Click-Point($x,$y,$double=$false) {')
    loop=s.find('for($round=0; $round -lt 28; $round++) {',start)
    end=s.find('exit 4',loop)
    if start < 0 or loop < 0 or end < 0:
        raise RuntimeError('1.4.24 Marker für MicroFe-Diagnose fehlt.')

    new_funcs=r'''$debugFile=Join-Path ([Environment]::GetFolderPath('Desktop')) 'Engbers_MB_MicroFe_Debug.txt'
try { Set-Content -Path $debugFile -Value ('Engbers Projektzentrale 1.4.24 - ' + (Get-Date -Format s)) -Encoding UTF8 } catch {}
function Dbg($text) { try { Add-Content -Path $debugFile -Value $text -Encoding UTF8 } catch {} }
function Desc($el) {
    try {
        $r=$el.Current.BoundingRectangle
        return ('Name="{0}" Type={1} Class="{2}" AutoId="{3}" Offscreen={4} Rect={5},{6},{7},{8}' -f $el.Current.Name,$el.Current.ControlType.ProgrammaticName,$el.Current.ClassName,$el.Current.AutomationId,$el.Current.IsOffscreen,[int]$r.Left,[int]$r.Top,[int]$r.Width,[int]$r.Height)
    } catch { return 'Element konnte nicht beschrieben werden.' }
}
function Click-Point($x,$y,$double=$false) {
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
    } catch { Dbg ('Click-Point FEHLER: '+$_.Exception.Message); return $false }
}
function Click-UiaElement($el,$double=$false) {
    try {
        $r=$el.Current.BoundingRectangle
        if($el.Current.IsOffscreen -or $r.Width -le 1 -or $r.Height -le 1) { return $false }
        Dbg ('KLICK: '+(Desc $el))
        return (Click-Point ($r.Left + ($r.Width/2.0)) ($r.Top + ($r.Height/2.0)) $double)
    } catch { return $false }
}
function Get-CardElement($el) {
    $cur=$el
    $best=$null
    $bestArea=[double]::MaxValue
    for($j=0; $j -lt 9 -and $null -ne $cur; $j++) {
        try {
            $r=$cur.Current.BoundingRectangle
            $area=[double]$r.Width*[double]$r.Height
            Dbg ('ANCESTOR '+$j+': '+(Desc $cur))
            if(-not $cur.Current.IsOffscreen -and $r.Width -ge 180 -and $r.Width -le 700 -and $r.Height -ge 80 -and $r.Height -le 450 -and $area -lt $bestArea) {
                $best=$cur; $bestArea=$area
            }
        } catch {}
        try { $cur=$walker.GetParent($cur) } catch { $cur=$null }
    }
    if($null -ne $best) { Dbg ('KARTE: '+(Desc $best)); return $best }
    Dbg 'Keine Karten-Huelle gefunden; Titel selbst wird verwendet.'
    return $el
}
function Try-PhysicalUseButton() {
    try {
        $all2=$window.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
        $found=0
        foreach($b in $all2) {
            $bn=$b.Current.Name
            if($bn -ne 'Verwenden') { continue }
            $found++
            Dbg ('VERWENDEN-KANDIDAT: '+(Desc $b))
            try {
                $r=$b.Current.BoundingRectangle
                if(-not $b.Current.IsOffscreen -and $r.Width -gt 5 -and $r.Height -gt 5) {
                    return (Click-Point ($r.Left + ($r.Width/2.0)) ($r.Top + ($r.Height/2.0)) $false)
                }
            } catch {}
        }
        Dbg ('Verwenden-Kandidaten gesamt: '+$found)
    } catch { Dbg ('Try-PhysicalUseButton FEHLER: '+$_.Exception.Message) }
    return $false
}
function MicroFe-WindowOpened() {
    try {
        $wins=$root.FindAll([System.Windows.Automation.TreeScope]::Children,[System.Windows.Automation.Condition]::TrueCondition)
        foreach($w in $wins) {
            $n=$w.Current.Name
            if(-not [string]::IsNullOrWhiteSpace($n)) { Dbg ('TOPWINDOW: '+$n) }
            if($n -like '*MicroFe*' -and $n -notlike '*ProjektManager*') { return $true }
        }
    } catch {}
    return $false
}
function Try-OpenElement($el) {
    Dbg ('MODELL-KANDIDAT: '+(Desc $el))
    try {
        try {
            $hwnd=[IntPtr]$window.Current.NativeWindowHandle
            if($hwnd -ne [IntPtr]::Zero) { [EngbersMouse]::SetForegroundWindow($hwnd) | Out-Null; Start-Sleep -Milliseconds 180 }
        } catch { try { $window.SetFocus() } catch {} }

        # First click the visible title itself. On mb cards this is often more
        # reliable for selection than the geometric card centre.
        if(Click-UiaElement $el $false) {
            Start-Sleep -Milliseconds 350
            if(Try-PhysicalUseButton) {
                for($v=0; $v -lt 16; $v++) { Start-Sleep -Milliseconds 250; if(MicroFe-WindowOpened) { Dbg 'ERFOLG nach Titel + Verwenden'; return $true } }
            }
        }

        # Then try the card ancestor near its upper-left content area.
        $card=Get-CardElement $el
        try {
            $r=$card.Current.BoundingRectangle
            if(-not $card.Current.IsOffscreen -and $r.Width -gt 20 -and $r.Height -gt 20) {
                Dbg ('Karte gezielt oben links: '+(Desc $card))
                Click-Point ($r.Left+45) ($r.Top+38) $false | Out-Null
                Start-Sleep -Milliseconds 350
                if(Try-PhysicalUseButton) {
                    for($v=0; $v -lt 16; $v++) { Start-Sleep -Milliseconds 250; if(MicroFe-WindowOpened) { Dbg 'ERFOLG nach Karte + Verwenden'; return $true } }
                }
            }
        } catch {}

        # Last physical attempt: double-click title exactly.
        if(Click-UiaElement $el $true) {
            for($v=0; $v -lt 16; $v++) { Start-Sleep -Milliseconds 250; if(MicroFe-WindowOpened) { Dbg 'ERFOLG nach Titel-Doppelklick'; return $true } }
        }
    } catch { Dbg ('Try-OpenElement FEHLER: '+$_.Exception.Message) }
    Dbg 'Kandidat ohne Erfolg.'
    return $false
}

'''
    s=s[:start]+new_funcs+s[loop:]

    loop=s.find('for($round=0; $round -lt 28; $round++) {',s.find(new_funcs[:30]))
    end=s.find('exit 4',loop)
    new_loop=r'''Dbg ('Projekt='+$project+' App='+$wanted+' Modell='+$model)
$matched=0
for($round=0; $round -lt 32; $round++) {
    $all=$window.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
    foreach($el in $all) {
        $name=$el.Current.Name
        if([string]::IsNullOrWhiteSpace($name)) { continue }
        $n=$name.Trim()
        if($n -eq $model -or $n -like ($model+' *')) {
            try { if($el.Current.IsOffscreen) { continue } } catch {}
            $matched++
            if(Try-OpenElement $el) { exit 0 }
        }
    }
    if($round -eq 4 -or $round -eq 16 -or $round -eq 31) { Dbg ('Suchrunde '+$round+' Treffer bisher='+$matched) }
    Start-Sleep -Milliseconds 250
}
Dbg ('KEIN ERFOLG. Treffer gesamt='+$matched)
try {
    Dbg '--- SICHTBARE BENANNTE ELEMENTE (Auszug) ---'
    $all=$window.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
    $c=0
    foreach($el in $all) {
        if($c -ge 350) { break }
        try {
            $n=$el.Current.Name
            if([string]::IsNullOrWhiteSpace($n) -or $el.Current.IsOffscreen) { continue }
            Dbg (Desc $el); $c++
        } catch {}
    }
} catch {}
exit 4'''
    s=s[:loop]+new_loop+s[end+len('exit 4'):]

    s=s.replace(
        'Hinweis 1.4.23: Bei MicroFe wird jetzt die tatsächliche Kartenfläche statt nur der Titelzeile angeklickt. Anschließend wird „Verwenden“ physisch angeklickt und erst nach Erkennen eines geöffneten MicroFe-Fensters Erfolg gemeldet.',
        'Hinweis 1.4.24: MicroFe-Start protokolliert nun die tatsächlich sichtbaren UI-Elemente und Klickziele. Bei einem Fehlschlag wird auf dem Desktop Engbers_MB_MicroFe_Debug.txt erzeugt; mb-Daten und Registry bleiben unverändert.'
    )
    s=s.replace(
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb und Windows-Dateizuordnungen werden read-only gelesen. Positionsakte 1.4.23 klickt die gefundene MicroFe-Kartenfläche und den sichtbaren ProjektManager-Befehl „Verwenden“ physisch; mb-Daten und Registry bleiben unverändert.',
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb und Windows-Dateizuordnungen werden read-only gelesen. Positionsakte 1.4.24 protokolliert beim MicroFe-Start sichtbare UI-Elemente und Klickziele in eine Desktop-Diagnosedatei; mb-Daten und Registry bleiben unverändert.'
    )

    required=(
        'APP_VERSION = "1.4.24"',
        'Engbers_MB_MicroFe_Debug.txt',
        'function Dbg($text)',
        'MODELL-KANDIDAT:',
        'VERWENDEN-KANDIDAT:',
        'SICHTBARE BENANNTE ELEMENTE',
        'for($round=0; $round -lt 32; $round++)',
        "m=posid:_mb_open_project_application(f,a,m)",
    )
    if not all(x in s for x in required):
        raise RuntimeError('Patch-Ergebnis 1.4.24 unvollständig. Es wurde nichts verändert.')
    if s==original:
        raise RuntimeError('Keine Änderung erzeugt.')

    tmp=APP.with_name('app.py.1424.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.v1423_vor_1424_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp.replace(APP)
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1424_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        print('FEHLER:',e)
        raise SystemExit(1)
