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
OLD='1.8.0'
NEW='1.8.1'
MARK='PZ_WORD_CSHARP_COM_BRIDGE_V1801'

NEW_FILL = r'''def fill_docx(src, dst, data):
    # PZ_WORD_CSHARP_COM_BRIDGE_V1801
    # XML wird weiterhin nur gelesen, um die Legacy-FormFields zuzuordnen.
    # Word selbst wird ueber einen kleinen C#-COM-Bridge mit BENANNTEN Parametern
    # gesteuert. Dadurch entfallen die fehleranfaelligen PowerShell-COM-Optionalparameter.
    src=Path(src).resolve()
    dst=Path(dst).resolve()
    vals=_values(data)

    if not src.exists():
        raise RuntimeError('Word-Datei wurde nicht gefunden.')

    with zipfile.ZipFile(src,'r') as zin:
        root=ET.fromstring(zin.read('word/document.xml'))
    parents={c:p for p in root.iter() for c in p}
    plan=[]
    for index,ff in enumerate(root.iter(Q('ffData')),start=1):
        cb=ff.find(Q('checkBox'))
        if cb is not None:
            p=_ancestor(ff,'p',parents)
            text=_txt(p).casefold()
            if ('von mir aufgestellten' in text
                    and 'fachplaner' not in text
                    and 'von mir geprüften' not in text):
                plan.append({'index':index,'kind':'checkbox','value':'1','key':'primary_checkbox'})
            continue
        key=_classify(ff,parents)
        value=vals.get(key) if key else ''
        if key and value:
            plan.append({'index':index,'kind':'text','value':str(value),'key':key})

    if not plan:
        return 0

    try:
        same_target=src.resolve()==dst.resolve()
    except Exception:
        same_target=str(src).casefold()==str(dst).casefold()
    if same_target:
        _safety_backup(src)

    dst.parent.mkdir(parents=True,exist_ok=True)
    pdf_path=dst.with_suffix('.pdf')
    try:
        if pdf_path.exists():
            pdf_path.unlink()
    except PermissionError:
        raise RuntimeError('Die vorhandene PDF ist noch geöffnet oder gesperrt. Bitte PDF schliessen und erneut ausfüllen.')

    work=None
    normalized=None
    pdf_tmp=None
    plan_file=None
    ps_file=None
    try:
        import base64
        token=datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
        work=dst.parent/(dst.stem+f'.pz1801_work_{token}.docx')
        normalized=dst.parent/(dst.stem+f'.pz1801_normalized_{token}.docx')
        pdf_tmp=dst.parent/(dst.stem+f'.pz1801_pdf_{token}.pdf')
        shutil.copy2(src,work)

        fd,plan_file=tempfile.mkstemp(prefix='engbers_word_plan_1801_',suffix='.txt')
        os.close(fd)
        lines=[]
        for item in plan:
            raw=str(item['value']).encode('utf-8')
            enc=base64.b64encode(raw).decode('ascii')
            lines.append(f"{int(item['index'])}|{item['kind']}|{enc}")
        Path(plan_file).write_text('\n'.join(lines),encoding='ascii')

        ps=r'''param(
 [Parameter(Mandatory=$true)][string]$WorkPath,
 [Parameter(Mandatory=$true)][string]$NormalizedPath,
 [Parameter(Mandatory=$true)][string]$PdfPath,
 [Parameter(Mandatory=$true)][string]$PlanPath
)
$ErrorActionPreference='Stop'
$csharp=@"
using System;
using System.IO;
using System.Text;
using System.Runtime.InteropServices;

public static class EngbersWordBridge1801
{
    static string CleanMessage(Exception ex)
    {
        while (ex != null && ex.InnerException != null) ex = ex.InnerException;
        return ex == null ? "Unbekannter Fehler" : ex.Message;
    }

    public static string Run(string workPath, string normalizedPath, string pdfPath, string planPath)
    {
        dynamic word = null;
        dynamic doc = null;
        string stage = "start";
        string repairError = "";
        try
        {
            stage = "word-start";
            Type t = Type.GetTypeFromProgID("Word.Application");
            if (t == null) throw new Exception("Microsoft Word COM ist nicht registriert.");
            word = Activator.CreateInstance(t);
            word.Visible = false;
            word.DisplayAlerts = 0;

            stage = "open-repair";
            try
            {
                doc = word.Documents.Open(
                    FileName: workPath,
                    ConfirmConversions: false,
                    ReadOnly: false,
                    AddToRecentFiles: false,
                    Visible: false,
                    OpenAndRepair: true,
                    NoEncodingDialog: true);
            }
            catch (Exception exRepair)
            {
                repairError = CleanMessage(exRepair);
                stage = "open-normal";
                try
                {
                    doc = word.Documents.Open(
                        FileName: workPath,
                        ConfirmConversions: false,
                        ReadOnly: false,
                        AddToRecentFiles: false,
                        Visible: false,
                        NoEncodingDialog: true);
                }
                catch (Exception exNormal)
                {
                    throw new Exception("REPARATUR: " + repairError + " | NORMAL: " + CleanMessage(exNormal));
                }
            }

            if (doc == null) throw new Exception("Microsoft Word konnte die Arbeitskopie nicht öffnen.");

            stage = "formfields";
            int count = (int)doc.FormFields.Count;
            string[] lines = File.ReadAllLines(planPath, Encoding.ASCII);
            int maxIndex = 0;
            foreach (string line in lines)
            {
                if (String.IsNullOrWhiteSpace(line)) continue;
                string[] parts = line.Split(new char[] {'|'}, 3);
                if (parts.Length != 3) throw new Exception("Ungültige Formularplan-Zeile.");
                int idx = Int32.Parse(parts[0]);
                if (idx > maxIndex) maxIndex = idx;
            }
            if (count < maxIndex)
                throw new Exception("Word meldet nur " + count + " Legacy-Formularfelder; benötigt wird Feld " + maxIndex + ".");

            stage = "fill";
            foreach (string line in lines)
            {
                if (String.IsNullOrWhiteSpace(line)) continue;
                string[] parts = line.Split(new char[] {'|'}, 3);
                int idx = Int32.Parse(parts[0]);
                string kind = parts[1];
                string value = Encoding.UTF8.GetString(Convert.FromBase64String(parts[2]));
                dynamic ff = doc.FormFields.Item(idx);
                if (kind == "checkbox") ff.CheckBox.Value = true;
                else ff.Result = value;
                try { Marshal.FinalReleaseComObject(ff); } catch { }
            }

            stage = "save-normalized";
            doc.SaveAs2(FileName: normalizedPath, FileFormat: 16);

            stage = "export-pdf";
            doc.ExportAsFixedFormat(OutputFileName: pdfPath, ExportFormat: 17);

            stage = "close";
            doc.Close(false);
            try { Marshal.FinalReleaseComObject(doc); } catch { }
            doc = null;
            word.Quit(false);
            try { Marshal.FinalReleaseComObject(word); } catch { }
            word = null;

            if (!File.Exists(normalizedPath)) throw new Exception("Word hat die normalisierte DOCX nicht erzeugt.");
            if (!File.Exists(pdfPath)) throw new Exception("Word hat die PDF nicht erzeugt.");
            if (new FileInfo(pdfPath).Length < 100) throw new Exception("Die erzeugte PDF ist leer oder unvollständig.");
            return "OK|" + count + "|" + maxIndex;
        }
        catch (Exception ex)
        {
            return "ERR|" + stage + "|" + CleanMessage(ex);
        }
        finally
        {
            if (doc != null)
            {
                try { doc.Close(false); } catch { }
                try { Marshal.FinalReleaseComObject(doc); } catch { }
            }
            if (word != null)
            {
                try { word.Quit(false); } catch { }
                try { Marshal.FinalReleaseComObject(word); } catch { }
            }
            GC.Collect();
            GC.WaitForPendingFinalizers();
        }
    }
}
"@
Add-Type -TypeDefinition $csharp -Language CSharp -ReferencedAssemblies 'System.dll','System.Core.dll','Microsoft.CSharp.dll'
$result=[EngbersWordBridge1801]::Run($WorkPath,$NormalizedPath,$PdfPath,$PlanPath)
if($result -like 'OK|*'){
  Write-Output $result
  exit 0
}
Write-Error $result
exit 1
'''
        fd,ps_file=tempfile.mkstemp(prefix='engbers_word_1801_',suffix='.ps1')
        os.close(fd)
        Path(ps_file).write_text(ps,encoding='utf-8-sig')

        cp=subprocess.run(
            ['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',ps_file,
             '-WorkPath',str(work),'-NormalizedPath',str(normalized),
             '-PdfPath',str(pdf_tmp),'-PlanPath',str(plan_file)],
            capture_output=True,text=True,timeout=90,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)
        )
        if cp.returncode!=0:
            detail=(cp.stderr or cp.stdout or '').strip()
            raise RuntimeError(detail or f'Word-C#-Bridge Rückgabecode {cp.returncode}')

        if not normalized.exists() or normalized.stat().st_size<100:
            raise RuntimeError('Word hat keine gültige normalisierte DOCX erzeugt.')
        if not pdf_tmp.exists() or pdf_tmp.stat().st_size<100:
            raise RuntimeError('Word hat keine gültige PDF erzeugt.')

        os.replace(normalized,dst)
        normalized=None
        os.replace(pdf_tmp,pdf_path)
        pdf_tmp=None
        return len(plan)

    except subprocess.TimeoutExpired:
        raise RuntimeError('Microsoft Word hat den gemeinsamen Formular/PDF-Lauf nicht innerhalb von 90 Sekunden beendet.')
    finally:
        for p in (work,normalized,pdf_tmp,plan_file,ps_file):
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
    raise RuntimeError(f'1.8.1: Funktion {name} wurde nicht gefunden.')


def main():
    if not APP.exists() or not MOD.exists():
        raise RuntimeError('1.8.1: app.py oder wordforms_v1700.py wurde nicht gefunden.')
    app=APP.read_text(encoding='utf-8')
    mod=MOD.read_text(encoding='utf-8')
    cur=_version(app)
    if cur==NEW and MARK in mod:
        return 0
    if cur!=OLD:
        raise RuntimeError(f'Update 1.8.1 erwartet Projektzentrale {OLD}; gefunden: {cur or "unbekannt"}.')

    mod=_replace_function(mod,'fill_docx',NEW_FILL)
    if MARK not in mod:
        raise RuntimeError('1.8.1: C#-COM-Bridge-Marker fehlt.')

    app_new=re.sub(r'(APP_VERSION\s*=\s*)["\'][^"\']+["\']',lambda m:m.group(1)+'"'+NEW+'"',app,count=1)
    app_new=app_new.replace('Projektzentrale 1.8.0','Projektzentrale 1.8.1')

    active_start=mod.find(MARK)
    active_end=mod.find('\ndef ',active_start)
    active=mod[active_start:active_end if active_end>0 else len(mod)]
    for required in (
        'EngbersWordBridge1801',
        'OpenAndRepair: true',
        'doc.FormFields.Item',
        'doc.SaveAs2(FileName: normalizedPath, FileFormat: 16)',
        'doc.ExportAsFixedFormat(OutputFileName: pdfPath, ExportFormat: 17)',
        'Microsoft.CSharp.dll',
        'REPARATUR:',
    ):
        if required not in active:
            raise RuntimeError('1.8.1: erwarteter C#-Bridge-Baustein fehlt: '+required)
    if '$word.Documents.OpenNoRepairDialog' in active or '$word.Documents.Open(' in active:
        raise RuntimeError('1.8.1: direkte PowerShell-Word-COM-Öffnung ist noch aktiv.')

    chk1=APP.with_name('app.py.1801.check')
    chk2=MOD.with_name('wordforms_v1700.py.1801.check')
    try:
        chk1.write_text(app_new,encoding='utf-8'); py_compile.compile(str(chk1),doraise=True)
        chk2.write_text(mod,encoding='utf-8'); py_compile.compile(str(chk2),doraise=True)
    finally:
        for p in (chk1,chk2):
            try:p.unlink()
            except Exception:pass

    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for p in (APP,MOD):
        shutil.copy2(p,p.with_name(p.name+'.vor_1_8_1_'+stamp+'.bak'))
    t=APP.with_name('app.py.1801.tmp'); t.write_text(app_new,encoding='utf-8'); t.replace(APP)
    t=MOD.with_name('wordforms_v1700.py.1801.tmp'); t.write_text(mod,encoding='utf-8'); t.replace(MOD)
    APP.with_name('patch_1801_report.txt').write_text(
        'OK: Projektzentrale 1.8.1 installiert.\n'
        'Word-COM wird jetzt ueber einen C#-Bridge mit benannten Parametern gesteuert.\n'
        'OpenAndRepair, Formularfelder, Speichern und PDF-Export laufen in derselben Word-Instanz.\n',encoding='utf-8')
    return 0

if __name__=='__main__':
    try: raise SystemExit(main())
    except SystemExit: raise
    except Exception:
        try: APP.with_name('patch_1801_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception: pass
        raise
