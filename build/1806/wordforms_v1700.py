import copy
import json
import os
import re
import zipfile
import datetime
import subprocess
import tempfile
import time
import hashlib
import shutil
from pathlib import Path
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import masterdata_v1604 as _md

W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
Q=lambda n:f'{{{W}}}{n}'


def _txt(el):
    if el is None:
        return ''
    return ''.join((x.text or '') for x in el.iter(Q('t')))


def _ancestor(el, tag, parents):
    q=Q(tag)
    while el is not None and el.tag != q:
        el=parents.get(el)
    return el


def _ctx(ff, parents):
    tc=_ancestor(ff,'tc',parents)
    tr=_ancestor(ff,'tr',parents)
    p=_ancestor(ff,'p',parents)
    cell=_txt(tc)
    if tr is not None:
        row=' | '.join(_txt(c) for c in list(tr) if c.tag==Q('tc'))
    else:
        row=_txt(p)
    return cell,row,p,tc


def _field_index(ff, parents):
    tc=_ancestor(ff,'tc',parents)
    p=_ancestor(ff,'p',parents)
    base=tc if tc is not None else p
    arr=[x for x in base.iter(Q('ffData'))] if base is not None else [ff]
    return arr.index(ff),len(arr)


def _classify(ff, parents):
    # Kontrollkästchen bleiben grundsätzlich unangetastet.
    if ff.find(Q('checkBox')) is not None:
        return None
    cell,row,_,_=_ctx(ff,parents)
    c=cell.casefold()
    r=row.casefold()
    combo=(cell+' '+row).casefold()
    idx,_=_field_index(ff,parents)

    # Unterschriftsbereich: Ort und Datum stehen in zwei Formularfeldern
    # der linken Zelle unter "III. Unterschrift".
    if 'iii. unterschrift' in c:
        if idx==0:
            return 'signature_place'
        if idx==1:
            return 'signature_date'

    # Bauvorhaben / Bauort.
    if 'genaue bezeichnung' in combo or 'bezeichnung des bauvorhabens' in combo:
        return 'project_title'
    if 'bauort' in combo or 'anschrift des bauvorhabens' in combo or 'objektanschrift' in combo:
        return 'project_address'

    # Beteiligte. Bei Feldern in einer gemeinsamen Zelle entscheidet die Reihenfolge:
    # erstes Formularfeld = Name, zweites Formularfeld = Anschrift.
    if 'bauherrschaft' in c or re.search(r'\bbauherr\b',c):
        return 'client_name' if idx==0 else 'client_address'
    if 'entwurfsverfass' in c or 'planverfasser' in c or 'architekt' in c:
        return 'architect_name' if idx==0 else 'architect_address'
    if ('fachplanerin' in c or 'fachplaner' in c or 'tragwerksplan' in c) and ('name' in c or 'anschrift' in c):
        return 'engineer_name' if idx==0 else 'engineer_address'

    # Kopfbereich saSV / Büro. Die Beschriftung steht häufig in der linken Tabellenzelle,
    # das eigentliche Formularfeld in der rechten Zelle.
    if 'vor- und nachname der/des sasv' in r or 'name der/des sasv' in r:
        return 'engineer_name'
    if 'bürobezeichnung' in r or 'buerobezeichnung' in r:
        return 'engineer_firm'
    if r.strip().startswith('anschrift') and len(r)<100:
        return 'engineer_address'

    # Weitere Kontaktfelder, falls andere Bescheinigungen sie explizit enthalten.
    if 'telefon' in c or 'tel.' in c:
        if 'bauherr' in c: return 'client_phone'
        if 'architekt' in c or 'entwurfsverfass' in c: return 'architect_phone'
        if 'fachplaner' in c or 'sasv' in c: return 'engineer_phone'
    if 'e-mail' in c or 'email' in c:
        if 'bauherr' in c: return 'client_email'
        if 'architekt' in c or 'entwurfsverfass' in c: return 'architect_email'
        if 'fachplaner' in c or 'sasv' in c: return 'engineer_email'
    return None


def _flatten(ff, value, parents):
    fld=parents.get(ff)
    begin=_ancestor(fld,'r',parents)
    p=_ancestor(begin,'p',parents)
    if begin is None or p is None:
        return False
    children=list(p)
    try:
        bi=children.index(begin)
    except ValueError:
        return False
    endi=None
    bookmark_ids=[]
    for i,el in enumerate(children[bi:],bi):
        bs=el.find(Q('bookmarkStart'))
        if bs is not None and bs.get(Q('id')):
            bookmark_ids.append(bs.get(Q('id')))
        fc=el.find('.//'+Q('fldChar'))
        if fc is not None and fc.get(Q('fldCharType'))=='end':
            endi=i
            break
    if endi is None:
        return False

    rpr=begin.find(Q('rPr'))
    rpr=copy.deepcopy(rpr) if rpr is not None else None
    for el in children[bi:endi+1]:
        p.remove(el)
    # Zu entfernten Formularfeldern gehörige Bookmark-Enden nicht als Waisen stehen lassen.
    for el in list(p):
        if el.tag==Q('bookmarkEnd') and el.get(Q('id')) in bookmark_ids:
            p.remove(el)

    run=ET.Element(Q('r'))
    if rpr is not None:
        run.append(rpr)
    t=ET.SubElement(run,Q('t'))
    t.text=str(value)
    p.insert(min(bi,len(p)),run)
    return True


def _set_form_result(ff, value, parents):
    # PZ_WORD_INPLACE_FIELDS_V1703: Ergebnis eines alten Word-Formularfeldes
    # aktualisieren, ohne das eigentliche Formularfeld zu entfernen.
    fld=parents.get(ff)
    begin=_ancestor(fld,'r',parents)
    p=_ancestor(begin,'p',parents)
    if begin is None or p is None:
        return False
    children=list(p)
    try:
        bi=children.index(begin)
    except ValueError:
        return False
    sep_i=end_i=None
    for i,el in enumerate(children[bi:],bi):
        fc=el.find('.//'+Q('fldChar'))
        if fc is None:
            continue
        typ=fc.get(Q('fldCharType'))
        if typ=='separate' and sep_i is None:
            sep_i=i
        elif typ=='end' and sep_i is not None:
            end_i=i
            break
    if sep_i is None or end_i is None:
        return False
    rpr=None
    for el in children[sep_i+1:end_i]:
        if el.tag==Q('r'):
            old_rpr=el.find(Q('rPr'))
            if old_rpr is not None:
                rpr=copy.deepcopy(old_rpr)
            break
    if rpr is None:
        old_rpr=begin.find(Q('rPr'))
        if old_rpr is not None:
            rpr=copy.deepcopy(old_rpr)
    for el in children[sep_i+1:end_i]:
        p.remove(el)
    run=ET.Element(Q('r'))
    if rpr is not None:
        run.append(rpr)
    t=ET.SubElement(run,Q('t'))
    t.text=str(value)
    p.insert(sep_i+1,run)
    return True


def _safety_backup_path(src):
    src=Path(src)
    base=Path(os.environ.get('LOCALAPPDATA') or tempfile.gettempdir())/'Engbers Projektzentrale'/'word_backups'
    token=hashlib.sha1(str(src.resolve()).encode('utf-8',errors='ignore')).hexdigest()[:12]
    return base/(src.stem+'_'+token+'_vor_automatik'+src.suffix)


def _safety_backup(src):
    # PZ_WORD_RESET_V1860: Die erste, noch leere Formularfassung bleibt als
    # einzige Sicherheitskopie außerhalb des Projektordners erhalten.
    # Sie wird bei späterem Ausfüllen bewusst nicht überschrieben.
    try:
        src=Path(src)
        dst=_safety_backup_path(src)
        dst.parent.mkdir(parents=True,exist_ok=True)
        if not dst.exists():
            shutil.copy2(src,dst)
        return dst
    except Exception:
        return None


def _address(street, zip_code, city):
    street=str(street or '').strip()
    zip_code=str(zip_code or '').strip()
    city=str(city or '').strip()
    tail=' '.join(x for x in (zip_code,city) if x)
    return ', '.join(x for x in (street,tail) if x)


def _values(data):
    return {
        'engineer_name':str(data.get('engineer_name','') or '').strip(),
        'engineer_firm':str(data.get('engineer_firm','') or '').strip(),
        'engineer_address':_address(data.get('engineer_street'),data.get('engineer_zip'),data.get('engineer_city')),
        'engineer_phone':str(data.get('engineer_phone','') or '').strip(),
        'engineer_email':str(data.get('engineer_email','') or '').strip(),
        'project_title':str(data.get('project_title','') or '').strip(),
        'project_address':_address(data.get('project_street'),data.get('project_zip'),data.get('project_city')),
        'client_name':str(data.get('client_name','') or '').strip(),
        'client_address':_address(data.get('client_street'),data.get('client_zip'),data.get('client_city')),
        'client_phone':str(data.get('client_phone','') or '').strip(),
        'client_email':str(data.get('client_email','') or '').strip(),
        'architect_name':str(data.get('architect_name','') or data.get('architect_firm','') or '').strip(),
        'architect_address':_address(data.get('architect_street'),data.get('architect_zip'),data.get('architect_city')),
        'architect_phone':str(data.get('architect_phone','') or '').strip(),
        'architect_email':str(data.get('architect_email','') or '').strip(),
        'signature_place':str(data.get('engineer_city','') or 'Lingen').strip(),
        'signature_date':datetime.date.today().strftime('%d.%m.%Y'),
    }


def inspect_docx(path, data=None):
    vals=_values(data or {})
    try:
        with zipfile.ZipFile(path,'r') as z:
            root=ET.fromstring(z.read('word/document.xml'))
    except Exception as e:
        return {'ok':False,'mapped':0,'text_fields':0,'error':str(e)}
    parents={c:p for p in root.iter() for c in p}
    mapped=0
    manual=0
    text_fields=0
    keys=[]
    for ff in root.iter(Q('ffData')):
        if ff.find(Q('checkBox')) is not None:
            continue
        text_fields+=1
        key=_classify(ff,parents)
        if key and (not vals or vals.get(key)):
            mapped+=1
            keys.append(key)
        elif _extra_field_label(ff,parents):
            manual+=1
    return {'ok':True,'mapped':mapped,'manual':manual,'text_fields':text_fields,'keys':keys,'error':''}


def _extra_field_label(ff, parents):
    """Return the human label for supported document-specific form fields."""
    if ff.find(Q('checkBox')) is not None:
        return ''
    cell,row,_,_=_ctx(ff,parents)
    text=(cell+' '+row).casefold()
    index,total=_field_index(ff,parents)
    if 'prüf-nr' in text or 'pruef-nr' in text or 'prüfnummer' in text:
        return 'Prüf-Nr. / Aktenzeichen'
    if 'bauleitende' in cell.casefold():
        return 'Bauleitende Person' if index==0 else 'Anschrift der bauleitenden Person'
    if 'abschließenden kontrolle' in text or 'abschliessenden kontrolle' in text:
        labels=(
            'Datum der abschließenden Baustellenkontrolle',
            'Datum der Berechnungsdokumentation',
            'Registriernummer des Energieausweises',
            'Ausstellungsdatum des Energieausweises',
        )
        return labels[index] if index < len(labels) else ''
    if 'stichprobenhafte' in row.casefold() and 'kontrolle' in row.casefold():
        return 'Kontrollbericht Nr. von' if index==0 else 'Kontrollbericht Nr. bis'
    if 'verteiler' in row.casefold():
        return 'Verteiler'
    return ''


def _document_extra_fields(path):
    try:
        with zipfile.ZipFile(path,'r') as z:
            root=ET.fromstring(z.read('word/document.xml'))
    except Exception:
        return []
    parents={c:p for p in root.iter() for c in p}
    out=[]
    for field_index,ff in enumerate(root.iter(Q('ffData')),start=1):
        if _classify(ff,parents):
            continue
        label=_extra_field_label(ff,parents)
        if not label:
            continue
        value=_field_result_text(ff,parents).replace('\u2002',' ').strip()
        out.append((field_index,label,value))
    return out


def _prompt_extra_values(parent, path, BG, PANEL, INK, MUTED, ACCENT, DARK):
    fields=_document_extra_fields(path)
    if not fields:
        return {}
    result={'value':None}
    dlg=tk.Toplevel(parent)
    dlg.title('Zusätzliche Angaben zur Bescheinigung')
    height=min(820,max(430,225+len(fields)*48))
    dlg.geometry(f'760x{height}')
    dlg.configure(bg=BG); dlg.transient(parent); dlg.grab_set()
    tk.Label(dlg,text='ZUSÄTZLICHE ANGABEN',bg=BG,fg=INK,font=('Segoe UI Semibold',17)).pack(anchor='w',padx=24,pady=(20,4))
    tk.Label(dlg,text=Path(path).name+'\nDiese Angaben stehen nicht in den Projektstammdaten und gelten nur für diese Bescheinigung.',bg=BG,fg=MUTED,justify='left',wraplength=700).pack(anchor='w',padx=24,pady=(0,14))
    canvas=tk.Canvas(dlg,bg=BG,highlightthickness=0)
    scrollbar=ttk.Scrollbar(dlg,orient='vertical',command=canvas.yview)
    body=tk.Frame(canvas,bg=PANEL,bd=1,relief='solid')
    body_id=canvas.create_window((0,0),window=body,anchor='nw')
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side='top',fill='both',expand=True,padx=(24,0)); scrollbar.place(relx=1.0,x=-24,y=105,relheight=.68,anchor='ne')
    body.grid_columnconfigure(1,weight=1)
    entries={}
    for row,(field_index,label,value) in enumerate(fields):
        tk.Label(body,text=label,bg=PANEL,fg=MUTED,anchor='w',width=35).grid(row=row,column=0,sticky='w',padx=(14,8),pady=7)
        var=tk.StringVar(value=value); entries[field_index]=var
        tk.Entry(body,textvariable=var,font=('Segoe UI',10),bd=0,highlightthickness=1,highlightbackground='#c8c5bd').grid(row=row,column=1,sticky='ew',padx=(0,14),pady=7,ipady=5)
    def resize(_event=None):
        canvas.configure(scrollregion=canvas.bbox('all'))
        canvas.itemconfigure(body_id,width=max(100,canvas.winfo_width()))
    body.bind('<Configure>',resize); canvas.bind('<Configure>',resize)
    foot=tk.Frame(dlg,bg=BG); foot.pack(fill='x',padx=24,pady=16)
    def accept():
        result['value']={index:var.get().strip() for index,var in entries.items()}
        dlg.destroy()
    tk.Button(foot,text='ÜBERNEHMEN UND PDF ERSTELLEN',command=accept,bg=ACCENT,fg='white',bd=0,padx=16,pady=9).pack(side='right')
    tk.Button(foot,text='ABBRECHEN',command=dlg.destroy,bg='#e7e4dc',fg=INK,bd=0,padx=16,pady=9).pack(side='right',padx=8)
    dlg.protocol('WM_DELETE_WINDOW',dlg.destroy)
    parent.wait_window(dlg)
    return result['value']


def _set_primary_checkbox(root, parents):
    # PZ_WORD_DATE_CHECKBOX_PDF_V1702
    # Nur die erste fachliche Bestätigung automatisch markieren:
    # "Die von mir aufgestellten ...". Das Fachplaner/Prüfer-Kästchen bleibt frei.
    for ff in root.iter(Q('ffData')):
        cb=ff.find(Q('checkBox'))
        if cb is None:
            continue
        p=_ancestor(ff,'p',parents)
        text=_txt(p).casefold()
        if 'von mir aufgestellten' not in text:
            continue
        if 'fachplaner' in text or 'von mir geprüften' in text:
            continue
        default=cb.find(Q('default'))
        if default is None:
            default=ET.SubElement(cb,Q('default'))
        default.set(Q('val'),'1')
        checked=cb.find(Q('checked'))
        if checked is None:
            checked=ET.SubElement(cb,Q('checked'))
        checked.set(Q('val'),'1')
        return 1
    return 0


def fill_docx(src, dst, data, extra_values=None):
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
        elif (extra_values is not None and index in extra_values
              and str(extra_values[index]).strip()):
            plan.append({'index':index,'kind':'text','value':str(extra_values[index]).strip(),'key':'manual'})

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




def _project_sources(app):
    try:
        srcs=app._project_sources()
    except Exception:
        srcs=[{'path':app.get_project_folder()}]
    out=[]
    seen=set()
    for s in srcs:
        p=Path(s.get('path',''))
        if not p.exists():
            continue
        k=str(p).casefold()
        if k in seen:
            continue
        seen.add(k)
        out.append(p)
    return out


def _bescheinigungen_roots(app):
    roots=[]
    seen=set()
    for project_root in _project_sources(app):
        direct=project_root/'Bescheinigungen'
        candidates=[]
        if direct.is_dir():
            candidates.append(direct)
        try:
            for dp,ds,fs in os.walk(project_root):
                ds[:]=[d for d in ds if d.casefold() not in ('.git','__pycache__','ausgefüllt','ausgefuellt') and not d.startswith('.engbers')]
                p=Path(dp)
                if p.name.casefold()=='bescheinigungen':
                    candidates.append(p)
                    ds[:]=[]
        except Exception:
            pass
        for p in candidates:
            k=str(p.resolve()).casefold()
            if k not in seen:
                seen.add(k); roots.append(p)
    return roots


def _documents(app):
    rows=[]
    seen=set()
    for root in _bescheinigungen_roots(app):
        for p in root.rglob('*.docx'):
            if any(part.casefold() in ('ausgefüllt','ausgefuellt') for part in p.parts):
                continue
            if p.name.startswith('~$') or '_ausgefüllt' in p.stem.casefold() or '_ausgefuellt' in p.stem.casefold():
                continue
            k=str(p).casefold()
            if k in seen:
                continue
            seen.add(k)
            try: rel=p.relative_to(root)
            except Exception: rel=Path(p.name)
            rows.append((root,p,rel))
    rows.sort(key=lambda x:(str(x[0]).casefold(),str(x[2]).casefold()))
    return rows


def _output_path(root, src, rel):
    # Vorhandenes Projektformular direkt aktualisieren.
    return Path(src)


def _pdf_output_path(root, src, rel):
    # PDF liegt direkt neben dem Word-Formular.
    return Path(src).with_suffix('.pdf')


def _field_result_text(ff, parents):
    fld=parents.get(ff)
    begin=_ancestor(fld,'r',parents)
    p=_ancestor(begin,'p',parents)
    if begin is None or p is None:
        return ''
    children=list(p)
    try:
        bi=children.index(begin)
    except ValueError:
        return ''
    sep_i=end_i=None
    for i,el in enumerate(children[bi:],bi):
        fc=el.find('.//'+Q('fldChar'))
        if fc is None:
            continue
        typ=fc.get(Q('fldCharType'))
        if typ=='separate' and sep_i is None:
            sep_i=i
        elif typ=='end' and sep_i is not None:
            end_i=i
            break
    if sep_i is None or end_i is None:
        return ''
    return ''.join(_txt(el) for el in children[sep_i+1:end_i])


def _make_export_safe_docx(src):
    # PZ_PDF_EXPORT_SAFE_DOCX_V1707
    # Fuer den PDF-Export werden nur die alten Text-Formularfelder in einer
    # temporaeren Kopie in normalen Text umgewandelt. Die Projekt-DOCX selbst
    # bleibt unveraendert und behaelt ihre Formularfelder fuer spaetere Updates.
    src=Path(src).resolve()
    with zipfile.ZipFile(src,'r') as zin:
        root=ET.fromstring(zin.read('word/document.xml'))
        parents={c:p for p in root.iter() for c in p}
        fields=list(root.iter(Q('ffData')))
        flattened=0
        for ff in fields:
            if ff.find(Q('checkBox')) is not None:
                continue
            value=_field_result_text(ff,parents)
            if _flatten(ff,value,parents):
                flattened+=1
        new_xml=ET.tostring(root,encoding='utf-8',xml_declaration=True)
        fd,tmp=tempfile.mkstemp(prefix='engbers_pdf_export_',suffix='.docx')
        os.close(fd)
        try:
            with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    content=new_xml if item.filename=='word/document.xml' else zin.read(item.filename)
                    zout.writestr(item,content)
            with zipfile.ZipFile(tmp,'r') as chk:
                if chk.testzip() is not None:
                    raise RuntimeError('Export-Zwischendatei ist kein gueltiges DOCX-Archiv.')
            return Path(tmp),flattened
        except Exception:
            try: Path(tmp).unlink()
            except Exception: pass
            raise


def _export_pdf_with_word(docx_path, pdf_path):
    # 1.8.0: PDF entsteht bereits im selben Word-Lauf wie das Ausfuellen.
    # Diese Funktion bleibt nur als kompatibler Status-Check fuer die UI bestehen.
    pdf_path=Path(pdf_path)
    if pdf_path.exists():
        try:
            if pdf_path.stat().st_size>100:
                return True,''
        except Exception:
            pass
    return False,'Die PDF wurde im gemeinsamen Word-Lauf nicht erzeugt.'








def _sasv_stamp_asset_path():
    # PZ_SASV_RELEASE_STAMP_V1802
    base=Path(os.environ.get('LOCALAPPDATA') or (Path.home()/'AppData'/'Local'))/'Engbers Projektzentrale'/'assets'
    local=base/'sasv_stempel_unterschrift.png'
    if local.exists():
        return local
    bundled=Path(__file__).resolve().parent/'assets'/'Engbers_saSV_Stempel_Unterschrift.png'
    return bundled if bundled.exists() else local


def _stamp_approved_pdf(docx_path, pdf_path, asset_path):
    # PZ_SASV_PYMUPDF_STAMP_V1805
    # Die bereits erzeugte PDF wird direkt mit dem lokal installierten
    # PyMuPDF bearbeitet. Weder Word noch Adobe/Acrobat COM werden verwendet.
    import importlib
    import sys

    pdf_path = Path(pdf_path).resolve()
    asset_path = Path(asset_path).resolve()
    if not pdf_path.exists():
        return False, 'Die zu stempelnde PDF wurde nicht gefunden.'
    if not asset_path.exists():
        return False, 'Lokale Stempeldatei wurde nicht gefunden.'

    base = Path(__file__).resolve().parent
    vendor = base / '_vendor'
    if vendor.exists() and str(vendor) not in sys.path:
        sys.path.insert(0, str(vendor))

    fitz = None
    engine_errors = []
    for module_name in ('pymupdf', 'fitz'):
        try:
            fitz = importlib.import_module(module_name)
            break
        except Exception as exc:
            engine_errors.append(f'{module_name}: {exc}')
    if fitz is None:
        return False, (
            'Die lokale PDF-Engine konnte nicht geladen werden. '
            'Bitte unter Sicherung / Update erneut nach Updates suchen. '
            + ' | '.join(engine_errors)
        )

    token = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
    out = pdf_path.parent / (pdf_path.stem + f'.pz1805_stamped_{token}.pdf')
    clean_png = pdf_path.parent / (pdf_path.stem + f'.pz1805_stamp_{token}.png')
    document = None
    try:
        # Die vorhandene Stempelgrafik kann noch einen weissen Hintergrund
        # enthalten. Nahezu weisse Pixel werden transparent; vorhandene
        # Transparenz bleibt erhalten.
        source = fitz.Pixmap(str(asset_path))
        if source.colorspace is None:
            raise RuntimeError('Die Stempelgrafik besitzt keinen lesbaren Farbraum.')
        if int(source.colorspace.n) != 3:
            source = fitz.Pixmap(fitz.csRGB, source)
        stamp = fitz.Pixmap(source, 1)
        samples = bytes(stamp.samples)
        channels = int(stamp.n)
        if channels != 4:
            raise RuntimeError('Die Stempelgrafik konnte nicht in RGBA umgewandelt werden.')
        alpha = bytearray(stamp.width * stamp.height)
        ai = 0
        for pos in range(0, len(samples), channels):
            red, green, blue, original_alpha = samples[pos:pos + 4]
            minimum = min(red, green, blue)
            value = original_alpha
            if minimum >= 245:
                value = 0
            elif minimum > 220:
                value = round(value * (245 - minimum) / 25.0)
            alpha[ai] = max(0, min(255, value))
            ai += 1
        stamp.set_alpha(bytes(alpha), premultiply=0)
        stamp.save(str(clean_png))
        image_width = float(stamp.width)
        image_height = float(stamp.height)
        if image_width <= 0 or image_height <= 0:
            raise RuntimeError('Die Stempelgrafik hat ungueltige Abmessungen.')

        document = fitz.open(str(pdf_path))
        page_count = len(document)
        if page_count < 1:
            raise RuntimeError('Die PDF enthaelt keine Seite.')
        if getattr(document, 'needs_pass', False):
            raise RuntimeError('Die PDF ist kennwortgeschuetzt und kann nicht gestempelt werden.')

        page = document[0]
        page_width = float(page.rect.width)
        page_height = float(page.rect.height)
        # Position wie im bisherigen Bescheinigungsmodul, proportional auf die
        # tatsaechliche A4-Seitengroesse abgebildet.
        scale_x = page_width / 595.28
        scale_y = page_height / 841.89
        left = 220.0 * scale_x
        top = 575.0 * scale_y
        stamp_width = 210.0 * scale_x
        stamp_height = stamp_width * image_height / image_width
        max_bottom = page_height - (8.0 * scale_y)
        if top + stamp_height > max_bottom:
            stamp_height = max(1.0, max_bottom - top)
        rect = fitz.Rect(left, top, left + stamp_width, top + stamp_height)
        page.insert_image(
            rect,
            filename=str(clean_png),
            keep_proportion=True,
            overlay=True,
        )
        document.save(str(out), garbage=3, deflate=True)
        document.close()
        document = None

        if not out.exists() or out.stat().st_size < 100:
            raise RuntimeError('Es wurde keine gueltige gestempelte PDF erzeugt.')
        check = fitz.open(str(out))
        try:
            if len(check) != page_count:
                raise RuntimeError('Die Seitenzahl der PDF hat sich beim Stempeln veraendert.')
            if len(check) < 1:
                raise RuntimeError('Die gestempelte PDF enthaelt keine Seite.')
        finally:
            check.close()

        try:
            os.replace(out, pdf_path)
        except PermissionError:
            return False, 'Die PDF ist noch in einem PDF-Programm geoeffnet. Bitte PDF schliessen und erneut freigeben.'
        out = None
        return True, ''
    except Exception as exc:
        return False, 'Direktes PDF-Stempeln fehlgeschlagen: ' + str(exc)
    finally:
        if document is not None:
            try:
                document.close()
            except Exception:
                pass
        for temporary in (out, clean_png):
            if not temporary:
                continue
            try:
                Path(temporary).unlink()
            except Exception:
                pass


def _form_fill_score(path):
    try:
        with zipfile.ZipFile(path,'r') as z:
            root=ET.fromstring(z.read('word/document.xml'))
        parents={c:p for p in root.iter() for c in p}
        score=0
        for ff in root.iter(Q('ffData')):
            cb=ff.find(Q('checkBox'))
            if cb is not None:
                checked=cb.find(Q('checked'))
                default=cb.find(Q('default'))
                if ((checked is not None and checked.get(Q('val')) in ('1','true','on')) or
                        (default is not None and default.get(Q('val')) in ('1','true','on'))):
                    score+=1
            elif _field_result_text(ff,parents).replace('\u2002',' ').strip():
                score+=1
        return score
    except Exception:
        return 9999


def _reset_docx_to_blank(path):
    """Restore the pristine backup, or clear all legacy form fields in place."""
    path=Path(path).resolve()
    if not path.exists():
        raise RuntimeError('Die Word-Datei wurde nicht gefunden.')
    backup=_safety_backup_path(path)
    token=datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
    temporary=path.with_name(path.stem+f'.pz1860_reset_{token}.docx')
    try:
        use_backup=(backup.exists() and
                    (_form_fill_score(backup)<=1 or _form_fill_score(backup)<_form_fill_score(path)))
        if use_backup:
            with zipfile.ZipFile(backup,'r') as check:
                if check.testzip() is not None:
                    raise RuntimeError('Die Sicherheitskopie der Vorlage ist beschädigt.')
            shutil.copy2(backup,temporary)
        else:
            # Fallback für Formulare, die bereits vor Update 1.8.6 ausgefüllt
            # wurden und noch keine unveränderte Sicherheitskopie besitzen.
            with zipfile.ZipFile(path,'r') as zin:
                root=ET.fromstring(zin.read('word/document.xml'))
                parents={c:p for p in root.iter() for c in p}
                for ff in list(root.iter(Q('ffData'))):
                    cb=ff.find(Q('checkBox'))
                    if cb is not None:
                        for name in ('default','checked'):
                            node=cb.find(Q(name))
                            if node is not None:
                                node.set(Q('val'),'0')
                        _set_form_result(ff,'☐',parents)
                    else:
                        _set_form_result(ff,'',parents)
                new_xml=ET.tostring(root,encoding='utf-8',xml_declaration=True)
                with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as zout:
                    for item in zin.infolist():
                        content=new_xml if item.filename=='word/document.xml' else zin.read(item.filename)
                        zout.writestr(item,content)
        with zipfile.ZipFile(temporary,'r') as check:
            if check.testzip() is not None:
                raise RuntimeError('Die zurückgesetzte Word-Datei ist beschädigt.')
        os.replace(temporary,path)
        return bool(use_backup)
    except PermissionError as exc:
        raise RuntimeError('Die Word-Datei ist noch geöffnet. Bitte Word schließen und erneut versuchen.') from exc
    finally:
        try: temporary.unlink()
        except Exception: pass


def _send_to_recycle_bin(path):
    """Move a file to the Windows Recycle Bin without extra UI."""
    path=Path(path).resolve()
    if not path.exists():
        return False
    if os.name!='nt':
        path.unlink()
        return True
    import ctypes
    from ctypes import wintypes
    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_=[
            ('hwnd',wintypes.HWND),('wFunc',wintypes.UINT),('pFrom',wintypes.LPCWSTR),
            ('pTo',wintypes.LPCWSTR),('fFlags',wintypes.WORD),
            ('fAnyOperationsAborted',wintypes.BOOL),('hNameMappings',ctypes.c_void_p),
            ('lpszProgressTitle',wintypes.LPCWSTR),
        ]
    operation=SHFILEOPSTRUCTW()
    operation.wFunc=3  # FO_DELETE
    operation.pFrom=str(path)+'\0\0'
    operation.fFlags=0x0040|0x0010|0x0004|0x0400  # ALLOWUNDO, NOCONFIRMATION, SILENT, NOERRORUI
    result=ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))
    if result!=0 or operation.fAnyOperationsAborted:
        raise RuntimeError('Die PDF konnte nicht in den Windows-Papierkorb verschoben werden.')
    return True




def open_wordforms(app):
    data=_md._masterdata_row(app)
    db,_,BG,PANEL,INK,MUTED,ACCENT,DARK=_md._base._env(app)
    w=tk.Toplevel(app)
    w.title('Word-Bescheinigungen ausfüllen')
    w.geometry('1180x760')
    w.configure(bg=BG)
    w.transient(app)

    head=tk.Frame(w,bg=BG); head.pack(fill='x',padx=22,pady=(18,10))
    tk.Label(head,text='WORD-BESCHEINIGUNGEN',bg=BG,fg=INK,font=('Segoe UI Semibold',18)).pack(anchor='w')
    tk.Label(head,text='Quelle: Ordner Bescheinigungen · Word-Datei wird direkt aktualisiert · PDF wird direkt daneben gespeichert',bg=BG,fg=MUTED).pack(anchor='w',pady=(5,0))

    info=tk.Frame(w,bg=PANEL,bd=1,relief='solid'); info.pack(fill='x',padx=22,pady=(0,10))
    summary=[
        ('Bauvorhaben',data.get('project_title','')),
        ('Bauort',_address(data.get('project_street'),data.get('project_zip'),data.get('project_city'))),
        ('Bauherr',data.get('client_name','')),
        ('Architekt',data.get('architect_name','') or data.get('architect_firm','')),
    ]
    for i,(k,v) in enumerate(summary):
        row=tk.Frame(info,bg=PANEL); row.pack(fill='x',padx=14,pady=(8 if i==0 else 2,8 if i==len(summary)-1 else 2))
        tk.Label(row,text=k,width=16,anchor='w',bg=PANEL,fg=MUTED).pack(side='left')
        tk.Label(row,text=v or '—',anchor='w',bg=PANEL,fg=INK,font=('Segoe UI Semibold',10)).pack(side='left',fill='x',expand=True)

    box=tk.Frame(w,bg=PANEL,bd=1,relief='solid'); box.pack(fill='both',expand=True,padx=22,pady=(0,10))
    tree=ttk.Treeview(box,columns=('Datei','Ordner','Felder','Status'),show='headings',selectmode='extended')
    widths=(360,330,170,260)
    for c,wi in zip(('Datei','Ordner','Felder','Status'),widths):
        tree.heading(c,text=c); tree.column(c,width=wi,anchor='w')
    tree.pack(side='left',fill='both',expand=True,padx=(10,0),pady=10)
    sb=ttk.Scrollbar(box,orient='vertical',command=tree.yview); sb.pack(side='right',fill='y',padx=(0,10),pady=10); tree.configure(yscrollcommand=sb.set)

    docs={}
    roots=_bescheinigungen_roots(app)
    for root,src,rel in _documents(app):
        check=inspect_docx(src,data)
        if check['ok']:
            fields=f"{check['mapped']} automatisch"
            if check.get('manual'):
                fields+=f" + {check['manual']} Zusatzangaben"
        else:
            fields='Fehler'
        status=('bereit' if check['ok'] and check['mapped'] else ('keine passenden Formularfelder' if check['ok'] else check['error']))
        iid=tree.insert('','end',values=(src.name,str(rel.parent) if str(rel.parent)!='.' else 'Bescheinigungen',fields,status))
        docs[iid]={'root':root,'src':src,'rel':rel,'check':check,'dst':None,'pdf':None,'pdf_error':''}

    status_lbl=tk.Label(w,bg=BG,fg=MUTED,anchor='w')
    if roots:
        status_lbl.configure(text=f'{len(docs)} Word-Datei(en) in {len(roots)} Bescheinigungen-Ordner(n) gefunden')
    else:
        status_lbl.configure(text='Kein Ordner Bescheinigungen im aktuellen Projekt gefunden.')
    status_lbl.pack(fill='x',padx=22,pady=(0,8))

    def _fill(ids):
        if not ids:
            messagebox.showinfo('Word-Bescheinigungen','Bitte mindestens eine Word-Datei auswählen.',parent=w)
            return
        made=[]; pdf_made=[]; skipped=[]; failed=[]
        for iid in ids:
            item=docs.get(iid)
            if not item: continue
            if not item['check'].get('mapped'):
                skipped.append(item['src'].name); continue
            dst=_output_path(item['root'],item['src'],item['rel'])
            try:
                extra=_prompt_extra_values(w,item['src'],BG,PANEL,INK,MUTED,ACCENT,DARK)
                if extra is None:
                    skipped.append(item['src'].name); continue
                n=fill_docx(item['src'],dst,data,extra_values=extra)
                if n:
                    item['dst']=dst; made.append(dst)
                    pdf=_pdf_output_path(item['root'],item['src'],item['rel'])
                    pdf_ok,pdf_err=_export_pdf_with_word(dst,pdf)
                    item['pdf']=pdf if pdf_ok else None
                    item['pdf_error']=pdf_err
                    if pdf_ok:
                        pdf_made.append(pdf)
                    vals=list(tree.item(iid,'values'))
                    vals[3]=(f'{n} automatisch · PDF erstellt' if pdf_ok else f'{n} automatisch · PDF-Fehler')
                    tree.item(iid,values=vals)
                else:
                    skipped.append(item['src'].name)
            except Exception as e:
                failed.append(f'{item["src"].name}: {e}')
                vals=list(tree.item(iid,'values')); vals[3]='Fehler'; tree.item(iid,values=vals)
        status_lbl.configure(text=f'{len(made)} Word-Datei(en) aktualisiert · PDF direkt daneben')
        msg=[]
        if made: msg.append(f'{len(made)} Word-Datei(en) direkt aktualisiert.')
        if pdf_made: msg.append(f'{len(pdf_made)} PDF-Datei(en) automatisch erzeugt.')
        if made and len(pdf_made)!=len(made):
            errs=[str(x.get('pdf_error','') or '').strip() for x in docs.values() if x.get('pdf_error')]
            detail=(errs[0] if errs else 'Unbekannter PDF-Fehler')
            msg.append('Bei mindestens einer Datei konnte Word kein PDF erzeugen.\nGrund: '+detail)
        if skipped: msg.append(f'{len(skipped)} Datei(en) ohne passende/gefüllte Felder übersprungen.')
        if failed: msg.append('Fehler:\n'+'\n'.join(failed[:5]))
        if made:
            msg.append('\nPDF-Datei liegt jeweils direkt neben dem Word-Formular.')
        messagebox.showinfo('Word-Bescheinigungen','\n'.join(msg) or 'Keine Datei geändert.',parent=w)

    def fill_selected():
        ids=list(tree.selection())
        _fill(ids)
        if len(ids)==1:
            item=docs.get(ids[0])
            if item and item.get('dst') and item['dst'].exists():
                _open_generated(item['dst'])

    def fill_all():
        _fill(list(docs.keys()))

    def reset_and_refill():
        sel=list(tree.selection())
        if len(sel)!=1:
            messagebox.showinfo('Löschen und neu ausfüllen','Bitte genau eine Bescheinigung auswählen.',parent=w)
            return
        iid=sel[0]; item=docs.get(iid)
        if not item:
            return
        docx=Path(item['src']); pdf=docx.with_suffix('.pdf')
        if not messagebox.askyesno(
            'Löschen und neu ausfüllen',
            'Die fehlerhafte PDF wird in den Windows-Papierkorb verschoben.\n'
            'Die Word-Bescheinigung wird auf die leere Vorlage zurückgesetzt.\n\n'
            'Danach öffnet sich das Ausfüllen sofort erneut.\n\nFortfahren?',
            parent=w,
        ):
            return
        try:
            if pdf.exists():
                _send_to_recycle_bin(pdf)
            restored=_reset_docx_to_blank(docx)
            item['dst']=None; item['pdf']=None; item['pdf_error']=''
            item['check']=inspect_docx(docx,data)
            fields=f"{item['check'].get('mapped',0)} automatisch"
            if item['check'].get('manual'):
                fields+=f" + {item['check']['manual']} Zusatzangaben"
            vals=list(tree.item(iid,'values')); vals[2]=fields; vals[3]='zurückgesetzt · bereit zum Ausfüllen'; tree.item(iid,values=vals)
            status_lbl.configure(text='Bescheinigung zurückgesetzt. Die fehlerhafte PDF wurde gelöscht.')
            _fill([iid])
            if item.get('dst') and item['dst'].exists():
                _open_generated(item['dst'])
        except Exception as exc:
            messagebox.showerror('Löschen und neu ausfüllen',str(exc),parent=w)

    def open_original(event=None):
        sel=tree.selection()
        if sel:
            app.open_external_path(str(docs[sel[0]]['src']))

    def _open_generated(path):
        # PZ_WORD_OUTPUT_DIRECT_V1701: erzeugte Word-Datei unter Windows direkt öffnen.
        try:
            if hasattr(__import__('os'),'startfile'):
                os.startfile(str(path))
            else:
                app.open_external_path(str(path))
            return True
        except Exception as e:
            try:
                app.open_external_path(str(path))
                return True
            except Exception:
                messagebox.showerror('Word-Bescheinigungen',f'Datei konnte nicht geöffnet werden.\n\n{path}\n\n{e}',parent=w)
                return False

    def open_output():
        sel=tree.selection()
        if sel and docs[sel[0]].get('dst') and docs[sel[0]]['dst'].exists():
            _open_generated(docs[sel[0]]['dst'])
            return
        for item in docs.values():
            if item.get('dst') and item['dst'].exists():
                _open_generated(item['dst']); return
        if roots:
            app.open_external_path(str(roots[0]))

    def open_pdf():
        sel=tree.selection()
        if sel and docs[sel[0]].get('pdf') and docs[sel[0]]['pdf'].exists():
            _open_generated(docs[sel[0]]['pdf'])
            return
        for item in docs.values():
            if item.get('pdf') and item['pdf'].exists():
                _open_generated(item['pdf']); return
        messagebox.showinfo('Word-Bescheinigungen','Für die aktuelle Auswahl wurde noch keine PDF-Datei erzeugt.',parent=w)

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
    foot=tk.Frame(w,bg=BG); foot.pack(fill='x',padx=22,pady=(0,16))
    utility=tk.Frame(foot,bg=BG); utility.pack(fill='x',pady=(0,8))
    tk.Button(utility,text='WORD ÖFFNEN',command=open_output,bg='#e7e4dc',fg=INK,bd=0,padx=14,pady=8).pack(side='left')
    tk.Button(utility,text='PDF ÖFFNEN',command=open_pdf,bg='#e7e4dc',fg=INK,bd=0,padx=14,pady=8).pack(side='left',padx=(8,0))
    tk.Button(utility,text='STEMPEL EINRICHTEN',command=configure_stamp,bg='#e7e4dc',fg=INK,bd=0,padx=14,pady=8).pack(side='left',padx=(8,0))
    tk.Button(utility,text='LÖSCHEN UND NEU AUSFÜLLEN',command=reset_and_refill,bg='#e7e4dc',fg=INK,bd=0,padx=14,pady=8).pack(side='left',padx=(8,0))
    actions=tk.Frame(foot,bg=BG); actions.pack(fill='x')
    tk.Button(actions,text='SCHLIESSEN',command=w.destroy,bg='#e7e4dc',fg=INK,bd=0,padx=14,pady=9).pack(side='right')
    tk.Button(actions,text='FREIGEBEN & STEMPELN',command=release_and_stamp,bg=ACCENT,fg='white',bd=0,padx=16,pady=9).pack(side='right',padx=8)
    tk.Button(actions,text='ALLE AUSFÜLLEN',command=fill_all,bg=ACCENT,fg='white',bd=0,padx=16,pady=9).pack(side='right',padx=8)
    tk.Button(actions,text='MARKIERTE AUSFÜLLEN',command=fill_selected,bg=DARK,fg='white',bd=0,padx=16,pady=9).pack(side='right')
    return w
