from pathlib import Path
import py_compile, sys

ROOT=Path(sys.argv[1]).resolve()
APP=ROOT/"app.py"
POST=ROOT/"post_update.py"
ARCH=ROOT/"outlook_archive_v1823.py"
DIAG=ROOT/"outlook_diag_v1828.py"

def one(t,a,b,label):
    c=t.count(a)
    if c!=1:
        raise RuntimeError(f"{label}: {c}")
    return t.replace(a,b,1)

app=APP.read_text(encoding="utf-8")
app=one(app,'APP_VERSION = "1.8.28"','APP_VERSION = "1.8.29"',"app version")
APP.write_text(app,encoding="utf-8")

arch=ARCH.read_text(encoding="utf-8")
if "import tempfile" not in arch:
    arch=arch.replace("import subprocess\n","import subprocess\nimport tempfile\n",1)

start=arch.index("def _powershell(script: str, env_extra=None, timeout=45) -> str:\n")
end=arch.index("\n\ndef ensure_schema",start)
new_func='''def _powershell(script: str, env_extra=None, timeout=45) -> str:
    if os.name != "nt":
        raise RuntimeError("Die Outlook-Anbindung ist nur unter Windows verfügbar.")

    env = os.environ.copy()
    if env_extra:
        env.update({str(k): str(v) for k, v in env_extra.items()})

    temp_dir = Path(tempfile.mkdtemp(prefix="engbers_outlook_"))
    ps1 = temp_dir / "run.ps1"
    result_file = temp_dir / "result.txt"
    env["PZ_RESULT_FILE"] = str(result_file)

    wrapper = (
        "$ErrorActionPreference = 'Stop'\\r\\n"
        "& {\\r\\n"
        + script
        + "\\r\\n} | Out-File -LiteralPath $env:PZ_RESULT_FILE -Encoding utf8\\r\\n"
    )
    ps1.write_text(wrapper, encoding="utf-8-sig")

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1)],
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=flags,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            if detail:
                detail = detail.splitlines()[-1]
            raise RuntimeError(detail or "Outlook konnte nicht gelesen werden.")

        if result_file.exists():
            try:
                return result_file.read_text(encoding="utf-8-sig", errors="replace").strip()
            except Exception:
                return result_file.read_text(encoding="utf-8", errors="replace").strip()
        return (result.stdout or "").strip()
    except FileNotFoundError as exc:
        raise RuntimeError("Windows PowerShell wurde nicht gefunden.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Outlook hat nicht rechtzeitig reagiert.") from exc
    finally:
        try:
            for p in temp_dir.iterdir():
                try:
                    p.unlink()
                except Exception:
                    pass
            temp_dir.rmdir()
        except Exception:
            pass
'''
arch=arch[:start]+new_func+arch[end:]
ARCH.write_text(arch,encoding="utf-8")

diag=DIAG.read_text(encoding="utf-8")
start=diag.index("def _run_diag() -> str:\n")
end=diag.index("\n\ndef open_outlook_diagnostics",start)
new_diag='''def _run_diag() -> str:
    from outlook_archive_v1823 import _powershell

    script = r\'\'\'
$ErrorActionPreference = "Stop"
try { $outlook = [Runtime.InteropServices.Marshal]::GetActiveObject("Outlook.Application") }
catch {
    $t = [type]::GetTypeFromProgID("Outlook.Application")
    if ($null -eq $t) { throw "Outlook (klassisch) wurde nicht gefunden." }
    $outlook = [Activator]::CreateInstance($t)
}
$ns = $outlook.GetNamespace("MAPI")
$lines = New-Object System.Collections.Generic.List[string]

function Add-Line([string]$s) { [void]$lines.Add($s) }
function C([object]$v) { if ($null -eq $v) { return "" }; return [string]$v }

Add-Line "OUTLOOK-DIAGNOSE"
Add-Line ("Stores: " + $ns.Stores.Count)
try { Add-Line ("Accounts: " + $ns.Accounts.Count) } catch { Add-Line "Accounts: nicht lesbar" }
Add-Line ""

function Walk([object]$folder, [int]$depth, [string]$prefix) {
    if ($null -eq $folder -or $depth -lt 0) { return }
    $name = ""
    $path = ""
    $count = "?"
    try { $name = C $folder.Name } catch {}
    try { $path = C $folder.FolderPath } catch {}
    try { $count = C $folder.Items.Count } catch {}
    Add-Line ($prefix + "- " + $name + " | Elemente: " + $count + " | Pfad: " + $path)
    if ($depth -eq 0) { return }
    try { $children = $folder.Folders } catch { return }
    for ($i=1; $i -le $children.Count; $i++) {
        try { $child = $children.Item($i) } catch { continue }
        Walk $child ($depth-1) ($prefix + "  ")
    }
}

$stores = $ns.Stores
for ($s=1; $s -le $stores.Count; $s++) {
    $store = $null
    try { $store = $stores.Item($s) } catch {}
    if ($null -eq $store) { continue }

    Add-Line ("KONTO " + $s + ": " + (C $store.DisplayName))
    try {
        $f = $store.GetDefaultFolder(6)
        Add-Line ("  Standard-Posteingang: OK | Elemente: " + $f.Items.Count + " | " + (C $f.FolderPath))
    } catch {
        Add-Line ("  Standard-Posteingang: FEHLER | " + $_.Exception.Message)
    }
    try {
        $f = $store.GetDefaultFolder(5)
        Add-Line ("  Standard-Gesendet: OK | Elemente: " + $f.Items.Count + " | " + (C $f.FolderPath))
    } catch {
        Add-Line ("  Standard-Gesendet: FEHLER | " + $_.Exception.Message)
    }
    Add-Line "  Ordnerstruktur:"
    try { Walk ($store.GetRootFolder()) 4 "    " } catch { Add-Line ("    FEHLER: " + $_.Exception.Message) }
    Add-Line ""
}

$lines -join [Environment]::NewLine
\'\'\'
    return _powershell(script, timeout=45) or "Keine Diagnosedaten zurückgegeben."
'''
diag=diag[:start]+new_diag+diag[end:]
DIAG.write_text(diag,encoding="utf-8")

post=POST.read_text(encoding="utf-8")
post=post.replace("update_1828_install.log","update_1829_install.log")
post=post.replace("update_1828_error.txt","update_1829_error.txt")
post=one(post,'APP_VERSION = "1.8.28"','APP_VERSION = "1.8.29"',"post version")
post=post.replace("OK: Update 1.8.28 erfolgreich installiert.","OK: Update 1.8.29 erfolgreich installiert.")
POST.write_text(post,encoding="utf-8")

for p in (APP,POST,ARCH,DIAG):
    py_compile.compile(str(p),doraise=True)

print("OK 1.8.29 PowerShell temp-file transport")
