from pathlib import Path
import datetime
import py_compile
import shutil

APP=Path(__file__).resolve().parent/'app.py'

OLD="subprocess.run(['attrib','+h',str(meta)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)"
NEW="""_attrs=__import__('ctypes').windll.kernel32.GetFileAttributesW(str(meta))
                    if _attrs not in (-1, 0xFFFFFFFF) and not (_attrs & 0x2):
                        __import__('ctypes').windll.kernel32.SetFileAttributesW(str(meta), _attrs | 0x2)"""


def compile_text(text,name):
    p=APP.with_name(name)
    try:
        p.write_text(text,encoding='utf-8')
        py_compile.compile(str(p),doraise=True)
    finally:
        try:p.unlink()
        except Exception:pass


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.46"' in s:
        return 0
    if 'APP_VERSION = "1.4.45"' not in s:
        raise RuntimeError('Update 1.4.46 erwartet exakt Projektzentrale 1.4.45. Es wurde nichts verändert.')

    if OLD not in s:
        raise RuntimeError('1.4.46: Die bekannte Ursache für das Fensterflackern wurde nicht gefunden. Es wurde nichts verändert.')

    s=s.replace(OLD,NEW,1)
    if "subprocess.run(['attrib','+h',str(meta)]" in s:
        raise RuntimeError('1.4.46: Wiederholter attrib-Prozess ist noch vorhanden.')
    if 'GetFileAttributesW' not in s or 'SetFileAttributesW' not in s:
        raise RuntimeError('1.4.46: Fensterlose .engbers-Markierung wurde nicht eingebaut.')

    compile_text(s,'app.py.1446.check')
    s=s.replace('APP_VERSION = "1.4.45"','APP_VERSION = "1.4.46"',1)
    compile_text(s,'app.py.1446.final.check')

    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(APP,APP.with_name(f'app.py.vor_1446_{stamp}.bak'))
    tmp=APP.with_name('app.py.1446.tmp')
    tmp.write_text(s,encoding='utf-8')
    tmp.replace(APP)
    try:
        APP.with_name('patch_1446_report.txt').write_text(
            'Ausgangsversion: 1.4.45\nFensterflackern in Statik behoben: .engbers wird ohne externen attrib-Prozess verborgen.\n',
            encoding='utf-8')
    except Exception:pass
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1446_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        raise SystemExit(1)
