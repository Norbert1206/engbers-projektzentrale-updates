import os, sys, json, sqlite3, shutil, zipfile, datetime, re, urllib.request, subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

APP_NAME = "Engbers Projektzentrale"
APP_VERSION = "1.8.6"
BASE = Path(__file__).resolve().parent
APPDATA = Path(os.environ.get("APPDATA", str(Path.home()))) / "Engbers Projektzentrale"
LOCALDATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Engbers Projektzentrale"
SETTINGS_PATH = APPDATA / "settings.json"
ASSET_DIR = BASE / "assets"
DATA_DIR = LOCALDATA / "data"
DB_PATH = DATA_DIR / "engbers_projekte.sqlite"
PROJECT_ROOT = Path.home() / "Engbers Projekte"
BACKUP_DIR = Path.home() / "Engbers Backups"
FILES_DIR = PROJECT_ROOT


def load_settings():
    global PROJECT_ROOT, BACKUP_DIR, FILES_DIR
    if SETTINGS_PATH.exists():
        try:
            cfg=json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if cfg.get("project_root"): PROJECT_ROOT=Path(cfg["project_root"])
            if cfg.get("backup_root"): BACKUP_DIR=Path(cfg["backup_root"])
        except Exception:
            pass
    FILES_DIR=PROJECT_ROOT


def save_settings(project_root=None, backup_root=None, update_feed=None):
    APPDATA.mkdir(parents=True,exist_ok=True)
    cfg={}
    if SETTINGS_PATH.exists():
        try: cfg=json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except Exception: cfg={}
    if project_root is not None: cfg["project_root"]=str(project_root)
    if backup_root is not None: cfg["backup_root"]=str(backup_root)
    if update_feed is not None: cfg["update_feed"]=update_feed
    cfg["configured"]=True
    SETTINGS_PATH.write_text(json.dumps(cfg,indent=2,ensure_ascii=False),encoding="utf-8")
    load_settings()


def first_run_setup():
    load_settings()
    try:
        cfg=json.loads(SETTINGS_PATH.read_text(encoding="utf-8")) if SETTINGS_PATH.exists() else {}
    except Exception: cfg={}
    if cfg.get("configured") and cfg.get("project_root"):
        return True
    root=tk.Tk(); root.withdraw()
    messagebox.showinfo("Engbers Projektzentrale – Ersteinrichtung",
        "Willkommen. Beim ersten Start werden nur die zentralen Speicherorte festgelegt.\n\n"
        "Ihre Projektdateien bleiben normale Windows-Dateien und sind jederzeit im Explorer erreichbar.",parent=root)
    pr=filedialog.askdirectory(title="Zentrale Projektablage auswählen",parent=root)
    if not pr:
        root.destroy(); return False
    default_backup=str(Path(pr).parent / "Engbers_Backup")
    use_default=messagebox.askyesno("Backup-Ziel",
        f"Als Sicherungsziel wird vorgeschlagen:\n{default_backup}\n\nDiesen Ordner verwenden?",parent=root)
    if use_default:
        br=default_backup
    else:
        br=filedialog.askdirectory(title="Sicherungsziel auswählen",parent=root)
        if not br: br=default_backup
    save_settings(Path(pr),Path(br))
    Path(pr).mkdir(parents=True,exist_ok=True); Path(br).mkdir(parents=True,exist_ok=True)
    messagebox.showinfo("Einrichtung abgeschlossen",
        f"Projektablage:\n{pr}\n\nSicherungen:\n{br}\n\nDiese Speicherorte können später unter Sicherung / Update geändert werden.",parent=root)
    root.destroy(); return True


BG = "#f4f1ea"       # warm off-white
PANEL = "#fbfaf6"
INK = "#161616"
MUTED = "#6c6c68"
LINE = "#c8c5bd"
DARK = "#202020"
DARK2 = "#2a2a2a"
ACCENT = "#b08b49"
GREEN = "#4d7d63"
RED = "#a85b52"
YELLOW = "#b59a45"


def now_iso():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    DATA_DIR.mkdir(parents=True,exist_ok=True)
    con = db(); cur = con.cursor()
    cur.executescript('''
    CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE IF NOT EXISTS projects(
      id INTEGER PRIMARY KEY, number TEXT UNIQUE, title TEXT, address TEXT, client TEXT,
      architect TEXT, status TEXT, year INTEGER, description TEXT, created_at TEXT, closed_at TEXT
    );
    CREATE TABLE IF NOT EXISTS disciplines(
      id INTEGER PRIMARY KEY, project_id INTEGER, name TEXT, status TEXT, note TEXT, sort INTEGER
    );
    CREATE TABLE IF NOT EXISTS statics(
      id INTEGER PRIMARY KEY, project_id INTEGER, pos TEXT, title TEXT, system TEXT, result TEXT,
      utilization REAL, deformation TEXT, checker TEXT, status TEXT
    );
    CREATE TABLE IF NOT EXISTS thermal(
      id INTEGER PRIMARY KEY, project_id INTEGER, area TEXT, item TEXT, status TEXT, note TEXT
    );
    CREATE TABLE IF NOT EXISTS dgnb(
      id INTEGER PRIMARY KEY, project_id INTEGER, code TEXT, criterion TEXT, qng TEXT,
      evidence TEXT, owner TEXT, status TEXT, note TEXT
    );
    CREATE TABLE IF NOT EXISTS acoustic(
      id INTEGER PRIMARY KEY, project_id INTEGER, component TEXT, requirement TEXT, result TEXT, status TEXT
    );
    CREATE TABLE IF NOT EXISTS site(
      id INTEGER PRIMARY KEY, project_id INTEGER, date TEXT, type TEXT, title TEXT, result TEXT, status TEXT
    );
    CREATE TABLE IF NOT EXISTS comm(
      id INTEGER PRIMARY KEY, project_id INTEGER, ts TEXT, channel TEXT, sender TEXT, recipient TEXT,
      subject TEXT, body TEXT, attachment TEXT, original_path TEXT, immutable INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS tasks(
      id INTEGER PRIMARY KEY, project_id INTEGER, title TEXT, area TEXT, owner TEXT, due TEXT,
      priority TEXT, status TEXT, source TEXT
    );
    CREATE TABLE IF NOT EXISTS checker(
      id INTEGER PRIMARY KEY, project_id INTEGER, ref TEXT, position TEXT, comment TEXT, response TEXT, status TEXT
    );
    CREATE TABLE IF NOT EXISTS documents(
      id INTEGER PRIMARY KEY, project_id INTEGER, category TEXT, filename TEXT, version TEXT, status TEXT, path TEXT
    );
    CREATE TABLE IF NOT EXISTS project_file_index(
      id INTEGER PRIMARY KEY, project_id INTEGER, rel_path TEXT, filename TEXT, extension TEXT,
      size_bytes INTEGER, modified_ts REAL, modified_text TEXT, category TEXT, confidence TEXT,
      UNIQUE(project_id, rel_path)
    );
    CREATE TABLE IF NOT EXISTS file_assignments(
      id INTEGER PRIMARY KEY, project_id INTEGER, rel_path TEXT, is_folder INTEGER DEFAULT 0,
      category TEXT, assigned_at TEXT, UNIQUE(project_id, rel_path)
    );
    CREATE TABLE IF NOT EXISTS project_sources(
      id INTEGER PRIMARY KEY, project_id INTEGER, source_project_id INTEGER, folder_path TEXT,
      label TEXT, source_type TEXT DEFAULT 'verknüpft', created_at TEXT,
      UNIQUE(project_id, folder_path)
    );
    CREATE TABLE IF NOT EXISTS interfaces(
      id INTEGER PRIMARY KEY, name TEXT UNIQUE, status TEXT, method TEXT, note TEXT
    );
    ''')
    
    # Datenbankmigration 1 -> 2: externer Projektordner pro Projekt
    cols=[r[1] for r in cur.execute("PRAGMA table_info(projects)").fetchall()]
    if "folder_path" not in cols:
        cur.execute("ALTER TABLE projects ADD COLUMN folder_path TEXT DEFAULT ''")
    cur.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version','4')")
    cur.execute("SELECT COUNT(*) c FROM projects")
    if cur.fetchone()['c'] == 0:
        seed_demo(cur)
    con.commit(); con.close()


def seed_demo(cur):
    cur.execute('''INSERT INTO projects(number,title,address,client,architect,status,year,description,created_at,closed_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?)''',
                ("26-014","Villa Eichenhöhe","Am Eichenhang 14, 48161 Münster","Familie Hartmann",
                 "Engelshove Bau GmbH","Abgeschlossen",2026,
                 "Komplexe Villa mit Tiefgarage, Pool, großen Öffnungen und anspruchsvollen Detailanschlüssen.",
                 "2026-01-15","2026-08-28"))
    pid = cur.lastrowid
    disciplines = [
      ("Projektakte","Abgeschlossen","Stammdaten, Beteiligte und Projektchronik",10),
      ("Statik","Abgeschlossen","Tragwerksplanung inkl. Prüfstatik",20),
      ("Wärmeschutz","Abgeschlossen","Hauptbereich für KfW/EEE, DGNB/QNG und Wärmeschutznachweis",30),
      ("Schallschutz","Abgeschlossen","Nachweise und Baustellenkontrollen",40),
      ("Bauleitung","Abgeschlossen","Ortstermine, Mängel und Freigaben",50),
      ("Kommunikation","Abgeschlossen","E-Mail, WhatsApp, Telefonnotizen, Goodnotes",60),
      ("Dokumente","Abgeschlossen","Projektakte vollständig archiviert",70)
    ]
    cur.executemany("INSERT INTO disciplines(project_id,name,status,note,sort) VALUES(?,?,?,?,?)", [(pid,*x) for x in disciplines])
    stat = [
      ("01","Tragwerkskonzept","Gesamttragwerk / Lastpfade","Lastabtrag plausibel dokumentiert",0.72,"Verformungszonen festgelegt","Prüfbericht erledigt","Abgeschlossen"),
      ("12","EG-Decke 34 cm","Flachdecke mit Überzügen","Biegung / Querkraft / GZG erfüllt",0.84,"w0=8 mm, w∞=19 mm","ohne Beanstandung","Abgeschlossen"),
      ("24","Randträger Gartenfassade","Überzug / Randträger","Bemessung erfüllt",0.79,"Δ=12 mm; Fensterbauer informiert","Hinweis beantwortet","Abgeschlossen"),
      ("31","Stütze S3","Stahlbetonstütze","N-M Interaktion erfüllt",0.68,"—","—","Abgeschlossen"),
      ("44","Stützenfuß Terrasse","Stahlanschluss / Simpson CMR","Herstellernachweis + Plausibilisierung",0.91,"—","anerkannt","Abgeschlossen"),
      ("51","Fundament F3","Einzelfundament","Bodenpressung / Gleiten / Kippen erfüllt",0.73,"Setzung plausibilisiert","—","Abgeschlossen")]
    cur.executemany("INSERT INTO statics(project_id,pos,title,system,result,utilization,deformation,checker,status) VALUES(?,?,?,?,?,?,?,?,?)", [(pid,*x) for x in stat])
    thermal = [
      ("KfW / EEE","Förderkonzept","Abgeschlossen","Effizienzhaus-Nachweise, Bestätigung und Projektdokumentation vollständig"),
      ("KfW / EEE","Baubegleitung","Abgeschlossen","Ausführung kontrolliert, Fotodokumentation vorhanden"),
      ("Wärmeschutznachweis","GEG / Bilanz","Abgeschlossen","Nachweis final, Planstand Schlussplanung"),
      ("Wärmeschutznachweis","Wärmebrücken","Abgeschlossen","Detailnachweise / Gleichwertigkeitsnachweise abgelegt"),
      ("Wärmeschutznachweis","Luftdichtheit","Abgeschlossen","Blower-Door-Nachweis hinterlegt"),
      ("DGNB / QNG","Zertifizierung","Abgeschlossen","Nachweismatrix vollständig; Auditorenakte geschlossen")]
    cur.executemany("INSERT INTO thermal(project_id,area,item,status,note) VALUES(?,?,?,?,?)", [(pid,*x) for x in thermal])
    dgnb = [
      ("ENV1.1","Ökobilanz des Gebäudes","QNG Plus","LCA-Bericht, Bauteilliste","Engbers","Einreichungsfertig","Final geprüft"),
      ("ENV1.2","Risiken für die lokale Umwelt","QNG Plus","Produktnachweise / Schadstoffe","Architekt","Einreichungsfertig","Freigaben vollständig"),
      ("ENV2.2","Trinkwasserbedarf und Abwasser","QNG ergänzend","Sanitärkonzept","TGA","Geprüft","Plausibilisiert"),
      ("ECO1.1","Gebäudebezogene Kosten im Lebenszyklus","QNG Plus","LCC-Berechnung","Engbers","Einreichungsfertig","Final"),
      ("ECO2.1","Flexibilität und Umnutzungsfähigkeit","QNG ergänzend","Grundriss-/Konstruktionsbewertung","Architekt","Geprüft","Final"),
      ("SOC1.1","Thermischer Komfort","QNG Plus","Sommerlicher Wärmeschutz","Engbers","Einreichungsfertig","Final"),
      ("SOC1.2","Innenraumluftqualität","QNG Plus","Produkt- und Messnachweise","Bauherr","Geprüft","Final"),
      ("SOC1.3","Akustischer Komfort","QNG ergänzend","Schallschutznachweis","Engbers","Einreichungsfertig","Final"),
      ("SOC1.4","Visueller Komfort","—","Planunterlagen / Tageslicht","Architekt","Geprüft","Final"),
      ("SOC1.6","Aufenthaltsqualitäten","—","Außenraum / Nutzungsqualität","Architekt","Geprüft","Final"),
      ("TEC1.3","Qualität der Gebäudehülle","QNG Plus","Hülle, Luftdichtheit, Details","Engbers","Einreichungsfertig","Final"),
      ("TEC1.4","Einsatz und Integration von Gebäudetechnik","QNG ergänzend","TGA-Dokumentation","TGA","Geprüft","Final"),
      ("TEC1.6","Rückbau- und Recyclingfreundlichkeit","QNG Plus","Material-/Demontagekonzept","Architekt","Geprüft","Final"),
      ("PRO1.1","Qualität der Projektvorbereitung","—","Protokolle / Anforderungen","Bauherr","Geprüft","Final"),
      ("PRO1.5","Dokumentation für nachhaltige Bewirtschaftung","QNG Plus","Revisionsunterlagen","Bauleitung","Einreichungsfertig","Final"),
      ("SITE1.1","Mikrostandort","—","Standortbewertung","Architekt","Geprüft","Final")]
    cur.executemany("INSERT INTO dgnb(project_id,code,criterion,qng,evidence,owner,status,note) VALUES(?,?,?,?,?,?,?,?)", [(pid,*x) for x in dgnb])
    acoust = [
      ("Trennwand Schlafen/Technik","R'w ≥ 47 dB","R'w = 51 dB","Abgeschlossen"),
      ("Decke Wohnen/Tiefgarage","L'n,w ≤ 50 dB","L'n,w = 45 dB","Abgeschlossen"),
      ("Außenfassade Schlafräume","erforderliches R'w,res","Nachweis erfüllt","Abgeschlossen")]
    cur.executemany("INSERT INTO acoustic(project_id,component,requirement,result,status) VALUES(?,?,?,?,?)", [(pid,*x) for x in acoust])
    site = [
      ("2026-04-22","Ortstermin","Abdichtung Sockel / Z-Sperre","Anschluss korrigiert und fotografisch dokumentiert","Erledigt"),
      ("2026-05-12","Goodnotes","Fensteranschluss Gartenfassade","Verformungsangaben an Fensterbauer weitergegeben","Erledigt"),
      ("2026-06-03","Ortstermin","Bewehrung EG-Decke","Freigabe nach Kontrolle","Erledigt"),
      ("2026-07-18","Abnahme","Schallschutzdetails","Ausführung entsprechend Planung","Erledigt")]
    cur.executemany("INSERT INTO site(project_id,date,type,title,result,status) VALUES(?,?,?,?,?,?)", [(pid,*x) for x in site])
    comms = [
      ("2026-02-02 09:18","E-Mail","architektur@engelshove.de","info@engbers-ingenieurbau.de","Planstand EG / große Öffnung","Aktualisierte Pläne mit Bitte um Prüfung der Gartenfassade.","EG_Rev03.pdf","demo://mail/001.eml"),
      ("2026-02-02 10:06","E-Mail","info@engbers-ingenieurbau.de","architektur@engelshove.de","AW: Planstand EG / große Öffnung","Unterlagen erhalten. Randträger und Verformung werden geprüft.","","demo://mail/002.eml"),
      ("2026-05-12 11:22","WhatsApp","Bauleitung","Engbers","Fensteraufmaß","Foto und Rückfrage zur erforderlichen Bewegungsfuge am Randträger.","IMG_5211.jpg","demo://whatsapp/2026-05-12"),
      ("2026-05-12 11:40","WhatsApp","Engbers","Bauleitung","Fensteraufmaß","Endverformung laut Statik 12 mm; Montagefuge entsprechend berücksichtigen.","","demo://whatsapp/2026-05-12"),
      ("2026-06-03 15:30","Goodnotes","Norbert Engbers","Projektakte","Baustellennotiz EG-Decke","Bewehrung kontrolliert, zwei offene Randzulagen vor Betonage ergänzt.","Goodnotes_2026-06-03.pdf","demo://goodnotes/003.pdf"),
      ("2026-08-25 08:15","Telefonnotiz","Prüfingenieur","Engbers","Abschluss Prüfstatik","Letzte Rückfrage zum Stützenfuß telefonisch geklärt.","","demo://phone/001")]
    cur.executemany("INSERT INTO comm(project_id,ts,channel,sender,recipient,subject,body,attachment,original_path) VALUES(?,?,?,?,?,?,?,?,?)", [(pid,*x) for x in comms])
    tasks = [
      ("Prüfbericht Punkt 7 beantworten","Prüfstatik","Engbers","2026-03-08","Hoch","Erledigt","Prüfbericht"),
      ("Fensterbauer Verformungsangabe senden","Statik","Engbers","2026-05-13","Hoch","Erledigt","Goodnotes"),
      ("QNG Produktnachweise vervollständigen","DGNB / QNG","Architekt","2026-07-10","Mittel","Erledigt","DGNB-Matrix"),
      ("Schlussdokumentation archivieren","Projektakte","Engbers","2026-08-28","Mittel","Erledigt","Projektabschluss")]
    cur.executemany("INSERT INTO tasks(project_id,title,area,owner,due,priority,status,source) VALUES(?,?,?,?,?,?,?,?)", [(pid,*x) for x in tasks])
    checker = [
      ("PB-01/3","Pos. 12","Bitte Verformungsannahmen für Fassadenanschluss ergänzen.","Anfangs- und Endverformung im Plan ergänzt und an Fensterbauer übergeben.","Erledigt"),
      ("PB-01/7","Pos. 44","Nachweis Stützenfuß / Lastkombination nachvollziehbar darstellen.","Herstellernachweis und kurze Plausibilisierung ergänzt.","Erledigt"),
      ("PB-02/2","Pos. 24","Lastweiterleitung Randträger erläutern.","Lastpfad Decke → Randträger → Stütze ergänzt.","Erledigt")]
    cur.executemany("INSERT INTO checker(project_id,ref,position,comment,response,status) VALUES(?,?,?,?,?,?)", [(pid,*x) for x in checker])
    docs = [
      ("01 Projekt","Projektstammdaten.pdf","Final","Archiviert","01_Projekt/Projektstammdaten.pdf"),
      ("02 Statik","Statische_Berechnung_Final.pdf","Final","Archiviert","02_Statik/Statische_Berechnung_Final.pdf"),
      ("03 Prüfstatik","Pruefbericht_abgeschlossen.pdf","Final","Archiviert","03_Pruefstatik/Pruefbericht_abgeschlossen.pdf"),
      ("04 Wärmeschutz/KfW","GEG_KfW_Final.pdf","Final","Archiviert","04_Waermeschutz/GEG_KfW_Final.pdf"),
      ("05 DGNB-QNG","DGNB_QNG_Nachweismatrix.xlsx","Final","Archiviert","05_DGNB_QNG/DGNB_QNG_Nachweismatrix.xlsx"),
      ("06 Schallschutz","Schallschutznachweis_Final.pdf","Final","Archiviert","06_Schallschutz/Schallschutznachweis_Final.pdf"),
      ("07 Bauleitung","Baustellendokumentation.pdf","Final","Archiviert","07_Bauleitung/Baustellendokumentation.pdf"),
      ("08 Kommunikation","Kommunikationsakte.pdf","Final","Archiviert","08_Kommunikation/Kommunikationsakte.pdf")]
    cur.executemany("INSERT INTO documents(project_id,category,filename,version,status,path) VALUES(?,?,?,?,?,?)", [(pid,*x) for x in docs])
    interfaces = [
      ("Outlook / Microsoft 365","Vorbereitet","Microsoft Graph / OAuth","E-Mail, Kalender, Kontakte; Live-Verbindung in nächster Integrationsstufe"),
      ("WhatsApp Business","Vorbereitet","WhatsApp Business Platform / Webhooks","Keine Browser-Automation; Originalnachrichten + Anhänge projektbezogen archivieren"),
      ("Goodnotes / OneDrive","Testbar","Goodnotes Auto Backup → OneDrive-Projektordner","PDF-Import und Ordnerübernahme bereits als Desktop-Funktion vorgesehen"),
      ("DGNB System Software","Vorgesehen","Export/Import bzw. offizielle Schnittstelle","Datenmodell ist für späteren Datenaustausch vorbereitet")]
    cur.executemany("INSERT INTO interfaces(name,status,method,note) VALUES(?,?,?,?)", interfaces)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} · {APP_VERSION}")
        self.geometry("1500x920")
        self.minsize(1180,760)
        self.configure(bg=BG)
        self.project_id = 1
        self.nav_buttons = {}
        self.setup_styles()
        self.build_shell()
        self.show_dashboard()
        self.after(1800, lambda: self.check_updates(silent=True))

    def setup_styles(self):
        s=ttk.Style(self); s.theme_use('clam')
        s.configure('Treeview', background=PANEL, fieldbackground=PANEL, foreground=INK, rowheight=30, borderwidth=0, font=('Segoe UI',10))
        s.configure('Treeview.Heading', background='#e7e4dc', foreground=INK, relief='flat', font=('Segoe UI Semibold',10))
        s.map('Treeview', background=[('selected','#ddd6c7')], foreground=[('selected',INK)])
        s.configure('TNotebook', background=BG, borderwidth=0)
        s.configure('TNotebook.Tab', padding=(16,9), font=('Segoe UI Semibold',10), background='#e7e4dc')
        s.map('TNotebook.Tab', background=[('selected',PANEL)], foreground=[('selected',INK)])

    def build_shell(self):
        self.sidebar=tk.Frame(self,bg=DARK,width=238); self.sidebar.pack(side='left',fill='y'); self.sidebar.pack_propagate(False)
        logo_path=ASSET_DIR/'logo-engbers.png'
        try:
            self.logo=tk.PhotoImage(file=str(logo_path))
            # native Tk supports PNG; keep exact supplied logo, scaled down without redraw
            if self.logo.width() > 170:
                factor=max(1, round(self.logo.width()/160))
                self.logo=self.logo.subsample(factor,factor)
            tk.Label(self.sidebar,image=self.logo,bg=DARK,bd=0).pack(padx=24,pady=(22,6),anchor='w')
        except Exception:
            tk.Label(self.sidebar,text='ENGBERS\nINGENIEURBAU',fg='white',bg=DARK,font=('Arial',16,'bold'),justify='left').pack(padx=24,pady=(26,12),anchor='w')
        tk.Label(self.sidebar,text='PROJEKTZENTRALE',fg='#b9b7b0',bg=DARK,font=('Segoe UI',8,'bold')).pack(padx=24,pady=(0,18),anchor='w')
        tk.Button(self.sidebar,text='+  NEUES PROJEKT',command=self.new_project_wizard,anchor='w',bd=0,bg='#b08b49',fg='white',activebackground='#9b783d',activeforeground='white',font=('Segoe UI Semibold',9),padx=24,pady=10,cursor='hand2').pack(fill='x',pady=(0,8))
        self.project_var=tk.StringVar()
        self.project_combo=ttk.Combobox(self.sidebar,textvariable=self.project_var,state='readonly',font=('Segoe UI',9))
        self.project_combo.pack(fill='x',padx=18,pady=(0,14)); self.project_combo.bind('<<ComboboxSelected>>',self.switch_project)
        self.refresh_project_combo()
        nav=[('Übersicht',self.show_dashboard),('Projektakte',self.show_project),('Projekt-Explorer',self.show_project_explorer),('Statik',self.show_statics),('Wärmeschutz',self.show_thermal),('Schallschutz',self.show_acoustic),('Bauleitung',self.show_site),('Kommunikation',self.show_comm),('Aufgaben',self.show_tasks),('Prüfstatik',self.show_checker),('Dokumente',self.show_documents),('PDF stempeln',self.show_pdf_stamp),('Schnittstellen',self.show_interfaces),('Sicherung / Update',self.show_backup)]
        for label,cmd in nav:
            b=tk.Button(self.sidebar,text=label,command=lambda l=label,c=cmd:self.navigate(l,c),anchor='w',bd=0,bg=DARK,fg='#eceae4',activebackground=DARK2,activeforeground='white',font=('Segoe UI',10),padx=24,pady=10,cursor='hand2')
            b.pack(fill='x'); self.nav_buttons[label]=b
            if label=='Statik':
                # PZ_STATIK_PDF_NAV_V1444
                # PZ_STATIK_PDF_NAV_V1445: eigener Statik-PDF-Bereich
                self.statik_pdf_nav=tk.Button(self.sidebar,text='   ↳ Statik PDF',command=self.show_statik_pdf,anchor='w',bd=0,bg=DARK,fg='#b9b7b0',activebackground=DARK2,activeforeground='white',font=('Segoe UI',9),padx=30,pady=5,cursor='hand2')
                self.statik_pdf_nav.pack(fill='x')
        # PZ_STATIK_NAV_SEPARATE_V1448: Hauptpunkt Statik ist fest die mb-/Positionsansicht.
        try:
            if 'Statik' in self.nav_buttons:
                self.nav_buttons['Statik'].configure(command=lambda:self.navigate('Statik',self.show_statics))
        except Exception:
            pass
        tk.Frame(self.sidebar,bg=DARK).pack(fill='both',expand=True)
        tk.Label(self.sidebar,text=f'Version {APP_VERSION}',fg='#85837d',bg=DARK,font=('Segoe UI',8)).pack(padx=24,pady=(8,18),anchor='w')

        self.main=tk.Frame(self,bg=BG); self.main.pack(side='left',fill='both',expand=True)
        top=tk.Frame(self.main,bg=BG,height=76); top.pack(fill='x',padx=30,pady=(18,0)); top.pack_propagate(False)
        self.header=tk.Label(top,text='Projektzentrale',bg=BG,fg=INK,font=('Segoe UI Semibold',24)); self.header.pack(side='left',anchor='center')
        self.search_var=tk.StringVar()
        e=tk.Entry(top,textvariable=self.search_var,font=('Segoe UI',10),bd=0,relief='flat',highlightthickness=1,highlightbackground=LINE,highlightcolor=INK,width=34)
        e.pack(side='right',ipady=8,padx=(10,0)); e.bind('<Return>',lambda _ : self.global_search())
        tk.Button(top,text='Suchen',command=self.global_search,bg=DARK,fg='white',bd=0,padx=16,pady=8).pack(side='right')
        self.content=tk.Frame(self.main,bg=BG); self.content.pack(fill='both',expand=True,padx=30,pady=(4,28))

    def refresh_project_combo(self):
        con=db(); rows=con.execute("SELECT id,number,title FROM projects ORDER BY year DESC, number DESC").fetchall(); con.close()
        self.project_map={f"{r['number']} · {r['title']}":r['id'] for r in rows}
        self.project_combo['values']=list(self.project_map.keys())
        for label,pid in self.project_map.items():
            if pid==self.project_id: self.project_var.set(label); break

    def switch_project(self,event=None):
        label=self.project_var.get()
        if label in self.project_map:
            self.project_id=self.project_map[label]; self.header.configure(text='Projektzentrale'); self.show_dashboard()

    def new_project_wizard(self):
        w=tk.Toplevel(self); w.title('Neues Projekt anlegen'); w.geometry('760x720'); w.configure(bg=BG); w.transient(self); w.grab_set()
        tk.Label(w,text='NEUES PROJEKT',bg=BG,fg=INK,font=('Segoe UI Semibold',22)).pack(anchor='w',padx=28,pady=(24,4))
        tk.Label(w,text='Stammdaten einmal erfassen – alle Fachbereiche verwenden denselben Projektdatensatz.',bg=BG,fg=MUTED,font=('Segoe UI',10)).pack(anchor='w',padx=28,pady=(0,18))
        form=tk.Frame(w,bg=PANEL,highlightbackground=LINE,highlightthickness=1); form.pack(fill='x',padx=28)
        fields=[('Projektnummer*','number'),('Projektbezeichnung*','title'),('Straße / Ort','address'),('Bauherr','client'),('Architekt / Planer','architect'),('Beschreibung','description')]; entries={}
        for label,key in fields:
            row=tk.Frame(form,bg=PANEL); row.pack(fill='x',padx=18,pady=7); tk.Label(row,text=label,width=20,anchor='w',bg=PANEL,fg=MUTED).pack(side='left'); e=tk.Entry(row,font=('Segoe UI',10),bd=0,highlightthickness=1,highlightbackground=LINE); e.pack(side='left',fill='x',expand=True,ipady=6); entries[key]=e
        tk.Label(w,text='LEISTUNGEN / FACHBEREICHE',bg=BG,fg=INK,font=('Segoe UI Semibold',10)).pack(anchor='w',padx=28,pady=(20,8))
        box=tk.Frame(w,bg=PANEL,highlightbackground=LINE,highlightthickness=1); box.pack(fill='x',padx=28)
        opts=['Statik','Prüfstatik','Wärmeschutz','KfW / EEE','DGNB / QNG','Schallschutz','Bauleitung','Kommunikation','Goodnotes / Baustelle','Dokumente']; vars={}
        for i,name in enumerate(opts):
            v=tk.BooleanVar(value=name in ['Statik','Wärmeschutz','Kommunikation','Dokumente']); vars[name]=v; tk.Checkbutton(box,text=name,variable=v,bg=PANEL,fg=INK,activebackground=PANEL,selectcolor=PANEL,font=('Segoe UI',10),anchor='w').grid(row=i//2,column=i%2,sticky='w',padx=18,pady=6)
        def create():
            num=entries['number'].get().strip(); title=entries['title'].get().strip()
            if not num or not title: messagebox.showwarning('Neues Projekt','Projektnummer und Projektbezeichnung sind erforderlich.',parent=w); return
            try:
                con=db(); cur=con.cursor(); cur.execute("INSERT INTO projects(number,title,address,client,architect,status,year,description,created_at,closed_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(num,title,entries['address'].get().strip(),entries['client'].get().strip(),entries['architect'].get().strip(),'Aktiv',datetime.datetime.now().year,entries['description'].get().strip(),now_iso(),'')); pid=cur.lastrowid
                selected=[n for n,v in vars.items() if v.get()]; base=['Projektakte']
                if any(n in selected for n in ['Statik','Prüfstatik']): base.append('Statik')
                if any(n in selected for n in ['Wärmeschutz','KfW / EEE','DGNB / QNG']): base.append('Wärmeschutz')
                if 'Schallschutz' in selected: base.append('Schallschutz')
                if 'Bauleitung' in selected or 'Goodnotes / Baustelle' in selected: base.append('Bauleitung')
                if 'Kommunikation' in selected: base.append('Kommunikation')
                if 'Dokumente' in selected: base.append('Dokumente')
                for i,n in enumerate(base): cur.execute('INSERT INTO disciplines(project_id,name,status,note,sort) VALUES(?,?,?,?,?)',(pid,n,'Aktiv','Projekt neu angelegt',10*(i+1)))
                if 'KfW / EEE' in selected: cur.execute('INSERT INTO thermal(project_id,area,item,status,note) VALUES(?,?,?,?,?)',(pid,'KfW / EEE','Projekt / Förderkonzept','Offen','Nachweise und Baubegleitung strukturieren'))
                if 'Wärmeschutz' in selected: cur.execute('INSERT INTO thermal(project_id,area,item,status,note) VALUES(?,?,?,?,?)',(pid,'Wärmeschutznachweis','GEG / Bilanz','Offen','Nachweis anlegen'))
                if 'DGNB / QNG' in selected:
                    for code,crit in [('ENV1.1','Ökobilanz des Gebäudes'),('ENV1.2','Risiken für die lokale Umwelt'),('ECO1.1','Gebäudebezogene Kosten im Lebenszyklus'),('SOC1.1','Thermischer Komfort'),('SOC1.2','Innenraumluftqualität'),('SOC1.3','Akustischer Komfort'),('TEC1.3','Qualität der Gebäudehülle'),('TEC1.6','Rückbau- und Recyclingfreundlichkeit'),('PRO1.1','Qualität der Projektvorbereitung'),('PRO1.5','Dokumentation für nachhaltige Bewirtschaftung')]: cur.execute('INSERT INTO dgnb(project_id,code,criterion,qng,evidence,owner,status,note) VALUES(?,?,?,?,?,?,?,?)',(pid,code,crit,'zu prüfen','','','Offen',''))
                con.commit(); con.close(); year_folder=PROJECT_ROOT / f'{int(str(num)[:2])+2000} Projekte' if re.match(r'^\d{2}-',num) else PROJECT_ROOT
                year_folder.mkdir(parents=True,exist_ok=True)
                root=year_folder/re.sub(r'[^A-Za-z0-9._-]+','_',f'{num}_{title}'); cur2=db(); cur2.execute('UPDATE projects SET folder_path=? WHERE id=?',(str(root),pid)); cur2.commit(); cur2.close()
                for folder in ['01_Projekt','02_Statik','03_Pruefstatik','04_Waermeschutz','05_DGNB_QNG','06_Schallschutz','07_Bauleitung','08_Kommunikation','09_Dokumente','Goodnotes']: (root/folder).mkdir(parents=True,exist_ok=True)
                self.project_id=pid; self.refresh_project_combo(); w.destroy(); self.show_dashboard(); messagebox.showinfo('Projekt angelegt',f'{num} · {title} wurde angelegt. Fachbereiche können später ergänzt oder entfernt werden.')
            except sqlite3.IntegrityError: messagebox.showerror('Neues Projekt','Diese Projektnummer existiert bereits.',parent=w)
            except Exception as e: messagebox.showerror('Neues Projekt',str(e),parent=w)
        tk.Button(w,text='PROJEKT ANLEGEN',command=create,bg=DARK,fg='white',bd=0,padx=22,pady=11,font=('Segoe UI Semibold',10)).pack(anchor='e',padx=28,pady=22)

    def navigate(self,label,cmd):
        for n,b in self.nav_buttons.items(): b.configure(bg=DARK2 if n==label else DARK)
        self.header.configure(text=label); cmd()

    def clear(self):
        for w in self.content.winfo_children(): w.destroy()

    def titleblock(self,parent,title,subtitle=''):
        f=tk.Frame(parent,bg=BG); f.pack(fill='x',pady=(0,16))
        tk.Label(f,text=title,bg=BG,fg=INK,font=('Segoe UI Semibold',22)).pack(anchor='w')
        if subtitle: tk.Label(f,text=subtitle,bg=BG,fg=MUTED,font=('Segoe UI',10)).pack(anchor='w',pady=(3,0))

    def panel(self,parent,title):
        outer=tk.Frame(parent,bg=PANEL,highlightbackground=LINE,highlightthickness=1)
        tk.Label(outer,text=title.upper(),bg=PANEL,fg=INK,font=('Segoe UI Semibold',9)).pack(anchor='w',padx=16,pady=(13,8))
        tk.Frame(outer,bg=LINE,height=1).pack(fill='x')
        body=tk.Frame(outer,bg=PANEL); body.pack(fill='both',expand=True,padx=16,pady=14)
        return outer,body

    def tree(self,parent,cols,rows,widths=None):
        tr=ttk.Treeview(parent,columns=cols,show='headings')
        for i,c in enumerate(cols):
            tr.heading(c,text=c); tr.column(c,width=(widths[i] if widths else 140),anchor='w')
        for r in rows: tr.insert('', 'end', values=r)
        tr.pack(fill='both',expand=True)
        return tr

    def project_row(self):
        con=db(); r=con.execute('SELECT * FROM projects WHERE id=?',(self.project_id,)).fetchone(); con.close(); return r

    def show_dashboard(self):
        # PZ_DASHBOARD_TO_COCKPIT_V1500
        return self.show_cockpit()


    def show_project(self):
        self.clear(); r=self.project_row(); self.titleblock(self.content,f"{r['number']} · {r['title']}",r['address'])
        actions=tk.Frame(self.content,bg=BG); actions.pack(fill='x',pady=(0,12))
        tk.Button(actions,text='PROJEKTORDNER ÖFFNEN',command=self.open_project_folder,bg=DARK,fg='white',bd=0,padx=16,pady=9).pack(side='left')
        tk.Button(actions,text='BESTEHENDEN ORDNER ZUORDNEN',command=self.assign_existing_folder,bg='#e7e4dc',fg=INK,bd=0,padx=16,pady=9).pack(side='left',padx=8)
        tk.Button(actions,text='BESTAND 2025/2026 EINLESEN',command=self.scan_existing_projects,bg='#e7e4dc',fg=INK,bd=0,padx=16,pady=9).pack(side='left')
        tk.Button(actions,text='PROJEKT ANALYSIEREN',command=self.analyze_project,bg=ACCENT,fg='white',bd=0,padx=16,pady=9).pack(side='left',padx=8)
        actions2=tk.Frame(self.content,bg=BG); actions2.pack(fill='x',pady=(0,12))
        tk.Button(actions2,text='STAMMDATEN AUS PLÄNEN',command=self.masterdata_from_plans,bg=DARK,fg='white',bd=0,padx=16,pady=9).pack(side='left')
        tk.Button(actions2,text='STAMMDATEN BEARBEITEN',command=self.edit_project_masterdata,bg='#e7e4dc',fg=INK,bd=0,padx=16,pady=9).pack(side='left',padx=8)
        tk.Button(actions2,text='WORD-BESCHEINIGUNGEN',command=self.word_bescheinigungen,bg=DARK,fg='white',bd=0,padx=16,pady=9).pack(side='left')
        # PZ_MASTERDATA_CARDS_V1604
        # PZ_MASTERDATA_NAME_ADDRESS_FIX_V1605: vollständige zentrale Stammdaten direkt in der Projektakte.
        from masterdata_v1604 import render_project_masterdata_cards
        render_project_masterdata_cards(self,self.content)
        pan2,b2=self.panel(self.content,'Fachbereiche'); pan2.pack(fill='x',pady=(4,0))
        con=db(); rows=con.execute('SELECT name,status,note FROM disciplines WHERE project_id=? ORDER BY sort',(self.project_id,)).fetchall(); con.close()
        disc_tree=self.tree(b2,('Fachbereich','Status','Hinweis'),[tuple(x) for x in rows],[150,100,420])
        disc_tree.configure(height=max(1,min(len(rows),6)))
        con=db(); indexed=con.execute('SELECT COUNT(*) c FROM project_file_index WHERE project_id=?',(self.project_id,)).fetchone()['c']; rows=con.execute('SELECT filename,category,extension,modified_text,rel_path FROM project_file_index WHERE project_id=? ORDER BY modified_ts DESC LIMIT 120',(self.project_id,)).fetchall(); con.close()
        pan3,b3=self.panel(self.content,f'Dateibestand · {indexed} indexierte Dateien'); pan3.pack(fill='both',expand=True,pady=(16,0))
        if rows:
            cols=('Datei','Fachbereich','Typ','Geändert','Unterordner')
            wrap=tk.Frame(b3,bg=PANEL); wrap.pack(fill='both',expand=True)
            tr=ttk.Treeview(wrap,columns=cols,show='headings',height=12)
            widths=[300,150,80,145,420]
            for i,c in enumerate(cols):
                tr.heading(c,text=c); tr.column(c,width=widths[i],anchor='w')
            for x in rows:
                sub=str(Path(x['rel_path']).parent); sub='—' if sub=='.' else sub
                tr.insert('', 'end', values=(x['filename'],x['category'],x['extension'] or '—',x['modified_text'],sub), tags=(x['rel_path'],))
            sy=ttk.Scrollbar(wrap,orient='vertical',command=tr.yview); sx=ttk.Scrollbar(wrap,orient='horizontal',command=tr.xview)
            tr.configure(yscrollcommand=sy.set,xscrollcommand=sx.set)
            tr.grid(row=0,column=0,sticky='nsew'); sy.grid(row=0,column=1,sticky='ns'); sx.grid(row=1,column=0,sticky='ew')
            wrap.grid_rowconfigure(0,weight=1); wrap.grid_columnconfigure(0,weight=1)
            def open_indexed(_evt=None):
                sel=tr.selection()
                if not sel: return
                tags=tr.item(sel[0],'tags')
                if not tags: return
                target=Path(self.get_project_folder())/tags[0]
                try:
                    if os.name=='nt': os.startfile(str(target))
                    elif sys.platform=='darwin': os.system(f'open \"{target}\"')
                    else: os.system(f'xdg-open \"{target}\" >/dev/null 2>&1 &')
                except Exception as e: messagebox.showerror('Datei öffnen',str(e))
            tr.bind('<Double-1>',open_indexed)
            tk.Label(b3,text='Anzeige: die 120 zuletzt geänderten Dateien · Doppelklick öffnet die Originaldatei. Originaldateien bleiben unverändert.',bg=PANEL,fg=MUTED,anchor='w').pack(fill='x',pady=(8,0))
        else:
            tk.Label(b3,text='Noch kein Dateibestand indexiert. „PROJEKT ANALYSIEREN“ liest den Projektordner ausschließlich lesend ein.',bg=PANEL,fg=MUTED,anchor='w').pack(fill='x',pady=8)

    def masterdata_from_plans(self):
        # PZ_MASTERDATA_CARDS_V1604
        from masterdata_v1604 import open_masterdata
        return open_masterdata(self)

    def word_bescheinigungen(self):
        # PZ_WORD_BESCHEINIGUNGEN_V1700
        from wordforms_v1700 import open_wordforms
        return open_wordforms(self)

    def edit_project_masterdata(self):
        # PZ_MASTERDATA_EDIT_V1860
        from masterdata_edit_v1860 import open_masterdata_editor
        return open_masterdata_editor(self)

    def show_pdf_stamp(self):
        # PZ_PDF_STAMP_TOOL_V1860
        from pdf_stamp_v1860 import open_pdf_stamp_dialog
        return open_pdf_stamp_dialog(self)

    def get_project_folder(self, row=None):
        row=row or self.project_row()
        try:
            fp=row['folder_path']
        except Exception:
            fp=''
        if fp: return fp
        return str(PROJECT_ROOT/re.sub(r'[^A-Za-z0-9._-]+','_',f"{row['number']}_{row['title']}"))

    def open_project_folder(self):
        r=self.project_row(); folder=Path(self.get_project_folder(r)); folder.mkdir(parents=True,exist_ok=True)
        try:
            if os.name=='nt': os.startfile(str(folder))
            elif sys.platform=='darwin': os.system(f'open "{folder}"')
            else: os.system(f'xdg-open "{folder}" >/dev/null 2>&1 &')
        except Exception as e: messagebox.showerror('Projektordner',str(e))

    def scan_existing_projects(self):
        candidates=[]
        for year in (2025,2026):
            base=PROJECT_ROOT/f"{year} Projekte"
            if not base.exists(): continue
            for folder in sorted([x for x in base.iterdir() if x.is_dir()]):
                m=re.match(r"^(\d{2}-\d{2,4})(?:[ _-]+(.*))?$",folder.name)
                if not m: continue
                num=m.group(1); title=(m.group(2) or folder.name).strip(" _-")
                candidates.append((num,title,folder,year))
        if not candidates:
            messagebox.showinfo('Bestandsprojekte','In den Ordnern 2025 Projekte und 2026 Projekte wurden keine passenden Projektordner gefunden.')
            return
        con=db(); existing={r[0] for r in con.execute('SELECT number FROM projects')}; con.close()
        new=[c for c in candidates if c[0] not in existing]
        preview='\n'.join(f"{n} · {t}" for n,t,_,_ in new[:30])
        more=f"\n… und {len(new)-30} weitere" if len(new)>30 else ''
        if not new:
            messagebox.showinfo('Bestandsprojekte',f'{len(candidates)} Projektordner gefunden; alle sind bereits registriert.')
            return
        if not messagebox.askyesno('Bestandsprojekte registrieren',f"Gefunden: {len(candidates)}\nNeu zu registrieren: {len(new)}\n\n{preview}{more}\n\nNur Pfade registrieren? Dateien und Ordner werden NICHT verändert."):
            return
        con=db(); cur=con.cursor(); added=0
        for num,title,folder,year in new:
            try:
                cur.execute('INSERT INTO projects(number,title,address,client,architect,status,year,description,created_at,folder_path) VALUES(?,?,?,?,?,?,?,?,?,?)',(num,title,'','','','Bestand',year,'Bestehendes Projekt – nur registriert',now_iso(),str(folder)))
                added+=1
            except sqlite3.IntegrityError: pass
        con.commit(); con.close(); self.refresh_project_combo()
        messagebox.showinfo('Bestandsprojekte',f'{added} Projekte wurden registriert.\n\nEs wurden keine Projektdateien verschoben, umbenannt, kopiert oder gelöscht.')

    def classify_project_file(self, rel_path):
        text=str(rel_path).lower().replace('\\','/')
        rules=[
            ('Baugrund / Bodengutachten',('bodengutachten','baugrund','geotechnik','gründung','gruendung','bodenpressung','grundwasser','erdstoff','soil')),
            ('Prüfstatik',('prüfstatik','pruefstatik','prüfbericht','pruefbericht','prüfer','pruefer')),
            ('DGNB/QNG',('dgnb','qng','ökobilanz','oekobilanz','lca')),
            ('Wärmeschutz',('wärmeschutz','waermeschutz','energie','kfw','eee',' geg','geg_','energieausweis')),
            ('Schallschutz',('schallschutz','akustik','schall')),
            ('Bauleitung',('bauleitung','baustelle','mangel','abnahme','fotodoku','goodnotes')),
            ('Kommunikation',('schriftverkehr','kommunikation','email','e-mail','whatsapp','anschreiben','protokoll')),
            ('Bescheinigungen',('bescheinigung','bescheinigungen','bestätigung','bestaetigung','formular','wordformblätter','wordformblaetter')),
            ('Pläne / CAD',('pläne','plaene','planunterlagen','zeichnungen','cad')),
            ('Statik',('statik','baustatik','bemessung','tragwerk','bewehrung','schalplan','positionsplan','microfe','idea','allplan')),
        ]
        for name,keys in rules:
            if any(k in text for k in keys): return name,'hoch'
        ext=Path(rel_path).suffix.lower()
        if ext in ('.dwg','.dxf','.ifc','.skp','.c4d'): return 'Pläne / CAD','mittel'
        if ext in ('.eml','.msg'): return 'Kommunikation','hoch'
        if ext in ('.jpg','.jpeg','.png','.heic'): return 'Fotos / Bilder','mittel'
        if ext in ('.pdf','.doc','.docx','.xls','.xlsx','.xlsm','.txt'): return 'Dokumente','niedrig'
        return 'Sonstiges','niedrig'

    def analyze_project(self):
        """Read-only scan + local metadata index. Original project files are never changed."""
        r=self.project_row(); folder=Path(self.get_project_folder(r))
        if not folder.exists():
            messagebox.showwarning('Projektanalyse',f'Der Projektordner wurde nicht gefunden:\n{folder}')
            return
        files=[]
        try:
            for p in folder.rglob('*'):
                if p.is_file(): files.append(p)
        except Exception as e:
            messagebox.showerror('Projektanalyse',f'Projektordner konnte nicht vollständig gelesen werden:\n{e}')
            return
        category_counts={}; ext_counts={}; entries=[]
        for p in files:
            rel=p.relative_to(folder)
            category,confidence=self.classify_project_file(rel)
            category_counts[category]=category_counts.get(category,0)+1
            ext=(p.suffix.lower() or '(ohne Endung)')
            ext_counts[ext]=ext_counts.get(ext,0)+1
            try:
                st=p.stat(); mtext=datetime.datetime.fromtimestamp(st.st_mtime).strftime('%d.%m.%Y %H:%M')
                entries.append((str(rel),p.name,ext,st.st_size,st.st_mtime,mtext,category,confidence))
            except OSError:
                entries.append((str(rel),p.name,ext,0,0.0,'—',category,confidence))
        fachbereiche=[x for x in ('Statik','Prüfstatik','Wärmeschutz','DGNB/QNG','Schallschutz','Bauleitung','Kommunikation','Dokumente') if category_counts.get(x,0)>0]
        top_ext=sorted(ext_counts.items(),key=lambda x:(-x[1],x[0]))[:10]
        ext_text=', '.join(f'{k}: {v}' for k,v in top_ext) if top_ext else 'keine Dateien'
        cat_text='\n'.join(f'• {k}: {v} Dateien' for k,v in sorted(category_counts.items(),key=lambda x:(-x[1],x[0]))) or '• keine Dateien'
        msg=(f"Projekt: {r['number']} · {r['title']}\n"
             f"Ordner: {folder}\n\n"
             f"Gefundene Dateien: {len(files)}\n"
             f"Dateitypen: {ext_text}\n\n"
             f"Vorgeschlagene Zuordnung:\n{cat_text}\n\n"
             f"Erkannte Fachbereiche: {', '.join(fachbereiche) if fachbereiche else 'keine'}\n\n"
             "Dateibestand lokal indexieren und erkannte Fachbereiche registrieren?\n"
             "Originaldateien und Ordner werden NICHT verändert.")
        if not messagebox.askyesno('Projektanalyse – Vorschau',msg): return
        con=db(); cur=con.cursor()
        cur.execute('DELETE FROM project_file_index WHERE project_id=?',(self.project_id,))
        cur.executemany('INSERT INTO project_file_index(project_id,rel_path,filename,extension,size_bytes,modified_ts,modified_text,category,confidence) VALUES(?,?,?,?,?,?,?,?,?)',[(self.project_id,*e) for e in entries])
        existing={x[0] for x in cur.execute('SELECT name FROM disciplines WHERE project_id=?',(self.project_id,)).fetchall()}
        added=0; sort=10
        for name in fachbereiche:
            count=category_counts.get(name,0)
            note=f'Automatische Projektanalyse: {count} Dateien zugeordnet'
            if name not in existing:
                cur.execute('INSERT INTO disciplines(project_id,name,status,note,sort) VALUES(?,?,?,?,?)',(self.project_id,name,'Erkannt',note,sort)); added+=1
            else:
                cur.execute("UPDATE disciplines SET note=? WHERE project_id=? AND name=? AND status='Erkannt'",(note,self.project_id,name))
            sort+=10
        con.commit(); con.close()
        messagebox.showinfo('Projektanalyse',f'Analyse abgeschlossen.\n\n{len(files)} Dateien indexiert.\n{len(fachbereiche)} Fachbereiche erkannt, {added} neu registriert.\n\nEs wurden keine Originaldateien verändert.')
        self.show_project()

    def assign_existing_folder(self):
        folder=filedialog.askdirectory(title='Bestehenden Projektordner auswählen')
        if not folder: return
        con=db(); con.execute('UPDATE projects SET folder_path=? WHERE id=?',(folder,self.project_id)); con.commit(); con.close()
        messagebox.showinfo('Projektordner','Der bestehende Ordner wurde dem Projekt zugeordnet. Es wurden keine Dateien verschoben oder kopiert.')
        self.show_project()

    def open_external_path(self, target):
        """Öffnet eine vorhandene Originaldatei oder einen Ordner; verändert nichts am Ziel."""
        target=Path(target)
        if not target.exists():
            messagebox.showwarning('Öffnen',f'Pfad wurde nicht gefunden:\n{target}')
            return False
        try:
            if os.name=='nt': os.startfile(str(target))
            elif sys.platform=='darwin': subprocess.Popen(['open',str(target)])
            else: subprocess.Popen(['xdg-open',str(target)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            messagebox.showerror('Öffnen',str(e)); return False

    def _settings_dict(self):
        try:
            return json.loads(SETTINGS_PATH.read_text(encoding='utf-8')) if SETTINGS_PATH.exists() else {}
        except Exception:
            return {}

    def _save_program_path(self, key, path):
        cfg=self._settings_dict(); paths=cfg.get('program_paths') or {}; paths[key]=str(path); cfg['program_paths']=paths; cfg['configured']=True
        APPDATA.mkdir(parents=True,exist_ok=True)
        SETTINGS_PATH.write_text(json.dumps(cfg,indent=2,ensure_ascii=False),encoding='utf-8')

    def launch_configured_program(self, key, label):
        cfg=self._settings_dict(); raw=(cfg.get('program_paths') or {}).get(key,''); path=Path(raw) if raw else None
        if not path or not path.exists():
            if not messagebox.askyesno(label,f'Für {label} ist noch kein Programm hinterlegt.\n\nJetzt die EXE-Datei auswählen?'):
                return
            chosen=filedialog.askopenfilename(title=f'{label} – Programmdatei auswählen',filetypes=[('Programme','*.exe'),('Alle Dateien','*.*')])
            if not chosen: return
            path=Path(chosen); self._save_program_path(key,path)
        try:
            subprocess.Popen([str(path)],cwd=str(path.parent))
        except Exception as e:
            messagebox.showerror(label,f'Programm konnte nicht gestartet werden:\n{e}')

    # PZ_COCKPIT_V1500
    def _pz150_settings(self):
        try:
            return json.loads(SETTINGS_PATH.read_text(encoding='utf-8')) if SETTINGS_PATH.exists() else {}
        except Exception:
            return {}

    def _pz150_save_setting(self,key,value):
        cfg=self._pz150_settings(); cfg[key]=value; cfg['configured']=True
        APPDATA.mkdir(parents=True,exist_ok=True)
        SETTINGS_PATH.write_text(json.dumps(cfg,indent=2,ensure_ascii=False),encoding='utf-8')

    def _pz150_mb_projects(self):
        """Read-only scan of mb project folders for the active project."""
        try:r=self.project_row(); root=Path(self.get_project_folder(r) or '')
        except Exception:root=Path(self.get_project_folder() or '')
        out=[]; seen=set()
        if not root.exists(): return out
        candidates=[]
        try:
            for d in root.rglob('*'):
                if not d.is_dir(): continue
                norm=''.join(ch for ch in d.name.casefold() if ch.isalnum())
                if norm in ('mbsoftware','mbaec','mbworksite','mbworksuite'):
                    candidates.append(d)
        except Exception:
            pass
        for mr in candidates:
            try: folders=[x for x in mr.iterdir() if x.is_dir()]
            except Exception: folders=[]
            for folder in folders:
                key=str(folder).casefold()
                if key in seen: continue
                try:
                    mbps=list(folder.glob('*.mbp'))
                    dbs=list(folder.rglob('BSPos.mbdb'))
                except Exception:
                    mbps=[]; dbs=[]
                if not mbps and not dbs: continue
                seen.add(key)
                stamp=0
                for f in mbps+dbs:
                    try: stamp=max(stamp,f.stat().st_mtime)
                    except Exception: pass
                year='—'
                hay=' '.join([folder.name,str(folder)]+[x.name for x in mbps])
                years=re.findall(r'20(?:2[0-9])',hay)
                if years: year=years[-1]
                changed=datetime.datetime.fromtimestamp(stamp).strftime('%d.%m.%Y %H:%M') if stamp else '—'
                out.append({'name':folder.name,'path':str(folder),'version':year,'mbp':len(mbps),'db':len(dbs),'changed':changed,'stamp':stamp})
        # Fallback: einzelne .mbp-Projekte, die nicht unter einem typischen mb-Stammordner liegen.
        try:
            for mbp in root.rglob('*.mbp'):
                folder=mbp.parent; key=str(folder).casefold()
                if key in seen: continue
                seen.add(key)
                try:stamp=mbp.stat().st_mtime
                except Exception:stamp=0
                years=re.findall(r'20(?:2[0-9])',str(folder)+' '+mbp.name)
                out.append({'name':folder.name,'path':str(folder),'version':years[-1] if years else '—','mbp':len(list(folder.glob('*.mbp'))),'db':len(list(folder.rglob('BSPos.mbdb'))),'changed':datetime.datetime.fromtimestamp(stamp).strftime('%d.%m.%Y %H:%M') if stamp else '—','stamp':stamp})
        except Exception:
            pass
        out.sort(key=lambda x:(-x['stamp'],x['name'].casefold()))
        return out

    def _pz150_installed_mb_versions(self):
        years=set(); paths=[]
        roots=[]
        for env in ('ProgramFiles','ProgramFiles(x86)','ProgramW6432'):
            v=os.environ.get(env)
            if v and Path(v).exists() and str(Path(v)).casefold() not in [str(x).casefold() for x in roots]: roots.append(Path(v))
        for root in roots:
            try:
                level1=list(root.iterdir())
            except Exception:
                level1=[]
            for d in level1:
                if not d.is_dir(): continue
                dn=d.name.casefold()
                if 'mb' not in dn and 'baustatik' not in dn and 'worksuite' not in dn: continue
                paths.append(str(d))
                scan=[d]
                try:scan += [x for x in d.iterdir() if x.is_dir()]
                except Exception:pass
                for x in scan:
                    for y in re.findall(r'20(?:2[0-9])',str(x)):
                        years.add(y)
        return sorted(years),paths

    def _pz150_pdf_stats(self):
        try:r=self.project_row(); root=Path(self.get_project_folder(r) or '')
        except Exception:root=Path(self.get_project_folder() or '')
        count=0; latest=0; folders=set()
        if root.exists():
            try:
                for p in root.rglob('*.pdf'):
                    count+=1; folders.add(str(p.parent))
                    try:latest=max(latest,p.stat().st_mtime)
                    except Exception:pass
            except Exception:pass
        return count,len(folders),(datetime.datetime.fromtimestamp(latest).strftime('%d.%m.%Y %H:%M') if latest else '—')

    def _pz150_set_favorite_mb(self,path):
        cfg=self._pz150_settings(); fav=cfg.get('mb_project_favorites',{})
        fav[str(self.project_id)]=str(path); self._pz150_save_setting('mb_project_favorites',fav)
        messagebox.showinfo('Haupt-MB-Projekt','Dieses MB-Projekt ist jetzt als Hauptprojekt markiert.')
        self.show_cockpit()

    def _pz150_open_mb_folder_project(self,folder):
        folder=Path(folder)
        try:mbps=sorted(folder.glob('*.mbp'),key=lambda p:p.name.casefold())
        except Exception:mbps=[]
        if mbps:self.open_external_path(mbps[0])
        else:self.open_external_path(folder)

    def _pz150_open_path(self,path):
        try:self.open_external_path(Path(path))
        except Exception as e:messagebox.showwarning('Öffnen',str(e))

    def _pz150_project_check(self):
        try:r=self.project_row(); root=Path(self.get_project_folder(r) or '')
        except Exception:root=Path(self.get_project_folder() or '')
        mb=self._pz150_mb_projects(); pdfn,_,_=self._pz150_pdf_stats(); checks=[]
        checks.append(('Projektordner','OK' if root.exists() else 'FEHLT',str(root)))
        checks.append(('MB-Projekt','OK' if mb else 'FEHLT',f'{len(mb)} erkannt'))
        checks.append(('PDF-Bestand','OK' if pdfn else 'HINWEIS',f'{pdfn} PDF-Dateien'))
        for names,label in [(('prüfstatik','pruefstatik'),'Prüfstatik'),(('baugrund','bodengutachten'),'Baugrund')]:
            if isinstance(names,str): names=(names,)
            found=False
            if root.exists():
                try:found=any(any(k in p.name.casefold() for k in names) for p in root.rglob('*') if p.is_dir())
                except Exception:pass
            checks.append((label,'OK' if found else 'HINWEIS','Ordner erkannt' if found else 'nicht eindeutig erkannt'))
        return checks

    def show_cockpit(self):
        self.clear(); r=self.project_row()
        self.titleblock(self.content,'Projekt-Cockpit',f"{r['number']} · {r['title']} · Projektzentrale 1.8.5")
        self.program_starter_bar(self.content)
        mb=self._pz150_mb_projects(); years,_hits=self._pz150_installed_mb_versions(); pdfn,pdffolders,pdflatest=self._pz150_pdf_stats(); checks=self._pz150_project_check()
        cfg=self._pz150_settings(); fav=str(cfg.get('mb_project_favorites',{}).get(str(self.project_id),''))
        cards=tk.Frame(self.content,bg=BG); cards.pack(fill='x',pady=(0,14))
        vals=[('MB-PROJEKTE',str(len(mb)),('Installierte Jahresversionen: '+', '.join(years)) if years else 'Installierte MB-Jahresversionen noch nicht eindeutig erkannt'),('PDF-DATEIEN',str(pdfn),f'{pdffolders} Ordner · zuletzt {pdflatest}'),('PROJEKTCHECK',f"{sum(1 for x in checks if x[1]=='OK')}/{len(checks)}",'nur lesende Prüfung')]
        for i,(a,b,c) in enumerate(vals):
            p,body=self.panel(cards,a); p.pack(side='left',fill='both',expand=True,padx=(0 if i==0 else 7,0 if i==len(vals)-1 else 7))
            tk.Label(body,text=b,bg=PANEL,fg=INK,font=('Segoe UI Semibold',24)).pack(anchor='w')
            tk.Label(body,text=c,bg=PANEL,fg=MUTED,font=('Segoe UI',9),wraplength=330,justify='left').pack(anchor='w')

        pan,body=self.panel(self.content,'MB-Projekte / Hauptprojekt'); pan.pack(fill='both',expand=True,pady=(0,12))
        cols=('Haupt','MB-Projekt','Jahresinfo','Geändert','.mbp','BSPos DB','Pfad')
        tr=ttk.Treeview(body,columns=cols,show='headings',height=8)
        widths=[55,210,95,145,60,75,500]
        for i,c in enumerate(cols):tr.heading(c,text=c); tr.column(c,width=widths[i],anchor='w')
        by_iid={}
        for x in mb:
            isfav=bool(fav and str(Path(fav)).casefold()==str(Path(x['path'])).casefold())
            iid=tr.insert('','end',values=('★' if isfav else '',x['name'],x['version'],x['changed'],x['mbp'],x['db'],x['path'])); by_iid[iid]=x
        tr.pack(fill='both',expand=True)
        buttons=tk.Frame(body,bg=PANEL); buttons.pack(fill='x',pady=(8,0))
        def selected():
            s=tr.selection(); return by_iid.get(s[0]) if s else None
        tk.Button(buttons,text='MB-PROJEKT ÖFFNEN',bg=DARK,fg='white',bd=0,padx=14,pady=7,command=lambda:self._pz150_open_mb_folder_project(selected()['path']) if selected() else None).pack(side='left')
        tk.Button(buttons,text='ALS HAUPTPROJEKT',bg=ACCENT,fg='white',bd=0,padx=14,pady=7,command=lambda:self._pz150_set_favorite_mb(selected()['path']) if selected() else None).pack(side='left',padx=8)
        tk.Button(buttons,text='ORDNER ÖFFNEN',bg='#e7e4dc',fg=INK,bd=0,padx=14,pady=7,command=lambda:self._pz150_open_path(selected()['path']) if selected() else None).pack(side='left')
        tr.bind('<Double-1>',lambda e:self._pz150_open_mb_folder_project(selected()['path']) if selected() else None)

        bottom=tk.Frame(self.content,bg=BG); bottom.pack(fill='x')
        p1,b1=self.panel(bottom,'Projektprüfung'); p1.pack(side='left',fill='both',expand=True,padx=(0,8))
        self.tree(b1,('Bereich','Status','Hinweis'),checks,[150,90,340]).configure(height=5)
        p2,b2=self.panel(bottom,'1.5 · vorbereitet für Netzwerk / iPad / Handy'); p2.pack(side='left',fill='both',expand=True,padx=(8,0))
        text=('✓ parallele MB-Jahresversionen vorbereitet\n'
              '✓ Haupt-MB-Projekt pro Projekt merkbar\n'
              '✓ alte MB-Projektordner bleiben unverändert\n'
              '✓ Projekt- und Dokumentpfade bleiben versionsneutral\n'
              '✓ Update-Rollback und Cache-Schutz aktiv')
        tk.Label(b2,text=text,bg=PANEL,fg=INK,justify='left',anchor='nw',font=('Segoe UI',10)).pack(fill='both',expand=True)

    def launch_mb_project_for_current(self):
        # PZ_MB_LAUNCHER_V1500
        try:projects=self._pz150_mb_projects()
        except Exception:projects=[]
        if not projects:
            root=Path(self.get_project_folder())
            try:files=sorted(root.rglob('*.mbp'),key=lambda x:str(x).casefold()) if root.exists() else []
            except Exception:files=[]
            if not files:
                messagebox.showinfo('mb AEC','Im aktuellen Projekt wurde kein mb-Projekt gefunden.'); return
            projects=[{'name':p.stem,'path':str(p.parent),'version':'—','changed':'—'} for p in files]
        cfg=self._pz150_settings() if hasattr(self,'_pz150_settings') else {}
        fav=str(cfg.get('mb_project_favorites',{}).get(str(self.project_id),''))
        favorite=next((x for x in projects if fav and str(Path(x['path'])).casefold()==str(Path(fav)).casefold()),None)
        if favorite is not None:
            self._pz150_open_mb_folder_project(favorite['path']); return
        if len(projects)==1:
            self._pz150_open_mb_folder_project(projects[0]['path']); return
        w=tk.Toplevel(self); w.title('mb-Projekt auswählen'); w.geometry('900x410'); w.configure(bg=BG); w.transient(self)
        tk.Label(w,text='MB-PROJEKT AUSWÄHLEN',bg=BG,fg=INK,font=('Segoe UI Semibold',13)).pack(anchor='w',padx=20,pady=(18,4))
        tk.Label(w,text='Es wird nur das ausgewählte Projekt geöffnet. Vorhandene ältere Projektordner bleiben unverändert.',bg=BG,fg=MUTED,font=('Segoe UI',9)).pack(anchor='w',padx=20,pady=(0,10))
        cols=('Projekt','Jahresinfo','Geändert','Pfad'); tr=ttk.Treeview(w,columns=cols,show='headings',height=12)
        for c,width in (('Projekt',230),('Jahresinfo',90),('Geändert',145),('Pfad',400)):
            tr.heading(c,text=c); tr.column(c,width=width,anchor='w')
        imap={}
        for x in projects:
            iid=tr.insert('','end',values=(x.get('name',''),x.get('version','—'),x.get('changed','—'),x.get('path',''))); imap[iid]=x
        tr.pack(fill='both',expand=True,padx=20,pady=(0,10))
        def selected():
            s=tr.selection(); return imap.get(s[0]) if s else None
        def go(_evt=None):
            x=selected()
            if x:w.destroy(); self._pz150_open_mb_folder_project(x['path'])
        tr.bind('<Double-1>',go); tr.bind('<Return>',go)
        bar=tk.Frame(w,bg=BG); bar.pack(fill='x',padx=20,pady=(0,16))
        tk.Button(bar,text='ÖFFNEN',command=go,bg=DARK,fg='white',bd=0,padx=16,pady=8).pack(side='right')
        tk.Button(bar,text='ALS HAUPTPROJEKT MERKEN',command=lambda:self._pz150_set_favorite_mb(selected()['path']) if selected() else None,bg=ACCENT,fg='white',bd=0,padx=16,pady=8).pack(side='right',padx=(0,8))


    def program_starter_bar(self, parent):
        bar=tk.Frame(parent,bg=BG); bar.pack(fill='x',pady=(0,12))
        tk.Label(bar,text='PROGRAMME',bg=BG,fg=MUTED,font=('Segoe UI Semibold',8)).pack(side='left',padx=(0,10))
        specs=[
            ('EXPLORER',lambda:self.open_external_path(self.get_project_folder()),DARK),
            ('MB AEC',self.launch_mb_project_for_current,ACCENT),
            ('ALLPLAN',lambda:self.launch_configured_program('allplan','Allplan'),'#e7e4dc'),
            ('ALLMENU',lambda:self.launch_configured_program('allmenu','Allmenu'),'#e7e4dc'),
            ('IDEA STATICA',lambda:self.launch_configured_program('idea','IDEA StatiCa'),'#e7e4dc'),
            ('WÄRMESCHUTZ',lambda:self.launch_configured_program('waermeschutz','Wärmeschutz'),'#e7e4dc')]
        for text,cmd,bg in specs:
            fg='white' if bg in (DARK,ACCENT) else INK
            tk.Button(bar,text=text,command=cmd,bg=bg,fg=fg,activebackground=bg,activeforeground=fg,bd=0,padx=13,pady=7,font=('Segoe UI Semibold',8)).pack(side='left',padx=(0,6))
        tk.Label(bar,text='Nicht hinterlegte Programme fragen beim ersten Start nach der EXE-Datei.',bg=BG,fg=MUTED,font=('Segoe UI',8)).pack(side='right')
        return bar

    def _manual_assignment(self, rel_path):
        rel=str(rel_path).replace('\\','/')
        con=db()
        rows=con.execute('SELECT rel_path,is_folder,category FROM file_assignments WHERE project_id=?',(self.project_id,)).fetchall(); con.close()
        exact=None; inherited=None; best=-1
        for r in rows:
            rr=str(r['rel_path']).replace('\\','/').rstrip('/')
            if rel==rr: exact=(r['category'],'manuell')
            elif r['is_folder'] and (rel.startswith(rr+'/')) and len(rr)>best:
                inherited=(r['category'],'Ordnerregel'); best=len(rr)
        return exact or inherited

    def _effective_category(self, rel_path):
        m=self._manual_assignment(rel_path)
        if m:return m
        cat,conf=self.classify_project_file(rel_path)
        return cat,'automatisch · '+conf

    def _set_file_assignment(self, rel_path, is_folder, category):
        rel=str(rel_path).replace('\\','/')
        con=db(); con.execute('INSERT OR REPLACE INTO file_assignments(project_id,rel_path,is_folder,category,assigned_at) VALUES(?,?,?,?,?)',(self.project_id,rel,1 if is_folder else 0,category,now_iso())); con.commit(); con.close()

    def _project_sources(self):
        """Primary project folder plus manually linked folders. Read-only sources."""
        r=self.project_row(); primary=Path(self.get_project_folder(r))
        out=[{'path':primary,'label':f"{r['number']} · {r['title']}",'kind':'Hauptordner','source_project_id':self.project_id}]
        con=db(); rows=con.execute('SELECT source_project_id,folder_path,label,source_type FROM project_sources WHERE project_id=? ORDER BY id',(self.project_id,)).fetchall(); con.close()
        seen={str(primary).casefold()}
        for x in rows:
            pp=Path(x['folder_path'])
            if str(pp).casefold() in seen: continue
            seen.add(str(pp).casefold()); out.append({'path':pp,'label':x['label'] or pp.name,'kind':'Verknüpft','source_project_id':x['source_project_id']})
        return out

    def _link_project_source(self):
        con=db(); rows=con.execute('SELECT id,number,title,folder_path FROM projects WHERE id<>? ORDER BY number',(self.project_id,)).fetchall(); con.close()
        w=tk.Toplevel(self); w.title('Projektordner verknüpfen'); w.geometry('700x430'); w.configure(bg=BG); w.transient(self); w.grab_set()
        tk.Label(w,text='ZUGEHÖRIGEN PROJEKTORDNER VERKNÜPFEN',bg=BG,fg=INK,font=('Segoe UI Semibold',13)).pack(anchor='w',padx=20,pady=(18,5))
        tk.Label(w,text='Die Ordner bleiben an ihrem Windows-Speicherort. Die Projektzentrale merkt sich nur die fachliche Verknüpfung.',bg=BG,fg=MUTED,wraplength=650,justify='left').pack(anchor='w',padx=20,pady=(0,12))
        lb=tk.Listbox(w,font=('Segoe UI',10),bd=0,highlightthickness=1,highlightbackground=LINE); lb.pack(fill='both',expand=True,padx=20)
        valid=[]
        for x in rows:
            fp=x['folder_path'] or ''
            if fp and Path(fp).exists():
                valid.append(x); lb.insert('end',f"{x['number']} · {x['title']}    |    {fp}")
        def save():
            sel=lb.curselection()
            if not sel:return
            x=valid[sel[0]]; con=db(); con.execute('INSERT OR IGNORE INTO project_sources(project_id,source_project_id,folder_path,label,source_type,created_at) VALUES(?,?,?,?,?,?)',(self.project_id,x['id'],x['folder_path'],f"{x['number']} · {x['title']}",'Projektordner',now_iso())); con.commit(); con.close(); w.destroy(); self.show_project_explorer()
        tk.Button(w,text='VERKNÜPFEN',command=save,bg=ACCENT,fg='white',bd=0,padx=16,pady=8).pack(anchor='e',padx=20,pady=16)

    def _unlink_project_source(self, folder_path):
        if not messagebox.askyesno('Verknüpfung lösen','Nur die Verknüpfung in der Projektzentrale lösen?\n\nDie Originaldateien bleiben vollständig unverändert.'): return
        con=db(); con.execute('DELETE FROM project_sources WHERE project_id=? AND folder_path=?',(self.project_id,str(folder_path))); con.commit(); con.close(); self.show_project_explorer()

    def show_project_explorer(self):
        # PZ_PROJECT_EXPLORER_SELECT_FIX_V1506
        # Dateisystem-I/O nur im Worker. Worker beruehrt Tkinter NICHT.
        # Ergebnisse kommen ueber Queue zurueck; Tk arbeitet ausschliesslich im Hauptthread.
        self.clear()
        r = self.project_row()
        sources = self._project_sources()
        self.titleblock(self.content, 'Projekt-Explorer', f"{r['number']} · {r['title']} · stabile Ordneransicht")
        self.program_starter_bar(self.content)

        import queue as _queue
        import threading as _threading
        import faulthandler as _faulthandler

        toolbar = tk.Frame(self.content, bg=BG)
        toolbar.pack(fill='x', pady=(0, 10))
        tk.Button(toolbar, text='+ PROJEKTORDNER VERKNÜPFEN', command=self._link_project_source,
                  bg=ACCENT, fg='white', bd=0, padx=12, pady=7).pack(side='left')
        tk.Label(toolbar, text=f"{len(sources)} Speicherort{'e' if len(sources) != 1 else ''}",
                 bg=BG, fg=MUTED).pack(side='left', padx=(10, 16))
        tk.Label(toolbar, text='Suche in geladenen Einträgen:', bg=BG, fg=MUTED).pack(side='left')
        search_var = tk.StringVar()
        search_entry = tk.Entry(toolbar, textvariable=search_var, width=28)
        search_entry.pack(side='left', padx=(5, 6), ipady=4)
        status_lbl = tk.Label(toolbar, text='', bg=BG, fg=MUTED, font=('Segoe UI', 8))
        status_lbl.pack(side='left', padx=(8, 0))

        pan, body = self.panel(self.content, 'Projektakte · Explorer')
        pan.pack(fill='both', expand=True)
        split = tk.PanedWindow(body, orient='horizontal', bg=PANEL, sashwidth=5, bd=0)
        split.pack(fill='both', expand=True)
        left = tk.Frame(split, bg=PANEL)
        right = tk.Frame(split, bg=PANEL, width=350)
        split.add(left, stretch='always')
        split.add(right, minsize=320)

        cols = ('Typ', 'Geändert', 'Größe', 'Pfad')
        tr = ttk.Treeview(left, columns=cols, show='tree headings', height=22)
        tr.heading('#0', text='Ordner / Datei')
        tr.column('#0', width=390, minwidth=240, stretch=True, anchor='w')
        for c, wid in (('Typ', 85), ('Geändert', 145), ('Größe', 90), ('Pfad', 520)):
            tr.heading(c, text=c)
            tr.column(c, width=wid, minwidth=70, stretch=(c == 'Pfad'), anchor='w')
        sy = ttk.Scrollbar(left, orient='vertical', command=tr.yview)
        sx = ttk.Scrollbar(left, orient='horizontal', command=tr.xview)
        tr.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        tr.grid(row=0, column=0, sticky='nsew')
        sy.grid(row=0, column=1, sticky='ns')
        sx.grid(row=1, column=0, sticky='ew')
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)

        pathmap = {}
        rootmap = {}
        sourcemap = {}
        isdirmap = {}
        mtimemap = {}
        sizemap = {}
        loaded = set()
        loading = set()
        load_token = {}
        dummy = '__PZ_DUMMY__'
        result_q = _queue.Queue()
        poll_scheduled = [False]
        generation = [0]

        def log_error(where):
            try:
                import traceback as _traceback
                p = Path(__file__).resolve().parent / 'project_explorer_error.txt'
                with p.open('a', encoding='utf-8') as f:
                    f.write('\n--- ' + datetime.datetime.now().isoformat() + ' · ' + where + ' ---\n')
                    f.write(_traceback.format_exc())
            except Exception:
                pass

        def dump_hang(tag):
            try:
                p = Path(__file__).resolve().parent / 'project_explorer_hang.log'
                with p.open('ab', buffering=0) as f:
                    f.write(('\n--- ' + datetime.datetime.now().isoformat() + ' · ' + tag + ' ---\n').encode('utf-8','replace'))
                    _faulthandler.dump_traceback(file=f, all_threads=True)
            except Exception:
                pass

        def arm_main_watchdog(tag, seconds=5.0):
            timer = _threading.Timer(seconds, lambda: dump_hang(tag))
            timer.daemon = True
            timer.start()
            return timer

        def fmt_changed(ts):
            try: return datetime.datetime.fromtimestamp(ts).strftime('%d.%m.%Y %H:%M') if ts else '—'
            except Exception: return '—'

        def fmt_size(size, is_dir):
            if is_dir: return '—'
            try: return self.human_size(size)
            except Exception: return '—'

        def selected(event=None):
            # 1.5.6: Nur AUSLESEN, niemals die Treeview-Auswahl hier erneut setzen.
            # refresh_detail wird durch <<TreeviewSelect>> aufgerufen; selection_set() an
            # dieser Stelle hat erneut <<TreeviewSelect>> erzeugt und damit eine Endlosschleife.
            iid = ''
            try:
                if event is not None: iid = tr.identify_row(event.y)
            except Exception: iid = ''
            if not iid:
                try:
                    sel = tr.selection(); iid = sel[0] if sel else ''
                except Exception: iid = ''
            return pathmap.get(iid), rootmap.get(iid), iid

        def insert_child(parent, root, info, src=None):
            pp = Path(info['path']); is_dir = bool(info.get('is_dir'))
            try: rel_text = str(pp.relative_to(root))
            except Exception: rel_text = pp.name
            typ = 'Ordner' if is_dir else (pp.suffix.upper().lstrip('.') or 'Datei')
            iid = tr.insert(parent, 'end', text=info.get('name') or pp.name,
                            values=(typ, fmt_changed(info.get('mtime',0)), fmt_size(info.get('size',0), is_dir), rel_text), open=False)
            pathmap[iid] = pp; rootmap[iid] = root; isdirmap[iid] = is_dir
            mtimemap[iid] = info.get('mtime',0); sizemap[iid] = info.get('size',0)
            if src is not None: sourcemap[iid] = src
            if is_dir: tr.insert(iid, 'end', text=dummy, values=('', '', '', ''))
            return iid

        def finish_apply(iid, token, items, error_text=''):
            if token != load_token.get(iid) or iid not in pathmap: return
            loading.discard(iid)
            try:
                for child in tr.get_children(iid):
                    if tr.item(child,'text') in (dummy, 'Wird geladen …'):
                        tr.delete(child)
            except Exception: pass
            if error_text:
                try:
                    tr.insert(iid, 'end', text='Ordner konnte nicht gelesen werden', values=('Hinweis','—','—',error_text))
                    status_lbl.configure(text='Ordner konnte nicht gelesen werden')
                except Exception: pass
                loaded.add(iid); return

            pos = [0]
            def batch():
                if token != load_token.get(iid) or iid not in pathmap: return
                watchdog = arm_main_watchdog('Treeview-Einfuegen blockiert: ' + str(pathmap.get(iid,'')), 5.0)
                try:
                    end = min(pos[0] + 80, len(items))
                    src = sourcemap.get(iid); root = rootmap.get(iid)
                    for info in items[pos[0]:end]: insert_child(iid, root, info, src)
                    pos[0] = end
                    watchdog.cancel()
                    if pos[0] < len(items): self.after(1, batch)
                    else:
                        loaded.add(iid)
                        status_lbl.configure(text=f'{len(items)} Einträge')
                except Exception:
                    try: watchdog.cancel()
                    except Exception: pass
                    log_error('finish_apply/batch')
            batch()

        def poll_results():
            poll_scheduled[0] = False
            try:
                while True:
                    iid, token, items, error_text = result_q.get_nowait()
                    finish_apply(iid, token, items, error_text)
            except _queue.Empty:
                pass
            except Exception:
                log_error('poll_results')
            if loading: schedule_poll()

        def schedule_poll():
            if poll_scheduled[0]: return
            poll_scheduled[0] = True
            try: self.after(50, poll_results)
            except Exception: poll_scheduled[0] = False

        def load_node_async(iid):
            if not iid or iid in loaded or iid in loading: return
            pp = pathmap.get(iid); root = rootmap.get(iid)
            if pp is None or root is None: loaded.add(iid); return
            if not bool(isdirmap.get(iid, False)): loaded.add(iid); return
            generation[0] += 1
            token = generation[0]; load_token[iid] = token; loading.add(iid)
            try:
                for child in tr.get_children(iid):
                    if tr.item(child,'text') == dummy: tr.item(child, text='Wird geladen …')
                status_lbl.configure(text='Ordner wird im Hintergrund gelesen …')
            except Exception: pass
            schedule_poll()

            def worker(path_text, target_iid, target_token):
                items=[]; error_text=''
                try:
                    import os as _os
                    with _os.scandir(path_text) as it:
                        for entry in it:
                            try: is_dir = entry.is_dir(follow_symlinks=False)
                            except Exception: is_dir = False
                            try:
                                st = entry.stat(follow_symlinks=False); mt, sz = st.st_mtime, st.st_size
                            except Exception: mt, sz = 0, 0
                            items.append({'path':entry.path, 'name':entry.name, 'is_dir':is_dir, 'mtime':mt, 'size':sz})
                    items.sort(key=lambda x:(not x['is_dir'], str(x['name']).casefold()))
                except Exception as exc:
                    error_text = repr(exc)
                try: result_q.put((target_iid, target_token, items, error_text))
                except Exception: pass

            _threading.Thread(target=worker, args=(str(pp), iid, token), name='PZ-Filesystem-Only', daemon=True).start()

            def slow_notice(expected_iid=iid, expected_token=token):
                if expected_iid in loading and load_token.get(expected_iid) == expected_token:
                    try: status_lbl.configure(text='Ordner reagiert langsam – Oberfläche bleibt bedienbar')
                    except Exception: pass
            try: self.after(8000, slow_notice)
            except Exception: pass

        def add_source(src, open_root=False):
            root = Path(src['path']); label = f"{src['kind']}: {src['label']}"
            iid = tr.insert('', 'end', text=label, values=('Speicherort','—','—',str(root)), open=open_root)
            pathmap[iid]=root; rootmap[iid]=root; sourcemap[iid]=src; isdirmap[iid]=True; mtimemap[iid]=0; sizemap[iid]=0
            tr.insert(iid, 'end', text=dummy, values=('', '', '', ''))
            if open_root: load_node_async(iid)
            return iid

        def render_normal():
            try:
                generation[0] += 1
                for iid in tr.get_children(''): tr.delete(iid)
                pathmap.clear(); rootmap.clear(); sourcemap.clear(); isdirmap.clear(); mtimemap.clear(); sizemap.clear()
                loaded.clear(); loading.clear(); load_token.clear()
                for idx, src in enumerate(sources): add_source(src, idx == 0)
                status_lbl.configure(text='')
            except Exception: log_error('render_normal')

        tk.Label(right, text='DATEI / ORDNER', bg=PANEL, fg=INK, font=('Segoe UI Semibold', 9)).pack(anchor='w', padx=12, pady=(0,8))
        detail = tk.Text(right, height=13, wrap='word', font=('Segoe UI',9), bg='#fbfaf6', fg=INK, bd=1, relief='solid')
        detail.pack(fill='both', expand=True, padx=12)
        btns=tk.Frame(right,bg=PANEL); btns.pack(fill='x',padx=12,pady=8)
        open_btn=tk.Button(btns,text='ÖFFNEN',bg=DARK,fg='white',bd=0,padx=10,pady=7); open_btn.pack(side='left')
        explorer_btn=tk.Button(btns,text='EXPLORER',bg='#e7e4dc',fg=INK,bd=0,padx=10,pady=7); explorer_btn.pack(side='left',padx=6)
        copy_btn=tk.Button(btns,text='PFAD KOPIEREN',bg='#e7e4dc',fg=INK,bd=0,padx=9,pady=7); copy_btn.pack(side='left')

        def refresh_detail(_evt=None):
            try:
                pp, root, iid = selected(); detail.configure(state='normal'); detail.delete('1.0','end')
                if not pp: detail.configure(state='disabled'); return
                try: rel = pp.relative_to(root)
                except Exception: rel = Path('.')
                is_dir = bool(isdirmap.get(iid, False))
                changed = fmt_changed(mtimemap.get(iid,0)); size = fmt_size(sizemap.get(iid,0), is_dir)
                detail.insert('1.0', f"Name: {pp.name}\nTyp: {'Ordner' if is_dir else (pp.suffix.upper() or 'Datei')}\n\nGeändert: {changed}\nGröße: {size}\n\nRelativer Pfad:\n{rel}\n\nOriginalpfad:\n{pp}")
                detail.configure(state='disabled')
            except Exception: log_error('refresh_detail')

        def open_selected(event=None):
            try:
                pp, root, iid = selected(event)
                if not pp: return 'break'
                if bool(isdirmap.get(iid, False)):
                    load_node_async(iid)
                    try: tr.item(iid, open=True)
                    except Exception: pass
                else: self.open_external_path(str(pp))
            except Exception: log_error('open_selected')
            return 'break'

        def show_in_explorer():
            try:
                pp,_,iid=selected()
                if not pp:return
                if os.name=='nt':
                    if bool(isdirmap.get(iid,False)): subprocess.Popen(['explorer.exe',str(pp)])
                    else: subprocess.Popen(['explorer.exe','/select,',str(pp)])
                else: self.open_external_path(str(pp))
            except Exception: log_error('show_in_explorer')

        def copy_path():
            try:
                pp,_,_=selected()
                if not pp:return
                self.clipboard_clear(); self.clipboard_append(str(pp)); self.update_idletasks()
            except Exception: log_error('copy_path')

        def on_tree_open(_evt=None):
            try: load_node_async(tr.focus())
            except Exception: log_error('on_tree_open')

        def do_search(_evt=None):
            q=search_var.get().strip().casefold()
            if not q: status_lbl.configure(text=''); return 'break'
            hits=[]
            for iid,pp in list(pathmap.items()):
                try:
                    if q in pp.name.casefold(): hits.append(iid)
                except Exception: pass
            if hits:
                iid=hits[0]; tr.selection_set(iid); tr.focus(iid); tr.see(iid); refresh_detail(); status_lbl.configure(text=f'{len(hits)} Treffer in geladenen Einträgen')
            else: status_lbl.configure(text='Kein Treffer in geladenen Einträgen')
            return 'break'

        def collapse_all():
            for iid in list(pathmap):
                try: tr.item(iid,open=False)
                except Exception: pass

        open_btn.configure(command=open_selected); explorer_btn.configure(command=show_in_explorer); copy_btn.configure(command=copy_path)
        tk.Button(toolbar,text='AKTUALISIEREN',command=render_normal,bg='#e7e4dc',fg=INK,bd=0,padx=10,pady=7).pack(side='right')
        tk.Button(toolbar,text='ZUKLAPPEN',command=collapse_all,bg='#e7e4dc',fg=INK,bd=0,padx=10,pady=7).pack(side='right',padx=6)

        menu=tk.Menu(self,tearoff=0)
        menu.add_command(label='Öffnen',command=open_selected); menu.add_command(label='Im Windows-Explorer zeigen',command=show_in_explorer); menu.add_separator(); menu.add_command(label='Pfad kopieren',command=copy_path)
        def popup(e):
            try:
                iid=tr.identify_row(e.y)
                if iid: tr.selection_set(iid); tr.focus(iid); menu.tk_popup(e.x_root,e.y_root)
            except Exception: log_error('popup')

        tr.bind('<<TreeviewOpen>>',on_tree_open); tr.bind('<Double-1>',open_selected); tr.bind('<Return>',open_selected)
        tr.bind('<<TreeviewSelect>>',refresh_detail); tr.bind('<Button-3>',popup); tr.bind('<F5>',lambda e:render_normal())
        tr.bind('<Control-c>',lambda e:(copy_path(),'break')[1]); search_entry.bind('<Return>',do_search); search_entry.bind('<Escape>',lambda e:search_var.set(''))
        render_normal()





    def show_statik_pdf(self):
        # PZ_STATIK_PDF_TREE_V1449: Explorer-artige Ordnerstruktur für Statik-PDF.
        self.clear()
        try:
            self.header.configure(text='Statik PDF')
            for _n,_b in self.nav_buttons.items():
                _b.configure(bg=DARK2 if _n=='Statik' else DARK)
        except Exception:
            pass
        r=self.project_row()
        self.titleblock(self.content,'Statik PDF',f"{r['number']} · {r['title']} · Originaldateien, keine Kopien")
        self.program_starter_bar(self.content)
        project_root=Path(self.get_project_folder())

        def find_folder():
            try:
                for child in project_root.iterdir():
                    if child.is_dir() and ''.join(ch for ch in child.name.casefold() if ch.isalnum())=='statikpdf':
                        return child
            except Exception:
                pass
            return project_root/'Statik PDF'

        tools=tk.Frame(self.content,bg=BG); tools.pack(fill='x',pady=(0,10))
        tk.Button(tools,text='← ZURÜCK ZUR STATIK',command=lambda:self.navigate('Statik',self.show_statics),bg='#e7e4dc',fg=INK,bd=0,padx=12,pady=7).pack(side='left',padx=(0,10))
        info=tk.Label(tools,text='',bg=BG,fg=MUTED,anchor='w'); info.pack(side='left',fill='x',expand=True)
        search_var=tk.StringVar()
        tk.Label(tools,text='Suche:',bg=BG,fg=MUTED).pack(side='left',padx=(8,4))
        search_entry=tk.Entry(tools,textvariable=search_var,width=24); search_entry.pack(side='left')

        pan,body=self.panel(self.content,'Statik PDF · Ordnerstruktur'); pan.pack(fill='both',expand=True)
        cols=('Typ','Geändert','Größe')
        tree=ttk.Treeview(body,columns=cols,show='tree headings',height=22)
        tree.heading('#0',text='Ordner / PDF-Datei'); tree.column('#0',width=760,minwidth=320,stretch=True,anchor='w')
        for col,w,m in (('Typ',90,70),('Geändert',145,125),('Größe',90,70)):
            tree.heading(col,text=col); tree.column(col,width=w,minwidth=m,stretch=False,anchor='w')
        sy=ttk.Scrollbar(body,orient='vertical',command=tree.yview); tree.configure(yscrollcommand=sy.set)
        tree.grid(row=0,column=0,sticky='nsew'); sy.grid(row=0,column=1,sticky='ns')
        body.grid_rowconfigure(0,weight=1); body.grid_columnconfigure(0,weight=1)
        pathmap={}

        def human_size(size):
            try:
                size=float(size)
                for unit in ('B','KB','MB','GB'):
                    if size<1024 or unit=='GB':
                        return f'{size:.0f} {unit}' if unit=='B' else f'{size:.1f} {unit}'
                    size/=1024
            except Exception:
                return '—'

        def changed_text(p):
            try:return datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime('%d.%m.%Y %H:%M')
            except Exception:return '—'

        def selected_path(event=None):
            iid=''
            if event is not None:
                try:iid=tree.identify_row(event.y)
                except Exception:iid=''
            if not iid:
                sel=tree.selection(); iid=sel[0] if sel else ''
            if iid:
                try:tree.selection_set(iid); tree.focus(iid)
                except Exception:pass
            return pathmap.get(iid),iid

        def expand_branch(iid):
            try:tree.item(iid,open=True)
            except Exception:pass
            for child in tree.get_children(iid):
                p=pathmap.get(child)
                if p is not None and p.is_dir():expand_branch(child)

        def expand_all():
            for iid in tree.get_children(''):expand_branch(iid)

        def collapse_all():
            def close(iid):
                for child in tree.get_children(iid):close(child)
                try:tree.item(iid,open=False)
                except Exception:pass
            for iid in tree.get_children(''):close(iid)

        def refresh(*_):
            for iid in tree.get_children(''):tree.delete(iid)
            pathmap.clear(); folder=find_folder(); q=search_var.get().strip().casefold()
            all_pdfs=[]
            if folder.exists():
                try:
                    all_pdfs=[p for p in folder.rglob('*.pdf') if p.is_file()]
                except Exception:all_pdfs=[]
            all_pdfs.sort(key=lambda p:str(p.relative_to(folder)).casefold() if folder.exists() else p.name.casefold())
            matched=[]
            for p in all_pdfs:
                try:rel=p.relative_to(folder)
                except Exception:rel=Path(p.name)
                hay=(p.name+' '+str(rel)).casefold()
                if not q or q in hay:matched.append(p)

            needed={folder} if folder.exists() else set()
            by_parent={}
            for p in matched:
                by_parent.setdefault(p.parent,[]).append(p)
                d=p.parent
                while folder.exists() and d!=folder:
                    needed.add(d); d=d.parent
                if folder.exists():needed.add(folder)
            child_dirs={}
            for d in needed:
                if d!=folder:child_dirs.setdefault(d.parent,[]).append(d)
            for vals in child_dirs.values():vals.sort(key=lambda p:p.name.casefold())
            for vals in by_parent.values():vals.sort(key=lambda p:p.name.casefold())

            def add_dir(parent_iid,d):
                iid=tree.insert(parent_iid,'end',text=d.name,values=('Ordner',changed_text(d),'—'),open=bool(q))
                pathmap[iid]=d
                for cd in child_dirs.get(d,[]):add_dir(iid,cd)
                for p in by_parent.get(d,[]):
                    try:size=human_size(p.stat().st_size)
                    except Exception:size='—'
                    fid=tree.insert(iid,'end',text=p.name,values=('PDF',changed_text(p),size))
                    pathmap[fid]=p

            if folder.exists():
                for d in child_dirs.get(folder,[]):add_dir('',d)
                for p in by_parent.get(folder,[]):
                    try:size=human_size(p.stat().st_size)
                    except Exception:size='—'
                    fid=tree.insert('','end',text=p.name,values=('PDF',changed_text(p),size)); pathmap[fid]=p
            info.config(text=(f'{len(matched)} von {len(all_pdfs)} PDF-Datei(en) · {folder}' if folder.exists() else f'Ordner noch nicht vorhanden · {folder}'))
            if q:expand_all()

        def open_selected(event=None):
            p,iid=selected_path(event)
            if not p:return 'break'
            if p.is_dir():
                try:tree.item(iid,open=not bool(tree.item(iid,'open')))
                except Exception:pass
            else:self.open_external_path(p)
            return 'break'

        def show_in_explorer():
            p,_=selected_path()
            if not p:return
            try:
                if os.name=='nt' and p.is_file():subprocess.Popen(['explorer','/select,',str(p)])
                else:self.open_external_path(p if p.is_dir() else p.parent)
            except Exception as exc:messagebox.showerror('Statik PDF',str(exc))

        def copy_path():
            p,_=selected_path()
            if not p:return
            try:self.clipboard_clear(); self.clipboard_append(str(p)); self.update_idletasks()
            except Exception:pass

        def open_folder():
            folder=find_folder()
            if not folder.exists():
                if not messagebox.askyesno('Statik PDF',f'Der Ordner ist noch nicht vorhanden:\n{folder}\n\nJetzt anlegen?'):return
                try:folder.mkdir(parents=True,exist_ok=True)
                except Exception as exc:messagebox.showerror('Statik PDF',str(exc)); return
            self.open_external_path(folder); refresh()

        tk.Button(tools,text='ORDNER ÖFFNEN',command=open_folder,bg=DARK,fg='white',bd=0,padx=13,pady=7).pack(side='right',padx=(6,0))
        tk.Button(tools,text='AKTUALISIEREN',command=refresh,bg='#e7e4dc',fg=INK,bd=0,padx=13,pady=7).pack(side='right',padx=(6,0))
        tk.Button(tools,text='ZUKLAPPEN',command=collapse_all,bg='#e7e4dc',fg=INK,bd=0,padx=10,pady=7).pack(side='right',padx=(6,0))
        tk.Button(tools,text='AUFKLAPPEN',command=expand_all,bg='#e7e4dc',fg=INK,bd=0,padx=10,pady=7).pack(side='right',padx=(6,0))

        menu=tk.Menu(self,tearoff=0)
        menu.add_command(label='Öffnen',command=open_selected)
        menu.add_command(label='Im Windows-Explorer zeigen',command=show_in_explorer)
        menu.add_command(label='Pfad kopieren',command=copy_path)
        def popup(e):
            iid=tree.identify_row(e.y)
            if iid:
                tree.selection_set(iid); tree.focus(iid); menu.tk_popup(e.x_root,e.y_root)
        tree.bind('<Button-3>',popup)
        tree.bind('<Double-1>',open_selected); tree.bind('<Return>',open_selected)
        tree.bind('<Control-c>',lambda _e:(copy_path(),'break')[1])
        search_var.trace_add('write',lambda *_:refresh())
        search_entry.bind('<Escape>',lambda _e:search_var.set(''))
        refresh()

    def show_statics(self):
        self.clear(); self.titleblock(self.content,'Statik','Baugrund · mb AEC Projekte · Positionsakte · Prüfstatik · Pläne · Lastfluss')
        self.program_starter_bar(self.content)
        project_root=Path(self.get_project_folder())

        def child_ci(parent,*names):
            if not parent or not parent.exists(): return None
            wanted={n.casefold() for n in names}
            try:
                for p in parent.iterdir():
                    if p.is_dir() and p.name.casefold() in wanted: return p
            except OSError: pass
            return None

        def classify_position(name,desc,prog):
            n=(name or '').strip(); d=(desc or '').strip(); p=(prog or '').strip()
            if p=='S960': return 'Gliederung'
            if p in ('S009','S010','S011','S014'): return 'Dokumente & Grundlagen'
            low=(n+' '+d).casefold()
            if p in ('S030.de','S031.de','S037.de','S030','S031','S037') or n.upper().startswith('WS') or 'last' in low or 'wind' in low or 'schnee' in low:
                return 'Lasten & Einwirkungen'
            return 'Tragwerkspositionen'

        def read_mb_positions(folder):
            dbfile=folder/'STATIK'/'BSPos.mbdb'
            if not dbfile.exists(): return [], f'Keine Positionsdatenbank gefunden: {dbfile.name}'
            con=None
            try:
                con=sqlite3.connect(dbfile.resolve().as_uri()+'?mode=ro',uri=True,timeout=2)
                con.row_factory=sqlite3.Row
                if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='BSPositionen'").fetchone():
                    return [], 'BSPositionen ist in dieser mb-Datenbank nicht vorhanden.'
                cols={r[1] for r in con.execute('PRAGMA table_info(BSPositionen)').fetchall()}
                needed={'strNamePosition','strBeschreibungPosition','strProgPosition','PosOrder'}
                if not needed.issubset(cols): return [], 'Positionsschema dieser mb-Version wird noch nicht unterstützt.'
                rows=con.execute('SELECT strIDPosition,PosOrder,strNamePosition,strBeschreibungPosition,strProgPosition,Berechnungsstatus,IstGesperrt,Ergebnisse,Modified FROM BSPositionen ORDER BY PosOrder, Created, strNamePosition').fetchall()
                out=[]
                for r in rows:
                    name=r['strNamePosition'] or ''; desc=r['strBeschreibungPosition'] or ''; prog=(r['strProgPosition'] or '').strip()
                    group=classify_position(name,desc,prog)
                    if prog=='S960': art='Gliederung'
                    elif prog in ('S009','S010','S011'): art='Dokument'
                    elif prog=='S014': art='Anlage / Grundlage'
                    else: art='Position'
                    out.append({'id':r['strIDPosition'], 'order':r['PosOrder'] if r['PosOrder'] is not None else '', 'pos':name, 'desc':desc, 'module':prog or '—', 'group':group, 'art':art,
                                'results':r['Ergebnisse'] if r['Ergebnisse'] is not None else 0, 'locked':'ja' if r['IstGesperrt'] else 'nein',
                                'calc_status':r['Berechnungsstatus'] if r['Berechnungsstatus'] is not None else 0})
                return out,None
            except sqlite3.Error as e: return [], 'mb-Positionsdaten konnten nicht gelesen werden: '+str(e)
            finally:
                if con is not None:
                    try: con.close()
                    except Exception: pass

        def read_mb_position_detail(folder,row):
            """Liest nur verifizierbare Metadaten zur gewählten mb-Position; keine Schreibzugriffe."""
            dbfile=folder/'STATIK'/'BSPos.mbdb'
            result={'calc_version':'—','calculated_with':'—','output_exists':False,'output_chars':0,
                    'output_program':'—','output_version':'—','sections':[], 'simple_results':0,
                    'grid_results':0,'document_entries':0,'file_refs':0,'auswertung_types':[]}
            con=None
            try:
                con=sqlite3.connect(dbfile.resolve().as_uri()+'?mode=ro',uri=True,timeout=2)
                con.row_factory=sqlite3.Row; pid=row.get('id')
                def table(name):
                    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone() is not None
                if table('BSBerechnung'):
                    x=con.execute('SELECT Version,BerechnetMit FROM BSBerechnung WHERE strIDPosition=? LIMIT 1',(pid,)).fetchone()
                    if x: result['calc_version']=x['Version']; result['calculated_with']=x['BerechnetMit'] or '—'
                if table('BSAuswertung'):
                    result['auswertung_types']=[x[0] for x in con.execute('SELECT Typ FROM BSAuswertung WHERE strIDPosition=? ORDER BY Typ',(pid,)).fetchall()]
                if table('BSPositionsausgaben'):
                    x=con.execute('SELECT Ausgabe FROM BSPositionsausgaben WHERE strIDPosition=? AND Sprache=0 LIMIT 1',(pid,)).fetchone()
                    if not x: x=con.execute('SELECT Ausgabe FROM BSPositionsausgaben WHERE strIDPosition=? LIMIT 1',(pid,)).fetchone()
                    if x and x['Ausgabe']:
                        raw=x['Ausgabe']; result['output_exists']=True; result['output_chars']=len(raw)
                        m=re.search(r'\$Programm="([^"]+)"',raw); result['output_program']=m.group(1) if m else '—'
                        m=re.search(r'\$Version="([^"]+)"',raw); result['output_version']=m.group(1) if m else '—'
                        seen=[]
                        for sec in re.findall(r'@LABEL\s+\d+\s+"([^"]+)"@',raw):
                            sec=sec.strip()
                            if sec and sec not in seen: seen.append(sec)
                        result['sections']=seen[:12]
                for t,key in (('BSSimpleResults','simple_results'),('BSGridResults','grid_results'),('BSDateireferenzen','file_refs')):
                    if table(t): result[key]=con.execute(f'SELECT COUNT(*) FROM {t} WHERE strIDPosition=?',(pid,)).fetchone()[0]
                if table('BSDokumenteneintraege'):
                    result['document_entries']=con.execute('SELECT COUNT(*) FROM BSDokumenteneintraege WHERE PosUUID=?',(pid,)).fetchone()[0]
                return result,None
            except sqlite3.Error as e:
                return result,'Positionsdetails konnten nicht gelesen werden: '+str(e)
            finally:
                if con is not None:
                    try: con.close()
                    except Exception: pass

        def read_mb_position_output(folder,row):
            """Liest die gespeicherte mb-Positionsausgabe strikt read-only."""
            dbfile=folder/'STATIK'/'BSPos.mbdb'
            con=None
            try:
                con=sqlite3.connect(dbfile.resolve().as_uri()+'?mode=ro',uri=True,timeout=2)
                con.row_factory=sqlite3.Row; pid=row.get('id')
                x=con.execute('SELECT Ausgabe FROM BSPositionsausgaben WHERE strIDPosition=? AND Sprache=0 LIMIT 1',(pid,)).fetchone()
                if not x: x=con.execute('SELECT Ausgabe FROM BSPositionsausgaben WHERE strIDPosition=? LIMIT 1',(pid,)).fetchone()
                return (x['Ausgabe'] if x and x['Ausgabe'] else ''),None
            except sqlite3.Error as e:
                return '',str(e)
            finally:
                if con is not None:
                    try: con.close()
                    except Exception: pass

        def mb_plain_text(raw):
            """Macht die interne mb-Ausgabe lesbar, ohne sie fachlich umzudeuten."""
            if not raw: return ''
            t=raw.replace('\r','')
            # Tabellen zuerst strukturieren, bevor die Steuerbefehle entfernt werden.
            t=t.replace('@TBL2_CELL_END@',' | ').replace('@TBL2_ROW_END@','\n')
            t=t.replace('@BLOCK_END@','\n').replace('@LF+ 1@','\n').replace('@LF- 1@','\n')
            t=t.replace('@LF+@','\n').replace('@LF-@','\n')
            t=re.sub(r'@OLE_PICTURE[^@]*(?:@|$)','[Grafik]\n',t)
            t=re.sub(r'@PGNUMTEXT\s+"[^"]*"\s+"([^"]*)"@',r'\1',t)
            t=re.sub(r'@VARTEXT\s+"([^"]*)"@',r'\1',t)
            # Häufige Format-/Steuerbefehle entfernen.
            t=re.sub(r'@[A-Z_a-z0-9+\-]+(?:\s+[^@\n]*)?@','',t)
            t=re.sub(r'\$[A-Za-z0-9_]+="[^"]*"','',t)
            t=t.replace('@','')
            # kleine mb-Formatmarker
            t=t.replace('SUB+','').replace('SUB-','').replace('ITL+','').replace('ITL-','')
            lines=[]
            for line in t.splitlines():
                line=re.sub(r'[ \t]+',' ',line).strip(' |\t')
                if line and not line.startswith('$'):
                    lines.append(line)
            return '\n'.join(lines)

        # mb-Projekte können aus dem Hauptordner oder einem verknüpften Projektordner stammen.
        mb_projects=[]
        for source in self._project_sources():
            src_root=source['path']; statik_root=child_ci(src_root,'Statik','02_Statik')
            mb_root=child_ci(statik_root,'mb-Software','mb Software','mb_AEC') if statik_root else None
            if not mb_root or not mb_root.exists(): continue
            try: folders=sorted((p for p in mb_root.iterdir() if p.is_dir()),key=lambda p:p.name.casefold())
            except OSError: folders=[]
            for folder in folders:
                try: mbps=sorted(folder.glob('*.mbp'))
                except OSError: mbps=[]
                lead=mbps[0] if len(mbps)==1 else None
                if len(mbps)==1: status='mb-Projekt erkannt'; lead_name=lead.name; stamp=lead.stat().st_mtime
                elif len(mbps)>1: status=f'{len(mbps)} .mbp-Dateien – prüfen'; lead_name=f'{len(mbps)} Dateien'; stamp=folder.stat().st_mtime
                else: status='Projektordner erkannt'; lead_name='—'; stamp=folder.stat().st_mtime
                try: changed=datetime.datetime.fromtimestamp(stamp).strftime('%d.%m.%Y %H:%M')
                except Exception: changed='—'
                try: rel=f"{source['label']} · {folder.relative_to(src_root)}"
                except Exception: rel=str(folder)
                mb_projects.append((folder,folder.name,lead_name,changed,rel,status))

        # 1.4.5: vorhandene Erkennung ergänzen. Direkte Unterordner eines
        # mb-Software-Ordners gelten jeweils als eigenständiges mb-Projekt, sobald
        # eine .mbp-Leitdatei oder eine BSPos.mbdb vorhanden ist.
        try:
            _seen_mb=set()
            for _e in mb_projects:
                try: _seen_mb.add(str(Path(_e[0]).resolve()).casefold())
                except Exception: _seen_mb.add(str(Path(_e[0])).casefold())
            _mb_roots=[]; _root_seen=set()
            for _e in list(mb_projects):
                try:
                    _parent=Path(_e[0]).parent
                    _norm=''.join(ch for ch in _parent.name.casefold() if ch.isalnum())
                    if _norm in {'mbsoftware','mbaec'}:
                        _k=str(_parent.resolve()).casefold()
                        if _k not in _root_seen: _root_seen.add(_k); _mb_roots.append(_parent)
                except Exception:
                    pass
            if project_root.exists():
                try:
                    for _cand in project_root.rglob('*'):
                        try:
                            if not _cand.is_dir(): continue
                            _norm=''.join(ch for ch in _cand.name.casefold() if ch.isalnum())
                            if _norm not in {'mbsoftware','mbaec'}: continue
                            _k=str(_cand.resolve()).casefold()
                            if _k not in _root_seen: _root_seen.add(_k); _mb_roots.append(_cand)
                        except OSError:
                            continue
                except OSError:
                    pass
            for _mbroot in _mb_roots:
                try: _children=sorted((x for x in _mbroot.iterdir() if x.is_dir()),key=lambda x:x.name.casefold())
                except OSError: continue
                for _folder in _children:
                    try: _key=str(_folder.resolve()).casefold()
                    except Exception: _key=str(_folder).casefold()
                    if _key in _seen_mb: continue
                    try: _leads=sorted(_folder.glob('*.mbp'),key=lambda x:x.name.casefold())
                    except OSError: _leads=[]
                    _dbs=[]
                    try:
                        for _db in _folder.rglob('*'):
                            try:
                                if _db.is_file() and _db.name.casefold()=='bspos.mbdb': _dbs.append(_db); break
                            except OSError: continue
                    except OSError: pass
                    if not _leads and not _dbs: continue
                    _lead=None
                    for _x in _leads:
                        if _x.stem.casefold()==_folder.name.casefold(): _lead=_x; break
                    if _lead is None and _leads: _lead=_leads[0]
                    _lead_name=_lead.name if _lead else '—'
                    _stamp=_lead or (_dbs[0] if _dbs else None)
                    try: _changed=datetime.datetime.fromtimestamp(_stamp.stat().st_mtime).strftime('%d.%m.%Y %H:%M') if _stamp else '—'
                    except OSError: _changed='—'
                    try: _rel=str(_folder.relative_to(project_root))
                    except Exception: _rel=str(_folder)
                    mb_projects.append((_folder,_folder.name,_lead_name,_changed,_rel,'mb-Projekt erkannt'))
                    _seen_mb.add(_key)
            mb_projects.sort(key=lambda e:str(e[0]).casefold())
        except Exception:
            # Die bereits vorhandene Erkennung bleibt im Fehlerfall vollständig erhalten.
            pass

        # PZ_STATIK_QUICKACCESS_REMOVED_V1448: PDF-Liste ist ausschließlich im Unterpunkt Statik PDF.

        # Baugrund / Bodengutachten: rein lesende Dateisuche im bestehenden Projektordner.
        pan_bg,b_bg=self.panel(self.content,'Baugrund / Bodengutachten'); pan_bg.pack(fill='x',pady=(0,10))
        ground_files=[]
        ground_keys=('bodengutachten','baugrund','geotechnik','geotechnisch','gründung','gruendung','bodenpressung','grundwasser','erdstoff','bodenmechanik','gründungsberatung','gruendungsberatung','baugrunduntersuchung','bodenuntersuchung')
        for source in self._project_sources():
            src_root=source['path']
            if not src_root.exists(): continue
            try:
                for p in src_root.rglob('*'):
                    if not p.is_file(): continue
                    rel=p.relative_to(src_root); low=str(rel).casefold(); manual=self._manual_assignment(rel)
                    if any(k in low for k in ground_keys) or (manual and manual[0]=='Baugrund / Bodengutachten'):
                        try: st=p.stat(); changed=datetime.datetime.fromtimestamp(st.st_mtime).strftime('%d.%m.%Y %H:%M')
                        except OSError: changed='—'
                        ground_files.append((p,changed,source['label'],src_root))
            except OSError: pass
        ground_files=sorted(ground_files,key=lambda x:str(x[0]).casefold())[:80]
        if ground_files:
            cols=('Datei','Typ','Geändert','Ordner')
            gt=ttk.Treeview(b_bg,columns=cols,show='headings',height=min(5,max(2,len(ground_files))))
            for c,wid in zip(cols,(340,80,145,520)):
                gt.heading(c,text=c); gt.column(c,width=wid,anchor='w')
            gmap={}
            for p,changed,source_label,src_root in ground_files:
                try: rel=p.relative_to(src_root); folder=f"{source_label} · {rel.parent}"; folder=source_label if str(rel.parent)=='.' else folder
                except Exception: folder=str(p.parent)
                iid=gt.insert('', 'end', values=(p.name,p.suffix.lower().lstrip('.').upper() or 'Datei',changed,folder)); gmap[iid]=p
            sy=ttk.Scrollbar(b_bg,orient='vertical',command=gt.yview); gt.configure(yscrollcommand=sy.set)
            gt.pack(side='left',fill='both',expand=True); sy.pack(side='right',fill='y')
            def open_ground(_evt=None):
                sel=gt.selection()
                if sel:self.open_external_path(gmap.get(sel[0]))
            gt.bind('<Double-1>',open_ground)
            tk.Label(b_bg,text=f'{len(ground_files)} passende Datei(en) erkannt · Doppelklick öffnet das Original. Später lesen wir daraus gezielt Gründungs- und Bodenkennwerte.',bg=PANEL,fg=MUTED,anchor='w').pack(fill='x',pady=(8,0))
        else:
            tk.Label(b_bg,text='Noch kein Bodengutachten/Baugrund-Dokument erkannt. Gesucht wird ausschließlich lesend nach typischen Datei- und Ordnernamen.',bg=PANEL,fg=MUTED,anchor='w',justify='left').pack(fill='x',pady=4)

        pan_mb,b_mb=self.panel(self.content,f'mb AEC · {len(mb_projects)} Projekte erkannt'); pan_mb.pack(fill='x',pady=(0,10))

        # Positionsakte: links fachlich gruppierte Positionen, rechts Details zur markierten Position.
        pan_pos,b_pos=self.panel(self.content,'mb-Positionsakte · Gesamtakte / mb-Projekt'); pan_pos.pack(fill='both',expand=True,pady=(0,10))
        topbar=tk.Frame(b_pos,bg=PANEL); topbar.pack(fill='x',pady=(0,8))
        pos_info=tk.Label(topbar,text='Noch kein mb-Projekt ausgewählt.',bg=PANEL,fg=MUTED,anchor='w'); pos_info.pack(side='left',fill='x',expand=True)
        tk.Label(topbar,text='Filter:',bg=PANEL,fg=MUTED).pack(side='left',padx=(8,4))
        filter_var=tk.StringVar(value='Alle')
        filter_box=ttk.Combobox(topbar,textvariable=filter_var,state='readonly',width=23,values=('Alle','Tragwerkspositionen','Lasten & Einwirkungen','Dokumente & Grundlagen','Gliederung'))
        filter_box.pack(side='left')
        tk.Label(topbar,text='Suche:',bg=PANEL,fg=MUTED).pack(side='left',padx=(10,4))
        search_var=tk.StringVar(); search_entry=tk.Entry(topbar,textvariable=search_var,width=24); search_entry.pack(side='left')

        split=tk.PanedWindow(b_pos,orient='horizontal',bg=LINE,sashwidth=4,bd=0); split.pack(fill='both',expand=True)
        left=tk.Frame(split,bg=PANEL); right=tk.Frame(split,bg=PANEL,width=365); split.add(left,minsize=650); split.add(right,minsize=320)

        pcols=('mb-Projekt','Pos.','Bezeichnung','mb-Modul','mb-Kennwert')
        ptr=ttk.Treeview(left,columns=pcols,show='tree headings',height=15)
        ptr.heading('#0',text='Gruppe'); ptr.column('#0',width=190,anchor='w')
        widths=[180,125,350,95,80]
        for i,c in enumerate(pcols): ptr.heading(c,text=c); ptr.column(c,width=widths[i],anchor='w')
        psy=ttk.Scrollbar(left,orient='vertical',command=ptr.yview); psx=ttk.Scrollbar(left,orient='horizontal',command=ptr.xview)
        ptr.configure(yscrollcommand=psy.set,xscrollcommand=psx.set)
        ptr.grid(row=0,column=0,sticky='nsew'); psy.grid(row=0,column=1,sticky='ns'); psx.grid(row=1,column=0,sticky='ew')
        left.grid_rowconfigure(0,weight=1); left.grid_columnconfigure(0,weight=1)

        tk.Label(right,text='POSITIONSAKTE',bg=PANEL,fg=INK,font=('Segoe UI',10,'bold'),anchor='w').pack(fill='x',pady=(0,8))
        detail_text=tk.Text(right,height=15,wrap='word',bg='#fbfaf7',fg=INK,relief='solid',bd=1,font=('Segoe UI',9),padx=10,pady=8)
        detail_text.pack(fill='both',expand=True)
        detail_text.insert('1.0','Position auswählen.\n\nHier werden die sicher aus mb gelesenen Positionsdaten angezeigt.'); detail_text.config(state='disabled')
        actions=tk.Frame(right,bg=PANEL); actions.pack(fill='x',pady=(8,3))
        btn_output=tk.Button(actions,text='MB-AUSGABE ANZEIGEN',state='disabled',bg=ACCENT,fg='white',relief='flat',padx=10,pady=5)
        btn_output.pack(side='left')
        btn_mbp=tk.Button(actions,text='MB-PROJEKT ÖFFNEN',state='disabled',bg='#343434',fg='white',relief='flat',padx=10,pady=5)
        btn_mbp.pack(side='left',padx=(6,0))
        links=tk.Frame(right,bg=PANEL); links.pack(fill='x',pady=(5,0))
        for label in ('Prüfstatik','Pläne','Eigene Nachweise','Lastfluss','Notizen'):
            row=tk.Frame(links,bg=PANEL); row.pack(fill='x',pady=1)
            tk.Label(row,text=label,bg=PANEL,fg=MUTED,width=18,anchor='w').pack(side='left')
            tk.Label(row,text='— noch nicht verknüpft',bg=PANEL,fg=INK,anchor='w').pack(side='left')

                # 1.4.5: universelle, rein lesende mb-Projekt-/Positionsauswertung.
        # Der reale Projektordner ist die Identität. BSPos.mbdb wird nicht mehr an
        # einer einzigen festen Stelle erwartet; auch leicht abweichende Schemata
        # werden anhand ihrer Spalten erkannt. Keine mb-Datei wird geschrieben.
        def _mb_find_databases(folder):
            import sqlite3 as _sqlite3  # noqa: F401 - dokumentiert SQLite-Abhängigkeit lokal
            folder=Path(folder)
            found=[]; seen=set()
            preferred=(folder/'STATIK'/'BSPos.mbdb', folder/'Statik'/'BSPos.mbdb',
                       folder/'statik'/'BSPos.mbdb', folder/'BSPos.mbdb')
            for db in preferred:
                try:
                    if db.is_file():
                        key=str(db.resolve()).casefold()
                        if key not in seen: seen.add(key); found.append(db)
                except OSError:
                    pass
            try:
                for db in folder.rglob('*'):
                    try:
                        if not db.is_file() or db.name.casefold()!='bspos.mbdb': continue
                        key=str(db.resolve()).casefold()
                        if key not in seen: seen.add(key); found.append(db)
                    except OSError:
                        continue
            except OSError:
                pass
            return found

        def _mb_pick(data,*names):
            low={str(k).casefold():v for k,v in data.items()}
            for name in names:
                if name.casefold() in low: return low[name.casefold()]
            return None

        def _mb_group(pos,desc,module):
            p=(pos or '').strip().casefold(); d=(desc or '').strip().casefold(); m=(module or '').strip().casefold()
            section_names={'erdgeschoss','obergeschoss','dachgeschoss','gründung','gruendung','keller','carport','fundamente','dach'}
            if m.startswith('s960') or p in section_names:
                return 'Gliederung'
            if m.startswith(('s030','s031','s037')) or p.startswith('ws') or 'last' in p or 'last' in d:
                return 'Lasten / Grundlagen'
            if (m.startswith(('s009','s010','s011','s014')) or p in {'tb','vorbemerkung','s1'} or
                'titelblatt' in d or 'schlussseite' in d or 'bodengutachten' in d or 'grundlagen' in d):
                return 'Dokumente / Grundlagen'
            return 'Tragwerkspositionen'

        def _mb_find_position_table(con):
            names=[r[0] for r in con.execute("select name from sqlite_master where type in ('table','view')")]
            exact=next((n for n in names if str(n).casefold()=='bspositionen'),None)
            if exact: return exact
            best=None; bestscore=0
            for table in names:
                try:
                    cols=[r[1] for r in con.execute('pragma table_info("'+str(table).replace('"','""')+'")')]
                except Exception:
                    continue
                lc={str(c).casefold() for c in cols}; score=0
                if any(c in lc for c in ('strnameposition','nameposition','posname','position','positionsname')): score+=4
                if any(c in lc for c in ('strbeschreibungposition','beschreibungposition','beschreibung','bezeichnung','description')): score+=2
                if any(c in lc for c in ('strprogposition','progposition','programm','modul','program')): score+=2
                if any(c in lc for c in ('stridposition','idposition','posuuid','uuid','id')): score+=1
                if score>bestscore: bestscore=score; best=table
            return best if bestscore>=4 else None

        def read_mb_positions(folder):
            import sqlite3
            rows=[]; errors=[]; usable_db=False
            dbs=_mb_find_databases(folder)
            if not dbs:
                return [], 'Keine BSPos.mbdb im mb-Projekt gefunden.'
            for db in dbs:
                con=None
                try:
                    con=sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True)
                    con.row_factory=sqlite3.Row
                    table=_mb_find_position_table(con)
                    if not table:
                        errors.append(f'{db.name}: keine Positionstabelle erkannt'); continue
                    usable_db=True
                    sql='select * from "'+str(table).replace('"','""')+'"'
                    for rr in con.execute(sql):
                        data=dict(rr)
                        pos=_mb_pick(data,'strNamePosition','NamePosition','PosName','Position','Positionsname','Name')
                        desc=_mb_pick(data,'strBeschreibungPosition','BeschreibungPosition','Beschreibung','Bezeichnung','Description','Text')
                        module=_mb_pick(data,'strProgPosition','ProgPosition','Programm','Modul','Program','Module')
                        rid=_mb_pick(data,'strIDPosition','IDPosition','PosUUID','UUID','ID','PositionID')
                        order=_mb_pick(data,'PosOrder','Reihenfolge','nIndex','Index','Sortierung','Order')
                        results=_mb_pick(data,'Ergebnisse','Ergebnis','nErgebnisse','Result','Results')
                        locked=_mb_pick(data,'IstGesperrt','Gesperrt','Locked','IsLocked')
                        calc=_mb_pick(data,'Berechnungsstatus','CalcStatus','Status','CalculationStatus')
                        if not str(pos or '').strip() and not str(desc or '').strip(): continue
                        row={
                            'id':str(rid or ''), 'uuid':str(rid or ''),
                            'pos':str(pos or '').strip(), 'desc':str(desc or '').strip(),
                            'module':str(module or '').strip(),
                            'group':_mb_group(str(pos or ''),str(desc or ''),str(module or '')),
                            'order':order if order is not None else 0,
                            'row_order':order if order is not None else 0,
                            'results':results if results is not None else 0,
                            'locked':locked if locked is not None else 0,
                            'calc_status':calc if calc is not None else 0,
                            'status':calc if calc is not None else 0,
                            'art':'Position','type':'Position','_db':str(db)
                        }
                        rows.append(row)
                except Exception as e:
                    errors.append(f'{db.name}: {e}')
                finally:
                    try:
                        if con is not None: con.close()
                    except Exception:
                        pass
            uniq=[]; seen=set()
            for row in rows:
                key=('id',row['id'].casefold()) if row.get('id') else ('data',row['pos'].casefold(),row['desc'].casefold(),row['module'].casefold())
                if key in seen: continue
                seen.add(key); uniq.append(row)
            def _sortkey(row):
                try: order=float(row.get('order',0))
                except Exception: order=1e12
                return (order,row.get('pos','').casefold(),row.get('desc','').casefold())
            uniq.sort(key=_sortkey)
            if uniq: return uniq, (' · '.join(errors) if errors and not usable_db else None)
            if errors: return [], ' · '.join(errors)
            return [], None

        def read_mb_position_detail(folder,r):
            import sqlite3
            detail={'file_refs':0,'auswertung_types':[],'version':'','berechnet_mit':'','berechnung':'','calculation':'',
                    'output':'','ausgabe':'','output_len':0,'ausgabe_len':0,'db':''}
            db=None
            try:
                raw=r.get('_db') if isinstance(r,dict) else None
                if raw:
                    cand=Path(raw)
                    if cand.is_file(): db=cand
            except Exception:
                db=None
            if db is None:
                dbs=_mb_find_databases(folder)
                if dbs: db=dbs[0]
            if db is None:
                return detail,'Keine BSPos.mbdb gefunden.'
            detail['db']=str(db)
            pid=str((r or {}).get('id') or (r or {}).get('uuid') or '')
            if not pid:
                return detail,None
            con=None
            try:
                con=sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True); con.row_factory=sqlite3.Row
                tables={str(x[0]).casefold():x[0] for x in con.execute("select name from sqlite_master where type in ('table','view')")}
                def _qtable(name): return tables.get(name.casefold())
                t=_qtable('BSBerechnung')
                if t:
                    try:
                        rr=con.execute('select * from "'+str(t).replace('"','""')+'" where strIDPosition=? limit 1',(pid,)).fetchone()
                        if rr:
                            d=dict(rr); detail['version']=str(_mb_pick(d,'Version','Versionsnummer') or '')
                            detail['berechnet_mit']=str(_mb_pick(d,'BerechnetMit','Programmversion') or '')
                            detail['berechnung']=detail['berechnet_mit']; detail['calculation']=detail['berechnet_mit']
                    except Exception: pass
                t=_qtable('BSAuswertung')
                if t:
                    try:
                        vals=[]
                        for rr in con.execute('select * from "'+str(t).replace('"','""')+'" where strIDPosition=?',(pid,)):
                            typ=_mb_pick(dict(rr),'Typ','Type','Auswertungstyp')
                            if typ is not None and typ not in vals: vals.append(typ)
                        detail['auswertung_types']=vals
                    except Exception: pass
                t=_qtable('BSDateireferenzen')
                if t:
                    try:
                        detail['file_refs']=int(con.execute('select count(*) from "'+str(t).replace('"','""')+'" where strIDPosition=?',(pid,)).fetchone()[0])
                    except Exception: pass
                t=_qtable('BSPositionsausgaben')
                if t:
                    try:
                        candidates=[]
                        for rr in con.execute('select * from "'+str(t).replace('"','""')+'" where strIDPosition=?',(pid,)):
                            val=_mb_pick(dict(rr),'Ausgabe','Output','Text','Inhalt')
                            if val is not None:
                                if isinstance(val,bytes):
                                    try: val=val.decode('utf-8','replace')
                                    except Exception: val=str(val)
                                candidates.append(str(val))
                        if candidates:
                            out=max(candidates,key=len); detail['output']=out; detail['ausgabe']=out
                            detail['output_len']=len(out); detail['ausgabe_len']=len(out)
                    except Exception: pass
                return detail,None
            except Exception as e:
                return detail,str(e)
            finally:
                try:
                    if con is not None: con.close()
                except Exception: pass

        current_rows=[]; item_rows={}; current_project={'folder':None,'name':'ALLE mb-PROJEKTE'}; selected_position={'row':None}
        group_order=('Tragwerkspositionen','Lasten & Einwirkungen','Dokumente & Grundlagen','Gliederung')

        def open_mb_project():
            r=selected_position.get('row')
            folder=(r or {}).get('_folder') or current_project.get('folder')
            if not folder:
                try: messagebox.showinfo('mb AEC','Bitte zuerst ein konkretes mb-Projekt oder eine Position auswählen.')
                except Exception: pass
                return
            folder=Path(folder)
            leads=[]
            try: leads=sorted(folder.glob('*.mbp'),key=lambda x:x.name.casefold())
            except OSError: leads=[]
            preferred=next((x for x in leads if x.stem.casefold()==folder.name.casefold()),None)
            if preferred is None and leads: preferred=leads[0]
            if preferred is None:
                try:
                    deep=sorted(folder.rglob('*.mbp'),key=lambda x:(len(x.parts),x.name.casefold()))
                    preferred=deep[0] if deep else None
                except OSError:
                    preferred=None
            if preferred is not None:
                self.open_external_path(preferred)
            else:
                self.open_external_path(folder)

        def show_mb_output():
            r=selected_position.get('row'); folder=(r or {}).get('_folder') or current_project.get('folder')
            if not r or not folder: return
            raw,err=read_mb_position_output(folder,r)
            if err:
                messagebox.showerror('mb-Ausgabe','Ausgabe konnte nicht gelesen werden:\n'+err); return
            if not raw:
                messagebox.showinfo('mb-Ausgabe','Für diese Position wurde keine gespeicherte mb-Ausgabe gefunden.'); return
            win=tk.Toplevel(self); win.title(f"mb-Ausgabe · {r['pos']} · {r['desc']}"); win.geometry('1100x760'); win.minsize(760,520)
            head=tk.Frame(win,bg='#f3f1ec',padx=12,pady=10); head.pack(fill='x')
            tk.Label(head,text=f"Pos. {r['pos']} · {r['desc']}",font=('Segoe UI',12,'bold'),bg='#f3f1ec',fg=INK,anchor='w').pack(fill='x')
            tk.Label(head,text=f"{current_project['name']} · {r['module']} · gespeicherte mb-Ausgabe · nur lesend",font=('Segoe UI',9),bg='#f3f1ec',fg=MUTED,anchor='w').pack(fill='x')
            body=tk.PanedWindow(win,orient='horizontal',sashwidth=4,bd=0); body.pack(fill='both',expand=True,padx=10,pady=10)
            lf=tk.Frame(body); rf=tk.Frame(body); body.add(lf,minsize=220); body.add(rf,minsize=480)
            sec_list=tk.Listbox(lf,font=('Segoe UI',9),exportselection=False); sec_list.pack(fill='both',expand=True)
            txt=tk.Text(rf,wrap='word',font=('Consolas',9),padx=10,pady=8); sy=ttk.Scrollbar(rf,orient='vertical',command=txt.yview); txt.configure(yscrollcommand=sy.set)
            txt.pack(side='left',fill='both',expand=True); sy.pack(side='right',fill='y')
            matches=list(re.finditer(r'@LABEL\s+\d+\s+"([^"]+)"@',raw))
            sections=[]; seen={}
            for i,m in enumerate(matches):
                name=m.group(1).strip() or f'Abschnitt {i+1}'
                start=m.start(); end=matches[i+1].start() if i+1<len(matches) else len(raw)
                key=name
                if key in seen:
                    seen[key]+=1; key=f'{name} ({seen[name]})'
                else: seen[key]=1
                sections.append((key,raw[start:end]))
            if not sections: sections=[('Gesamtausgabe',raw)]
            for name,_ in sections: sec_list.insert('end',name)
            def show_section(_evt=None):
                idx=sec_list.curselection(); idx=idx[0] if idx else 0
                plain=mb_plain_text(sections[idx][1])
                txt.config(state='normal'); txt.delete('1.0','end'); txt.insert('1.0',plain or '[Abschnitt enthält nur Grafik-/Formatdaten]'); txt.config(state='disabled')
            sec_list.bind('<<ListboxSelect>>',show_section); sec_list.selection_set(0); show_section()
            foot=tk.Frame(win,bg='#f3f1ec',padx=10,pady=7); foot.pack(fill='x')
            tk.Label(foot,text='Quelle: BSPositionsausgaben · SQLite mode=ro · Originaldaten werden nicht verändert.',bg='#f3f1ec',fg=MUTED,anchor='w').pack(side='left',fill='x',expand=True)
            tk.Button(foot,text='SCHLIESSEN',command=win.destroy,relief='flat',padx=12,pady=4).pack(side='right')

        btn_output.config(command=show_mb_output)
        btn_mbp.config(command=open_mb_project)

        def set_detail(r=None):
            detail_text.config(state='normal'); detail_text.delete('1.0','end')
            if not r:
                selected_position['row']=None; btn_output.config(state='disabled'); btn_mbp.config(state='normal' if current_project.get('folder') else 'disabled')
                detail_text.insert('1.0','Position auswählen.\n\nDie Positionsakte verknüpft später mb-Berechnung, Prüfstatik, Pläne, eigene Nachweise, Lastfluss und Notizen.'); detail_text.config(state='disabled'); return
            selected_position['row']=r; btn_mbp.config(state='normal')
            txt=(f"Pos. {r['pos']}\n{r['desc']}\n\n"
                 f"mb-Projekt: {r.get('_project', current_project['name'])}\n"
                 f"mb-Modul: {r['module']}\n"
                 f"Art: {r['art']}\n"
                 f"Fachgruppe: {r['group']}\n"
                 f"Reihenfolge: {r['order']}\n"
                 f"mb-Ergebniskennwert: {r['results']} (interner Statuswert, keine Anzahl)\n"
                 f"Gesperrt: {r['locked']}\n"
                 f"Berechnungsstatus: {r['calc_status']}\n\n"
                 "Quelle: STATIK/BSPos.mbdb (nur lesend)")
            detail_folder=r.get('_folder') or current_project.get('folder')
            detail,derr=read_mb_position_detail(detail_folder,r) if detail_folder else ({},None)
            txt += "\nBERECHNUNG / AUSGABE\n"
            txt += f"Berechnet mit: {detail.get('calculated_with','—')} · Datenversion: {detail.get('calc_version','—')}\n"
            if detail.get('output_exists'):
                btn_output.config(state='normal')
                txt += f"mb-Ausgabe vorhanden: ja · {detail.get('output_chars',0):,} Zeichen\n".replace(',', '.')
                txt += f"Ausgabe: {detail.get('output_program','—')} · Version {detail.get('output_version','—')}\n"
                secs=detail.get('sections') or []
                if secs: txt += "Abschnitte: " + " · ".join(secs) + "\n"
            else:
                btn_output.config(state='disabled')
                txt += "mb-Ausgabe vorhanden: nein / nicht gefunden\n"
            txt += (f"Strukturierte Ergebniszeilen: {detail.get('simple_results',0)} einfach · {detail.get('grid_results',0)} Raster\n"
                    f"Dokumenteinträge zur Position: {detail.get('document_entries',0)}\n"
                    f"Dateireferenzen zur Position: {detail.get('file_refs',0)}\n")
            if detail.get('auswertung_types'): txt += "Auswertungstypen (mb intern): " + ', '.join(map(str,detail['auswertung_types'])) + "\n"
            if derr: txt += "\nHinweis: "+derr+"\n"
            txt += "\nHinweis 1.4.2: Projekt-Explorer mit Detailbereich, zuletzt geänderten Dateien und manueller fachlicher Zuordnung. Originaldateien bleiben read-only."
            detail_text.insert('1.0',txt); detail_text.config(state='disabled')

        def rebuild_positions(*_):
            for iid in ptr.get_children(): ptr.delete(iid)
            item_rows.clear(); q=search_var.get().strip().casefold(); wanted=filter_var.get()
            groups={g:[] for g in group_order}
            for r in current_rows:
                if wanted!='Alle' and r['group']!=wanted: continue
                hay=(r.get('_project','')+' '+r['pos']+' '+r['desc']+' '+r['module']+' '+r['group']).casefold()
                if q and q not in hay: continue
                groups.setdefault(r['group'],[]).append(r)
            shown=0
            for g in group_order:
                rows=groups.get(g) or []
                if not rows: continue
                parent=ptr.insert('', 'end', text=f'{g} ({len(rows)})', open=True, values=('', '', '', '', ''))
                for r in rows:
                    iid=ptr.insert(parent,'end',text='',values=(r.get('_project',''),r['pos'],r['desc'],r['module'],r['results']))
                    item_rows[iid]=r; shown+=1
            if current_project['name']:
                pos_info.config(text=f"{current_project['name']} · {len(current_rows)} Einträge gelesen · {shown} angezeigt",fg=INK)
            set_detail(None)

        def load_positions(folder,name):
            current_project['folder']=folder; current_project['name']=name
            rows,err=read_mb_positions(folder)
            current_rows[:] = rows
            if err:
                pos_info.config(text=f'{name}: {err}',fg=RED); current_rows[:] = []; rebuild_positions(); return
            rebuild_positions()

        def load_all_positions():
            current_project['folder']=None; current_project['name']='ALLE mb-PROJEKTE'
            merged=[]; errors=[]
            for folder,name,lead_name,changed,rel,status in mb_projects:
                rows,err=read_mb_positions(folder)
                if err:
                    errors.append(f'{name}: {err}'); continue
                for r in rows:
                    r=dict(r); r['_folder']=folder; r['_project']=name; merged.append(r)
            current_rows[:] = merged
            rebuild_positions()
            if errors and not merged: pos_info.config(text=' · '.join(errors),fg=RED)
            elif errors: pos_info.config(text=f'ALLE mb-PROJEKTE · {len(merged)} Einträge gelesen · Hinweise bei {len(errors)} Projekt(en)',fg=INK)

        def position_selected(_evt=None):
            sel=ptr.selection()
            if not sel: set_detail(None); return
            set_detail(item_rows.get(sel[0]))

        # 1.4.6: Positionsakte 2.0 – bestehende Anzeige unangetastet lassen,
        # aber Zaehler eindeutiger machen und automatisch passende Projektdateien
        # zur markierten mb-Position finden. Alles rein lesend.
        _rebuild_positions_145 = rebuild_positions
        def rebuild_positions(*_args):
            _rebuild_positions_145(*_args)
            try:
                visible=sum(1 for iid in list(item_rows.keys()) if ptr.exists(iid))
                project_name=current_project.get('name') or 'mb-Projekt'
                pos_info.config(text=f'{project_name} · {len(current_rows)} DB-Einträge gelesen · {visible} Positionszeilen sichtbar',fg=INK)
            except Exception:
                pass

        _position_files_cache={'files':None}
        _position_match_cache={}
        def _position_candidate_files():
            if _position_files_cache['files'] is not None:
                return _position_files_cache['files']
            out=[]
            allowed={'.pdf','.doc','.docx','.xls','.xlsx','.xlsm','.dwg','.dxf','.ndw','.npl','.jpg','.jpeg','.png','.tif','.tiff','.eml','.msg','.txt'}
            try:
                for p in project_root.rglob('*'):
                    try:
                        if not p.is_file() or p.suffix.casefold() not in allowed:
                            continue
                        rel=p.relative_to(project_root)
                        low=str(rel).replace('\\','/').casefold()
                        # mb-interne Dateien sind Quelle, aber keine externe Positionsverknuepfung.
                        if '/mb-software/' in '/'+low+'/' or '/mbaec/' in '/'+low+'/':
                            continue
                        out.append((p,rel,low))
                    except (OSError,ValueError):
                        continue
            except OSError:
                pass
            _position_files_cache['files']=out
            return out

        def _position_file_matches(row):
            pos=str((row or {}).get('pos') or '').strip()
            if not pos:
                return []
            key=pos.casefold()
            if key in _position_match_cache:
                return _position_match_cache[key]
            exact=key.replace(' ','')
            compact=''.join(ch for ch in key if ch.isalnum())
            parts=[x for x in __import__('re').split(r'[^0-9a-zäöüß]+',key) if x]
            matches=[]
            for p,rel,low in _position_candidate_files():
                low_no_space=low.replace(' ','')
                norm=''.join(ch for ch in low if ch.isalnum())
                hit=False; score=0
                if exact and exact in low_no_space:
                    hit=True; score+=100
                if compact and len(compact)>=4 and compact in norm:
                    hit=True; score+=80
                if len(parts)>=2 and all(part in low for part in parts if len(part)>=2):
                    hit=True; score+=30
                if not hit:
                    continue
                if 'prüf' in low or 'pruef' in low:
                    cat='Prüfstatik'; score+=12
                elif any(x in low for x in ('plan','allplan','cad','.dwg','.dxf','.ndw','.npl')):
                    cat='Pläne / CAD'; score+=10
                elif any(x in low for x in ('nachweis','berechnung','statik','bemessung')):
                    cat='Eigene Nachweise'; score+=8
                else:
                    cat='Dokumente'
                try: ts=p.stat().st_mtime
                except OSError: ts=0
                matches.append((score,ts,cat,p,rel))
            matches.sort(key=lambda x:(-x[0],-x[1],str(x[4]).casefold()))
            result=matches[:12]
            _position_match_cache[key]=result
            return result

        _position_selected_145 = position_selected
        def position_selected(_evt=None):
            _position_selected_145(_evt)
            try:
                sel=ptr.selection()
                if not sel:return
                r=item_rows.get(sel[0])
                if not r:return
                lines=[]
                dbsrc=str(r.get('_db') or '').strip()
                if dbsrc:
                    try: dbsrc=str(Path(dbsrc).relative_to(project_root))
                    except Exception: pass
                    lines.append('\\nMB-QUELLE\\n'+dbsrc)
                matches=_position_file_matches(r)
                lines.append('\\n\\nVERKNÜPFTE PROJEKTDATEIEN · AUTOMATISCH')
                if matches:
                    for _score,_ts,cat,_p,rel in matches:
                        lines.append(f'• {cat}: {rel}')
                else:
                    lines.append('Noch keine Datei anhand der Positionsnummer eindeutig zuordenbar.')
                lines.append('\\nDie Zuordnung ist nur eine Lese-/Suchansicht; Originaldateien werden nicht verändert.')
                detail_text.config(state='normal')
                detail_text.insert('end',''.join(lines))
                detail_text.config(state='disabled')
            except Exception:
                try: detail_text.config(state='disabled')
                except Exception: pass

        # 1.4.7: Positionsakte kompakt und direkt bedienbar.
        # Die technischen Rohdaten bleiben verfügbar, wichtige Verknüpfungen
        # stehen nun oben und gefundene Dateien lassen sich per Doppelklick öffnen.
        _position_selected_146 = position_selected

        def _mb_preferred_lead(folder):
            try:
                folder=Path(folder)
                leads=sorted(folder.glob('*.mbp'),key=lambda x:x.name.casefold())
                preferred=next((x for x in leads if x.stem.casefold()==folder.name.casefold()),None)
                if preferred is None and leads: preferred=leads[0]
                if preferred is None:
                    deep=sorted(folder.rglob('*.mbp'),key=lambda x:(len(x.parts),x.name.casefold()))
                    preferred=deep[0] if deep else None
                return preferred
            except Exception:
                return None

        def _find_baustatik_exe():
            """Find BauStatik.exe robustly: App Paths/Uninstall registry plus mb install folders."""
            try:
                import os
                candidates=[]
                scan_dirs=[]

                def add_candidate(p,score=0):
                    try:
                        p=Path(str(p).strip().strip('"'))
                        if p.is_file() and p.name.casefold()=='baustatik.exe':
                            txt=str(p).casefold()
                            bonus=600 if '2026' in txt else 0
                            candidates.append((score+bonus,p))
                        elif p.is_dir():
                            scan_dirs.append(p)
                    except Exception:
                        pass

                # 1) Windows App Paths and installed-program registry entries.
                try:
                    import winreg
                    views=[0]
                    for flagname in ('KEY_WOW64_64KEY','KEY_WOW64_32KEY'):
                        flag=getattr(winreg,flagname,0)
                        if flag not in views: views.append(flag)
                    hives=(winreg.HKEY_LOCAL_MACHINE,winreg.HKEY_CURRENT_USER)
                    app_key=r'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\BauStatik.exe'
                    for hive in hives:
                        for view in views:
                            try:
                                with winreg.OpenKey(hive,app_key,0,winreg.KEY_READ|view) as k:
                                    try: add_candidate(winreg.QueryValueEx(k,None)[0],2000)
                                    except Exception: pass
                                    try: add_candidate(winreg.QueryValueEx(k,'Path')[0],1400)
                                    except Exception: pass
                            except Exception:
                                pass

                    uninstall_roots=(
                        r'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall',
                        r'SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall',
                    )
                    for hive in hives:
                        for base in uninstall_roots:
                            for view in views:
                                try:
                                    with winreg.OpenKey(hive,base,0,winreg.KEY_READ|view) as uk:
                                        count=winreg.QueryInfoKey(uk)[0]
                                        for i in range(count):
                                            try:
                                                sub=winreg.EnumKey(uk,i)
                                                with winreg.OpenKey(uk,sub) as sk:
                                                    try: name=str(winreg.QueryValueEx(sk,'DisplayName')[0])
                                                    except Exception: name=''
                                                    if 'mb worksuite' not in name.casefold() and 'mb aec' not in name.casefold():
                                                        continue
                                                    try: add_candidate(winreg.QueryValueEx(sk,'InstallLocation')[0],1300)
                                                    except Exception: pass
                                                    try:
                                                        icon=str(winreg.QueryValueEx(sk,'DisplayIcon')[0]).split(',')[0]
                                                        add_candidate(icon,900)
                                                    except Exception: pass
                                            except Exception:
                                                pass
                                except Exception:
                                    pass
                except Exception:
                    pass

                # 2) Standard Windows installation roots. Search inside mb folders, not all Program Files.
                roots=[]
                for env in ('ProgramFiles','ProgramW6432','ProgramFiles(x86)'):
                    p=os.environ.get(env)
                    if p and p not in roots:
                        roots.append(p)
                system_drive=os.environ.get('SystemDrive','C:')
                for extra in (str(Path(system_drive+'\\')/'mb2026'), str(Path(system_drive+'\\')/'mb2025')):
                    if extra not in roots:
                        roots.append(extra)

                for root in roots:
                    rp=Path(root)
                    if not rp.exists():
                        continue
                    if rp.name.casefold().startswith('mb20'):
                        scan_dirs.append(rp)
                    else:
                        for name in ('mb2026','mb2025','mb2024'):
                            d=rp/name
                            if d.exists(): scan_dirs.append(d)
                        try:
                            for d in rp.iterdir():
                                if not d.is_dir():
                                    continue
                                n=d.name.casefold()
                                if n.startswith('mb20') or 'mb aec' in n or 'mbaec' in n or 'worksuite' in n:
                                    scan_dirs.append(d)
                        except Exception:
                            pass

                # 3) Search only inside likely mb directories. This also finds x64/bin subfolders.
                seen=set()
                for d in scan_dirs:
                    key=str(d).casefold()
                    if key in seen or not d.exists():
                        continue
                    seen.add(key)
                    direct=d/'BauStatik.exe'
                    if direct.exists(): add_candidate(direct,1200)
                    try:
                        for exe in d.rglob('BauStatik.exe'):
                            add_candidate(exe,1100)
                    except Exception:
                        pass

                if not candidates:
                    return None
                uniq={str(p).casefold():(score,p) for score,p in candidates}
                return sorted(uniq.values(),key=lambda x:(x[0],str(x[1]).casefold()),reverse=True)[0][1]
            except Exception:
                return None

        def _open_baustatik_project(folder):
            """Start BauStatik directly for the selected mb project (1.4.9 test route)."""
            try:
                import subprocess
                folder=Path(folder)
                exe=_find_baustatik_exe()
                if exe is None:
                    # Fallback: user may have chosen a custom install directory.
                    try:
                        chosen=filedialog.askopenfilename(
                            title='BauStatik.exe auswählen',
                            filetypes=[('mb BauStatik','BauStatik.exe'),('EXE-Dateien','*.exe'),('Alle Dateien','*.*')]
                        )
                    except Exception:
                        chosen=''
                    if not chosen:
                        messagebox.showwarning('BauStatik','BauStatik.exe wurde nicht automatisch gefunden.\n\nDie Suche prüft Registry, Program Files und mb-Unterordner. Bei einer benutzerdefinierten Installation bitte BauStatik.exe einmal manuell auswählen.')
                        return
                    exe=Path(chosen)
                lead=_mb_preferred_lead(folder)
                cmd=[str(exe)]
                if lead is not None:
                    # mb applications normally receive the project lead file as shell argument.
                    # This is intentionally kept separate from ProjektManager opening so it can
                    # be tested safely without changing any mb project data.
                    cmd.append(str(lead))
                else:
                    cmd.append(str(folder))
                subprocess.Popen(cmd,cwd=str(exe.parent))
            except Exception as e:
                messagebox.showerror('BauStatik',f'BauStatik konnte nicht direkt gestartet werden:\n{e}')

        def _detail_add_action(text,label,callback,tag_index):
            tag=f'pzaction_{tag_index}'
            start=text.index('end-1c')
            text.insert('end',label+'\n')
            end=text.index('end-1c')
            try:
                text.tag_add(tag,start,end)
                text.tag_config(tag,underline=True)
                text.tag_bind(tag,'<Double-Button-1>',lambda _e,cb=callback: cb())
                text.tag_bind(tag,'<Enter>',lambda _e,t=text: t.config(cursor='hand2'))
                text.tag_bind(tag,'<Leave>',lambda _e,t=text: t.config(cursor=''))
            except Exception:
                pass
            return tag_index+1

        _mb_application_cache={}

        def _mb_application_for_position(folder,row):
            """Classify a position by real project data, without changing mb files.

            A BauStatik position that is backed by a MicroFe/FEM model is recognised
            through FEM/*.mbdb -> FEMWerteTabelle/ModellName. Everything else remains
            a BauStatik position. The scan is cached per mb project folder.
            """
            try:
                import sqlite3
                folder=Path(folder)
                pos=str((row or {}).get('pos') or '').strip()
                if not pos:
                    return 'BauStatik'
                key=str(folder.resolve()).casefold()
                names=_mb_application_cache.get(key)
                if names is None:
                    names=set()
                    fem=folder/'FEM'
                    if fem.exists():
                        for db in fem.rglob('*.mbdb'):
                            try:
                                uri='file:'+db.resolve().as_posix()+'?mode=ro'
                                con=sqlite3.connect(uri,uri=True,timeout=0.25)
                                try:
                                    tab=con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='FEMWerteTabelle' LIMIT 1").fetchone()
                                    if not tab:
                                        continue
                                    for rec in con.execute("SELECT strWert FROM FEMWerteTabelle WHERE lower(strName)=lower('ModellName')"):
                                        if rec and rec[0] not in (None,''):
                                            names.add(str(rec[0]).strip().casefold())
                                finally:
                                    con.close()
                            except Exception:
                                pass
                    _mb_application_cache[key]=names
                return 'MicroFe' if pos.casefold() in names else 'BauStatik'
            except Exception:
                return 'BauStatik'

        def _position_file_is_exact(pos,rel):
            """Match a project file to exactly one mb position.

            The position and candidate path are split into alpha/numeric components.
            This keeps common spellings such as E.01.D, E01D, E_01_D and
            'Pos E01 D' compatible, but E.01.D no longer matches E.01.DS-1.
            """
            try:
                import re
                def parts(value):
                    return re.findall(r'[A-Z]+|[0-9]+',str(value or '').upper())
                wanted=parts(pos)
                have=parts(rel)
                if not wanted or len(have)<len(wanted):
                    return False
                n=len(wanted)
                return any(have[i:i+n]==wanted for i in range(len(have)-n+1))
            except Exception:
                return False

        _mb_model_cache={}
        def _mb_model_for_position(folder,r):
            """Identify the concrete mb model behind a position, read-only.

            MicroFe: finds the FEM database that really contains the selected
            position and uses its filename as stable model identifier.
            BauStatik: uses the project .mbp/BSPos container and tries to read a
            descriptive project/model title only from clearly named metadata
            fields. No mb file is ever modified.
            """
            try:
                import re, sqlite3
                from pathlib import Path
                base=Path(folder)
                pos=str(r.get('pos') or '').strip()
                app=_mb_application_for_position(folder,r)
                key=(str(base).lower(),pos.upper(),str(app))
                if key in _mb_model_cache:
                    return _mb_model_cache[key]

                def _q(name):
                    return '"'+str(name).replace('"','""')+'"'

                def _db_open_ro(db):
                    return sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True)

                def _clean(value):
                    if value is None:
                        return ''
                    txt=' '.join(str(value).replace('\x00',' ').split()).strip()
                    if len(txt)<3 or len(txt)>180:
                        return ''
                    if txt.lower() in {'none','null','true','false'}:
                        return ''
                    return txt

                def _db_title(db):
                    """Return only high-confidence model/project metadata."""
                    try:
                        con=_db_open_ro(db)
                        tables=[x[0] for x in con.execute("select name from sqlite_master where type='table'")]
                        strong=('modellname','modelname','projektbezeichnung','projectname','projekttitel','projecttitle','modeltitle')
                        weak=('bezeichnung','name','titel','title')
                        for table in tables:
                            try:
                                cols=[x[1] for x in con.execute(f'pragma table_info({_q(table)})')]
                            except Exception:
                                continue
                            tl=re.sub(r'[^a-z0-9]','',str(table).lower())
                            for col in cols:
                                cl=re.sub(r'[^a-z0-9]','',str(col).lower())
                                ok=any(k in cl for k in strong)
                                if not ok and ('projekt' in tl or 'project' in tl or 'modell' in tl or 'model' in tl):
                                    ok=any(k in cl for k in weak)
                                if not ok:
                                    continue
                                try:
                                    vals=con.execute(f'SELECT {_q(col)} FROM {_q(table)} WHERE {_q(col)} IS NOT NULL LIMIT 8').fetchall()
                                except Exception:
                                    continue
                                for row in vals:
                                    txt=_clean(row[0] if row else '')
                                    if txt and not _position_file_is_exact(pos,txt):
                                        con.close()
                                        return txt
                        con.close()
                    except Exception:
                        pass
                    return ''

                def _db_has_position(db):
                    if not pos:
                        return False
                    try:
                        con=_db_open_ro(db)
                        tables=[x[0] for x in con.execute("select name from sqlite_master where type='table'")]
                        for table in tables:
                            try:
                                info=con.execute(f'pragma table_info({_q(table)})').fetchall()
                            except Exception:
                                continue
                            # Prefer likely position columns, then textual/typeless columns.
                            cols=[]
                            for c in info:
                                name=c[1]; typ=str(c[2] or '').upper(); low=str(name).lower()
                                if any(k in low for k in ('pos','position','bez','name')) or any(k in typ for k in ('CHAR','TEXT','CLOB')) or not typ:
                                    cols.append(name)
                            for col in cols[:12]:
                                try:
                                    rows=con.execute(f'SELECT {_q(col)} FROM {_q(table)} WHERE CAST({_q(col)} AS TEXT) LIKE ? LIMIT 30',(f'%{pos}%',)).fetchall()
                                except Exception:
                                    continue
                                for row in rows:
                                    if row and _position_file_is_exact(pos,row[0]):
                                        con.close()
                                        return True
                        con.close()
                    except Exception:
                        pass
                    return False

                result={'name':'—','id':'','source':'—','app':app,'confidence':'fallback'}

                if str(app).lower()=='microfe':
                    fem=base/'FEM'
                    dbs=sorted(fem.glob('*.mbdb')) if fem.exists() else []
                    chosen=None
                    for db in dbs:
                        if _db_has_position(db):
                            chosen=db
                            break
                    if chosen is None and len(dbs)==1:
                        chosen=dbs[0]
                    if chosen is not None:
                        title=_db_title(chosen)
                        internal_id=chosen.stem
                        # Generated mb identifiers are useful technically, but not as a display name.
                        if title and re.fullmatch(r'[A-Za-z0-9_-]{16,}',title) and not any(ch.isspace() for ch in title):
                            title=''
                        result={
                            'name':title or 'MicroFe-Modell',
                            'id':internal_id,
                            'source':str(chosen.relative_to(base)) if chosen.is_relative_to(base) else str(chosen),
                            'app':app,
                            'confidence':'position' if _db_has_position(chosen) else 'single',
                        }
                else:
                    # BauStatik positions live in BSPos.mbdb; the .mbp is the
                    # model/project container opened by the mb ProjectManager.
                    bs=base/'BSPos.mbdb'
                    mbps=sorted(base.glob('*.mbp'))
                    title=''
                    if bs.exists():
                        title=_db_title(bs)
                    source=bs if bs.exists() else (mbps[0] if mbps else None)
                    if not title and mbps:
                        # Conservative text metadata lookup; no guessing from random binary strings.
                        try:
                            raw=mbps[0].read_bytes()[:2_000_000]
                            texts=[]
                            for enc in ('utf-8','utf-16','cp1252'):
                                try:texts.append(raw.decode(enc,errors='ignore'))
                                except Exception:pass
                            pat=re.compile(r'(?i)(?:Projektbezeichnung|ProjectName|ModelName|ModellName|ProjektTitel|ProjectTitle)\s*[=:>]\s*["\']?([^"\'\r\n<>]{3,180})')
                            for txt in texts:
                                m=pat.search(txt)
                                if m:
                                    cand=_clean(m.group(1))
                                    if cand:
                                        title=cand; break
                        except Exception:
                            pass
                    fallback=mbps[0].stem if mbps else base.name
                    result={
                        'name':title or fallback,
                        'id':'',
                        'source':str(source.relative_to(base)) if source is not None and source.is_relative_to(base) else (str(source) if source else '—'),
                        'app':app,
                        'confidence':'metadata' if title else 'container',
                    }

                _mb_model_cache[key]=result
                return result
            except Exception:
                return {'name':'—','id':'','source':'—','app':'—','confidence':'error'}

        _mb_windows_start_cache={}
        def _mb_windows_start_info():
            """Read Windows file associations for mb project/model files.

            This is deliberately diagnostic only. It does not start a model and
            does not write to the registry. The result tells us whether Windows/
            mb exposes a supported handler for .mbp and .mbdb on this machine.
            """
            if 'value' in _mb_windows_start_cache:
                return _mb_windows_start_cache['value']
            result={
                'project_handler':'nicht registriert',
                'project_command':'',
                'model_handler':'nicht registriert',
                'model_command':'',
            }
            try:
                import winreg, re
                def _default(path):
                    try:
                        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,path) as k:
                            value,_=winreg.QueryValueEx(k,None)
                            return str(value or '').strip()
                    except Exception:
                        return ''
                def _command(ext):
                    progid=_default(ext)
                    candidates=[]
                    if progid:
                        candidates.append(progid+r'\shell\open\command')
                    candidates.append(ext+r'\shell\open\command')
                    for key in candidates:
                        cmd=_default(key)
                        if cmd:
                            return progid,cmd
                    return progid,''
                def _handler(cmd,progid):
                    if cmd:
                        m=re.match(r'^\s*"([^"]+\.exe)"|^\s*([^\s]+\.exe)',cmd,re.I)
                        if m:
                            try:return Path(m.group(1) or m.group(2)).name
                            except Exception:pass
                    return progid or 'nicht registriert'
                p_prog,p_cmd=_command('.mbp')
                m_prog,m_cmd=_command('.mbdb')
                result={
                    'project_handler':_handler(p_cmd,p_prog),
                    'project_command':p_cmd,
                    'model_handler':_handler(m_cmd,m_prog),
                    'model_command':m_cmd,
                }
            except Exception:
                pass
            _mb_windows_start_cache['value']=result
            return result

        def _mb_open_project_application(folder,app_name,model_hint=''):
            """Open the mb project and select BauStatik/MicroFe in ProjektManager.

            Deliberately stops at the application register. The concrete model/position
            is opened by the user in mb. This is the stable workflow proven in 1.4.18.
            """
            try:
                import os, subprocess, threading, time
                from pathlib import Path
                base=Path(folder)
                mbps=sorted(base.glob('*.mbp'))
                if not mbps:
                    try:
                        from tkinter import messagebox
                        messagebox.showwarning('mb-Projekt','Keine .mbp-Projektdatei gefunden.')
                    except Exception:
                        pass
                    return
                lead=mbps[0]
                try:
                    os.startfile(str(lead))
                except Exception as exc:
                    try:
                        from tkinter import messagebox
                        messagebox.showwarning('mb-Projekt',f'Projekt konnte nicht geöffnet werden:\n{exc}')
                    except Exception:
                        pass
                    return

                def _select_tab():
                    time.sleep(1.0)
                    wanted='MicroFe' if str(app_name).lower()=='microfe' else 'BauStatik'
                    env=os.environ.copy()
                    env['ENGBERS_MB_PROJECT']=lead.stem
                    env['ENGBERS_MB_APP']=wanted
                    ps=r"""
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$project=$env:ENGBERS_MB_PROJECT
$wanted=$env:ENGBERS_MB_APP
$root=[System.Windows.Automation.AutomationElement]::RootElement
$window=$null
for($i=0; $i -lt 48 -and $null -eq $window; $i++) {
    $wins=$root.FindAll([System.Windows.Automation.TreeScope]::Children,[System.Windows.Automation.Condition]::TrueCondition)
    foreach($w in $wins) {
        $name=$w.Current.Name
        if($name -and $name -like '*ProjektManager*' -and ($project -eq '' -or $name -like ('*'+$project+'*'))) {
            $window=$w
            break
        }
    }
    if($null -eq $window) { Start-Sleep -Milliseconds 250 }
}
if($null -eq $window) { exit 2 }
$cond=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::TabItem)
$tabs=$window.FindAll([System.Windows.Automation.TreeScope]::Descendants,$cond)
foreach($tab in $tabs) {
    $name=$tab.Current.Name
    $match=$false
    if($wanted -eq 'MicroFe') { $match=($name -like '*MicroFe*') }
    else { $match=($name -like '*BauStatik*') }
    if($match) {
        try {
            $p=$tab.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern)
            $p.Select()
            exit 0
        } catch {}
        try {
            $p=$tab.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
            $p.Invoke()
            exit 0
        } catch {}
        try { $tab.SetFocus(); exit 0 } catch {}
    }
}
exit 3
"""
                    try:
                        subprocess.run(
                            ['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-Command',ps],
                            env=env,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=15,
                            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),
                        )
                    except Exception:
                        pass
                threading.Thread(target=_select_tab,daemon=True).start()
            except Exception:
                pass

        _position_project_files_cache={}
        _position_pdf_text_cache={}
        def _position_project_root(folder):
            """Return the complete Engbers project root for an mb subproject folder."""
            try:
                from pathlib import Path
                p=Path(folder).resolve()
                # Typical layout: <Projekt>/Statik/mb-Software/<mb-Projekt>
                for anc in (p,)+tuple(p.parents):
                    if anc.name.lower()=='statik':
                        return anc.parent
                return p
            except Exception:
                return Path(folder)

        def _position_category(path,rel=''):
            try:
                ext=Path(path).suffix.lower()
                low=str(rel or path).lower()
                cad_ext={'.dwg','.dxf','.dgn','.ifc','.plt','.hpgl','.skp','.c4d'}
                sheet_ext={'.xls','.xlsx','.xlsm','.xlsb','.ods','.csv'}
                office_ext={'.doc','.docx','.rtf','.odt'}
                if any(x in low for x in ('prüf','pruef','prüfer','pruefer')):
                    return 'Prüfstatik'
                if ext in cad_ext or any(x in low for x in ('positionsplan','pos-plan','pos_plan','pos plan','plan','pläne','plaene','cad','bewehr','schalplan')):
                    return 'Pläne / CAD'
                if ext in sheet_ext or ext in office_ext or any(x in low for x in ('nachweis','berechnung','bemessung','statik')):
                    return 'Eigene Nachweise'
                return 'Dokumente'
            except Exception:
                return 'Dokumente'

        def _position_project_files(folder,pos):
            """Find files whose path contains exactly the selected position.

            1.4.26 starts at the complete Engbers project root, not merely inside
            the selected mb project folder. E.01.DS2 and E.01.DS-2 are treated as
            the same token sequence by _position_file_is_exact.
            """
            try:
                import os
                from pathlib import Path
                base=_position_project_root(folder)
                wanted=str(pos or '').strip()
                if not wanted or not base.exists():
                    return []
                key=(str(base).lower(),wanted.upper())
                cached=_position_project_files_cache.get(key)
                if cached is not None:
                    return list(cached)
                allowed={
                    '.pdf','.doc','.docx','.rtf','.odt',
                    '.xls','.xlsx','.xlsm','.xlsb','.ods','.csv',
                    '.dwg','.dxf','.dgn','.ifc','.plt','.hpgl',
                    '.jpg','.jpeg','.png','.tif','.tiff','.bmp',
                    '.txt','.xml','.zip','.skp','.c4d'
                }
                skip_dirs={'fem','__pycache__','.git','.svn','$recycle.bin','backup','backups','sicherung','sicherungen'}
                result=[]
                scanned=0
                for root,dirs,files in os.walk(base):
                    dirs[:]=[d for d in dirs if d.lower() not in skip_dirs and not d.startswith('.')]
                    for fn in files:
                        scanned+=1
                        if scanned>50000:
                            break
                        if fn.startswith('~$') or fn.startswith('.'):
                            continue
                        p=Path(root)/fn
                        ext=p.suffix.lower()
                        if ext not in allowed:
                            continue
                        try: rel=str(p.relative_to(base))
                        except Exception: rel=str(p)
                        if not _position_file_is_exact(wanted,rel):
                            continue
                        cat=_position_category(p,rel)
                        score=100
                        try:
                            if _position_file_is_exact(wanted,p.name): score+=30
                            if ext=='.pdf': score+=5
                            ts=p.stat().st_mtime
                        except Exception:
                            ts=0
                        result.append((score,ts,cat,p,rel))
                    if scanned>50000:
                        break
                result.sort(key=lambda x:(x[0],x[1]),reverse=True)
                _position_project_files_cache[key]=list(result)
                return result
            except Exception:
                return []

        def _position_pdf_extract_text(path):
            """Extract PDF text read-only using whichever reader is available."""
            try:
                p=Path(path)
                st=p.stat()
                cache_key=(str(p).lower(),int(st.st_mtime),int(st.st_size))
                if cache_key in _position_pdf_text_cache:
                    return _position_pdf_text_cache[cache_key]
                text=''
                # pypdf / PyPDF2 are preferred because they are lightweight.
                Reader=None
                try:
                    from pypdf import PdfReader as Reader
                except Exception:
                    try:
                        from PyPDF2 import PdfReader as Reader
                    except Exception:
                        Reader=None
                if Reader is not None:
                    try:
                        reader=Reader(str(p),strict=False)
                        chunks=[]
                        for page in list(reader.pages)[:50]:
                            try:
                                t=page.extract_text() or ''
                                if t: chunks.append(t)
                            except Exception:
                                pass
                        text='\n'.join(chunks)
                    except Exception:
                        text=''
                if not text:
                    try:
                        import fitz
                        doc=fitz.open(str(p))
                        chunks=[]
                        for i in range(min(len(doc),50)):
                            try:
                                t=doc[i].get_text('text') or ''
                                if t: chunks.append(t)
                            except Exception:
                                pass
                        doc.close()
                        text='\n'.join(chunks)
                    except Exception:
                        pass
                _position_pdf_text_cache[cache_key]=text
                return text
            except Exception:
                return ''

        def _position_plan_scope(pos):
            """Map an mb position to the project-wide plan scope used for manual assignment."""
            try:
                import re
                parts=re.findall(r'[A-Z]+|[0-9]+',str(pos or '').upper())
                head=parts[0] if parts else ''
                if head=='E': return 'EG'
                if head=='1': return 'OG'
                if head=='F': return 'SOHLE'
                if head=='G': return 'GARAGE'
                return 'POSITION'
            except Exception:
                return 'POSITION'

        def _position_metadata_dir(folder):
            # PZ_METADATA_DIR_V1445: Projektzentrale-Metadaten gebündelt in .engbers.
            try:base=_position_project_root(folder)
            except Exception:base=Path(folder)
            meta=base/'.engbers'
            try:
                meta.mkdir(parents=True,exist_ok=True)
                if os.name=='nt':
                    try:__import__('ctypes').windll.kernel32.SetFileAttributesW(str(meta), __import__('ctypes').windll.kernel32.GetFileAttributesW(str(meta)) | 0x2)
                    except Exception:pass
            except Exception:
                return base
            return meta

        def _position_migrate_store(folder,legacy_name,new_name):
            try:
                base=_position_project_root(folder); meta=_position_metadata_dir(folder)
                legacy=base/legacy_name; target=meta/new_name
                if meta!=base and legacy.exists() and not target.exists():
                    try:legacy.replace(target)
                    except Exception:
                        try:shutil.copy2(legacy,target)
                        except Exception:return legacy
                return target if meta!=base else legacy
            except Exception:
                return Path(folder)/legacy_name

        def _position_manual_plan_store(folder):
            return _position_migrate_store(folder,'.engbers_positionsplaene.json','positionsplaene.json')

        def _position_manual_plan_load(folder):
            try:
                import json
                store=_position_manual_plan_store(folder)
                if not store.exists(): return {'version':1,'plans':{}}
                data=json.loads(store.read_text(encoding='utf-8'))
                if not isinstance(data,dict): return {'version':1,'plans':{}}
                if not isinstance(data.get('plans'),dict): data['plans']={}
                return data
            except Exception:
                return {'version':1,'plans':{}}

        def _position_manual_plan_files(folder,pos):
            """Return a persistent, user-confirmed Positionsplan assignment for this floor."""
            try:
                base=_position_project_root(folder).resolve()
                scope=_position_plan_scope(pos)
                data=_position_manual_plan_load(folder)
                entry=data.get('plans',{}).get(scope)
                if not isinstance(entry,dict): return []
                rel=str(entry.get('path') or '').strip()
                if not rel: return []
                p=(base/rel).resolve()
                try: p.relative_to(base)
                except Exception: return []
                if not p.exists() or not p.is_file(): return []
                try: ts=p.stat().st_mtime
                except Exception: ts=0
                try: shown=str(p.relative_to(base))
                except Exception: shown=str(p)
                return [(1000,ts,'Pläne / CAD',p,shown+f'  [Positionsplan {scope} – dauerhaft zugeordnet]')]
            except Exception:
                return []

        def _position_assign_plan(folder,pos):
            """Let the user select one project file and store it as Positionsplan for the floor."""
            try:
                import json, datetime as _dt
                from tkinter import filedialog, messagebox
                base=_position_project_root(folder).resolve()
                scope=_position_plan_scope(pos)
                selected=filedialog.askopenfilename(
                    title=f'Positionsplan {scope} dauerhaft zuordnen',
                    initialdir=str(base),
                    filetypes=[
                        ('Plan-Dateien','*.pdf *.dwg *.dxf *.dgn *.ifc *.plt *.hpgl'),
                        ('PDF','*.pdf'),
                        ('Alle Dateien','*.*'),
                    ],
                )
                if not selected: return False
                p=Path(selected).resolve()
                try:
                    rel=p.relative_to(base)
                except Exception:
                    messagebox.showwarning('Positionsplan','Bitte eine Datei innerhalb des aktuellen Projektordners auswählen.')
                    return False
                data=_position_manual_plan_load(folder)
                data.setdefault('plans',{})[scope]={
                    'path':str(rel),
                    'assigned_at':_dt.datetime.now().isoformat(timespec='seconds'),
                }
                store=_position_manual_plan_store(folder)
                store.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                messagebox.showinfo('Positionsplan',f'Positionsplan {scope} wurde dauerhaft zugeordnet.\n\nPosition bitte einmal erneut anklicken.')
                return True
            except Exception as exc:
                try:
                    from tkinter import messagebox
                    messagebox.showwarning('Positionsplan',f'Zuordnung konnte nicht gespeichert werden:\n{exc}')
                except Exception:
                    pass
                return False

        def _position_remove_manual_plan(folder,pos):
            try:
                import json
                from tkinter import messagebox
                scope=_position_plan_scope(pos)
                data=_position_manual_plan_load(folder)
                plans=data.setdefault('plans',{})
                if scope not in plans: return False
                if not messagebox.askyesno('Positionsplan',f'Dauerhafte Zuordnung für Positionsplan {scope} entfernen?'):
                    return False
                plans.pop(scope,None)
                _position_manual_plan_store(folder).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                messagebox.showinfo('Positionsplan',f'Zuordnung für Positionsplan {scope} wurde entfernt.\n\nPosition bitte einmal erneut anklicken.')
                return True
            except Exception:
                return False

        def _position_record_store(folder):
            return _position_migrate_store(folder,'.engbers_positionsakte.json','positionsakte.json')

        def _position_record_key(folder,pos):
            try:
                base=_position_project_root(folder).resolve()
                mb=Path(folder).resolve()
                try: rel=str(mb.relative_to(base))
                except Exception: rel=str(mb)
                return rel.replace('\\','/').lower()+'|'+str(pos or '').strip().upper()
            except Exception:
                return str(pos or '').strip().upper()

        def _position_record_load(folder):
            try:
                import json
                store=_position_record_store(folder)
                if not store.exists(): return {'version':1,'positions':{}}
                data=json.loads(store.read_text(encoding='utf-8'))
                if not isinstance(data,dict): return {'version':1,'positions':{}}
                if not isinstance(data.get('positions'),dict): data['positions']={}
                return data
            except Exception:
                return {'version':1,'positions':{}}

        def _position_record_save(folder,data):
            try:
                import json
                store=_position_record_store(folder)
                tmp=store.with_name(store.name+'.tmp')
                tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                tmp.replace(store)
                return True
            except Exception:
                return False

        def _position_record_get(folder,pos):
            try:
                data=_position_record_load(folder)
                rec=data.get('positions',{}).get(_position_record_key(folder,pos),{})
                if not isinstance(rec,dict): rec={}
                files=rec.get('files',[])
                if not isinstance(files,list): files=[]
                return {'status':str(rec.get('status') or 'Offen'),'note':str(rec.get('note') or ''),'updated_at':str(rec.get('updated_at') or ''),'files':files}
            except Exception:
                return {'status':'Offen','note':'','updated_at':'','files':[]}

        def _position_record_update(folder,pos,**changes):
            try:
                import datetime as _dt
                data=_position_record_load(folder)
                key=_position_record_key(folder,pos)
                rec=data.setdefault('positions',{}).setdefault(key,{})
                if not isinstance(rec,dict): rec={}; data['positions'][key]=rec
                for k,v in changes.items(): rec[k]=v
                rec['updated_at']=_dt.datetime.now().isoformat(timespec='seconds')
                return _position_record_save(folder,data)
            except Exception:
                return False

        def _position_manual_position_files(folder,pos):
            try:
                base=_position_project_root(folder).resolve()
                rec=_position_record_get(folder,pos)
                out=[]
                for item in rec.get('files',[]):
                    if not isinstance(item,dict): continue
                    rel=str(item.get('path') or '').strip()
                    if not rel: continue
                    p=(base/rel).resolve()
                    try: p.relative_to(base)
                    except Exception: continue
                    if not p.exists() or not p.is_file(): continue
                    cat=str(item.get('category') or '').strip() or _position_category(p,rel)
                    try: ts=p.stat().st_mtime
                    except Exception: ts=0
                    try: shown=str(p.relative_to(base))
                    except Exception: shown=str(p)
                    out.append((900,ts,cat,p,shown+'  [manuell mit Position verknüpft]'))
                out.sort(key=lambda x:(x[0],x[1]),reverse=True)
                return out
            except Exception:
                return []

        def _position_link_file(folder,pos):
            try:
                from tkinter import filedialog, messagebox
                base=_position_project_root(folder).resolve()
                selected=filedialog.askopenfilename(title=f'Datei mit Position {pos} verknüpfen',initialdir=str(base),filetypes=[('Projektdateien','*.pdf *.doc *.docx *.xls *.xlsx *.xlsm *.dwg *.dxf *.ifc *.jpg *.jpeg *.png *.txt *.zip'),('Alle Dateien','*.*')])
                if not selected: return False
                p=Path(selected).resolve()
                try: rel=p.relative_to(base)
                except Exception:
                    messagebox.showwarning('Positionsakte','Bitte eine Datei innerhalb des aktuellen Projektordners auswählen.'); return False
                rec=_position_record_get(folder,pos); files=list(rec.get('files',[])); relstr=str(rel)
                if relstr.lower() in {str(x.get('path') or '').lower() for x in files if isinstance(x,dict)}:
                    messagebox.showinfo('Positionsakte','Diese Datei ist bereits mit der Position verknüpft.'); return False
                default_cat=_position_category(p,relstr); categories=('Prüfstatik','Pläne / CAD','Eigene Nachweise','Dokumente'); chosen={'value':None}
                win=tk.Toplevel(self); win.title('Kategorie wählen'); win.configure(bg=BG); win.transient(self); win.grab_set(); win.resizable(False,False)
                tk.Label(win,text=f'Datei mit Pos. {pos} verknüpfen',bg=BG,fg=INK,font=('Segoe UI Semibold',12)).pack(anchor='w',padx=20,pady=(18,4))
                tk.Label(win,text=p.name,bg=BG,fg=MUTED,font=('Segoe UI',9),wraplength=440,justify='left').pack(anchor='w',padx=20,pady=(0,12))
                def choose(cat): chosen['value']=cat; win.destroy()
                for cat in categories:
                    bg=ACCENT if cat==default_cat else '#e7e4dc'; fg='white' if cat==default_cat else INK
                    tk.Button(win,text=cat,command=lambda c=cat:choose(c),anchor='w',bg=bg,fg=fg,activebackground=bg,activeforeground=fg,bd=0,padx=14,pady=8,width=30).pack(fill='x',padx=20,pady=2)
                tk.Button(win,text='Abbrechen',command=win.destroy,bg=BG,fg=MUTED,bd=0,padx=14,pady=7).pack(anchor='e',padx=20,pady=(8,14))
                try:self.wait_window(win)
                except Exception:pass
                cat=chosen.get('value')
                if not cat:return False
                files.append({'path':relstr,'category':cat})
                if not _position_record_update(folder,pos,files=files):
                    messagebox.showwarning('Positionsakte','Die Dateiverknüpfung konnte nicht gespeichert werden.'); return False
                try:self.after_idle(position_selected)
                except Exception:pass
                return True
            except Exception as exc:
                try: messagebox.showwarning('Positionsakte',f'Datei konnte nicht verknüpft werden:\n{exc}')
                except Exception: pass
                return False

        def _position_unlink_file(folder,pos):
            try:
                from tkinter import messagebox, simpledialog
                rec=_position_record_get(folder,pos); files=[x for x in rec.get('files',[]) if isinstance(x,dict) and str(x.get('path') or '').strip()]
                if not files:
                    messagebox.showinfo('Positionsakte','Für diese Position gibt es keine manuelle Dateiverknüpfung.'); return False
                if len(files)==1:
                    idx=0
                    if not messagebox.askyesno('Positionsakte',f'Diese Dateiverknüpfung entfernen?\n\n{files[0].get("path","")}'): return False
                else:
                    listing='\n'.join(f'{i+1}: {x.get("path","")}' for i,x in enumerate(files[:25]))
                    n=simpledialog.askinteger('Positionsakte','Welche Verknüpfung soll entfernt werden?\n\n'+listing,minvalue=1,maxvalue=min(len(files),25))
                    if not n:return False
                    idx=n-1
                files.pop(idx)
                if not _position_record_update(folder,pos,files=files): return False
                try:self.after_idle(position_selected)
                except Exception:pass
                return True
            except Exception:return False

        def _position_update_bearbeitung_display(detail_text,status=None,note=None):
            """Update the visible BEARBEITUNG block immediately after saving."""
            if detail_text is None:
                return
            try:
                old_state=str(detail_text.cget('state'))
            except Exception:
                old_state='normal'
            try:
                if old_state=='disabled':
                    detail_text.config(state='normal')
                start=detail_text.search('BEARBEITUNG','1.0','end')
                if not start:
                    return
                if status is not None:
                    idx=detail_text.search('Status:',start,'end')
                    if idx:
                        detail_text.delete(idx,f'{idx} lineend')
                        detail_text.insert(idx,'Status: '+str(status))
                if note is not None:
                    idx=detail_text.search('Notiz:',start,'end')
                    if idx:
                        detail_text.delete(idx,f'{idx} lineend')
                        detail_text.insert(idx,'Notiz: '+(str(note) if str(note).strip() else '—'))
            except Exception:
                pass
            finally:
                try:
                    if old_state=='disabled':
                        detail_text.config(state='disabled')
                except Exception:
                    pass

        def _position_set_status(folder,pos,detail_text=None):
            """Choose a position status with direct buttons and refresh the visible status immediately."""
            try:
                import tkinter as tk
                from tkinter import messagebox
                current=_position_record_get(folder,pos).get('status') or 'Offen'
                options=('Offen','In Bearbeitung','Geprüft','Änderung erforderlich','Erledigt')
                chosen={'value':None}

                master=getattr(tk,'_default_root',None)
                dlg=tk.Toplevel(master) if master is not None else tk.Toplevel()
                dlg.title('Positionsstatus')
                dlg.resizable(False,False)
                try:
                    if master is not None: dlg.transient(master)
                except Exception:
                    pass

                outer=tk.Frame(dlg,padx=16,pady=14)
                outer.pack(fill='both',expand=True)
                tk.Label(outer,text='Bearbeitungsstatus für '+str(pos),anchor='w').pack(fill='x',pady=(0,4))
                tk.Label(outer,text='Aktuell: '+str(current),anchor='w').pack(fill='x',pady=(0,10))

                def _choose(value):
                    chosen['value']=value
                    try: dlg.destroy()
                    except Exception: pass

                for value in options:
                    label=('✓  ' if value==current else '   ')+value
                    tk.Button(outer,text=label,width=30,anchor='w',command=lambda v=value:_choose(v)).pack(fill='x',pady=2)

                tk.Button(outer,text='Abbrechen',width=30,command=lambda:_choose(None)).pack(fill='x',pady=(10,0))
                try:
                    dlg.protocol('WM_DELETE_WINDOW',lambda:_choose(None))
                    dlg.grab_set()
                    dlg.focus_force()
                    dlg.wait_window()
                except Exception:
                    pass

                status=chosen.get('value')
                if not status: return False
                if status==current:
                    _position_update_bearbeitung_display(detail_text,status=status)
                    try:_position_status_ui_refresh(folder,pos)
                    except Exception:pass
                    return True
                if not _position_record_update(folder,pos,status=status):
                    messagebox.showwarning('Positionsstatus','Der Status konnte nicht gespeichert werden.')
                    return False
                _position_update_bearbeitung_display(detail_text,status=status)
                try:_position_status_ui_refresh(folder,pos)
                except Exception:pass
                return True
            except Exception:
                return False

        def _position_edit_note(folder,pos,detail_text=None):
            try:
                from tkinter import simpledialog, messagebox
                current=_position_record_get(folder,pos).get('note') or ''
                note=simpledialog.askstring('Positionsnotiz',f'Kurze Notiz zu Position {pos}:',initialvalue=current)
                if note is None: return False
                note=' '.join(str(note).split())[:500]
                if not _position_record_update(folder,pos,note=note):
                    messagebox.showwarning('Positionsnotiz','Die Notiz konnte nicht gespeichert werden.')
                    return False
                _position_update_bearbeitung_display(detail_text,note=note)
                return True
            except Exception:
                return False

        def _position_context_plan_files(folder,pos):
            """Return likely plan files as possible context for the selected position.

            1.4.28 normalizes punctuation aggressively, so spellings such as
            'Pos.-Plan', 'Pos Plan', 'Positionsplan' and folder variants are all
            recognized. If no explicit Positionsplan token is present, PDFs/CAD
            files in clearly plan-like folders are offered as possible candidates.
            Exact filename/PDF-content hits still rank higher elsewhere.
            """
            try:
                import os, re, unicodedata
                from pathlib import Path
                base=_position_project_root(folder)
                wanted=str(pos or '').strip()
                if not wanted or not base.exists():
                    return []

                def _norm(value):
                    txt=str(value or '').lower()
                    txt=txt.replace('ä','ae').replace('ö','oe').replace('ü','ue').replace('ß','ss')
                    txt=unicodedata.normalize('NFKD',txt)
                    txt=''.join(ch for ch in txt if not unicodedata.combining(ch))
                    return re.sub(r'[^a-z0-9]+',' ',txt).strip()

                parts=re.findall(r'[A-Z]+|[0-9]+',wanted.upper())
                head=parts[0] if parts else ''
                floor_words=set()
                if head=='E': floor_words={'eg','erdgeschoss'}
                elif head=='1': floor_words={'og','obergeschoss'}
                elif head=='F': floor_words={'fundament','sohle','bodenplatte','gruendung'}
                elif head=='G': floor_words={'garage'}

                allowed={'.pdf','.dwg','.dxf','.dgn','.ifc','.plt','.hpgl'}
                skip_dirs={'fem','__pycache__','.git','.svn','$recycle.bin','backup','backups','sicherung','sicherungen'}
                result=[]
                scanned=0
                for root,dirs,files in os.walk(base):
                    dirs[:]=[d for d in dirs if d.lower() not in skip_dirs and not d.startswith('.')]
                    for fn in files:
                        scanned+=1
                        if scanned>50000:
                            break
                        if fn.startswith('~$') or fn.startswith('.'):
                            continue
                        p=Path(root)/fn
                        if p.suffix.lower() not in allowed:
                            continue
                        try: rel=str(p.relative_to(base))
                        except Exception: rel=str(p)

                        norm=_norm(rel)
                        tokens=norm.split()
                        compact=''.join(tokens)
                        token_set=set(tokens)

                        explicit=(
                            'positionsplan' in compact or 'positionsplaene' in compact or
                            'posplan' in compact or
                            ('pos' in token_set and 'plan' in token_set) or
                            ('position' in token_set and 'plan' in token_set)
                        )
                        plan_context=bool(token_set.intersection({'plan','plaene','zeichnung','zeichnungen','cad','allplan','bewehrungsplan','schalplan','tragwerksplan','statikplan'}))
                        if not explicit and not plan_context:
                            continue

                        score=45 if explicit else 18
                        if p.suffix.lower()=='.pdf': score+=5
                        if floor_words and token_set.intersection(floor_words): score+=25
                        if explicit and ('pos' in _norm(p.name).split() or 'positionsplan' in ''.join(_norm(p.name).split())): score+=15
                        if 'statik' in token_set or 'tragwerk' in token_set: score+=8
                        try: ts=p.stat().st_mtime
                        except Exception: ts=0
                        note='Positionsplan – mögliche Zuordnung' if explicit else 'Plan – mögliche Zuordnung'
                        result.append((score,ts,'Pläne / CAD',p,rel+'  ['+note+']'))
                    if scanned>50000:
                        break

                result.sort(key=lambda x:(x[0],x[1]),reverse=True)
                # Keep the panel useful: strongest candidates first, no flood of plans.
                return result[:15]
            except Exception:
                return []

        def _position_pdf_content_files(folder,pos):
            """Find PDFs whose actual text contains the selected position.

            This covers Positionspläne named only e.g. 'Positionsplan EG.pdf'.
            E.01.DS2 and E.01.DS-2 match equally. Image-only/scanned PDFs cannot
            be read here and can later be assigned manually.
            """
            try:
                import os
                from pathlib import Path
                base=_position_project_root(folder)
                wanted=str(pos or '').strip()
                if not wanted or not base.exists():
                    return []
                skip_dirs={'fem','__pycache__','.git','.svn','$recycle.bin','backup','backups','sicherung','sicherungen'}
                candidates=[]
                scanned=0
                for root,dirs,files in os.walk(base):
                    dirs[:]=[d for d in dirs if d.lower() not in skip_dirs and not d.startswith('.')]
                    for fn in files:
                        if not fn.lower().endswith('.pdf'):
                            continue
                        p=Path(root)/fn
                        try:
                            st=p.stat()
                            if st.st_size<=0 or st.st_size>120*1024*1024:
                                continue
                            rel=str(p.relative_to(base))
                        except Exception:
                            continue
                        low=rel.lower()
                        priority=0
                        if any(x in low for x in ('positionsplan','pos-plan','pos_plan','pos plan')): priority+=120
                        if any(x in low for x in ('plan','pläne','plaene','bewehr','schal')): priority+=50
                        if 'statik' in low: priority+=15
                        candidates.append((priority,st.st_mtime,p,rel))
                        scanned+=1
                        if scanned>=1200:
                            break
                    if scanned>=1200:
                        break
                candidates.sort(key=lambda x:(x[0],x[1]),reverse=True)
                # Avoid a long first click: likely plan PDFs first, then a limited
                # selection of other PDFs. Text is cached for later positions.
                likely=[x for x in candidates if x[0]>0][:80]
                other=[x for x in candidates if x[0]==0][:25]
                result=[]
                for priority,mtime,p,rel in likely+other:
                    text=_position_pdf_extract_text(p)
                    if not text or not _position_file_is_exact(wanted,text):
                        continue
                    cat=_position_category(p,rel)
                    score=90+min(priority,45)
                    result.append((score,mtime,cat,p,rel+'  [Treffer im PDF]'))
                result.sort(key=lambda x:(x[0],x[1]),reverse=True)
                return result
            except Exception:
                return []

        def _detail_add_link(text,label,path,tag_index):
            path=Path(path)
            tag=f'pzlink_{tag_index}'
            start=text.index('end-1c')
            text.insert('end',label+'\n')
            end=text.index('end-1c')
            try:
                text.tag_add(tag,start,end)
                text.tag_config(tag,underline=True)
                text.tag_bind(tag,'<Double-Button-1>',lambda _e,p=path:self.open_external_path(p))
                text.tag_bind(tag,'<Enter>',lambda _e,t=text: t.config(cursor='hand2'))
                text.tag_bind(tag,'<Leave>',lambda _e,t=text: t.config(cursor=''))
            except Exception:
                pass
            return tag_index+1

        def position_selected(_evt=None):
            try:
                sel=ptr.selection()
                if not sel:return
                r=item_rows.get(sel[0])
                if not r:return
                selected_position['row']=r
                folder=Path(r.get('_folder') or current_project.get('folder') or project_root)
                detail,err=read_mb_position_detail(folder,r)
                matches=_position_file_matches(r)

                detail_text.config(state='normal')
                detail_text.delete('1.0','end')
                try:
                    for _tag in list(detail_text.tag_names()):
                        if str(_tag).startswith('pzlink_'): detail_text.tag_delete(_tag)
                except Exception:
                    pass

                pos=str(r.get('pos') or '').strip() or '—'
                bez=str(r.get('bez') or r.get('desc') or '').strip() or '—'
                projekt=str(r.get('_project') or r.get('project') or current_project.get('name') or folder.name)
                modul=str(r.get('modul') or r.get('module') or '').strip() or '—'
                status=(detail or {}).get('status') or r.get('calc_status') or r.get('status') or '—'
                gruppe=str(r.get('gruppe') or r.get('group') or '').strip() or '—'

                detail_text.insert('end',f'Pos. {pos}\n{bez}\n\n')
                mb_app=_mb_application_for_position(folder,r)
                posid=str(r.get('pos') or '').strip() or '—'
                mb_model=_mb_model_for_position(folder,r)
                model_name=mb_model.get('name') or '—'
                model_id=mb_model.get('id') or ''
                model_source=mb_model.get('source') or '—'
                model_id_line=f'Modell-ID: {model_id}\n' if model_id else ''
                start_info=_mb_windows_start_info()
                if str(mb_app).lower()=='microfe':
                    start_probe=f'Startprüfung Modell (.mbdb): {start_info.get("model_handler") or "nicht registriert"}\n'
                    start_command=start_info.get('model_command') or '—'
                else:
                    start_probe=f'Startprüfung Projekt (.mbp): {start_info.get("project_handler") or "nicht registriert"}\n'
                    start_command=start_info.get('project_command') or '—'
                detail_text.insert('end',f'mb-Projekt: {projekt}\nmb-Modul: {modul}\nmb-Anwendung: {mb_app}\n{start_probe}Startkommando: {start_command}\nmb-Modell: {model_name}\n{model_id_line}Modellquelle: {model_source}\nFachgruppe: {gruppe}\nBerechnungsstatus: {status}\n')
                if mb_app=='MicroFe':
                    detail_text.insert('end','Startweg: ProjektManager → MicroFe (bzw. aus BauStatik)\n')
                else:
                    detail_text.insert('end','Startweg: ProjektManager → BauStatik\n')

                detail_text.insert('end','\nÖFFNEN · DOPPELKLICK\n')
                n=0
                lead=_mb_preferred_lead(folder)
                if lead is not None:
                    n=_detail_add_action(detail_text,f'• mb öffnen → {mb_app}',lambda f=folder,a=mb_app,m=posid:_mb_open_project_application(f,a,m),n)
                    n=_detail_add_link(detail_text,'• ProjektManager öffnen (nur Projekt)',lead,n)
                else:
                    n=_detail_add_link(detail_text,'• mb-Projektordner öffnen',folder,n)

                dbsrc=str(r.get('_db') or '').strip()
                if dbsrc:
                    dbp=Path(dbsrc)
                    if dbp.exists():
                        n=_detail_add_link(detail_text,'• mb-Quelldatenbank anzeigen',dbp,n)

                matches=[hit for hit in matches if _position_file_is_exact(r.get('pos'), hit[4] if len(hit)>4 else hit[3])]
                _seen_files=set()
                for _hit in matches:
                    try:_seen_files.add(str(Path(_hit[3]).resolve()).lower())
                    except Exception:_seen_files.add(str(_hit[3]).lower())
                for _hit in _position_project_files(folder,r.get('pos')):
                    try:_key=str(Path(_hit[3]).resolve()).lower()
                    except Exception:_key=str(_hit[3]).lower()
                    if _key not in _seen_files:
                        matches.append(_hit); _seen_files.add(_key)
                for _hit in _position_pdf_content_files(folder,r.get('pos')):
                    try:_key=str(Path(_hit[3]).resolve()).lower()
                    except Exception:_key=str(_hit[3]).lower()
                    if _key not in _seen_files:
                        matches.append(_hit); _seen_files.add(_key)
                for _hit in _position_context_plan_files(folder,r.get('pos')):
                    try:_key=str(Path(_hit[3]).resolve()).lower()
                    except Exception:_key=str(_hit[3]).lower()
                    if _key not in _seen_files:
                        matches.append(_hit); _seen_files.add(_key)
                for _hit in _position_manual_plan_files(folder,r.get('pos')):
                    try:_key=str(Path(_hit[3]).resolve()).lower()
                    except Exception:_key=str(_hit[3]).lower()
                    _new_matches=[]
                    for _old_hit in matches:
                        try:_old_key=str(Path(_old_hit[3]).resolve()).lower()
                        except Exception:_old_key=str(_old_hit[3]).lower()
                        if _old_key!=_key: _new_matches.append(_old_hit)
                    matches=_new_matches
                    matches.append(_hit); _seen_files.add(_key)
                for _hit in _position_manual_position_files(folder,r.get('pos')):
                    try:_key=str(Path(_hit[3]).resolve()).lower()
                    except Exception:_key=str(_hit[3]).lower()
                    _new_matches=[]
                    for _old_hit in matches:
                        try:_old_key=str(Path(_old_hit[3]).resolve()).lower()
                        except Exception:_old_key=str(_old_hit[3]).lower()
                        if _old_key!=_key: _new_matches.append(_old_hit)
                    matches=_new_matches
                    matches.append(_hit); _seen_files.add(_key)
                matches.sort(key=lambda _h:((_h[0] if len(_h)>0 else 0),(_h[1] if len(_h)>1 else 0)),reverse=True)

                _record=_position_record_get(folder,r.get('pos'))
                _status=_record.get('status') or 'Offen'
                _note=_record.get('note') or '—'
                detail_text.insert('end','\nBEARBEITUNG\n')
                detail_text.insert('end',f'Status: {_status}\n')
                detail_text.insert('end',f'Notiz: {_note}\n')
                _status_tag='posstatus_'+str(abs(hash((str(folder),str(r.get('pos'))))))
                detail_text.insert('end','• Status ändern … (Doppelklick)\n',_status_tag)
                detail_text.tag_config(_status_tag,underline=True)
                detail_text.tag_bind(_status_tag,'<Double-1>',lambda _e,_f=folder,_p=r.get('pos'),_t=detail_text:_position_set_status(_f,_p,_t))
                _note_tag='posnote_'+str(abs(hash((str(folder),str(r.get('pos'))))))
                detail_text.insert('end','• Notiz bearbeiten … (Doppelklick)\n',_note_tag)
                detail_text.tag_config(_note_tag,underline=True)
                detail_text.tag_bind(_note_tag,'<Double-1>',lambda _e,_f=folder,_p=r.get('pos'),_t=detail_text:_position_edit_note(_f,_p,_t))

                detail_text.insert('end',f'\nVERKNÜPFTE PROJEKTDATEIEN ({len(matches)})\n')
                _link_tag='posfile_link_'+str(abs(hash((str(folder),str(r.get('pos'))))))
                detail_text.insert('end','• Datei mit dieser Position verknüpfen … (Doppelklick)\n',_link_tag)
                detail_text.tag_config(_link_tag,underline=True)
                detail_text.tag_bind(_link_tag,'<Double-1>',lambda _e,_f=folder,_p=r.get('pos'):_position_link_file(_f,_p))
                if _position_manual_position_files(folder,r.get('pos')):
                    _unlink_tag='posfile_unlink_'+str(abs(hash((str(folder),str(r.get('pos'))))))
                    detail_text.insert('end','• Manuelle Dateiverknüpfung entfernen … (Doppelklick)\n',_unlink_tag)
                    detail_text.tag_config(_unlink_tag,underline=True)
                    detail_text.tag_bind(_unlink_tag,'<Double-1>',lambda _e,_f=folder,_p=r.get('pos'):_position_unlink_file(_f,_p))
                _scope=_position_plan_scope(r.get('pos'))
                _assign_tag='posplan_assign_'+str(abs(hash((str(folder),str(r.get('pos'))))))
                detail_text.insert('end',f'• Positionsplan {_scope} dauerhaft zuordnen … (Doppelklick)\n',_assign_tag)
                detail_text.tag_config(_assign_tag,underline=True)
                detail_text.tag_bind(_assign_tag,'<Double-1>',lambda _e,_f=folder,_p=r.get('pos'):_position_assign_plan(_f,_p))
                if _position_manual_plan_files(folder,r.get('pos')):
                    _remove_tag='posplan_remove_'+str(abs(hash((str(folder),str(r.get('pos'))))))
                    detail_text.insert('end',f'• Zuordnung Positionsplan {_scope} entfernen … (Doppelklick)\n',_remove_tag)
                    detail_text.tag_config(_remove_tag,underline=True)
                    detail_text.tag_bind(_remove_tag,'<Double-1>',lambda _e,_f=folder,_p=r.get('pos'):_position_remove_manual_plan(_f,_p))
                detail_text.insert('end','\n')
                if matches:
                    category_order=('Prüfstatik','Pläne / CAD','Eigene Nachweise','Dokumente')
                    groups={k:[] for k in category_order}
                    for hit in matches:
                        groups.setdefault(hit[2],[]).append(hit)
                    shown=0
                    for cat in category_order:
                        hits=groups.get(cat) or []
                        if not hits: continue
                        detail_text.insert('end',f'\n{cat.upper()}\n')
                        for _score,_ts,_cat,p,rel in hits[:4]:
                            n=_detail_add_link(detail_text,f'• {rel}',p,n); shown+=1
                    remaining=max(0,len(matches)-shown)
                    if remaining:
                        detail_text.insert('end',f'… {remaining} weitere Treffer\n')
                else:
                    detail_text.insert('end','Noch keine Datei anhand der Positionsnummer eindeutig zugeordnet.\n')

                # Technische Zusatzdaten bewusst kompakt darunter halten.
                extras=[]
                _extra_specs=(
                    (('art','type'),'Art'),
                    (('reihenfolge','order','row_order'),'Reihenfolge'),
                    (('ergebnis','results'),'mb-Ergebniskennwert'),
                    (('gesperrt','locked'),'Gesperrt'),
                    (('file_refs',),'Dateireferenzen'),
                )
                for keys,label in _extra_specs:
                    val=None
                    for key in keys:
                        if (detail or {}).get(key) not in (None,''):
                            val=(detail or {}).get(key); break
                        if r.get(key) not in (None,''):
                            val=r.get(key); break
                    if val not in (None,''):
                        extras.append(f'{label}: {val}')
                if extras:
                    detail_text.insert('end','\nMB-INTERN\n'+'\n'.join(extras)+'\n')
                if err:
                    detail_text.insert('end','\nHinweis: Detaildaten konnten nur teilweise gelesen werden.\n')
                detail_text.config(state='disabled')
            except Exception:
                # Bei einem unerwarteten Sonderfall bleibt die bisherige 1.4.6-Anzeige erhalten.
                try:_position_selected_146(_evt)
                except Exception:pass

        # 1.4.33: Bearbeitungsstatus direkt in der Positionsliste.
        # Bestehende mb-/Dateidaten bleiben unverändert; gelesen wird nur die
        # Projektzentrale-Metadatei .engbers_positionsakte.json.
        _position_status_values=('Offen','In Bearbeitung','Geprüft','Änderung erforderlich','Erledigt')
        _position_status_display={'Offen':'Offen','In Bearbeitung':'Bearbeitung','Geprüft':'Geprüft','Änderung erforderlich':'Änderung','Erledigt':'Erledigt'}

        def _position_status_row_folder(row):
            try:
                raw=(row or {}).get('_folder')
                if raw:
                    return Path(raw)
            except Exception:
                pass
            try:
                raw=(row or {}).get('_db')
                if raw:
                    db=Path(raw)
                    candidates=[db.parent]
                    candidates.extend(list(db.parents)[:5])
                    for cand in candidates:
                        try:
                            if cand.is_dir() and any(cand.glob('*.mbp')):
                                return cand
                        except Exception:
                            pass
            except Exception:
                pass
            try:
                raw=current_project.get('folder')
                if raw:
                    return Path(raw)
            except Exception:
                pass
            return None

        def _position_status_row_key(row):
            try:
                folder=_position_status_row_folder(row)
                fkey=str(folder.resolve()).casefold() if folder else ''
            except Exception:
                fkey=str(_position_status_row_folder(row) or '').casefold()
            return (fkey,str((row or {}).get('pos') or '').strip().upper())

        def _position_status_for_row(row):
            try:
                folder=_position_status_row_folder(row)
                pos=str((row or {}).get('pos') or '').strip()
                if not folder or not pos:
                    return 'Offen'
                status=str(_position_record_get(folder,pos).get('status') or 'Offen')
                return status if status in _position_status_values else 'Offen'
            except Exception:
                return 'Offen'

        def _position_layout_1449():
            # PZ_POSITION_LAYOUT_V1449: kompakt in Gesamt- und Einzelakte, ohne horizontales Scrollen.
            try:
                cols=list(ptr.cget('columns'))
                required=('Pos.','pz_bearbeitung','Bezeichnung','mb-Modul','mb-Kennwert')
                if not all(c in cols for c in required):return
                single=bool(current_project.get('folder'))
                display=required if single else ('mb-Projekt',)+required
                ptr.configure(displaycolumns=tuple(c for c in display if c in cols))
                ptr.heading('#0',text='Gruppe'); ptr.column('#0',width=78,minwidth=68,stretch=False,anchor='w')
                heads={'mb-Projekt':'mb-Projekt','Pos.':'Position','pz_bearbeitung':'Status','Bezeichnung':'Bezeichnung','mb-Modul':'mb-Modul','mb-Kennwert':'Kennwert'}
                widths={'mb-Projekt':(86,74,False),'Pos.':(68,60,False),'pz_bearbeitung':(76,70,False),'Bezeichnung':(170,115,True),'mb-Modul':(66,58,False),'mb-Kennwert':(50,46,False)}
                for col,text in heads.items():
                    if col in cols:ptr.heading(col,text=text)
                for col,(w,m,stretch) in widths.items():
                    if col in cols:ptr.column(col,width=w,minwidth=m,stretch=stretch,anchor='w')
                try:ptr.xview_moveto(0); psx.grid_remove()
                except Exception:pass
            except Exception:pass

        # 1.4.35: Bearbeitungsstatus kompakt direkt hinter der Positionsspalte.
        try:
            _cols=list(ptr.cget('columns'))
            if 'pz_bearbeitung' in _cols:
                _cols.remove('pz_bearbeitung')
            _insert_at=min(3,len(_cols))
            for _i,_col in enumerate(_cols):
                _name=str(_col).casefold()
                if 'pos' in _name and 'projekt' not in _name:
                    _insert_at=_i+1
                    break
            _cols.insert(_insert_at,'pz_bearbeitung')
            ptr.configure(columns=tuple(_cols))
            ptr.heading('pz_bearbeitung',text='Status')
            ptr.column('pz_bearbeitung',width=100,minwidth=88,stretch=False,anchor='w')
            # PZ_POSITION_LAYOUT_V1438: Positionsliste ohne notwendiges horizontales Scrollen.
            try:
                _pz_cols=list(ptr.cget('columns'))
                _pz_order=('gruppe','mb_projekt','pos','pz_bearbeitung','bezeichnung','modul','kennwert')
                _pz_display=[_c for _c in _pz_order if _c in _pz_cols]
                _pz_display.extend([_c for _c in _pz_cols if _c not in _pz_display])
                ptr.configure(displaycolumns=tuple(_pz_display))
                _pz_widths={
                    'gruppe':(132,95,False),
                    'mb_projekt':(112,88,False),
                    'pos':(82,72,False),
                    'pz_bearbeitung':(96,86,False),
                    'bezeichnung':(285,180,True),
                    'modul':(82,70,False),
                    'kennwert':(68,58,False),
                }
                for _col,(_width,_min,_stretch) in _pz_widths.items():
                    if _col in _pz_cols:
                        ptr.column(_col,width=_width,minwidth=_min,stretch=_stretch)
                if 'pz_bearbeitung' in _pz_cols:
                    ptr.heading('pz_bearbeitung',text='Status')
                try:ptr.xview_moveto(0)
                except Exception:pass
            except Exception:
                pass
        except Exception:
            pass

        _position_layout_1449()

        try:
            import tkinter as _tk
            _position_status_filter_var=_tk.StringVar(value='Alle')
        except Exception:
            _position_status_filter_var=None

        def _position_status_current_key():
            try:
                sel=ptr.selection()
                if sel:
                    row=item_rows.get(sel[0])
                    if row:
                        return _position_status_row_key(row)
            except Exception:
                pass
            return None

        def _position_status_reselect(key):
            if not key:
                return
            try:
                for iid,row in list(item_rows.items()):
                    if _position_status_row_key(row)!=key:
                        continue
                    if not ptr.exists(iid):
                        continue
                    try:
                        parent=ptr.parent(iid)
                        if not parent and iid not in ptr.get_children(''):
                            continue
                    except Exception:
                        pass
                    ptr.selection_set(iid)
                    ptr.focus(iid)
                    ptr.see(iid)
                    return
            except Exception:
                pass

        def _position_status_apply_to_tree():
            counts={x:0 for x in _position_status_values}
            wanted='Alle'
            try:
                if _position_status_filter_var is not None:
                    wanted=str(_position_status_filter_var.get() or 'Alle')
            except Exception:
                wanted='Alle'
            shown=0
            try:
                cols=list(ptr.cget('columns'))
                status_index=cols.index('pz_bearbeitung')
            except Exception:
                status_index=None
            for iid,row in list(item_rows.items()):
                try:
                    if not ptr.exists(iid):
                        continue
                except Exception:
                    continue
                status=_position_status_for_row(row)
                counts[status]=counts.get(status,0)+1
                if status_index is not None:
                    try:
                        vals=list(ptr.item(iid,'values'))
                        if len(vals)==len(cols)-1: vals.insert(status_index,'')
                        while len(vals)<len(cols): vals.append('')
                        vals[status_index]=_position_status_display.get(status,status)
                        ptr.item(iid,values=tuple(vals))
                    except Exception:
                        pass
                if wanted!='Alle' and status!=wanted:
                    try: ptr.detach(iid)
                    except Exception: pass
                else:
                    shown+=1

            if wanted!='Alle':
                try:
                    for root_iid in list(ptr.get_children('')):
                        if root_iid in item_rows:
                            continue
                        try:
                            if not ptr.get_children(root_iid):
                                ptr.detach(root_iid)
                        except Exception:
                            pass
                except Exception:
                    pass

            try:
                project_name=current_project.get('name') or 'mb-Projekt'
                summary=(
                    f"Offen {counts.get('Offen',0)} · "
                    f"Bearb. {counts.get('In Bearbeitung',0)} · "
                    f"Geprüft {counts.get('Geprüft',0)} · "
                    f"Änderung {counts.get('Änderung erforderlich',0)} · "
                    f"Erledigt {counts.get('Erledigt',0)}"
                )
                pos_info.config(
                    text=f'{project_name} · {len(current_rows)} DB-Einträge gelesen · '
                         f'{shown} Positionszeilen sichtbar   | Status: {summary}',
                    fg=INK,
                )
            except Exception:
                pass
            return counts

        _rebuild_positions_1432_status = rebuild_positions
        def rebuild_positions(*_args):
            keep=_position_status_current_key()
            _rebuild_positions_1432_status(*_args)
            _position_status_apply_to_tree()
            _position_layout_1449()
            _position_status_reselect(keep)

        def _position_status_filter_changed(_evt=None):
            try:
                rebuild_positions()
            except Exception:
                pass

        def _position_status_ui_refresh(folder,pos):
            """Refresh status column, counters and active status filter after a status change."""
            try:
                target=(str(Path(folder).resolve()).casefold(),str(pos or '').strip().upper())
            except Exception:
                target=(str(folder or '').casefold(),str(pos or '').strip().upper())
            try:
                rebuild_positions()
            except Exception:
                try:_position_status_apply_to_tree()
                except Exception:pass
            _position_status_reselect(target)

        # Statusfilter in die vorhandene Werkzeugzeile neben Filter/Suche einsetzen.
        try:
            if _position_status_filter_var is not None:
                _toolbar=pos_info.master
                _status_wrap=ttk.Frame(_toolbar)
                ttk.Label(_status_wrap,text='Status:').pack(side='left',padx=(0,4))
                _status_combo=ttk.Combobox(
                    _status_wrap,
                    textvariable=_position_status_filter_var,
                    values=('Alle',)+_position_status_values,
                    state='readonly',
                    width=17,
                )
                _status_combo.pack(side='left')
                _status_combo.bind('<<ComboboxSelected>>',_position_status_filter_changed)
                _mgr=str(pos_info.winfo_manager() or '')
                if _mgr=='pack':
                    _status_wrap.pack(side='right',padx=(8,10))
                elif _mgr=='grid':
                    _info=pos_info.grid_info()
                    _row=int(_info.get('row',0))
                    _cols_used=[]
                    for _w in _toolbar.grid_slaves():
                        try:_cols_used.append(int(_w.grid_info().get('column',0)))
                        except Exception:pass
                    _status_wrap.grid(row=_row,column=(max(_cols_used)+1 if _cols_used else 1),padx=(8,10),sticky='e')
                else:
                    _status_wrap.pack(side='right',padx=(8,10))
        except Exception:
            pass

        # Falls beim Start bereits Zeilen geladen sind, die neue Spalte sofort füllen.
        try:
            _position_status_apply_to_tree()
        except Exception:
            pass

        # PZ_POSITION_CONTEXT_V1449: häufige Aktionen direkt per Rechtsklick.
        def _position_context_data():
            sel=ptr.selection()
            if not sel:return None,None,None
            row=item_rows.get(sel[0])
            if not row:return None,None,None
            folder=row.get('_folder') or current_project.get('folder')
            if not folder:return row,None,str(row.get('pos') or '')
            return row,Path(folder),str(row.get('pos') or '')
        def _ctx_mb_open():
            row,folder,pos=_position_context_data()
            if row and folder:_mb_open_project_application(folder,_mb_application_for_position(folder,row),pos)
        def _ctx_status():
            row,folder,pos=_position_context_data()
            if folder and pos:_position_set_status(folder,pos,detail_text)
        def _ctx_note():
            row,folder,pos=_position_context_data()
            if folder and pos:_position_edit_note(folder,pos,detail_text)
        def _ctx_link():
            row,folder,pos=_position_context_data()
            if folder and pos:_position_link_file(folder,pos)
        def _ctx_unlink():
            row,folder,pos=_position_context_data()
            if folder and pos:_position_unlink_file(folder,pos)
        def _ctx_plan():
            row,folder,pos=_position_context_data()
            if folder and pos:_position_assign_plan(folder,pos)
        def _ctx_plan_remove():
            row,folder,pos=_position_context_data()
            if folder and pos:_position_remove_manual_plan(folder,pos)
        _pos_menu=tk.Menu(self,tearoff=0)
        _pos_menu.add_command(label='mb öffnen',command=_ctx_mb_open)
        _pos_menu.add_separator()
        _pos_menu.add_command(label='Status ändern …',command=_ctx_status)
        _pos_menu.add_command(label='Notiz bearbeiten …',command=_ctx_note)
        _pos_menu.add_separator()
        _pos_menu.add_command(label='Datei mit Position verknüpfen …',command=_ctx_link)
        _pos_menu.add_command(label='Dateiverknüpfung entfernen …',command=_ctx_unlink)
        _pos_menu.add_command(label='Positionsplan zuordnen …',command=_ctx_plan)
        _pos_menu.add_command(label='Positionsplan-Zuordnung entfernen …',command=_ctx_plan_remove)
        def _position_popup(e):
            iid=ptr.identify_row(e.y)
            if iid:
                try:ptr.selection_set(iid); ptr.focus(iid); position_selected()
                except Exception:pass
                _pos_menu.tk_popup(e.x_root,e.y_root)
            return 'break'
        ptr.bind('<Button-3>',_position_popup)
        ptr.bind('<<TreeviewSelect>>',position_selected)
        filter_box.bind('<<ComboboxSelected>>',rebuild_positions)
        search_var.trace_add('write',lambda *_: rebuild_positions())
        tk.Label(b_pos,text='Quelle: STATIK/BSPos.mbdb · SQLite mode=ro. Keine mb-Datei wird verändert. 1.4.2 ergänzt verknüpfte Projektordner, manuelle Dateizuordnung, Detailbereich und Änderungsübersicht; mb-Daten bleiben read-only.',bg=PANEL,fg=MUTED,anchor='w').pack(fill='x',pady=(8,0))

        if mb_projects:
            cols=('mb-Projekt','Leitdatei','Geändert','Projektordner','Status')
            tr=ttk.Treeview(b_mb,columns=cols,show='headings',height=max(3,min(len(mb_projects)+1,6)))
            widths=[240,230,135,500,180]
            for i,c in enumerate(cols): tr.heading(c,text=c); tr.column(c,width=widths[i],anchor='w')
            item_paths={}; item_names={}
            all_iid=tr.insert('', 'end', values=('ALLE mb-PROJEKTE','—','—','gesamte verknüpfte Projektakte','Gesamtansicht'))
            item_paths[all_iid]=None; item_names[all_iid]='ALLE mb-PROJEKTE'
            for folder,name,lead_name,changed,rel,status in mb_projects:
                iid=tr.insert('', 'end', values=(name,lead_name,changed,rel,status)); item_paths[iid]=folder; item_names[iid]=name
            sy=ttk.Scrollbar(b_mb,orient='vertical',command=tr.yview); tr.configure(yscrollcommand=sy.set)
            tr.pack(side='left',fill='both',expand=True); sy.pack(side='right',fill='y')
            def select_mb_project(_evt=None):
                sel=tr.selection()
                if not sel:return
                iid=sel[0]; target=item_paths.get(iid)
                # PZ_REMEMBER_MB_PROJECT_V1449
                try:self._pz_last_mb_project=(self.project_id,item_names.get(iid))
                except Exception:pass
                if item_names.get(iid)=='ALLE mb-PROJEKTE': load_all_positions()
                elif target: load_positions(target,item_names.get(iid,target.name))
            def open_mb_project(_evt=None):
                sel=tr.selection()
                if not sel:return
                target=item_paths.get(sel[0])
                if not target:return
                try:
                    if os.name=='nt': os.startfile(str(target))
                    elif sys.platform=='darwin': os.system(f'open "{target}"')
                    else: os.system(f'xdg-open "{target}" >/dev/null 2>&1 &')
                except Exception as e: messagebox.showerror('mb-Projekt öffnen',str(e))
            tr.bind('<<TreeviewSelect>>',select_mb_project); tr.bind('<Double-1>',open_mb_project)
            tk.Label(b_mb,text='Anklicken: Positionsakte laden · Doppelklick: mb-Projektordner öffnen.',bg=PANEL,fg=MUTED,anchor='w').pack(fill='x',pady=(8,0))
            first=tr.get_children()
            if first:
                _chosen=first[0]
                try:
                    _last=getattr(self,'_pz_last_mb_project',None)
                    if _last and _last[0]==self.project_id:
                        for _iid in first:
                            if item_names.get(_iid)==_last[1]:
                                _chosen=_iid; break
                except Exception:pass
                tr.selection_set(_chosen); tr.focus(_chosen); select_mb_project()
        else:
            hint='Kein Ordner „Statik/mb-Software“ gefunden.' if project_root.exists() else 'Projektordner nicht gefunden.'
            tk.Label(b_mb,text=hint+' Die Projektzentrale verändert keine mb-Dateien oder Unterordner.',bg=PANEL,fg=MUTED,anchor='w').pack(fill='x',pady=8)
            pos_info.config(text='Keine mb-Projekte erkannt.')

        con=db(); own=con.execute('SELECT pos,title,system,result,utilization,deformation,checker,status FROM statics WHERE project_id=?',(self.project_id,)).fetchall(); con.close()
        if own:
            pan,b=self.panel(self.content,'Eigene / übernommene Positionen'); pan.pack(fill='x')
            data=[(r['pos'],r['title'],r['system'],r['result'],f"{r['utilization']:.2f}",r['deformation'],r['checker'],r['status']) for r in own]
            owntr=self.tree(b,('Pos.','Bauteil','System','Ergebnis','η','Verformung','Prüfstatik','Status'),data,[65,180,170,240,60,190,150,110]); owntr.configure(height=min(6,len(data)))

    def show_thermal(self):
        self.clear(); self.titleblock(self.content,'Wärmeschutz','Hauptbereich · KfW / EEE · DGNB / QNG · Wärmeschutznachweis')
        nb=ttk.Notebook(self.content); nb.pack(fill='both',expand=True)
        for area in ['KfW / EEE','DGNB / QNG','Wärmeschutznachweis']:
            f=tk.Frame(nb,bg=PANEL); nb.add(f,text=area)
            if area=='DGNB / QNG':
                con=db(); rows=con.execute('SELECT code,criterion,qng,evidence,owner,status,note FROM dgnb WHERE project_id=?',(self.project_id,)).fetchall(); con.close()
                self.tree(f,('Code','Kriterium','QNG','Nachweis','Verantwortlich','Status','Notiz'),[tuple(r) for r in rows],[80,220,120,250,120,150,150])
            else:
                con=db(); rows=con.execute('SELECT item,status,note FROM thermal WHERE project_id=? AND area=?',(self.project_id,area)).fetchall(); con.close()
                self.tree(f,('Thema','Status','Hinweis'),[tuple(r) for r in rows],[260,160,700])

    def show_acoustic(self):
        self.clear(); self.titleblock(self.content,'Schallschutz','Nachweise und Ausführungskontrolle')
        con=db(); rows=con.execute('SELECT component,requirement,result,status FROM acoustic WHERE project_id=?',(self.project_id,)).fetchall(); con.close()
        pan,b=self.panel(self.content,'Bauteile'); pan.pack(fill='both',expand=True); self.tree(b,('Bauteil','Anforderung','Ergebnis','Status'),[tuple(r) for r in rows],[300,260,300,140])

    def show_site(self):
        self.clear(); self.titleblock(self.content,'Bauleitung','Ortstermine · Goodnotes · Mängel · Freigaben')
        con=db(); rows=con.execute('SELECT date,type,title,result,status FROM site WHERE project_id=? ORDER BY date',(self.project_id,)).fetchall(); con.close()
        pan,b=self.panel(self.content,'Baustellenchronik'); pan.pack(fill='both',expand=True); self.tree(b,('Datum','Typ','Thema','Ergebnis','Status'),[tuple(r) for r in rows],[110,120,250,500,120])

    def show_comm(self):
        self.clear(); self.titleblock(self.content,'Kommunikation','Chronologische Projektakte · Original und interne Auswertung getrennt')
        tools=tk.Frame(self.content,bg=BG); tools.pack(fill='x',pady=(0,10))
        for txt,cmd in [('E-Mail (.eml) importieren',self.import_eml),('WhatsApp (.txt) importieren',self.import_whatsapp),('Goodnotes-PDF importieren',self.import_goodnotes)]:
            tk.Button(tools,text=txt,command=cmd,bg=DARK,fg='white',bd=0,padx=14,pady=8).pack(side='left',padx=(0,8))
        con=db(); rows=con.execute('SELECT ts,channel,sender,recipient,subject,attachment FROM comm WHERE project_id=? ORDER BY ts DESC',(self.project_id,)).fetchall(); con.close()
        pan,b=self.panel(self.content,'Kommunikationsakte'); pan.pack(fill='both',expand=True); self.tree(b,('Zeit','Kanal','Von','An','Betreff / Thema','Anlage'),[tuple(r) for r in rows],[140,100,170,190,420,160])

    def show_tasks(self):
        self.clear(); self.titleblock(self.content,'Aufgaben & Wiedervorlage','Offen → in Bearbeitung → wartet auf Rückmeldung → erledigt')
        con=db(); rows=con.execute('SELECT title,area,owner,due,priority,status,source FROM tasks WHERE project_id=? ORDER BY due',(self.project_id,)).fetchall(); con.close()
        pan,b=self.panel(self.content,'Aufgaben'); pan.pack(fill='both',expand=True); self.tree(b,('Aufgabe','Fachbereich','Verantwortlich','Fällig','Priorität','Status','Quelle'),[tuple(r) for r in rows],[360,160,130,110,90,160,140])

    def show_checker(self):
        self.clear(); self.titleblock(self.content,'Prüfstatik','Prüfbericht → Position → Antwort → Status')
        con=db(); rows=con.execute('SELECT ref,position,comment,response,status FROM checker WHERE project_id=?',(self.project_id,)).fetchall(); con.close()
        pan,b=self.panel(self.content,'Prüfpunkte'); pan.pack(fill='both',expand=True); self.tree(b,('Ref.','Position','Prüferanmerkung','Antwort Engbers','Status'),[tuple(r) for r in rows],[90,100,390,470,120])

    def show_documents(self):
        self.clear(); self.titleblock(self.content,'Dokumente','Normale Projektdateien bleiben unabhängig vom Programm zugänglich')
        con=db(); rows=con.execute('SELECT category,filename,version,status,path FROM documents WHERE project_id=?',(self.project_id,)).fetchall(); con.close()
        pan,b=self.panel(self.content,'Projektablage'); pan.pack(fill='both',expand=True); self.tree(b,('Bereich','Datei','Version','Status','Pfad'),[tuple(r) for r in rows],[180,330,100,120,500])

    def show_interfaces(self):
        self.clear(); self.titleblock(self.content,'Schnittstellen','Kommunikation und externe Systeme')
        con=db(); rows=con.execute('SELECT name,status,method,note FROM interfaces').fetchall(); con.close()
        pan,b=self.panel(self.content,'Integrationen'); pan.pack(fill='both',expand=True); self.tree(b,('System','Status','Technik','Ziel'),[tuple(r) for r in rows],[230,130,300,650])
        tk.Label(self.content,text='Live-Anmeldungen werden nicht in der Projektdatei gespeichert. OAuth-Tokens gehören später verschlüsselt in den Windows-Anmeldeinformationsspeicher.',bg=BG,fg=MUTED,font=('Segoe UI',9)).pack(anchor='w',pady=(10,0))

    def show_backup(self):
        self.clear(); self.titleblock(self.content,'Sicherung / Update','Speicherorte sichtbar, Projektdaten getrennt vom Programm')
        pan,b=self.panel(self.content,'Speicherorte'); pan.pack(fill='x')
        for name,path in [('Zentrale Projektablage',PROJECT_ROOT),('Lokale Datenbank',DB_PATH),('Sicherungsziel',BACKUP_DIR),('Programmeinstellungen',SETTINGS_PATH)]:
            row=tk.Frame(b,bg=PANEL); row.pack(fill='x',pady=4); tk.Label(row,text=name,width=24,anchor='w',bg=PANEL,fg=MUTED).pack(side='left'); tk.Label(row,text=str(path),anchor='w',bg=PANEL,fg=INK).pack(side='left',fill='x',expand=True)
        br=tk.Frame(b,bg=PANEL); br.pack(anchor='w',pady=(12,0)); tk.Button(br,text='PROJEKTABLAGE ÄNDERN',command=self.change_project_root,bg='#e7e4dc',fg=INK,bd=0,padx=14,pady=8).pack(side='left'); tk.Button(br,text='BACKUP-ZIEL ÄNDERN',command=self.change_backup_root,bg='#e7e4dc',fg=INK,bd=0,padx=14,pady=8).pack(side='left',padx=8)
        pan2,b2=self.panel(self.content,'Datensicherung'); pan2.pack(fill='x',pady=(16,0))
        tk.Button(b2,text='GESAMTSICHERUNG JETZT ERSTELLEN',command=self.make_backup,bg=DARK,fg='white',bd=0,padx=18,pady=10).pack(side='left')
        tk.Label(b2,text=f'Letzte Sicherung: {self.last_backup()}',bg=PANEL,fg=MUTED).pack(side='left',padx=18)
        pan3,b3=self.panel(self.content,'Update / Upgrade'); pan3.pack(fill='x',pady=(16,0))
        tk.Label(b3,text=f'Installierte Programmversion: {APP_VERSION}\nDatenbankschema: 4\n\nBeim Start wird ein konfigurierter Update-Feed geprüft. Vor Installation eines Updates wird automatisch gesichert. Projektordner und Datenbank liegen außerhalb des Programmordners.',bg=PANEL,fg=INK,justify='left').pack(anchor='w')
        btnrow=tk.Frame(b3,bg=PANEL); btnrow.pack(anchor='w',pady=(14,0)); tk.Button(btnrow,text='NACH UPDATES SUCHEN',command=self.check_updates,bg=DARK,fg='white',bd=0,padx=18,pady=10).pack(side='left',padx=(0,8)); tk.Button(btnrow,text='UPDATE-PAKET MANUELL EINLESEN …',command=self.stage_update,bg='#e7e4dc',fg=INK,bd=0,padx=18,pady=10).pack(side='left')

    def change_project_root(self):
        global PROJECT_ROOT, FILES_DIR
        p=filedialog.askdirectory(title='Neue zentrale Projektablage auswählen',initialdir=str(PROJECT_ROOT))
        if not p: return
        save_settings(project_root=Path(p)); Path(p).mkdir(parents=True,exist_ok=True)
        messagebox.showinfo('Speicherort','Neue Projekte werden künftig dort angelegt. Bereits zugeordnete bestehende Projektordner bleiben unverändert.')
        self.show_backup()

    def change_backup_root(self):
        global BACKUP_DIR
        p=filedialog.askdirectory(title='Neues Sicherungsziel auswählen',initialdir=str(BACKUP_DIR))
        if not p: return
        save_settings(backup_root=Path(p)); Path(p).mkdir(parents=True,exist_ok=True); self.show_backup()

    def global_search(self):
        q=self.search_var.get().strip()
        if not q: return
        con=db(); hits=[]
        for table,fields,label in [
          ('projects',['number','title','address','client','architect'],'Projekt'),
          ('statics',['pos','title','system','result','deformation'],'Statik'),
          ('dgnb',['code','criterion','qng','evidence','owner','status'],'DGNB/QNG'),
          ('comm',['channel','sender','recipient','subject','body','attachment'],'Kommunikation'),
          ('documents',['category','filename','path'],'Dokument'),
          ('project_file_index',['filename','rel_path','category'],'Projektdatei'),
          ('tasks',['title','area','owner','source'],'Aufgabe')]:
            where=' OR '.join([f"lower({f}) LIKE ?" for f in fields]); params=['%'+q.lower()+'%']*len(fields)
            try:
                rows=con.execute(f"SELECT * FROM {table} WHERE {where} LIMIT 20",params).fetchall()
                for r in rows: hits.append((label, ' · '.join(str(r[f]) for f in fields[:2] if r[f])))
            except Exception: pass
        con.close()
        w=tk.Toplevel(self); w.title('Suche'); w.geometry('800x520'); w.configure(bg=BG)
        tk.Label(w,text=f'Suchergebnisse für „{q}“',bg=BG,fg=INK,font=('Segoe UI Semibold',18)).pack(anchor='w',padx=20,pady=20)
        frame=tk.Frame(w,bg=BG); frame.pack(fill='both',expand=True,padx=20,pady=(0,20))
        # PZ_SEARCH_OPEN_V1443
        result_tree=self.tree(frame,('Bereich','Treffer'),hits,[160,560])

        def open_search_hit(event=None):
            try:
                iid=''
                if event is not None:
                    try: iid=result_tree.identify_row(event.y)
                    except Exception: iid=''
                if not iid:
                    sel=result_tree.selection()
                    if sel: iid=sel[0]
                if not iid:
                    return
                result_tree.selection_set(iid)
                vals=result_tree.item(iid,'values')
                if len(vals)<2:
                    return
                area=str(vals[0]).strip()
                target=str(vals[1]).strip()
                if not target:
                    return

                # PZ_SEARCH_PROJECT_FILE_V1445
                if area=='Projektdatei':
                    try:
                        parts=[x.strip() for x in target.split(' · ',1)]
                        filename=parts[0] if parts else target
                        relpath=parts[1] if len(parts)>1 else ''
                        con=db()
                        if relpath:
                            doc=con.execute('SELECT i.project_id,i.rel_path,p.folder_path,p.number,p.title FROM project_file_index i JOIN projects p ON p.id=i.project_id WHERE i.filename=? AND i.rel_path=? ORDER BY CASE WHEN i.project_id=? THEN 0 ELSE 1 END LIMIT 1',(filename,relpath,self.project_id)).fetchone()
                        else:
                            doc=con.execute('SELECT i.project_id,i.rel_path,p.folder_path,p.number,p.title FROM project_file_index i JOIN projects p ON p.id=i.project_id WHERE i.filename=? ORDER BY CASE WHEN i.project_id=? THEN 0 ELSE 1 END LIMIT 1',(filename,self.project_id)).fetchone()
                        con.close()
                        if not doc:
                            messagebox.showwarning('Projektsuche',f'Die Projektdatei konnte nicht aufgelöst werden:\n{target}',parent=w); return 'break'
                        raw_root=str(doc['folder_path'] or '').strip()
                        root=Path(raw_root) if raw_root else PROJECT_ROOT/re.sub(r'[^A-Za-z0-9._-]+','_',f"{doc['number']}_{doc['title']}")
                        path=root/str(doc['rel_path'])
                        if self.open_external_path(path):w.destroy()
                        return 'break'
                    except Exception as exc:
                        messagebox.showwarning('Projektsuche',f'Projektdatei konnte nicht geöffnet werden:\n{exc}',parent=w); return 'break'

                # PZ_SEARCH_DOCUMENT_OPEN_V1444
                if area=='Dokument':
                    try:
                        parts=[x.strip() for x in target.split(' · ',1)]
                        category=parts[0] if len(parts)>1 else ''
                        filename=parts[-1]
                        con=db()
                        if category:
                            doc=con.execute('SELECT d.project_id,d.path,d.filename,p.folder_path,p.number,p.title FROM documents d JOIN projects p ON p.id=d.project_id WHERE d.category=? AND d.filename=? LIMIT 1',(category,filename)).fetchone()
                        else:
                            doc=con.execute('SELECT d.project_id,d.path,d.filename,p.folder_path,p.number,p.title FROM documents d JOIN projects p ON p.id=d.project_id WHERE d.filename=? LIMIT 1',(filename,)).fetchone()
                        con.close()
                        if not doc:
                            messagebox.showwarning('Dokumentsuche',f'Das Dokument konnte nicht aufgelöst werden:\n{target}',parent=w); return 'break'
                        raw_root=str(doc['folder_path'] or '').strip()
                        root=Path(raw_root) if raw_root else PROJECT_ROOT/re.sub(r'[^A-Za-z0-9._-]+','_',f"{doc['number']}_{doc['title']}")
                        path=Path(doc['path'] or doc['filename'])
                        if not path.is_absolute(): path=root/path
                        if self.open_external_path(path): w.destroy()
                        return 'break'
                    except Exception as exc:
                        messagebox.showwarning('Dokumentsuche',f'Dokument konnte nicht geöffnet werden:\n{exc}',parent=w); return 'break'

                if area!='Projekt':
                    return

                self.refresh_project_combo()
                pid=self.project_map.get(target)
                if pid is None:
                    m=re.match(r'\s*(\d{2}-\d{2,4})\b',target)
                    if m:
                        number=m.group(1)
                        for label,candidate_pid in self.project_map.items():
                            if str(label).startswith(number):
                                target=label
                                pid=candidate_pid
                                break
                if pid is None:
                    messagebox.showwarning('Projektsuche',
                        f'Das Projekt konnte nicht geöffnet werden:\n{target}',parent=w)
                    return 'break'

                active=None
                for label,button in self.nav_buttons.items():
                    try:
                        if str(button.cget('bg')).lower()==str(DARK2).lower():
                            active=label
                            break
                    except Exception:
                        pass
                # PZ_SEARCH_KEEP_VIEW_V1449
                try:active_view=str(self.header.cget('text') or '')
                except Exception:active_view=''

                self.project_id=pid
                self.project_var.set(target)
                w.destroy()

                def finish_switch():
                    if active_view=='Statik PDF' and hasattr(self,'show_statik_pdf'):
                        self.show_statik_pdf(); return
                    if active and active in self.nav_buttons:
                        try:
                            self.nav_buttons[active].invoke()
                            return
                        except Exception:
                            pass
                    self.header.configure(text='Projektzentrale')
                    self.show_dashboard()

                self.after_idle(finish_switch)
                return 'break'
            except Exception as exc:
                try:
                    messagebox.showerror('Projektsuche',
                        f'Projekt konnte nicht geöffnet werden:\n{exc}',parent=w)
                except Exception:
                    pass
                return 'break'

        result_tree.bind('<Double-1>',open_search_hit)
        result_tree.bind('<Return>',open_search_hit)

    def make_backup(self):
        BACKUP_DIR.mkdir(parents=True,exist_ok=True)
        stamp=datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')
        out=BACKUP_DIR/f'Engbers_Backup_{stamp}.zip'
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
            if DB_PATH.exists(): z.write(DB_PATH,arcname='Datenbank/engbers_projekte.sqlite')
            if PROJECT_ROOT.exists():
                for p in PROJECT_ROOT.rglob('*'):
                    if p.is_file() and not str(p).startswith(str(BACKUP_DIR)):
                        try: z.write(p,arcname='Projekte/'+str(p.relative_to(PROJECT_ROOT)))
                        except Exception: pass
            if SETTINGS_PATH.exists(): z.write(SETTINGS_PATH,arcname='Einstellungen/settings.json')
            manifest={'app_version':APP_VERSION,'created':now_iso(),'schema_version':3,'project_root':str(PROJECT_ROOT)}
            z.writestr('backup_manifest.json',json.dumps(manifest,indent=2,ensure_ascii=False))
        messagebox.showinfo('Sicherung',f'Sicherung erstellt:\n{out}')

    def last_backup(self):
        if not BACKUP_DIR.exists(): return 'noch keine'
        files=sorted(BACKUP_DIR.glob('Engbers_Backup_*.zip'),reverse=True)
        return files[0].name.replace('Engbers_Backup_','').replace('.zip','') if files else 'noch keine'

    def _urlopen_retry(self, url, timeout=10, attempts=3):
        # PZ_UPDATE_CACHEBUSTER_V1500
        """Update-URLs mit Retry und eindeutigem Cache-Buster öffnen."""
        import time
        last=None
        base=str(url)
        sep='&' if '?' in base else '?'
        busted=base+sep+'_pzcb='+str(int(time.time()*1000))
        headers={'User-Agent':'Engbers-Projektzentrale/'+APP_VERSION,'Cache-Control':'no-cache, no-store, max-age=0','Pragma':'no-cache'}
        req=urllib.request.Request(busted,headers=headers)
        for i in range(max(1,int(attempts))):
            try:return urllib.request.urlopen(req,timeout=timeout)
            except Exception as e:
                last=e
                if i+1<max(1,int(attempts)):time.sleep(0.8*(i+1))
        raise last


    def check_updates(self, silent=False):
        feed=''
        try:
            cfg=json.loads(SETTINGS_PATH.read_text(encoding='utf-8')) if SETTINGS_PATH.exists() else {}
            feed=cfg.get('update_feed','').strip()
        except Exception: pass
        if not feed:
            try:
                cfg2=json.loads((BASE/'update_config.json').read_text(encoding='utf-8'))
                feed=cfg2.get('feed_url','').strip()
            except Exception: pass
        if not feed:
            if not silent: messagebox.showinfo('Updates','Die Projektzentrale ist updatefähig. Für automatische Online-Hinweise muss ein Update-Feed hinterlegt sein.')
            return
        try:
            with self._urlopen_retry(feed,timeout=8,attempts=3) as r: info=json.loads(r.read().decode('utf-8'))
            latest=info.get('version','')
            def version_tuple(v):
                nums=re.findall(r'\d+',str(v))[:4]
                return tuple(int(x) for x in nums)+(0,)*(4-len(nums))
            is_newer=bool(latest) and version_tuple(latest)>version_tuple(APP_VERSION) and info.get('update_available',True) is not False
            if is_newer:
                if messagebox.askyesno('Update verfügbar',f"Neue Version {latest} ist verfügbar.\n\n{info.get('notes','')}\n\nUpdate herunterladen und vorbereiten?"):
                    url=info.get('package_url') or info.get('download_url','')
                    if not url: raise ValueError('Für dieses Update ist noch kein Paket freigegeben.')
                    target=LOCALDATA/'updates'/f'update_{latest}.zip'; target.parent.mkdir(parents=True,exist_ok=True)
                    fmt=(info.get('package_format') or 'zip').lower().strip()
                    if fmt in ('base64-json','json-base64'):
                        import base64, hashlib
                        with self._urlopen_retry(url,timeout=20,attempts=3) as r: payload=json.loads(r.read().decode('utf-8'))
                        raw=base64.b64decode(payload.get('payload_b64',''),validate=True)
                        inner_expected=(payload.get('sha256') or '').lower().strip()
                        if inner_expected and hashlib.sha256(raw).hexdigest()!=inner_expected:
                            raise ValueError('Prüfsumme des dekodierten Update-Pakets stimmt nicht.')
                        target.write_bytes(raw)
                    else:
                        target.write_bytes(self._urlopen_retry(url,timeout=30,attempts=3).read())
                    expected=(info.get('sha256') or '').lower().strip()
                    if expected:
                        import hashlib
                        actual=hashlib.sha256(target.read_bytes()).hexdigest()
                        if actual != expected: raise ValueError('Prüfsumme des Update-Pakets stimmt nicht. Installation abgebrochen.')
                    self.apply_update_package(target)
            elif not silent: messagebox.showinfo('Updates',f'Du verwendest die aktuelle Version {APP_VERSION}.')
        except Exception as e:
            if not silent: messagebox.showwarning('Updates',f'Update-Prüfung derzeit nicht möglich:\n{e}')

    def _program_update_backup(self):
        stamp=datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')
        out=LOCALDATA/'updates'/'rollback'/stamp
        out.mkdir(parents=True,exist_ok=True)
        protected={'data','project_files','backups','updates','__pycache__'}
        for src in BASE.rglob('*'):
            if not src.is_file(): continue
            rel=src.relative_to(BASE)
            if rel.parts and rel.parts[0] in protected: continue
            dst=out/rel; dst.parent.mkdir(parents=True,exist_ok=True)
            try: shutil.copy2(src,dst)
            except Exception: pass
        if SETTINGS_PATH.exists():
            try:
                sd=out/'_settings'; sd.mkdir(parents=True,exist_ok=True); shutil.copy2(SETTINGS_PATH,sd/'settings.json')
            except Exception: pass
        if DB_PATH.exists():
            try:
                dd=out/'_database'; dd.mkdir(parents=True,exist_ok=True); shutil.copy2(DB_PATH,dd/'engbers_projekte.sqlite')
            except Exception: pass
        return out

    def apply_update_package(self,p):
        upd=LOCALDATA/'updates'/'staged'
        if upd.exists(): shutil.rmtree(upd)
        upd.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(p) as z: z.extractall(upd)
        candidate=upd/'app.py'
        if candidate.exists():
            import py_compile
            py_compile.compile(str(candidate),doraise=True)
        rollback=self._program_update_backup()
        marker=LOCALDATA/'updates'/'pending_update.json'; marker.parent.mkdir(parents=True,exist_ok=True)
        marker.write_text(json.dumps({'staged':str(upd),'app_dir':str(BASE),'version':APP_VERSION,'rollback':str(rollback)},indent=2),encoding='utf-8')
        if messagebox.askyesno('Update vorbereitet','Update ist geprüft und vorbereitet. Die Programmsicherung wurde erstellt.\n\nProjektzentrale jetzt schließen, Update installieren und neu starten?'):
            import subprocess
            subprocess.Popen([sys.executable,str(BASE/'updater.py'),str(marker)],cwd=str(BASE))
            self.destroy()

    def stage_update(self):
        p=filedialog.askopenfilename(title='Update-Paket auswählen',filetypes=[('Engbers Update','*.zip')])
        if not p: return
        try: self.apply_update_package(Path(p))
        except Exception as e: messagebox.showerror('Update',str(e))

    def import_eml(self):
        p=filedialog.askopenfilename(filetypes=[('E-Mail','*.eml'),('Alle Dateien','*.*')]);
        if not p: return
        try:
            from email import policy
            from email.parser import BytesParser
            msg=BytesParser(policy=policy.default).parse(open(p,'rb'))
            body=''
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type()=='text/plain': body=part.get_content(); break
            else: body=msg.get_content()
            con=db(); con.execute('INSERT INTO comm(project_id,ts,channel,sender,recipient,subject,body,attachment,original_path) VALUES(?,?,?,?,?,?,?,?,?)',(self.project_id,now_iso(),'E-Mail',str(msg.get('From','')),str(msg.get('To','')),str(msg.get('Subject','')),body[:10000],'',p)); con.commit(); con.close(); self.show_comm()
        except Exception as e: messagebox.showerror('E-Mail Import',str(e))

    def import_whatsapp(self):
        p=filedialog.askopenfilename(filetypes=[('WhatsApp Export','*.txt'),('Alle Dateien','*.*')]);
        if not p: return
        try:
            text=Path(p).read_text(encoding='utf-8',errors='ignore')
            con=db(); con.execute('INSERT INTO comm(project_id,ts,channel,sender,recipient,subject,body,attachment,original_path) VALUES(?,?,?,?,?,?,?,?,?)',(self.project_id,now_iso(),'WhatsApp','WhatsApp Export','Projektakte','Importierter WhatsApp-Chat',text[:20000],Path(p).name,p)); con.commit(); con.close(); self.show_comm()
        except Exception as e: messagebox.showerror('WhatsApp Import',str(e))

    def import_goodnotes(self):
        p=filedialog.askopenfilename(filetypes=[('Goodnotes PDF','*.pdf'),('Alle Dateien','*.*')]);
        if not p: return
        dest=Path(self.get_project_folder())/'Goodnotes'; dest.mkdir(parents=True,exist_ok=True); target=dest/Path(p).name
        shutil.copy2(p,target)
        con=db(); con.execute('INSERT INTO comm(project_id,ts,channel,sender,recipient,subject,body,attachment,original_path) VALUES(?,?,?,?,?,?,?,?,?)',(self.project_id,now_iso(),'Goodnotes','iPad / Goodnotes','Projektakte','Baustellendokument importiert','Original-PDF unverändert in Projektablage übernommen.',Path(p).name,str(target))); con.commit(); con.close(); self.show_comm()


if __name__=='__main__':
    if not first_run_setup():
        sys.exit(0)
    load_settings()
    DATA_DIR.mkdir(parents=True,exist_ok=True); PROJECT_ROOT.mkdir(parents=True,exist_ok=True); BACKUP_DIR.mkdir(parents=True,exist_ok=True)
    init_db()
    App().mainloop()
