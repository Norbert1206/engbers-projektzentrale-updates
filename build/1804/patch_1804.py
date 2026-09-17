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
OLD='1.8.3'
NEW='1.8.4'
MARK='PZ_SASV_PDF_ONLY_STAMP_V1804'

NEW_STAMP = r'''def _stamp_approved_pdf(docx_path, pdf_path, asset_path):
    # PZ_SASV_PDF_ONLY_STAMP_V1804
    # Beim finalen Freigeben wird Word nicht verwendet. Die lokale PNG wird
    # in C# direkt zu einer transparenten Einseiten-PDF gebaut und anschliessend
    # von Acrobat auf Seite 1 der bereits geprueften PDF gelegt.
    pdf_path=Path(pdf_path).resolve()
    asset_path=Path(asset_path).resolve()
    if not pdf_path.exists():
        return False,'Die zu stempelnde PDF wurde nicht gefunden.'
    if not asset_path.exists():
        return False,'Lokale Stempeldatei wurde nicht gefunden.'

    token=datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
    out=pdf_path.parent/(pdf_path.stem+f'.pz1804_stamped_{token}.pdf')
    overlay=pdf_path.parent/(pdf_path.stem+f'.pz1804_overlay_{token}.pdf')
    ps_file=None
    try:
        ps=r"""param(
 [Parameter(Mandatory=$true)][string]$PdfPath,
 [Parameter(Mandatory=$true)][string]$OutPath,
 [Parameter(Mandatory=$true)][string]$AssetPath,
 [Parameter(Mandatory=$true)][string]$OverlayPdf
)
$ErrorActionPreference='Stop'
$csharp=@'
using System;
using System.IO;
using System.Text;
using System.Drawing;
using System.Drawing.Imaging;
using System.Globalization;
using System.Reflection;
using System.Runtime.InteropServices;

public static class EngbersPdfOnlyStamp1804
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

    static void WriteAscii(FileStream fs,string s)
    {
        byte[] b=Encoding.ASCII.GetBytes(s);
        fs.Write(b,0,b.Length);
    }

    static void BeginObj(FileStream fs,long[] offsets,int n)
    {
        offsets[n]=fs.Position;
        WriteAscii(fs,n.ToString(CultureInfo.InvariantCulture)+" 0 obj\n");
    }

    static void CreateOverlayPdf(string pngPath,string overlayPdf)
    {
        using(Bitmap src=new Bitmap(pngPath))
        using(Bitmap bmp=new Bitmap(src.Width,src.Height,PixelFormat.Format32bppArgb))
        {
            using(Graphics g=Graphics.FromImage(bmp))
            {
                g.Clear(Color.Transparent);
                g.DrawImage(src,0,0,src.Width,src.Height);
            }

            int w=bmp.Width, h=bmp.Height;
            byte[] rgb=new byte[w*h*3];
            byte[] alpha=new byte[w*h];
            int ri=0, ai=0;
            for(int y=0;y<h;y++)
            {
                for(int x=0;x<w;x++)
                {
                    Color c=bmp.GetPixel(x,y);
                    int min=Math.Min(c.R,Math.Min(c.G,c.B));
                    int a=c.A;
                    if(min>=245) a=0;
                    else if(min>220) a=(int)Math.Round(a*(245-min)/25.0);
                    rgb[ri++]=c.R; rgb[ri++]=c.G; rgb[ri++]=c.B;
                    alpha[ai++]=(byte)Math.Max(0,Math.Min(255,a));
                }
            }

            const double pageW=595.28, pageH=841.89, stampW=210.0, left=220.0, top=575.0;
            double stampH=stampW*h/(double)w;
            double bottom=pageH-top-stampH;
            if(bottom<8) bottom=8;
            string content=String.Format(CultureInfo.InvariantCulture,
                "q\n{0:0.###} 0 0 {1:0.###} {2:0.###} {3:0.###} cm\n/Im0 Do\nQ\n",
                stampW,stampH,left,bottom);
            byte[] contentBytes=Encoding.ASCII.GetBytes(content);

            if(File.Exists(overlayPdf)) File.Delete(overlayPdf);
            using(FileStream fs=new FileStream(overlayPdf,FileMode.CreateNew,FileAccess.Write,FileShare.None))
            {
                long[] off=new long[7];
                WriteAscii(fs,"%PDF-1.4\n%Engbers\n");
                BeginObj(fs,off,1); WriteAscii(fs,"<< /Type /Catalog /Pages 2 0 R >>\nendobj\n");
                BeginObj(fs,off,2); WriteAscii(fs,"<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n");
                BeginObj(fs,off,3); WriteAscii(fs,"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595.28 841.89] /Resources << /XObject << /Im0 5 0 R >> >> /Contents 4 0 R >>\nendobj\n");
                BeginObj(fs,off,4); WriteAscii(fs,"<< /Length "+contentBytes.Length.ToString(CultureInfo.InvariantCulture)+" >>\nstream\n"); fs.Write(contentBytes,0,contentBytes.Length); WriteAscii(fs,"endstream\nendobj\n");
                BeginObj(fs,off,5); WriteAscii(fs,"<< /Type /XObject /Subtype /Image /Width "+w+" /Height "+h+" /ColorSpace /DeviceRGB /BitsPerComponent 8 /SMask 6 0 R /Length "+rgb.Length+" >>\nstream\n"); fs.Write(rgb,0,rgb.Length); WriteAscii(fs,"\nendstream\nendobj\n");
                BeginObj(fs,off,6); WriteAscii(fs,"<< /Type /XObject /Subtype /Image /Width "+w+" /Height "+h+" /ColorSpace /DeviceGray /BitsPerComponent 8 /Length "+alpha.Length+" >>\nstream\n"); fs.Write(alpha,0,alpha.Length); WriteAscii(fs,"\nendstream\nendobj\n");
                long xref=fs.Position;
                WriteAscii(fs,"xref\n0 7\n0000000000 65535 f \n");
                for(int i=1;i<=6;i++) WriteAscii(fs,off[i].ToString("0000000000",CultureInfo.InvariantCulture)+" 00000 n \n");
                WriteAscii(fs,"trailer\n<< /Size 7 /Root 1 0 R >>\nstartxref\n"+xref.ToString(CultureInfo.InvariantCulture)+"\n%%EOF\n");
            }
        }
        if(!File.Exists(overlayPdf) || new FileInfo(overlayPdf).Length<100)
            throw new Exception("Die interne transparente Overlay-PDF wurde nicht erzeugt.");
    }

    static string DiPath(string path)
    {
        string p=Path.GetFullPath(path).Replace('\\','/');
        if(p.Length>=3 && p[1]==':') return "/"+Char.ToUpperInvariant(p[0])+p.Substring(2);
        return p;
    }

    static string JsEscape(string s)
    {
        return s.Replace("\\","\\\\").Replace("\"","\\\"");
    }

    static void ApplyOverlay(string pdfPath,string overlayPdf,string outPath)
    {
        dynamic acroApp=null,pdDoc=null,jso=null,avDoc=null,aform=null,fields=null;
        try
        {
            Type ta=Type.GetTypeFromProgID("AcroExch.App");
            Type tp=Type.GetTypeFromProgID("AcroExch.PDDoc");
            if(ta==null || tp==null) throw new Exception("Adobe Acrobat COM ist nicht registriert.");
            acroApp=Activator.CreateInstance(ta);
            pdDoc=Activator.CreateInstance(tp);
            if(!(bool)pdDoc.Open(pdfPath)) throw new Exception("Adobe Acrobat konnte die PDF nicht oeffnen. Bitte PDF in Acrobat schliessen.");
            jso=pdDoc.GetJSObject();
            if(jso==null) throw new Exception("Adobe Acrobat lieferte kein JavaScript-Dokumentobjekt.");

            bool applied=false;
            string firstError="";
            try
            {
                object[] args=new object[] { overlayPdf,0,0,0,true,true,true,1,1,0.0,0.0,false,1.0,false,0,1.0 };
                jso.GetType().InvokeMember("addWatermarkFromFile",BindingFlags.InvokeMethod,null,jso,args);
                applied=true;
            }
            catch(Exception exDirect) { firstError=Clean(exDirect); }

            if(!applied)
            {
                try
                {
                    avDoc=pdDoc.OpenAVDoc("");
                    Type tf=Type.GetTypeFromProgID("AFormAut.App");
                    if(tf==null) throw new Exception("AFormAut.App ist nicht registriert.");
                    aform=Activator.CreateInstance(tf);
                    fields=aform.Fields;
                    string dip=JsEscape(DiPath(overlayPdf));
                    string js="this.addWatermarkFromFile({cDIPath:\""+dip+"\",nSourcePage:0,nStart:0,nEnd:0,bOnTop:true,bOnScreen:true,bOnPrint:true,nHorizAlign:1,nVertAlign:1,nHorizValue:0,nVertValue:0,bPercentage:false,nScale:1.0,bFixedPrint:false,nRotation:0,nOpacity:1.0});";
                    fields.ExecuteThisJavascript(js);
                    applied=true;
                }
                catch(Exception exFallback)
                {
                    throw new Exception("Acrobat direkt: "+firstError+" | Fallback: "+Clean(exFallback));
                }
            }

            if(File.Exists(outPath)) File.Delete(outPath);
            bool saved=(bool)pdDoc.Save(1,outPath);
            if(!saved || !File.Exists(outPath)) throw new Exception("Adobe Acrobat konnte die gestempelte PDF nicht speichern.");
            try { pdDoc.Close(); } catch { }
            try { acroApp.Exit(); } catch { }
        }
        finally
        {
            Release(fields); Release(aform); Release(avDoc); Release(jso); Release(pdDoc); Release(acroApp);
        }
    }

    public static string Run(string pdfPath,string outPath,string assetPath,string overlayPdf)
    {
        string stage="start";
        try
        {
            if(!File.Exists(pdfPath)) throw new Exception("PDF wurde nicht gefunden.");
            if(!File.Exists(assetPath)) throw new Exception("Lokale Stempelgrafik wurde nicht gefunden.");
            stage="overlay-pdf";
            CreateOverlayPdf(assetPath,overlayPdf);
            stage="acrobat-stamp";
            ApplyOverlay(pdfPath,overlayPdf,outPath);
            stage="validate";
            if(!File.Exists(outPath) || new FileInfo(outPath).Length<100) throw new Exception("Die gestempelte PDF ist leer oder unvollstaendig.");
            return "OK";
        }
        catch(Exception ex) { return "ERR|"+stage+"|"+Clean(ex); }
        finally { GC.Collect(); GC.WaitForPendingFinalizers(); }
    }
}
'@
Add-Type -TypeDefinition $csharp -Language CSharp -ReferencedAssemblies 'System.dll','System.Core.dll','System.Drawing.dll','Microsoft.CSharp.dll'
$result=[EngbersPdfOnlyStamp1804]::Run($PdfPath,$OutPath,$AssetPath,$OverlayPdf)
if($result -eq 'OK') { Write-Output 'OK'; exit 0 }
Write-Error $result
exit 1
"""
        fd,ps_file=tempfile.mkstemp(prefix='engbers_sasv_stamp_1804_',suffix='.ps1')
        os.close(fd)
        Path(ps_file).write_text(ps,encoding='utf-8-sig')
        cp=subprocess.run(
            ['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',ps_file,
             '-PdfPath',str(pdf_path),'-OutPath',str(out),'-AssetPath',str(asset_path),'-OverlayPdf',str(overlay)],
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
        for p in (out,overlay,ps_file):
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
    raise RuntimeError(f'1.8.4: Funktion {name} wurde nicht gefunden.')


def main():
    if not APP.exists() or not MOD.exists():
        raise RuntimeError('1.8.4: app.py oder wordforms_v1700.py wurde nicht gefunden.')
    app=APP.read_text(encoding='utf-8')
    mod=MOD.read_text(encoding='utf-8')
    cur=_version(app)
    if cur==NEW and MARK in mod:
        return 0
    if cur!=OLD:
        raise RuntimeError(f'Update 1.8.4 erwartet Projektzentrale {OLD}; gefunden: {cur or "unbekannt"}.')

    mod=_replace_function(mod,'_stamp_approved_pdf',NEW_STAMP)
    if MARK not in mod:
        raise RuntimeError('1.8.4: PDF-only-Stempel-Marker fehlt.')

    app_new=re.sub(r'(APP_VERSION\s*=\s*)["\'][^"\']+["\']',lambda m:m.group(1)+'"'+NEW+'"',app,count=1)
    app_new=app_new.replace('Projektzentrale 1.8.3','Projektzentrale 1.8.4')

    chk1=APP.with_name('app.py.1804.check')
    chk2=MOD.with_name('wordforms_v1700.py.1804.check')
    try:
        chk1.write_text(app_new,encoding='utf-8'); py_compile.compile(str(chk1),doraise=True)
        chk2.write_text(mod,encoding='utf-8'); py_compile.compile(str(chk2),doraise=True)
    finally:
        for p in (chk1,chk2):
            try:p.unlink()
            except Exception:pass

    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for p in (APP,MOD):
        shutil.copy2(p,p.with_name(p.name+'.vor_1_8_4_'+stamp+'.bak'))
    t=APP.with_name('app.py.1804.tmp'); t.write_text(app_new,encoding='utf-8'); t.replace(APP)
    t=MOD.with_name('wordforms_v1700.py.1804.tmp'); t.write_text(mod,encoding='utf-8'); t.replace(MOD)
    APP.with_name('patch_1804_report.txt').write_text(
        'OK: Projektzentrale 1.8.4 installiert.\n'
        'Stempel-Overlay wird ohne Word direkt aus der lokalen PNG erzeugt.\n'
        'Word wird beim finalen PDF-Stempeln nicht verwendet.\n',encoding='utf-8')
    return 0

if __name__=='__main__':
    try: raise SystemExit(main())
    except SystemExit: raise
    except Exception:
        try: APP.with_name('patch_1804_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception: pass
        raise
