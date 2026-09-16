from pathlib import Path
import datetime
import py_compile
import shutil

APP=Path(__file__).resolve().parent/'app.py'

OLD_HIDE="""                if os.name=='nt':
                    try:subprocess.run(['attrib','+h',str(meta)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
                    except Exception:pass
"""
NEW_HIDE="""                if os.name=='nt':
                    try:
                        _k32=__import__('ctypes').windll.kernel32
                        _attrs=_k32.GetFileAttributesW(str(meta))
                        if _attrs not in (-1, 0xFFFFFFFF) and not (_attrs & 0x2):
                            _k32.SetFileAttributesW(str(meta), _attrs | 0x2)
                    except Exception:
                        pass
"""


def compile_text(text,name):
    p=APP.with_name(name)
    try:
        p.write_text(text,encoding='utf-8')
        py_compile.compile(str(p),doraise=True)
    finally:
        try:p.unlink()
        except Exception:pass


def transform(s):
    # 1) Die fehlerhafte 1.4.46/1.4.47-Ersetzung wird nicht mehr benutzt.
    # Statt nur den subprocess-Aufruf zu ersetzen, ersetzen wir den kompletten try-Block.
    if OLD_HIDE in s:
        s=s.replace(OLD_HIDE,NEW_HIDE,1)

    # Falls eine teilweise 1.4.46/1.4.47-Fassung vorhanden ist, auf den sicheren Block zurückführen.
    broken="""                if os.name=='nt':
                    try:_attrs=__import__('ctypes').windll.kernel32.GetFileAttributesW(str(meta))
                    if _attrs not in (-1, 0xFFFFFFFF) and not (_attrs & 0x2):
                        __import__('ctypes').windll.kernel32.SetFileAttributesW(str(meta), _attrs | 0x2)
                    except Exception:pass
"""
    if broken in s:
        s=s.replace(broken,NEW_HIDE,1)

    # 2) Alten Statik-PDF-Schnellzugriff aus der normalen Statikseite entfernen.
    # Statik PDF hat seit 1.4.45 einen eigenen Unterbereich und soll die mb-Ansicht nicht mehr beeinflussen.
    qstart=s.find('        # 1.4.35: Statik-PDF Schnellzugriff. Nur lesender Zugriff auf vorhandene PDFs.\n')
    qend=s.find('        # Baugrund / Bodengutachten:',qstart) if qstart>=0 else -1
    if qstart>=0 and qend>qstart:
        s=s[:qstart]+"        # PZ_STATIK_QUICKACCESS_REMOVED_V1448: PDF-Liste ist ausschließlich im Unterpunkt Statik PDF.\n\n"+s[qend:]

    # 3) PDF-Unterpunkt ohne navigate('Statik',...) direkt an seine eigene Ansicht binden.
    old_pdf="self.statik_pdf_nav=tk.Button(self.sidebar,text='   ↳ Statik PDF',command=lambda:self.navigate('Statik',self.show_statik_pdf),anchor='w',bd=0,bg=DARK,fg='#b9b7b0',activebackground=DARK2,activeforeground='white',font=('Segoe UI',9),padx=30,pady=5,cursor='hand2')"
    new_pdf="self.statik_pdf_nav=tk.Button(self.sidebar,text='   ↳ Statik PDF',command=self.show_statik_pdf,anchor='w',bd=0,bg=DARK,fg='#b9b7b0',activebackground=DARK2,activeforeground='white',font=('Segoe UI',9),padx=30,pady=5,cursor='hand2')"
    if old_pdf in s:
        s=s.replace(old_pdf,new_pdf,1)

    # 4) Hauptpunkt Statik nach dem Aufbau der Sidebar ausdrücklich an show_statics binden.
    if 'PZ_STATIK_NAV_SEPARATE_V1448' not in s:
        anchor="        tk.Frame(self.sidebar,bg=DARK).pack(fill='both',expand=True)\n"
        fix="""        # PZ_STATIK_NAV_SEPARATE_V1448: Hauptpunkt Statik ist fest die mb-/Positionsansicht.
        try:
            if 'Statik' in self.nav_buttons:
                self.nav_buttons['Statik'].configure(command=lambda:self.navigate('Statik',self.show_statics))
        except Exception:
            pass
        tk.Frame(self.sidebar,bg=DARK).pack(fill='both',expand=True)
"""
        if anchor not in s:
            raise RuntimeError('1.4.48: Sidebar-Ende nicht gefunden.')
        s=s.replace(anchor,fix,1)

    # 5) Eigene PDF-Seite klar kennzeichnen und Rückweg anbieten.
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
    if '← ZURÜCK ZUR STATIK' not in s and tools_line in s:
        s=s.replace(tools_line,"""        tools=tk.Frame(self.content,bg=BG); tools.pack(fill='x',pady=(0,10))
        tk.Button(tools,text='← ZURÜCK ZUR STATIK',command=lambda:self.navigate('Statik',self.show_statics),bg='#e7e4dc',fg=INK,bd=0,padx=12,pady=7).pack(side='left',padx=(0,10))
""",1)

    # Sicherheitsprüfungen: kein externer attrib-Prozess, klare Trennung vorhanden.
    if "subprocess.run(['attrib','+h',str(meta)]" in s:
        raise RuntimeError('1.4.48: externer attrib-Prozess ist noch vorhanden.')
    if 'PZ_STATIK_NAV_SEPARATE_V1448' not in s:
        raise RuntimeError('1.4.48: Statik-Hauptnavigation wurde nicht eingebaut.')
    if "command=self.show_statik_pdf" not in s:
        raise RuntimeError('1.4.48: Statik-PDF-Unterpunkt wurde nicht sicher getrennt.')
    if 'PZ_STATIK_QUICKACCESS_REMOVED_V1448' not in s:
        raise RuntimeError('1.4.48: alter Statik-PDF-Schnellzugriff wurde nicht entfernt.')
    return s


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.48"' in s:
        return 0
    previous=None
    for v in ('1.4.47','1.4.46','1.4.45'):
        if f'APP_VERSION = "{v}"' in s:
            previous=v; break
    if previous is None:
        raise RuntimeError('Update 1.4.48 erwartet Projektzentrale 1.4.45, 1.4.46 oder 1.4.47. Es wurde nichts verändert.')

    s=transform(s)
    compile_text(s,'app.py.1448.features.check')
    s=s.replace(f'APP_VERSION = "{previous}"','APP_VERSION = "1.4.48"',1)
    compile_text(s,'app.py.1448.final.check')

    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(APP,APP.with_name(f'app.py.vor_1448_{stamp}.bak'))
    tmp=APP.with_name('app.py.1448.tmp'); tmp.write_text(s,encoding='utf-8'); tmp.replace(APP)
    try:
        APP.with_name('patch_1448_report.txt').write_text(
            f'Ausgangsversion: {previous}\nStatik-Hauptpunkt fest auf mb-/Positionsansicht gesetzt.\nStatik PDF als eigener Unterbereich getrennt.\nAlter PDF-Schnellzugriff aus normaler Statik entfernt.\n.engbers-Verstecken ohne externen attrib-Prozess.\n',
            encoding='utf-8')
    except Exception:pass
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1448_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        raise SystemExit(1)
