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
OLD='1.7.18'
NEW='1.8.0'
MARK='PZ_WORD_SINGLE_COM_PIPELINE_V1800'

NEW_FILL = r'''def fill_docx(src, dst, data):
    # PZ_WORD_SINGLE_COM_PIPELINE_V1800
    # 1.8.0: XML dient nur noch zum Erkennen/Reihen der Legacy-Formularfelder.
    # Geschrieben, gespeichert und als PDF exportiert wird ausschliesslich durch
    # EINE frisch gestartete Microsoft-Word-COM-Instanz.
    src=Path(src).resolve()
    dst=Path(dst).resolve()
    vals=_values(data)

    if not src.exists():
        raise RuntimeError('Word-Datei wurde nicht gefunden.')

    # Formularplan aus OOXML lesen, aber das DOCX niemals per XML veraendern.
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
                plan.append({'index':index,'kind':'checkbox','value':True,'key':'primary_checkbox'})
            continue
        key=_classify(ff,parents)
        value=vals.get(key) if key else ''
        if key and value:
            plan.append({'index':index,'kind':'text','value':str(value),'key':key})

    if not plan:
        return 0

    # Sicherheitskopie ausserhalb des Projektordners, wie bisher.
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
        # Arbeitskopien liegen nur temporaer im Projektordner und werden nach
        # Erfolg atomar an die echten Dateinamen gesetzt.
        token=datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
        work=dst.parent/(dst.stem+f'.pz1800_work_{token}.docx')
        normalized=dst.parent/(dst.stem+f'.pz1800_normalized_{token}.docx')
        pdf_tmp=dst.parent/(dst.stem+f'.pz1800_pdf_{token}.pdf')
        shutil.copy2(src,work)

        fd,plan_file=tempfile.mkstemp(prefix='engbers_word_plan_',suffix='.json')
        os.close(fd)
        Path(plan_file).write_text(json.dumps(plan,ensure_ascii=False),encoding='utf-8')

        ps=r"""param(
 [Parameter(Mandatory=$true)][string]$WorkPath,
 [Parameter(Mandatory=$true)][string]$NormalizedPath,
 [Parameter(Mandatory=$true)][string]$PdfPath,
 [Parameter(Mandatory=$true)][string]$PlanPath
)
$ErrorActionPreference='Stop'
$word=$null
$doc=$null
$stage='start'
try {
  $stage='plan'
  $plan = Get-Content -LiteralPath $PlanPath -Raw -Encoding UTF8 | ConvertFrom-Json
  if($plan -isnot [System.Array]) { $plan=@($plan) }

  $stage='word-start'
  $word = New-Object -ComObject Word.Application
  $word.Visible = $false
  $word.DisplayAlerts = 0

  $missing=[System.Reflection.Missing]::Value
  $stage='open-repair'
  try {
    # OpenNoRepairDialog: OpenAndRepair ist Parameter 13.
    $doc = $word.Documents.OpenNoRepairDialog(
      $WorkPath,
      $missing,
      $false,
      $false,
      $missing,
      $missing,
      $false,
      $missing,
      $missing,
      $missing,
      $missing,
      $false,
      $true,
      $missing,
      $true,
      $missing
    )
  } catch {
    $stage='open-normal'
    $doc = $word.Documents.Open($WorkPath,$false,$false,$false)
  }

  if(-not $doc){ throw 'Microsoft Word konnte die Arbeitskopie nicht öffnen.' }

  $stage='formfields'
  $count=[int]$doc.FormFields.Count
  $maxIndex=0
  foreach($item in $plan){
    $idx=[int]$item.index
    if($idx -gt $maxIndex){ $maxIndex=$idx }
  }
  if($count -lt $maxIndex){
    throw ('Word meldet nur '+$count+' Legacy-Formularfelder; benötigt wird Feld '+$maxIndex+'.')
  }

  $stage='fill'
  foreach($item in $plan){
    $idx=[int]$item.index
    $ff=$doc.FormFields.Item($idx)
    if([string]$item.kind -eq 'checkbox'){
      $ff.CheckBox.Value = [bool]$item.value
    } else {
      $ff.Result = [string]$item.value
    }
  }

  $stage='save-normalized'
  # 16 = wdFormatDocumentDefault (.docx). SaveAs2 zwingt Word, das Dokument
  # selbst sauber neu zu serialisieren, statt unsererseits OOXML zu schreiben.
  $doc.SaveAs2($NormalizedPath,16)

  $stage='export-pdf'
  # 17 = wdExportFormatPDF
  $doc.ExportAsFixedFormat($PdfPath,17)

  $stage='close'
  $doc.Close($false)
  $doc=$null
  $word.Quit()
  $word=$null

  if(-not (Test-Path -LiteralPath $NormalizedPath)){
    throw 'Word hat die normalisierte DOCX nicht erzeugt.'
  }
  if(-not (Test-Path -LiteralPath $PdfPath)){
    throw 'Word hat die PDF nicht erzeugt.'
  }
  if((Get-Item -LiteralPath $PdfPath).Length -lt 100){
    throw 'Die erzeugte PDF ist leer oder unvollständig.'
  }
  Write-Output ('OK|'+$count+'|'+$maxIndex)
  exit 0
}
catch {
  $msg=$_.Exception.Message
  Write-Error ('STUFE='+$stage+' | '+$msg)
  exit 1
}
finally {
  if($doc){ try { $doc.Close($false) } catch {} }
  if($word){ try { $word.Quit() } catch {} }
  if($doc){ try { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($doc) } catch {} }
  if($word){ try { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($word) } catch {} }
  [GC]::Collect()
  [GC]::WaitForPendingFinalizers()
}
"""
        fd,ps_file=tempfile.mkstemp(prefix='engbers_word_1800_',suffix='.ps1')
        os.close(fd)
        Path(ps_file).write_text(ps,encoding='utf-8-sig')

        cp=subprocess.run(
            ['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',ps_file,
             '-WorkPath',str(work),'-NormalizedPath',str(normalized),
             '-PdfPath',str(pdf_tmp),'-PlanPath',str(plan_file)],
            capture_output=True,text=True,timeout=75,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)
        )
        if cp.returncode!=0:
            detail=(cp.stderr or cp.stdout or '').strip()
            raise RuntimeError(detail or f'Word-Automatik Rückgabecode {cp.returncode}')

        if not normalized.exists() or normalized.stat().st_size<100:
            raise RuntimeError('Word hat keine gültige normalisierte DOCX erzeugt.')
        if not pdf_tmp.exists() or pdf_tmp.stat().st_size<100:
            raise RuntimeError('Word hat keine gültige PDF erzeugt.')

        # Erst jetzt die echten Projektdateien austauschen.
        os.replace(normalized,dst)
        normalized=None
        os.replace(pdf_tmp,pdf_path)
        pdf_tmp=None
        return len(plan)

    except subprocess.TimeoutExpired:
        raise RuntimeError('Microsoft Word hat den gemeinsamen Formular/PDF-Lauf nicht innerhalb von 75 Sekunden beendet.')
    finally:
        for p in (work,normalized,pdf_tmp,plan_file,ps_file):
            if not p:
                continue
            try: Path(p).unlink()
            except Exception: pass
'''

NEW_EXPORT = r'''def _export_pdf_with_word(docx_path, pdf_path):
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
    raise RuntimeError(f'1.8.0: Funktion {name} wurde nicht gefunden.')

def main():
    if not APP.exists() or not MOD.exists():
        raise RuntimeError('1.8.0: app.py oder wordforms_v1700.py wurde nicht gefunden.')

    app=APP.read_text(encoding='utf-8')
    mod=MOD.read_text(encoding='utf-8')
    cur=_version(app)

    if cur==NEW and MARK in mod:
        return 0
    if cur!=OLD:
        raise RuntimeError(f'Update 1.8.0 erwartet Projektzentrale {OLD}; gefunden: {cur or "unbekannt"}.')

    # json ist fuer den Formularplan neu.
    if '\nimport json\n' not in '\n'+mod:
        anchor='import copy\n'
        if anchor not in mod:
            raise RuntimeError('1.8.0: Importblock wurde nicht gefunden.')
        mod=mod.replace(anchor,anchor+'import json\n',1)

    mod=_replace_function(mod,'fill_docx',NEW_FILL)
    mod=_replace_function(mod,'_export_pdf_with_word',NEW_EXPORT)

    if MARK not in mod:
        raise RuntimeError('1.8.0: neuer Word-Pipeline-Marker fehlt.')

    app_new=re.sub(
        r'(APP_VERSION\s*=\s*)["\'][^"\']+["\']',
        lambda m:m.group(1)+'"'+NEW+'"',
        app,count=1
    ).replace('Projektzentrale 1.7.18','Projektzentrale 1.8.0')

    active_start=mod.find(MARK)
    active_end=mod.find('\ndef ',active_start)
    active=mod[active_start:active_end if active_end>0 else len(mod)]
    for required in (
        'FormFields.Item',
        'CheckBox.Value',
        '.Result =',
        'SaveAs2($NormalizedPath,16)',
        'ExportAsFixedFormat($PdfPath,17)',
        'OpenNoRepairDialog',
        'OpenAndRepair ist Parameter 13',
    ):
        if required not in active:
            raise RuntimeError('1.8.0: neuer Word-Baustein fehlt: '+required)
    for forbidden in ('Start-Process -FilePath $DocxPath -Verb Print','SendWait(','PrintToFile=$true','GetActiveObject'):
        if forbidden in active:
            raise RuntimeError('1.8.0: alter PDF/Attach-Weg ist noch aktiv: '+forbidden)

    chk1=APP.with_name('app.py.1800.check')
    chk2=MOD.with_name('wordforms_v1700.py.1800.check')
    try:
        chk1.write_text(app_new,encoding='utf-8')
        py_compile.compile(str(chk1),doraise=True)
        chk2.write_text(mod,encoding='utf-8')
        py_compile.compile(str(chk2),doraise=True)
    finally:
        for p in (chk1,chk2):
            try:p.unlink()
            except Exception:pass

    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for p in (APP,MOD):
        shutil.copy2(p,p.with_name(p.name+'.vor_1_8_0_'+stamp+'.bak'))

    t=APP.with_name('app.py.1800.tmp')
    t.write_text(app_new,encoding='utf-8')
    t.replace(APP)
    t=MOD.with_name('wordforms_v1700.py.1800.tmp')
    t.write_text(mod,encoding='utf-8')
    t.replace(MOD)

    APP.with_name('patch_1800_report.txt').write_text(
        'OK: Projektzentrale 1.8.0 installiert.\n'
        'Word-Automatik komplett neu aufgebaut: ein Word-Prozess fuellt Legacy-FormFields, speichert eine von Word normalisierte DOCX und erzeugt im selben Lauf die PDF.\n'
        'Keine XML-Schreibzugriffe, keine UI-Automation, kein PDF-Drucker, kein Anhaengen an bereits geoeffnete Word-Instanzen.\n',
        encoding='utf-8'
    )
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        try:
            APP.with_name('patch_1800_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception:
            pass
        raise
