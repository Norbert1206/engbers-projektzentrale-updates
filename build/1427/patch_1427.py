from pathlib import Path
import datetime
import py_compile
import shutil

APP=Path(__file__).resolve().parent/'app.py'

CONTEXT_HELPER = r'''        def _position_context_plan_files(folder,pos):
            """Return likely Positionsplan files even when the PDF itself has no searchable text.

            Many CAD-exported PDFs contain outlined/vector text and therefore cannot be
            matched reliably by PDF text extraction. Files/folders clearly named as a
            Positionsplan are useful context for a selected position and are shown as a
            possible assignment, never as an exact content hit.
            """
            try:
                import os, re
                from pathlib import Path
                base=_position_project_root(folder)
                wanted=str(pos or '').strip()
                if not wanted or not base.exists():
                    return []
                strong_terms=(
                    'positionsplan','positions-plan','positions_plan','positions plan',
                    'positionspläne','positionsplaene','posplan','pos-plan','pos_plan','pos plan',
                    'tragwerksplan','tragwerks-plan','statikplan','statik-plan'
                )
                allowed={'.pdf','.dwg','.dxf','.dgn','.ifc','.plt','.hpgl'}
                skip_dirs={'fem','__pycache__','.git','.svn','$recycle.bin','backup','backups','sicherung','sicherungen'}
                parts=re.findall(r'[A-Z]+|[0-9]+',wanted.upper())
                head=parts[0] if parts else ''
                floor_terms=()
                if head=='E': floor_terms=(' eg','eg ','erdgeschoss','über eg','ueber eg')
                elif head=='1': floor_terms=(' og','og ','obergeschoss','über og','ueber og')
                elif head=='F': floor_terms=('fundament','sohle','bodenplatte','gründung','gruendung')
                elif head=='G': floor_terms=('garage',)
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
                        try:
                            rel=str(p.relative_to(base))
                            low=(' '+rel.lower().replace('_',' ').replace('-',' ')+' ')
                        except Exception:
                            rel=str(p); low=(' '+str(p).lower()+' ')
                        compact=str(rel).lower()
                        if not any(t in compact for t in strong_terms):
                            continue
                        score=45
                        if p.suffix.lower()=='.pdf': score+=5
                        if any(t in low for t in floor_terms): score+=25
                        if any(t in p.name.lower() for t in strong_terms): score+=15
                        try: ts=p.stat().st_mtime
                        except Exception: ts=0
                        result.append((score,ts,'Pläne / CAD',p,rel+'  [Positionsplan – mögliche Zuordnung]'))
                    if scanned>50000:
                        break
                result.sort(key=lambda x:(x[0],x[1]),reverse=True)
                return result[:12]
            except Exception:
                return []
'''


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.27"' in s:
        return 0
    if 'APP_VERSION = "1.4.26"' not in s:
        raise RuntimeError('Update 1.4.27 erwartet Projektzentrale 1.4.26. Es wurde nichts verändert.')
    original=s
    s=s.replace('APP_VERSION = "1.4.26"','APP_VERSION = "1.4.27"',1)

    marker='        def _position_pdf_content_files(folder,pos):'
    if marker not in s:
        raise RuntimeError('1.4.27 Marker für PDF-Positionssuche fehlt.')
    if 'def _position_context_plan_files' not in s:
        s=s.replace(marker,CONTEXT_HELPER+'\n'+marker,1)

    old="""                for _hit in _position_pdf_content_files(folder,r.get('pos')):
                    try:_key=str(Path(_hit[3]).resolve()).lower()
                    except Exception:_key=str(_hit[3]).lower()
                    if _key not in _seen_files:
                        matches.append(_hit); _seen_files.add(_key)
                matches.sort(key=lambda _h:((_h[0] if len(_h)>0 else 0),(_h[1] if len(_h)>1 else 0)),reverse=True)"""
    new="""                for _hit in _position_pdf_content_files(folder,r.get('pos')):
                    try:_key=str(Path(_hit[3]).resolve()).lower()
                    except Exception:_key=str(_hit[3]).lower()
                    if _key not in _seen_files:
                        matches.append(_hit); _seen_files.add(_key)
                for _hit in _position_context_plan_files(folder,r.get('pos')):
                    try:_key=str(Path(_hit[3]).resolve()).lower()
                    except Exception:_key=str(_hit[3]).lower()
                    if _key not in _seen_files:
                        matches.append(_hit); _seen_files.add(_key)
                matches.sort(key=lambda _h:((_h[0] if len(_h)>0 else 0),(_h[1] if len(_h)>1 else 0)),reverse=True)"""
    if old not in s:
        raise RuntimeError('1.4.27 Marker für kombinierte Dateizuordnung fehlt.')
    s=s.replace(old,new,1)

    s=s.replace(
        'Hinweis 1.4.26: Die Positionsakte durchsucht jetzt wirklich den kompletten Engbers-Projektordner. Zusätzlich werden PDF-Inhalte read-only nach der ausgewählten Position durchsucht, sodass z. B. ein Positionsplan auch ohne Positionsnummer im Dateinamen zugeordnet werden kann.',
        'Hinweis 1.4.27: Zusätzlich werden eindeutig benannte Positionspläne als mögliche Zuordnung angezeigt, auch wenn ein CAD-PDF keinen auslesbaren Text enthält. Exakte Dateinamen-/PDF-Treffer bleiben höher bewertet; mögliche Plan-Zuordnungen sind ausdrücklich gekennzeichnet.'
    )
    s=s.replace(
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb, Windows-Dateizuordnungen und Projektdateien werden ausschließlich read-only gelesen. Positionsakte 1.4.26 durchsucht den kompletten Projektbaum und kann textbasierte PDFs positionsgenau zuordnen; mb-Daten und Registry bleiben unverändert.',
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb, Windows-Dateizuordnungen und Projektdateien werden ausschließlich read-only gelesen. Positionsakte 1.4.27 ergänzt mögliche Positionsplan-Zuordnungen für CAD-PDFs ohne auslesbaren Text; mb-Daten und Registry bleiben unverändert.'
    )

    required=(
        'APP_VERSION = "1.4.27"',
        'def _position_context_plan_files(folder,pos)',
        'Positionsplan – mögliche Zuordnung',
        "for _hit in _position_context_plan_files(folder,r.get('pos'))",
        'def _position_pdf_content_files(folder,pos)',
        '• ProjektManager öffnen (nur Projekt)',
    )
    if not all(x in s for x in required):
        raise RuntimeError('Patch-Ergebnis 1.4.27 unvollständig. Es wurde nichts verändert.')
    if s==original:
        raise RuntimeError('Keine Änderung erzeugt.')

    tmp=APP.with_name('app.py.1427.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.v1426_vor_1427_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp.replace(APP)
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1427_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        print('FEHLER:',e)
        raise SystemExit(1)
