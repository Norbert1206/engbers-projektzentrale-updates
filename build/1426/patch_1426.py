from pathlib import Path
import datetime
import py_compile
import shutil

APP=Path(__file__).resolve().parent/'app.py'

FILE_HELPERS = r'''        _position_project_files_cache={}
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
'''


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.26"' in s:
        return 0
    if 'APP_VERSION = "1.4.25"' not in s:
        raise RuntimeError('Update 1.4.26 erwartet Projektzentrale 1.4.25. Es wurde nichts verändert.')
    original=s
    s=s.replace('APP_VERSION = "1.4.25"','APP_VERSION = "1.4.26"',1)

    start=s.find('        _position_project_files_cache={}')
    end=s.find('        def _detail_add_link(text,label,path,tag_index):',start)
    if start<0 or end<0:
        raise RuntimeError('1.4.26 Marker für Positionsdatei-Helfer fehlt.')
    s=s[:start]+FILE_HELPERS+'\n'+s[end:]

    old="""                for _hit in _position_project_files(folder,r.get('pos')):
                    try:_key=str(Path(_hit[3]).resolve()).lower()
                    except Exception:_key=str(_hit[3]).lower()
                    if _key not in _seen_files:
                        matches.append(_hit); _seen_files.add(_key)
                matches.sort(key=lambda _h:((_h[0] if len(_h)>0 else 0),(_h[1] if len(_h)>1 else 0)),reverse=True)"""
    new="""                for _hit in _position_project_files(folder,r.get('pos')):
                    try:_key=str(Path(_hit[3]).resolve()).lower()
                    except Exception:_key=str(_hit[3]).lower()
                    if _key not in _seen_files:
                        matches.append(_hit); _seen_files.add(_key)
                for _hit in _position_pdf_content_files(folder,r.get('pos')):
                    try:_key=str(Path(_hit[3]).resolve()).lower()
                    except Exception:_key=str(_hit[3]).lower()
                    if _key not in _seen_files:
                        matches.append(_hit); _seen_files.add(_key)
                matches.sort(key=lambda _h:((_h[0] if len(_h)>0 else 0),(_h[1] if len(_h)>1 else 0)),reverse=True)"""
    if old not in s:
        raise RuntimeError('1.4.26 Marker für kombinierte Dateizuordnung fehlt.')
    s=s.replace(old,new,1)

    s=s.replace(
        'Hinweis 1.4.25: Die Positionsakte durchsucht jetzt zusätzlich den gesamten Projektordner nach Dateien mit exakt passender Positionskennung und ordnet sie automatisch den Gruppen Prüfstatik, Pläne/CAD, Eigene Nachweise oder Dokumente zu. Der mb-Start endet stabil im richtigen BauStatik-/MicroFe-Register.',
        'Hinweis 1.4.26: Die Positionsakte durchsucht jetzt wirklich den kompletten Engbers-Projektordner. Zusätzlich werden PDF-Inhalte read-only nach der ausgewählten Position durchsucht, sodass z. B. ein Positionsplan auch ohne Positionsnummer im Dateinamen zugeordnet werden kann.'
    )
    s=s.replace(
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb, Windows-Dateizuordnungen und Projektdateien werden ausschließlich read-only gelesen. Positionsakte 1.4.25 ergänzt eine rekursive, positionsgenaue Dateizuordnung; mb-Daten und Registry bleiben unverändert.',
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb, Windows-Dateizuordnungen und Projektdateien werden ausschließlich read-only gelesen. Positionsakte 1.4.26 durchsucht den kompletten Projektbaum und kann textbasierte PDFs positionsgenau zuordnen; mb-Daten und Registry bleiben unverändert.'
    )

    required=(
        'APP_VERSION = "1.4.26"',
        'def _position_project_root(folder)',
        'def _position_pdf_content_files(folder,pos)',
        "from pypdf import PdfReader as Reader",
        "from PyPDF2 import PdfReader as Reader",
        "import fitz",
        "for _hit in _position_pdf_content_files(folder,r.get('pos'))",
        '[Treffer im PDF]',
        '• ProjektManager öffnen (nur Projekt)',
    )
    if not all(x in s for x in required):
        raise RuntimeError('Patch-Ergebnis 1.4.26 unvollständig. Es wurde nichts verändert.')
    if s==original:
        raise RuntimeError('Keine Änderung erzeugt.')

    tmp=APP.with_name('app.py.1426.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.v1425_vor_1426_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp.replace(APP)
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1426_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        print('FEHLER:',e)
        raise SystemExit(1)
