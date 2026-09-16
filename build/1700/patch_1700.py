from pathlib import Path
import datetime
import py_compile
import shutil
import traceback

BASE=Path(__file__).resolve().parent
APP=BASE/'app.py'
MOD=BASE/'wordforms_v1700.py'
OLD='1.6.9'; NEW='1.7.0'
MARK='PZ_WORD_BESCHEINIGUNGEN_V1700'

BUTTON="        tk.Button(actions,text='STAMMDATEN AUS PLÄNEN',command=self.masterdata_from_plans,bg=DARK,fg='white',bd=0,padx=16,pady=9).pack(side='left',padx=8)\n"
NEW_BUTTON="        tk.Button(actions,text='WORD-BESCHEINIGUNGEN',command=self.word_bescheinigungen,bg=DARK,fg='white',bd=0,padx=16,pady=9).pack(side='left',padx=8)\n"
WRAP="""    def word_bescheinigungen(self):
        # PZ_WORD_BESCHEINIGUNGEN_V1700
        from wordforms_v1700 import open_wordforms
        return open_wordforms(self)

"""


def main():
    if not APP.exists() or not MOD.exists():
        raise RuntimeError('1.7.0: app.py oder wordforms_v1700.py wurde nicht gefunden.')
    s=APP.read_text(encoding='utf-8')
    if f'APP_VERSION = "{NEW}"' in s and MARK in s:
        return 0
    if f'APP_VERSION = "{OLD}"' not in s:
        raise RuntimeError('Update 1.7.0 erwartet Projektzentrale 1.6.9.')
    if BUTTON not in s:
        raise RuntimeError('1.7.0: Aktionsleiste der Projektakte wurde nicht gefunden.')
    anchor='    def get_project_folder(self, row=None):\n'
    if anchor not in s:
        raise RuntimeError('1.7.0: Einfügepunkt für Word-Bescheinigungen wurde nicht gefunden.')

    s=s.replace(BUTTON,BUTTON+NEW_BUTTON,1)
    s=s.replace(anchor,WRAP+anchor,1)
    s=s.replace(f'APP_VERSION = "{OLD}"',f'APP_VERSION = "{NEW}"',1)
    s=s.replace('Projektzentrale 1.6.9','Projektzentrale 1.7.0')
    if MARK not in s:
        raise RuntimeError('1.7.0: Sicherheitsprüfung der Word-Funktion fehlgeschlagen.')

    chk=APP.with_name('app.py.1700.check')
    try:
        chk.write_text(s,encoding='utf-8')
        py_compile.compile(str(chk),doraise=True)
        py_compile.compile(str(MOD),doraise=True)
    finally:
        try: chk.unlink()
        except Exception: pass

    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name('app.py.vor_1_7_0_'+stamp+'.bak')
    shutil.copy2(APP,bak)
    tmp=APP.with_name('app.py.1700.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    tmp.replace(APP)

    APP.with_name('patch_1700_report.txt').write_text(
        'OK: Projektzentrale 1.7.0 installiert.\n'
        'Neue Funktion WORD-BESCHEINIGUNGEN in der Projektakte.\n'
        'Word-Dateien werden ausschließlich im Ordner Bescheinigungen gesucht.\n'
        'Ausgefüllte Kopien werden unter Bescheinigungen\\Ausgefüllt abgelegt.\n'
        'Originaldateien bleiben unverändert.\n'
        'Backup: '+str(bak)+'\n',encoding='utf-8')
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        try: APP.with_name('patch_1700_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception: pass
        raise
