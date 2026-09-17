from pathlib import Path
import importlib
import os
import py_compile
import subprocess
import sys
import traceback


BASE = Path(__file__).resolve().parent
VENDOR = BASE / '_vendor'
LOG = BASE / 'update_1811_install.log'
ERR = BASE / 'update_1811_error.txt'
REQUIRED = (
    BASE / 'app.py',
    BASE / 'wordforms_v1700.py',
    BASE / 'pdf_stamp_v1870.py',
    BASE / 'project_batch_stamp_v1870.py',
    BASE / 'masterdata_edit_v1860.py',
    BASE / 'commercial_v1890.py',
)


def _flags():
    return getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0


def _run(command, timeout=300):
    process = subprocess.run(
        command,
        cwd=str(BASE),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors='replace',
        timeout=timeout,
        creationflags=_flags(),
    )
    return process.returncode, process.stdout or ''


def _engine_ok():
    if VENDOR.exists() and str(VENDOR) not in sys.path:
        sys.path.insert(0, str(VENDOR))
    importlib.invalidate_caches()
    errors = []
    for module_name in ('pymupdf', 'fitz'):
        try:
            module = importlib.import_module(module_name)
            return True, str(getattr(module, '__file__', ''))
        except Exception as exc:
            errors.append(f'{module_name}: {exc}')
    return False, ' | '.join(errors)


def _ensure_engine():
    ok, detail = _engine_ok()
    transcript = ['Vorpruefung PDF-Engine:\n' + detail]
    if ok:
        return transcript
    VENDOR.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
        '--no-input', '--upgrade', '--target', str(VENDOR), 'PyMuPDF>=1.24,<2',
    ]
    return_code, output = _run(command)
    transcript.append('\nPyMuPDF-Installation:\n' + output)
    if return_code != 0:
        bootstrap_code, bootstrap_output = _run(
            [sys.executable, '-m', 'ensurepip', '--upgrade'], timeout=180
        )
        transcript.append('\nensurepip:\n' + bootstrap_output)
        if bootstrap_code == 0:
            return_code, output = _run(command)
            transcript.append('\nPyMuPDF-Installation nach ensurepip:\n' + output)
    ok, detail = _engine_ok()
    transcript.append('\nPruefung danach:\n' + detail)
    if not ok:
        raise RuntimeError('PyMuPDF konnte nicht geladen oder installiert werden.')
    return transcript


def main():
    transcript = []
    try:
        for path in REQUIRED:
            if not path.exists():
                raise RuntimeError('Update-Datei fehlt: ' + path.name)
            py_compile.compile(str(path), doraise=True)
        if not (BASE / 'masterdata_v1604.py').exists():
            raise RuntimeError('Das vorhandene Stammdatenmodul masterdata_v1604.py fehlt.')
        transcript.extend(_ensure_engine())
        app = (BASE / 'app.py').read_text(encoding='utf-8')
        word = (BASE / 'wordforms_v1700.py').read_text(encoding='utf-8')
        pdf = (BASE / 'pdf_stamp_v1870.py').read_text(encoding='utf-8')
        batch = (BASE / 'project_batch_stamp_v1870.py').read_text(encoding='utf-8')
        master = (BASE / 'masterdata_edit_v1860.py').read_text(encoding='utf-8')
        commercial = (BASE / 'commercial_v1890.py').read_text(encoding='utf-8')
        checks = (
            ('APP_VERSION = "1.8.11"', app),
            ('PZ_FILE_RECYCLE_V1880', app),
            ('PZ_WORD_RESET_V1860', word),
            ('PZ_PDF_STAMP_TOOL_V1870', pdf),
            ('PZ_PROJECT_BATCH_STAMP_V1870', app),
            ('PZ_PROJECT_BATCH_STAMP_V1880', batch),
            ('PZ_BATCH_DIALOG_FIT_V1880', batch),
            ('PZ_MASTERDATA_EDIT_V1860', master),
            ('PZ_COMMERCIAL_V1890', commercial),
            ('PZ_COMMERCIAL_GENERIC_INVOICE_V1810', commercial),
            ('PZ_TEXT_EDITOR_FIT_V1811', commercial),
            ('Angebote & Rechnungen', app),
        )
        for marker, text in checks:
            if marker not in text:
                raise RuntimeError('Funktionspruefung fehlgeschlagen: ' + marker)
        transcript.append('\nOK: Update 1.8.11 erfolgreich installiert.\n')
        LOG.write_text('\n'.join(transcript), encoding='utf-8')
        try:
            ERR.unlink()
        except Exception:
            pass
        return 0
    except Exception:
        text = traceback.format_exc()
        try:
            LOG.write_text('\n'.join(transcript) + '\nFEHLER:\n' + text, encoding='utf-8')
            ERR.write_text(text, encoding='utf-8')
        except Exception:
            pass
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
