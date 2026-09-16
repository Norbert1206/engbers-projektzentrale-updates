from pathlib import Path
import datetime, py_compile, shutil, traceback

APP=Path(__file__).resolve().parent/'app.py'
OLD='1.6.3'; NEW='1.6.4'
OLD_IMPORT='from masterdata_v1603 import open_masterdata'
NEW_IMPORT='from masterdata_v1604 import open_masterdata'
OLD_MARK='PZ_MASTERDATA_LOCAL_FITZ_V1603'
NEW_MARK='PZ_MASTERDATA_CARDS_V1604'

OLD_BLOCK="""        # Project data and disciplines share one row so the file index keeps a useful working height.\n        summary=tk.Frame(self.content,bg=BG); summary.pack(fill='x')\n        pan,b=self.panel(summary,'Projektstammdaten'); pan.pack(side='left',fill='both',expand=True,padx=(0,8))\n        vals=[('Projekt',f\"{r['number']} · {r['title']}\"),('Adresse',r['address']),('Bauherr',r['client']),('Architekt / Planer',r['architect']),('Status',r['status']),('Projektordner',self.get_project_folder(r))]\n        for k,v in vals:\n            row=tk.Frame(b,bg=PANEL); row.pack(fill='x',pady=4); tk.Label(row,text=k,width=22,anchor='w',bg=PANEL,fg=MUTED).pack(side='left'); tk.Label(row,text=v or '—',anchor='w',bg=PANEL,fg=INK,font=('Segoe UI Semibold',10) if k=='Projekt' else ('Segoe UI',10)).pack(side='left',fill='x',expand=True)\n        pan2,b2=self.panel(summary,'Fachbereiche'); pan2.pack(side='left',fill='both',expand=True,padx=(8,0))\n        con=db(); rows=con.execute('SELECT name,status,note FROM disciplines WHERE project_id=? ORDER BY sort',(self.project_id,)).fetchall(); con.close()\n        disc_tree=self.tree(b2,('Fachbereich','Status','Hinweis'),[tuple(x) for x in rows],[150,100,420])\n        disc_tree.configure(height=max(1,min(len(rows),6)))\n"""
NEW_BLOCK="""        # PZ_MASTERDATA_CARDS_V1604: vollständige zentrale Stammdaten direkt in der Projektakte.\n        from masterdata_v1604 import render_project_masterdata_cards\n        render_project_masterdata_cards(self,self.content)\n        pan2,b2=self.panel(self.content,'Fachbereiche'); pan2.pack(fill='x',pady=(4,0))\n        con=db(); rows=con.execute('SELECT name,status,note FROM disciplines WHERE project_id=? ORDER BY sort',(self.project_id,)).fetchall(); con.close()\n        disc_tree=self.tree(b2,('Fachbereich','Status','Hinweis'),[tuple(x) for x in rows],[150,100,420])\n        disc_tree.configure(height=max(1,min(len(rows),6)))\n"""


def main():
    if not APP.exists():raise RuntimeError('1.6.4: app.py wurde nicht gefunden.')
    s=APP.read_text(encoding='utf-8')
    if f'APP_VERSION = "{NEW}"' in s and NEW_IMPORT in s and 'PZ_MASTERDATA_CARDS_V1604' in s:return 0
    if f'APP_VERSION = "{OLD}"' not in s:raise RuntimeError('Update 1.6.4 erwartet Projektzentrale 1.6.3.')
    if OLD_IMPORT not in s or OLD_MARK not in s:raise RuntimeError('1.6.4: Stammdatenmodul aus 1.6.3 wurde nicht gefunden.')
    if OLD_BLOCK not in s:raise RuntimeError('1.6.4: bisherige Projektstammdaten-Ansicht wurde nicht eindeutig gefunden.')
    s=s.replace(OLD_IMPORT,NEW_IMPORT,1)
    s=s.replace(OLD_MARK,NEW_MARK,1)
    s=s.replace(OLD_BLOCK,NEW_BLOCK,1)
    s=s.replace(f'APP_VERSION = "{OLD}"',f'APP_VERSION = "{NEW}"',1)
    s=s.replace('Projektzentrale 1.6.3','Projektzentrale 1.6.4')
    chk=APP.with_name('app.py.1604.check')
    try:
        chk.write_text(s,encoding='utf-8');py_compile.compile(str(chk),doraise=True)
    finally:
        try:chk.unlink()
        except Exception:pass
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S');bak=APP.with_name('app.py.vor_1_6_4_'+stamp+'.bak');shutil.copy2(APP,bak)
    tmp=APP.with_name('app.py.1604.tmp');tmp.write_text(s,encoding='utf-8');py_compile.compile(str(tmp),doraise=True);tmp.replace(APP)
    APP.with_name('patch_1604_report.txt').write_text('OK: Projektzentrale 1.6.4 installiert.\nProjektakte: vollständige Stammdaten in vier Kacheln.\nStammdatenfenster: editierbare Kachelansicht.\nEigene Tragwerksplanerdaten werden aus dem Büroprofil geschützt.\nBackup: '+str(bak)+'\n',encoding='utf-8')
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except SystemExit:raise
    except Exception:
        try:APP.with_name('patch_1604_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception:pass
        raise
