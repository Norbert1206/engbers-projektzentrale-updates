from pathlib import Path
import runpy
import tempfile

BASE=Path(__file__).resolve().parent
SOURCE=BASE/'patch_1801.py'


def main():
    if not SOURCE.exists():
        raise RuntimeError('patch_1801.py fehlt im Programmordner.')
    text=SOURCE.read_text(encoding='utf-8')
    if "NEW_FILL = r'''def fill_docx" in text:
        text=text.replace("NEW_FILL = r'''def fill_docx", 'NEW_FILL = r"""def fill_docx', 1)
        marker="\n'''\n\n\ndef _version(text):"
        if marker not in text:
            raise RuntimeError('1.8.1: aeusserer NEW_FILL-Abschluss wurde nicht gefunden.')
        text=text.replace(marker, '\n"""\n\n\ndef _version(text):', 1)
    elif 'NEW_FILL = r"""def fill_docx' not in text:
        raise RuntimeError('1.8.1: NEW_FILL-Block wurde nicht gefunden.')

    tmp=BASE/'patch_1801_runtime_fixed.py'
    try:
        tmp.write_text(text,encoding='utf-8')
        ns=runpy.run_path(str(tmp),run_name='pz_patch_1801_runtime_fixed')
        fn=ns.get('main')
        if not callable(fn):
            raise RuntimeError('1.8.1: korrigierter Patch enthaelt keine main()-Funktion.')
        rc=fn()
        return 0 if rc in (None,0) else rc
    finally:
        try: tmp.unlink()
        except Exception: pass


if __name__=='__main__':
    raise SystemExit(main())
