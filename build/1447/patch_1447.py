from pathlib import Path
import datetime
import py_compile
import shutil

APP=Path(__file__).resolve().parent/'app.py'

ATTRIB_OLD="subprocess.run(['attrib','+h',str(meta)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)"
ATTRIB_NEW="""_attrs=__import__('ctypes').windll.kernel32.GetFileAttributesW(str(meta))
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
    if 'APP_VERSION = "1.4.47"' in s:
        return 0
    previous=None
    for v in ('1.4.46','1.4.45'):
        if f'APP_VERSION = "{v}"' in s:
            previous=v; break
    if previous is None:
        raise RuntimeError('Update 1.4.47 erwartet Projektzentrale 1.4.45 oder 1.4.46. Es wurde nichts verändert.')

    # 1) Fensterflackern aus 1.4.45 auch bei direktem Sprung von 1.4.45 beseitigen.
    if ATTRIB_OLD in s:
        s=s.replace(ATTRIB_OLD,ATTRIB_NEW,1)

    # 2) Statik und Statik-PDF strikt trennen.
    old_pdf="self.statik_pdf_nav=tk.Button(self.sidebar,text='   ↳ Statik PDF',command=lambda:self.navigate('Statik',self.show_statik_pdf),anchor='w',bd=0,bg=DARK,fg='#b9b7b0',activebackground=DARK2,activeforeground='white',font=('Segoe UI',9),padx=30,pady=5,cursor='hand2')"
    new_pdf="self.statik_pdf_nav=tk.Button(self.sidebar,text='   ↳ Statik PDF',command=self.show_statik_pdf,anchor='w',bd=0,bg=DARK,fg='#b9b7b0',activebackground=DARK2,activeforeground='white',font=('Segoe UI',9),padx=30,pady=5,cursor='hand2')"
    if old_pdf in s:
        s=s.replace(old_pdf,new_pdf,1)
    elif "command=self.show_statik_pdf" not in s:
        raise RuntimeError('1.4.47: Statik-PDF-Unterpunkt konnte nicht sicher getrennt werden.')

    nav_anchor="        tk.Frame(self.sidebar,bg=DARK).pack(fill='both',expand=True)\n"
    nav_fix="""        # PZ_STATIK_NAV_SEPARATE_V1447: Hauptpunkt Statik bleibt immer die normale Statikansicht.
        try:
            if 'Statik' in self.nav_buttons:
                self.nav_buttons['Statik'].configure(command=lambda:self.navigate('Statik',self.show_statics))
        except Exception:
            pass
        tk.Frame(self.sidebar,bg=DARK).pack(fill='both',expand=True)
"""
    if 'PZ_STATIK_NAV_SEPARATE_V1447' not in s:
        if nav_anchor not in s:
            raise RuntimeError('1.4.47: Sidebar-Ende nicht gefunden.')
        s=s.replace(nav_anchor,nav_fix,1)

    # PDF-Seite bekommt eigenen Header + sichtbaren Rückweg.
    pdf_start="""    def show_statik_pdf(self):
        # PZ_STATIK_PDF_VIEW_V1445: eigener, rein lesender Statik-PDF-Bereich.
        self.clear()
"""
    pdf_new="""    def show_statik_pdf(self):
        # PZ_STATIK_PDF_VIEW_V1445: eigener, rein lesender Statik-PDF-Bereich.
        self.clear()
        try:
            self.header.configure(text='Statik PDF')
            for _n,_b in self.nav_buttons.items():
                _b.configure(bg=DARK2 if _n=='Statik' else DARK)
        except Exception:
            pass
"""
    if pdf_start in s:
        s=s.replace(pdf_start,pdf_new,1)

    tools_line="        tools=tk.Frame(self.content,bg=BG); tools.pack(fill='x',pady=(0,10))\n"
    back_block="""        tools=tk.Frame(self.content,bg=BG); tools.pack(fill='x',pady=(0,10))
        tk.Button(tools,text='← ZURÜCK ZUR STATIK',command=lambda:self.navigate('Statik',self.show_statics),bg='#e7e4dc',fg=INK,bd=0,padx=12,pady=7).pack(side='left',padx=(0,10))
"""
    if "← ZURÜCK ZUR STATIK" not in s:
        if tools_line not in s:
            raise RuntimeError('1.4.47: Werkzeugleiste Statik PDF nicht gefunden.')
        s=s.replace(tools_line,back_block,1)

    if 'PZ_STATIK_NAV_SEPARATE_V1447' not in s or "self.nav_buttons['Statik'].configure" not in s:
        raise RuntimeError('1.4.47: Statik-Navigation wurde nicht vollständig repariert.')
    if ATTRIB_OLD in s:
        raise RuntimeError('1.4.47: attrib-Prozess ist noch vorhanden.')

    compile_text(s,'app.py.1447.features.check')
    s=s.replace(f'APP_VERSION = "{previous}"','APP_VERSION = "1.4.47"',1)
    compile_text(s,'app.py.1447.final.check')

    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(APP,APP.with_name(f'app.py.vor_1447_{stamp}.bak'))
    tmp=APP.with_name('app.py.1447.tmp'); tmp.write_text(s,encoding='utf-8'); tmp.replace(APP)
    try:
        APP.with_name('patch_1447_report.txt').write_text(
            f'Ausgangsversion: {previous}\nStatik-Hauptpunkt wieder fest mit show_statics verbunden.\nStatik PDF separat + Zurück-Schaltfläche.\nFensterflackern durch externen attrib-Prozess entfernt.\n',
            encoding='utf-8')
    except Exception:pass
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1447_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        raise SystemExit(1)
