from pathlib import Path
import ast
import datetime
import py_compile
import re
import shutil
import traceback

BASE=Path(__file__).resolve().parent
APP=BASE/'app.py'
MOD=BASE/'wordforms_v1700.py'
OLD='1.8.2'
NEW='1.8.3'
MARK='PZ_SASV_DIRECT_PDF_STAMP_V1803'

NEW_STAMP = r'''def _stamp_approved_pdf(docx_path, pdf_path, asset_path):
    # PZ_SASV_DIRECT_PDF_STAMP_V1803
    # Das Word-Original wird beim Freigeben nicht mehr geoeffnet oder veraendert.
    # Aus der lokalen PNG wird nur intern eine transparente A4-Overlay-PDF erzeugt;
    # Acrobat legt diese anschliessend direkt auf Seite 1 der bereits geprueften PDF.
    pdf_path=Path(pdf_path).resolve()
    asset_path=Path(asset_path).resolve()
    if not pdf_path.exists():
        return False,'Die zu stempelnde PDF wurde nicht gefunden.'
    if not asset_path.exists():
        return False,'Lokale Stempeldatei wurde nicht gefunden.'

    token=datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
    out=pdf_path.parent/(pdf_path.stem+f'.pz1803_stamped_{token}.pdf')
    clean_png=pdf_path.parent/(pdf_path.stem+f'.pz1803_stamp_{token}.png')
    overlay=pdf_path.parent/(pdf_path.stem+f'.pz1803_overlay_{token}.pdf')
    ps_file=None
    try:
        ps=r"""param(
 [Parameter(Mandatory=$true)][string]$PdfPath,
 [Parameter(Mandatory=$true)][string]$OutPath,
 [Parameter(Mandatory=$true)][string]$AssetPath,
 [Parameter(Mandatory=$true)][string]$CleanPng,
 [Parameter(Mandatory=$true)][string]$OverlayPdf
)
$ErrorActionPreference='Stop'
$csharp=@'
using System;
using System.IO;
using System.Drawing;
using System.Drawing.Imaging;
using System.Reflection;
using System.Runtime.InteropServices;

public static class EngbersDirectPdfStamp1803
{
    static string Clean(Exception ex)
    {
        while (ex != null && ex.InnerException != null) ex = ex.InnerException;
        return ex == null ? "Unbekannter Fehler" : ex.Message;
    }

    static void Release(object o)
    {
        if (o == null) return;
        try { if (Marshal.IsComObject(o)) Marshal.FinalReleaseComObject(o); } catch { }
    }

    static void MakeTransparent(string src, string dst)
    {
        using (Bitmap input = new Bitmap(src))
        using (Bitmap output = new Bitmap(input.Width, input.Height, PixelFormat.Format32bppArgb))
        {
            for (int y=0; y<input.Height; y++)
            {
                for (int x=0; x<input.Width; x++)
                {
                    Color c=input.GetPixel(x,y);
                    int min=Math.Min(c.R,Math.Min(c.G,c.B));
                    int a=c.A;
                    if (min >= 245) a=0;
                    else if (min > 220) a=(int)Math.Round(a * (245-min) / 25.0);
                    output.SetPixel(x,y,Color.FromArgb(Math.Max(0,Math.Min(255,a)),c.R,c.G,c.B));
                }
            }
            output.Save(dst,ImageFormat.Png);
        }
    }

    static void CreateOverlay(string cleanPng, string overlayPdf)
    {
        dynamic word=null, doc=null, shape=null, range=null;
        try
        {
            Type t=Type.GetTypeFromProgID("Word.Application");
            if (t==null) throw new Exception("Microsoft Word COM ist nicht registriert.");
            word=Activator.CreateInstance(t);
            word.Visible=false;
            word.DisplayAlerts=0;
            doc=word.Documents.Add();
            doc.PageSetup.PageWidth=595.3f;
            doc.PageSetup.PageHeight=841.9f;
            doc.PageSetup.LeftMargin=0.0f;
            doc.PageSetup.RightMargin=0.0f;
            doc.PageSetup.TopMargin=0.0f;
            doc.PageSetup.BottomMargin=0.0f;
            range=doc.Range(0,0);
            shape=doc.Shapes.AddPicture(
                FileName: cleanPng,
                LinkToFile: false,
                SaveWithDocument: true,
                Anchor: range);
            shape.RelativeHorizontalPosition=1; // Seite
            shape.RelativeVerticalPosition=1;   // Seite
            shape.Left=220.0f;
            shape.Top=575.0f;
            shape.LockAspectRatio=-1;
            shape.Width=210.0f;
            shape.WrapFormat.Type=3;
            doc.ExportAsFixedFormat(OutputFileName: overlayPdf, ExportFormat: 17);
            doc.Close(false);
            Release(shape); shape=null;
            Release(range); range=null;
            Release(doc); doc=null;
            word.Quit(false);
            Release(word); word=null;
        }
        finally
        {
            if (doc!=null) { try { doc.Close(false); } catch { } }
            if (word!=null) { try { word.Quit(false); } catch { } }
            Release(shape); Release(range); Release(doc); Release(word);
        }
        if (!File.Exists(overlayPdf) || new FileInfo(overlayPdf).Length < 100)
            throw new Exception("Die interne Stempel-Overlay-PDF wurde nicht erzeugt.");
    }

    static string DiPath(string path)
    {
        string p=Path.GetFullPath(path).Replace('\\','/');
        if (p.Length>=3 && p[1]==':') return "/"+Char.ToUpperInvariant(p[0])+p.Substring(2);
        return p;
    }

    static string JsEscape(string s)
    {
        return s.Replace("\\","\\\\").Replace("\"","\\\"");
    }

    static void ApplyOverlay(string pdfPath, string overlayPdf, string outPath)
    {
        dynamic acroApp=null, pdDoc=null, jso=null, avDoc=null, aform=null, fields=null;
        try
        {
            Type ta=Type.GetTypeFromProgID("AcroExch.App");
            Type tp=Type.GetTypeFromProgID("AcroExch.PDDoc");
            if (ta==null || tp==null) throw new Exception("Adobe Acrobat COM ist nicht registriert. Acrobat Pro wird benoetigt.");
            acroApp=Activator.CreateInstance(ta);
            pdDoc=Activator.CreateInstance(tp);
            bool opened=(bool)pdDoc.Open(pdfPath);
            if (!opened) throw new Exception("Adobe Acrobat konnte die PDF nicht oeffnen. Bitte PDF in Acrobat schliessen und erneut versuchen.");
            jso=pdDoc.GetJSObject();
            if (jso==null) throw new Exception("Adobe Acrobat lieferte kein JavaScript-Dokumentobjekt.");

            bool applied=false;
            string firstError="";
            try
            {
                object[] args=new object[] {
                    overlayPdf, 0, 0, 0,
                    true, true, true,
                    1, 1, 0.0, 0.0,
                    false, 1.0, false, 0, 1.0
                };
                jso.GetType().InvokeMember(
                    "addWatermarkFromFile",
                    BindingFlags.InvokeMethod,
                    null,
                    jso,
                    args);
                applied=true;
            }
            catch(Exception exDirect)
            {
                firstError=Clean(exDirect);
            }

            if (!applied)
            {
                try
                {
                    avDoc=pdDoc.OpenAVDoc("");
                    Type tf=Type.GetTypeFromProgID("AFormAut.App");
                    if (tf==null) throw new Exception("AFormAut.App ist nicht registriert.");
                    aform=Activator.CreateInstance(tf);
                    fields=aform.Fields;
                    string dip=JsEscape(DiPath(overlayPdf));
                    string js="this.addWatermarkFromFile({cDIPath:\""+dip+"\",nSourcePage:0,nStart:0,nEnd:0,bOnTop:true,bOnScreen:true,bOnPrint:true,nHorizAlign:1,nVertAlign:1,nHorizValue:0,nVertValue:0,bPercentage:false,nScale:1.0,bFixedPrint:false,nRotation:0,nOpacity:1.0});";
                    fields.ExecuteThisJavascript(js);
                    applied=true;
                }
                catch(Exception exFallback)
                {
                    throw new Exception("Acrobat-Wasserzeichen direkt: "+firstError+" | Fallback: "+Clean(exFallback));
                }
            }

            if (File.Exists(outPath)) File.Delete(outPath);
            bool saved=(bool)pdDoc.Save(1,outPath);
            if (!saved || !File.Exists(outPath)) throw new Exception("Adobe Acrobat konnte die gestempelte PDF nicht speichern.");
            try { pdDoc.Close(); } catch { }
            try { acroApp.Hide(); } catch { }
            try { acroApp.Exit(); } catch { }
        }
        finally
        {
            Release(fields); Release(aform); Release(avDoc); Release(jso); Release(pdDoc); Release(acroApp);
        }
    }

    public static string Run(string pdfPath, string outPath, string assetPath, string cleanPng, string overlayPdf)
    {
        string stage="start";
        try
        {
            if (!File.Exists(pdfPath)) throw new Exception("PDF wurde nicht gefunden.");
            if (!File.Exists(assetPath)) throw new Exception("Lokale Stempelgrafik wurde nicht gefunden.");
            stage="transparent-png";
            MakeTransparent(assetPath,cleanPng);
            stage="overlay-pdf";
            CreateOverlay(cleanPng,overlayPdf);
            stage="acrobat-stamp";
            ApplyOverlay(pdfPath,overlayPdf,outPath);
            stage="validate";
            if (!File.Exists(outPath) || new FileInfo(outPath).Length < 100)
                throw new Exception("Die gestempelte PDF ist leer oder unvollstaendig.");
            return "OK";
        }
        catch(Exception ex)
        {
            return "ERR|"+stage+"|"+Clean(ex);
        }
        finally
        {
            GC.Collect();
            GC.WaitForPendingFinalizers();
        }
    }
}
'@
Add-Type -TypeDefinition $csharp -Language CSharp -ReferencedAssemblies 'System.dll','System.Core.dll','System.Drawing.dll','Microsoft.CSharp.dll'
$result=[EngbersDirectPdfStamp1803]::Run($PdfPath,$OutPath,$AssetPath,$CleanPng,$OverlayPdf)
if($result -eq 'OK') { Write-Output 'OK'; exit 0 }
Write-Error $result
exit 1
"""
        fd,ps_file=tempfile.mkstemp(prefix='engbers_sasv_stamp_1803_',suffix='.ps1')
        os.close(fd)
        Path(ps_file).write_text(ps,encoding='utf-8-sig')
        cp=subprocess.run(
            ['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',ps_file,
             '-PdfPath',str(pdf_path),'-OutPath',str(out),'-AssetPath',str(asset_path),
             '-CleanPng',str(clean_png),'-OverlayPdf',str(overlay)],
            capture_output=True,text=True,timeout=90,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)
        )
        if cp.returncode!=0:
            detail=(cp.stderr or cp.stdout or '').strip()
            return False,(detail or f'PDF-Stempel Rückgabecode {cp.returncode}')
        if not out.exists() or out.stat().st_size<100:
            return False,'Es wurde keine gültige gestempelte PDF erzeugt.'
        try:
            os.replace(out,pdf_path)
        except PermissionError:
            return False,'Die PDF ist noch in Acrobat/Reader geöffnet. Bitte PDF schließen und erneut freigeben.'
        out=None
        return True,''
    except subprocess.TimeoutExpired:
        return False,'Der direkte PDF-Stempellauf wurde nicht innerhalb von 90 Sekunden beendet.'
    except Exception as e:
        return False,str(e)
    finally:
        for p in (out,clean_png,overlay,ps_file):
            if not p:
                continue
            try: Path(p).unlink()
            except Exception: pass
'''


def _version(text):
    m=re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']',text)
    return m.group(1).strip() if m else ''


def _replace_function(source,name,new_block):
    tree=ast.parse(source)
    lines=source.splitlines(keepends=True)
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name==name:
            start=sum(len(x) for x in lines[:node.lineno-1])
            end=sum(len(x) for x in lines[:node.end_lineno])
            return source[:start]+new_block.rstrip()+'\n\n'+source[end:]
    raise RuntimeError(f'1.8.3: Funktion {name} wurde nicht gefunden.')


def main():
    if not APP.exists() or not MOD.exists():
        raise RuntimeError('1.8.3: app.py oder wordforms_v1700.py wurde nicht gefunden.')
    app=APP.read_text(encoding='utf-8')
    mod=MOD.read_text(encoding='utf-8')
    cur=_version(app)
    if cur==NEW and MARK in mod:
        return 0
    if cur!=OLD:
        raise RuntimeError(f'Update 1.8.3 erwartet Projektzentrale {OLD}; gefunden: {cur or "unbekannt"}.')

    mod=_replace_function(mod,'_stamp_approved_pdf',NEW_STAMP)
    if MARK not in mod:
        raise RuntimeError('1.8.3: Direkt-PDF-Stempel-Marker fehlt.')

    app_new=re.sub(r'(APP_VERSION\s*=\s*)["\'][^"\']+["\']',lambda m:m.group(1)+'"'+NEW+'"',app,count=1)
    app_new=app_new.replace('Projektzentrale 1.8.2','Projektzentrale 1.8.3')

    chk1=APP.with_name('app.py.1803.check')
    chk2=MOD.with_name('wordforms_v1700.py.1803.check')
    try:
        chk1.write_text(app_new,encoding='utf-8'); py_compile.compile(str(chk1),doraise=True)
        chk2.write_text(mod,encoding='utf-8'); py_compile.compile(str(chk2),doraise=True)
    finally:
        for p in (chk1,chk2):
            try:p.unlink()
            except Exception:pass

    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for p in (APP,MOD):
        shutil.copy2(p,p.with_name(p.name+'.vor_1_8_3_'+stamp+'.bak'))
    t=APP.with_name('app.py.1803.tmp'); t.write_text(app_new,encoding='utf-8'); t.replace(APP)
    t=MOD.with_name('wordforms_v1700.py.1803.tmp'); t.write_text(mod,encoding='utf-8'); t.replace(MOD)
    APP.with_name('patch_1803_report.txt').write_text(
        'OK: Projektzentrale 1.8.3 installiert.\n'
        'Freigeben & Stempeln arbeitet jetzt direkt auf der PDF.\n'
        'Das Word-Original wird beim Stempeln nicht mehr geoeffnet oder veraendert.\n',encoding='utf-8')
    return 0

if __name__=='__main__':
    try: raise SystemExit(main())
    except SystemExit: raise
    except Exception:
        try: APP.with_name('patch_1803_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception: pass
        raise
