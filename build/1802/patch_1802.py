from pathlib import Path
import datetime
import py_compile
import re
import shutil
import traceback

BASE=Path(__file__).resolve().parent
APP=BASE/'app.py'
MOD=BASE/'wordforms_v1700.py'
OLD='1.8.1'
NEW='1.8.2'
MARK='PZ_SASV_RELEASE_STAMP_V1802'

IMPORT_OLD='from tkinter import ttk, messagebox\n'
IMPORT_NEW='from tkinter import ttk, messagebox, filedialog\n'

HELPER_ANCHOR='def open_wordforms(app):\n'
HELPERS=r'''def _sasv_stamp_asset_path():
    # PZ_SASV_RELEASE_STAMP_V1802
    base=Path(os.environ.get('LOCALAPPDATA') or (Path.home()/'AppData'/'Local'))/'Engbers Projektzentrale'/'assets'
    return base/'sasv_stempel_unterschrift.png'


def _stamp_approved_pdf(docx_path, pdf_path, asset_path):
    # Das Word-Original bleibt unveraendert. Es wird nur eine temporaere Word-Kopie
    # geoeffnet, dort die lokale Stempelgrafik als Shape eingesetzt und daraus eine
    # neue PDF exportiert. Erst nach Erfolg wird die vorhandene PDF ersetzt.
    docx_path=Path(docx_path).resolve()
    pdf_path=Path(pdf_path).resolve()
    asset_path=Path(asset_path).resolve()
    if not docx_path.exists():
        return False,'Word-Datei wurde nicht gefunden.'
    if not asset_path.exists():
        return False,'Lokale Stempeldatei wurde nicht gefunden.'
    pdf_path.parent.mkdir(parents=True,exist_ok=True)

    token=datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
    work=pdf_path.parent/(docx_path.stem+f'.pz1802_stamp_{token}.docx')
    out=pdf_path.parent/(pdf_path.stem+f'.pz1802_stamp_{token}.pdf')
    ps_file=None
    try:
        shutil.copy2(docx_path,work)
        ps=r"""param(
 [Parameter(Mandatory=$true)][string]$DocxPath,
 [Parameter(Mandatory=$true)][string]$PdfPath,
 [Parameter(Mandatory=$true)][string]$AssetPath
)
$ErrorActionPreference='Stop'
$csharp=@'
using System;
using System.IO;
using System.Runtime.InteropServices;

public static class EngbersSasvStamp1802
{
    static string Clean(Exception ex)
    {
        while (ex != null && ex.InnerException != null) ex = ex.InnerException;
        return ex == null ? "Unbekannter Fehler" : ex.Message;
    }

    public static string Run(string docxPath, string pdfPath, string assetPath)
    {
        dynamic word=null;
        dynamic doc=null;
        dynamic range=null;
        dynamic shape=null;
        string stage="start";
        try
        {
            if (!File.Exists(assetPath)) throw new Exception("Lokale Stempelgrafik fehlt.");
            stage="word-start";
            Type t=Type.GetTypeFromProgID("Word.Application");
            if (t==null) throw new Exception("Microsoft Word COM ist nicht registriert.");
            word=Activator.CreateInstance(t);
            word.Visible=false;
            word.DisplayAlerts=0;

            stage="open";
            doc=word.Documents.Open(
                FileName: docxPath,
                ConfirmConversions: false,
                ReadOnly: false,
                AddToRecentFiles: false,
                Visible: false,
                OpenAndRepair: true,
                NoEncodingDialog: true);

            stage="find-signature-area";
            range=doc.Content.Duplicate;
            dynamic find=range.Find;
            find.ClearFormatting();
            find.Text="III. Unterschrift";
            bool found=find.Execute();
            try { Marshal.FinalReleaseComObject(find); } catch { }
            if (!found) throw new Exception("Bereich 'III. Unterschrift' wurde im Word-Formular nicht gefunden.");

            stage="insert-stamp";
            shape=doc.Shapes.AddPicture(
                FileName: assetPath,
                LinkToFile: false,
                SaveWithDocument: true,
                Anchor: range);
            // Werte gemaess Word-Enums: horizontal Page=1, vertical Paragraph=2,
            // WrapFront/None=3. Position/Abmessungen in Punkt.
            shape.RelativeHorizontalPosition=1;
            shape.RelativeVerticalPosition=2;
            shape.Left=260.0f;
            shape.Top=8.0f;
            shape.LockAspectRatio=-1;
            shape.Width=190.0f;
            shape.WrapFormat.Type=3;
            try { shape.LayoutInCell=0; } catch { }

            stage="export-pdf";
            doc.ExportAsFixedFormat(OutputFileName: pdfPath, ExportFormat: 17);

            stage="close";
            doc.Close(false);
            try { Marshal.FinalReleaseComObject(shape); } catch { }
            shape=null;
            try { Marshal.FinalReleaseComObject(range); } catch { }
            range=null;
            try { Marshal.FinalReleaseComObject(doc); } catch { }
            doc=null;
            word.Quit(false);
            try { Marshal.FinalReleaseComObject(word); } catch { }
            word=null;

            if (!File.Exists(pdfPath)) throw new Exception("Word hat keine gestempelte PDF erzeugt.");
            if (new FileInfo(pdfPath).Length < 100) throw new Exception("Die gestempelte PDF ist leer oder unvollstaendig.");
            return "OK";
        }
        catch(Exception ex)
        {
            return "ERR|"+stage+"|"+Clean(ex);
        }
        finally
        {
            if (shape!=null) { try { Marshal.FinalReleaseComObject(shape); } catch { } }
            if (range!=null) { try { Marshal.FinalReleaseComObject(range); } catch { } }
            if (doc!=null) { try { doc.Close(false); } catch { } try { Marshal.FinalReleaseComObject(doc); } catch { } }
            if (word!=null) { try { word.Quit(false); } catch { } try { Marshal.FinalReleaseComObject(word); } catch { } }
            GC.Collect();
            GC.WaitForPendingFinalizers();
        }
    }
}
'@
Add-Type -TypeDefinition $csharp -Language CSharp -ReferencedAssemblies 'System.dll','System.Core.dll','Microsoft.CSharp.dll'
$result=[EngbersSasvStamp1802]::Run($DocxPath,$PdfPath,$AssetPath)
if($result -eq 'OK'){ Write-Output 'OK'; exit 0 }
Write-Error $result
exit 1
"""
        fd,ps_file=tempfile.mkstemp(prefix='engbers_sasv_stamp_1802_',suffix='.ps1')
        os.close(fd)
        Path(ps_file).write_text(ps,encoding='utf-8-sig')
        cp=subprocess.run(
            ['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',ps_file,
             '-DocxPath',str(work),'-PdfPath',str(out),'-AssetPath',str(asset_path)],
            capture_output=True,text=True,timeout=90,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)
        )
        if cp.returncode!=0:
            return False,(cp.stderr or cp.stdout or f'Stempel-Export Rueckgabecode {cp.returncode}').strip()
        if not out.exists() or out.stat().st_size<100:
            return False,'Word hat keine gueltige gestempelte PDF erzeugt.'
        try:
            os.replace(out,pdf_path)
        except PermissionError:
            return False,'Die PDF ist noch in Acrobat/Reader geoeffnet. Bitte PDF schliessen und erneut freigeben.'
        out=None
        return True,''
    except subprocess.TimeoutExpired:
        return False,'Word hat den Stempel/PDF-Lauf nicht innerhalb von 90 Sekunden beendet.'
    except Exception as e:
        return False,str(e)
    finally:
        for p in (work,out,ps_file):
            if not p:
                continue
            try: Path(p).unlink()
            except Exception: pass


def open_wordforms(app):
'''

OPEN_PDF_ANCHOR="""        messagebox.showinfo('Word-Bescheinigungen','Für die aktuelle Auswahl wurde noch keine PDF-Datei erzeugt.',parent=w)\n\n    tree.bind('<Double-1>',open_original)\n"""
OPEN_PDF_NEW=r'''        messagebox.showinfo('Word-Bescheinigungen','Für die aktuelle Auswahl wurde noch keine PDF-Datei erzeugt.',parent=w)

    def configure_stamp():
        src=filedialog.askopenfilename(
            parent=w,
            title='saSV-Stempel + Unterschrift auswählen',
            filetypes=[('PNG-Grafik','*.png')]
        )
        if not src:
            return
        src=Path(src)
        if src.suffix.casefold()!='.png':
            messagebox.showerror('Stempel einrichten','Bitte die vorbereitete PNG-Datei auswählen.',parent=w)
            return
        dst=_sasv_stamp_asset_path()
        try:
            dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(src,dst)
        except Exception as e:
            messagebox.showerror('Stempel einrichten',f'Stempel konnte lokal nicht gespeichert werden.\n\n{e}',parent=w)
            return
        messagebox.showinfo(
            'Stempel einrichten',
            'saSV-Stempel + Unterschrift wurden lokal eingerichtet.\n\n'
            'Speicherort:\n'+str(dst)+'\n\n'
            'Die Grafik liegt nur lokal auf diesem Rechner.',
            parent=w
        )

    def release_and_stamp():
        sel=tree.selection()
        if not sel:
            messagebox.showinfo('Freigeben & Stempeln','Bitte zuerst genau eine Bescheinigung auswählen.',parent=w)
            return
        item=docs.get(sel[0])
        if not item:
            return
        docx=Path(item['src'])
        pdf=docx.with_suffix('.pdf')
        if not pdf.exists():
            messagebox.showinfo(
                'Freigeben & Stempeln',
                'Zu dieser Bescheinigung gibt es noch keine PDF.\n\n'
                'Bitte zuerst MARKIERTE AUSFÜLLEN und die PDF prüfen.',
                parent=w
            )
            return
        asset=_sasv_stamp_asset_path()
        if not asset.exists():
            messagebox.showinfo(
                'Freigeben & Stempeln',
                'Der lokale saSV-Stempel ist noch nicht eingerichtet.\n\n'
                'Bitte zuerst STEMPEL EINRICHTEN anklicken und die vorbereitete PNG auswählen.',
                parent=w
            )
            return
        if not messagebox.askyesno(
            'Freigeben & Stempeln',
            'Ist die PDF geprüft und soll sie jetzt mit deinem echten saSV-Rundstempel '
            'und deiner Unterschrift final freigegeben werden?\n\n'
            'Die Word-Datei bleibt dabei ohne eingebrannten Stempel.',
            parent=w
        ):
            return
        ok,err=_stamp_approved_pdf(docx,pdf,asset)
        if not ok:
            messagebox.showerror('Freigeben & Stempeln','Stempeln fehlgeschlagen.\n\n'+err,parent=w)
            return
        vals=list(tree.item(sel[0],'values'))
        vals[3]='PDF freigegeben + gestempelt'
        tree.item(sel[0],values=vals)
        status_lbl.configure(text='PDF final freigegeben und mit saSV-Stempel + Unterschrift versehen.')
        messagebox.showinfo(
            'Freigeben & Stempeln',
            'Fertig. Die PDF wurde final mit saSV-Rundstempel und Unterschrift versehen.\n\n'
            'Die Word-Datei blieb unverändert.',
            parent=w
        )
        try:
            app.open_external_path(str(pdf))
        except Exception:
            pass

    tree.bind('<Double-1>',open_original)
'''

PDF_BUTTON="""    tk.Button(foot,text='PDF ÖFFNEN',command=open_pdf,bg='#e7e4dc',fg=INK,bd=0,padx=14,pady=9).pack(side='left',padx=(8,0))\n"""
PDF_BUTTON_NEW=PDF_BUTTON+"    tk.Button(foot,text='STEMPEL EINRICHTEN',command=configure_stamp,bg='#e7e4dc',fg=INK,bd=0,padx=14,pady=9).pack(side='left',padx=(8,0))\n"

CLOSE_BUTTON="""    tk.Button(foot,text='SCHLIESSEN',command=w.destroy,bg='#e7e4dc',fg=INK,bd=0,padx=14,pady=9).pack(side='right')\n"""
CLOSE_BUTTON_NEW=CLOSE_BUTTON+"    tk.Button(foot,text='FREIGEBEN & STEMPELN',command=release_and_stamp,bg=ACCENT,fg='white',bd=0,padx=16,pady=9).pack(side='right',padx=8)\n"


def _version(text):
    m=re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']',text)
    return m.group(1).strip() if m else ''


def _one(s,old,new,label):
    if old not in s:
        raise RuntimeError('1.8.2: '+label+' wurde nicht eindeutig gefunden.')
    return s.replace(old,new,1)


def main():
    if not APP.exists() or not MOD.exists():
        raise RuntimeError('1.8.2: app.py oder wordforms_v1700.py wurde nicht gefunden.')
    app=APP.read_text(encoding='utf-8')
    mod=MOD.read_text(encoding='utf-8')
    cur=_version(app)
    if cur==NEW and MARK in mod:
        return 0
    if cur!=OLD:
        raise RuntimeError(f'Update 1.8.2 erwartet Projektzentrale {OLD}; gefunden: {cur or "unbekannt"}.')

    if IMPORT_OLD in mod:
        mod=mod.replace(IMPORT_OLD,IMPORT_NEW,1)
    elif 'from tkinter import ttk, messagebox, filedialog\n' not in mod:
        raise RuntimeError('1.8.2: tkinter-Import wurde nicht gefunden.')
    mod=_one(mod,HELPER_ANCHOR,HELPERS,'Stempel-Helfer')
    mod=_one(mod,OPEN_PDF_ANCHOR,OPEN_PDF_NEW,'Freigabe-Funktionen')
    mod=_one(mod,PDF_BUTTON,PDF_BUTTON_NEW,'Stempel-einrichten-Button')
    mod=_one(mod,CLOSE_BUTTON,CLOSE_BUTTON_NEW,'Freigeben-Button')

    if MARK not in mod:
        raise RuntimeError('1.8.2: Stempel-Marker fehlt.')

    app_new=re.sub(r'(APP_VERSION\s*=\s*)["\'][^"\']+["\']',lambda m:m.group(1)+'"'+NEW+'"',app,count=1)
    app_new=app_new.replace('Projektzentrale 1.8.1','Projektzentrale 1.8.2')

    chk1=APP.with_name('app.py.1802.check')
    chk2=MOD.with_name('wordforms_v1700.py.1802.check')
    try:
        chk1.write_text(app_new,encoding='utf-8'); py_compile.compile(str(chk1),doraise=True)
        chk2.write_text(mod,encoding='utf-8'); py_compile.compile(str(chk2),doraise=True)
    finally:
        for p in (chk1,chk2):
            try:p.unlink()
            except Exception:pass

    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for p in (APP,MOD):
        shutil.copy2(p,p.with_name(p.name+'.vor_1_8_2_'+stamp+'.bak'))
    t=APP.with_name('app.py.1802.tmp'); t.write_text(app_new,encoding='utf-8'); t.replace(APP)
    t=MOD.with_name('wordforms_v1700.py.1802.tmp'); t.write_text(mod,encoding='utf-8'); t.replace(MOD)
    APP.with_name('patch_1802_report.txt').write_text(
        'OK: Projektzentrale 1.8.2 installiert.\n'
        'saSV-Stempelprofil wird nur lokal unter LOCALAPPDATA gespeichert.\n'
        'Neue Schaltflaechen: STEMPEL EINRICHTEN und FREIGEBEN & STEMPELN.\n'
        'Die Word-Datei bleibt beim finalen Stempeln unveraendert; nur die freigegebene PDF wird neu exportiert.\n',
        encoding='utf-8'
    )
    return 0

if __name__=='__main__':
    try: raise SystemExit(main())
    except SystemExit: raise
    except Exception:
        try: APP.with_name('patch_1802_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception: pass
        raise
