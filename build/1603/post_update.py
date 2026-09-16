from pathlib import Path
import importlib
import os
import runpy
import shutil
import subprocess
import sys
import traceback

BASE=Path(__file__).resolve().parent
VENDOR=BASE/'_vendor'
PATCH=BASE/'patch_1603.py'
LOG=BASE/'pymupdf_install_1603.log'
ERR=BASE/'pymupdf_install_1603_error.txt'


def _flags():
    return getattr(subprocess,'CREATE_NO_WINDOW',0) if os.name=='nt' else 0


def _run(cmd,timeout=240):
    p=subprocess.run(
        cmd,
        cwd=str(BASE),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors='replace',
        timeout=timeout,
        creationflags=_flags())
    return p.returncode,p.stdout or ''


def _local_engine_ok():
    code=(
        "import sys; "
        f"sys.path.insert(0,{str(VENDOR)!r}); "
        "import pymupdf; "
        "print(pymupdf.__file__)"
    )
    rc,out=_run([sys.executable,'-c',code],timeout=45)
    if rc!=0:
        return False,out
    try:
        loaded=Path(out.strip().splitlines()[-1]).resolve()
        root=VENDOR.resolve()
        ok=(loaded==root or root in loaded.parents)
    except Exception:
        ok=False
    return ok,out


def _install_engine():
    VENDOR.mkdir(parents=True,exist_ok=True)
    ok,out=_local_engine_ok()
    transcript=['Vorprüfung:\n'+out]
    if ok:
        LOG.write_text('PyMuPDF lokal bereits vorhanden.\n\n'+out,encoding='utf-8')
        return

    pip_cmd=[sys.executable,'-m','pip','install','--disable-pip-version-check','--no-input','--upgrade','--target',str(VENDOR),'PyMuPDF>=1.24,<2']
    rc,out=_run(pip_cmd,timeout=300)
    transcript.append('\nPip-Installation:\n'+out)

    if rc!=0:
        rc2,out2=_run([sys.executable,'-m','ensurepip','--upgrade'],timeout=180)
        transcript.append('\nensurepip:\n'+out2)
        if rc2==0:
            rc,out=_run(pip_cmd,timeout=300)
            transcript.append('\nPip-Installation nach ensurepip:\n'+out)

    importlib.invalidate_caches()
    ok,verify=_local_engine_ok()
    transcript.append('\nPrüfung nach Installation:\n'+verify)
    LOG.write_text('\n'.join(transcript),encoding='utf-8')
    if not ok:
        raise RuntimeError('PyMuPDF konnte nicht lokal installiert oder geladen werden. Details: '+str(LOG))


def main():
    try:
        _install_engine()
        if not PATCH.exists():
            raise RuntimeError('patch_1603.py wurde nicht gefunden.')
        runpy.run_path(str(PATCH),run_name='__main__')
        return 0
    except SystemExit as e:
        if e.code not in (None,0):
            raise
        return 0
    except Exception:
        ERR.write_text(traceback.format_exc(),encoding='utf-8')
        raise


if __name__=='__main__':
    raise SystemExit(main())
