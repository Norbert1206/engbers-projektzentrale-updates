from pathlib import Path
import datetime, py_compile, shutil, traceback
APP=Path(__file__).resolve().parent/'app.py'
OLD='1.5.6'; NEW='1.6.0'; MARK='PZ_MASTERDATA_PLANS_V1600'
BUTTON="        tk.Button(actions,text='PROJEKT ANALYSIEREN',command=self.analyze_project,bg=ACCENT,fg='white',bd=0,padx=16,pady=9).pack(side='left',padx=8)\n"
WRAP="""    def masterdata_from_plans(self):\n        # PZ_MASTERDATA_PLANS_V1600\n        from masterdata_v1600 import open_masterdata\n        return open_masterdata(self)\n\n"""
def main():
    if not APP.exists(): raise RuntimeError('1.6.0: app.py wurde nicht gefunden.')
    s=APP.read_text(encoding='utf-8')
    if f'APP_VERSION = "{NEW}"' in s and MARK in s:return 0
    if f'APP_VERSION = "{OLD}"' not in s:raise RuntimeError('Update 1.6.0 erwartet Projektzentrale 1.5.6.')
    if 'PZ_PROJECT_EXPLORER_SELECT_FIX_V1506' not in s:raise RuntimeError('1.6.0: stabiler 1.5.6-Explorer fehlt.')
    if BUTTON not in s:raise RuntimeError('1.6.0: Aktionsleiste Projektakte nicht gefunden.')
    s=s.replace(BUTTON,BUTTON+"        tk.Button(actions,text='STAMMDATEN AUS PLÄNEN',command=self.masterdata_from_plans,bg=DARK,fg='white',bd=0,padx=16,pady=9).pack(side='left',padx=8)\n",1)
    anchor='    def get_project_folder(self, row=None):\n'
    if anchor not in s:raise RuntimeError('1.6.0: Einfügepunkt nicht gefunden.')
    s=s.replace(anchor,WRAP+anchor,1)
    s=s.replace("cur.execute(\"INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','3')\")","cur.execute(\"INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','4')\")",1)
    s=s.replace('Datenbankschema: 3','Datenbankschema: 4').replace(f'APP_VERSION = "{OLD}"',f'APP_VERSION = "{NEW}"',1).replace('Projektzentrale 1.5.6','Projektzentrale 1.6.0')
    if MARK not in s:raise RuntimeError('1.6.0: Sicherheitsprüfung fehlgeschlagen.')
    chk=APP.with_name('app.py.1600.check')
    try:chk.write_text(s,encoding='utf-8');py_compile.compile(str(chk),doraise=True)
    finally:
        try:chk.unlink()
        except Exception:pass
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S');bak=APP.with_name('app.py.vor_1_6_0_'+stamp+'.bak');shutil.copy2(APP,bak)
    tmp=APP.with_name('app.py.1600.tmp');tmp.write_text(s,encoding='utf-8');py_compile.compile(str(tmp),doraise=True);tmp.replace(APP)
    APP.with_name('patch_1600_report.txt').write_text('OK: Projektzentrale 1.6.0 installiert.\nProjektstammdaten aus Architektenplänen aktiviert.\nBackup: '+str(bak)+'\n',encoding='utf-8');return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except SystemExit:raise
    except Exception:
        try:APP.with_name('patch_1600_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception:pass
        raise
