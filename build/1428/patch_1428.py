from pathlib import Path
import datetime
import py_compile
import shutil

APP=Path(__file__).resolve().parent/'app.py'

CONTEXT_HELPER = r'''        def _position_context_plan_files(folder,pos):
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
'''


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.28"' in s:
        return 0
    if 'APP_VERSION = "1.4.27"' not in s:
        raise RuntimeError('Update 1.4.28 erwartet Projektzentrale 1.4.27. Es wurde nichts verändert.')
    original=s
    s=s.replace('APP_VERSION = "1.4.27"','APP_VERSION = "1.4.28"',1)

    start=s.find('        def _position_context_plan_files(folder,pos):')
    end=s.find('        def _position_pdf_content_files(folder,pos):',start)
    if start<0 or end<0:
        raise RuntimeError('1.4.28 Marker für Plan-Kandidaten fehlt.')
    s=s[:start]+CONTEXT_HELPER+'\n'+s[end:]

    s=s.replace(
        'Hinweis 1.4.27: Zusätzlich werden eindeutig benannte Positionspläne als mögliche Zuordnung angezeigt, auch wenn ein CAD-PDF keinen auslesbaren Text enthält. Exakte Dateinamen-/PDF-Treffer bleiben höher bewertet; mögliche Plan-Zuordnungen sind ausdrücklich gekennzeichnet.',
        'Hinweis 1.4.28: Plan-Kandidaten werden robuster erkannt. Auch Schreibweisen wie Pos.-Plan, Pos Plan oder Positionsplan sowie Dateien in plan-/CAD-typischen Ordnern werden als mögliche Zuordnung angeboten. Exakte Treffer bleiben höher bewertet.'
    )
    s=s.replace(
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb, Windows-Dateizuordnungen und Projektdateien werden ausschließlich read-only gelesen. Positionsakte 1.4.27 ergänzt mögliche Positionsplan-Zuordnungen für CAD-PDFs ohne auslesbaren Text; mb-Daten und Registry bleiben unverändert.',
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb, Windows-Dateizuordnungen und Projektdateien werden ausschließlich read-only gelesen. Positionsakte 1.4.28 normalisiert Planbezeichnungen und bietet zusätzlich planartige Projektdateien als mögliche Zuordnung an; mb-Daten und Registry bleiben unverändert.'
    )

    required=(
        'APP_VERSION = "1.4.28"',
        'def _position_context_plan_files(folder,pos)',
        "('pos' in token_set and 'plan' in token_set)",
        'Plan – mögliche Zuordnung',
        'Positionsplan – mögliche Zuordnung',
        'def _position_pdf_content_files(folder,pos)',
    )
    if not all(x in s for x in required):
        raise RuntimeError('Patch-Ergebnis 1.4.28 unvollständig. Es wurde nichts verändert.')
    if s==original:
        raise RuntimeError('Keine Änderung erzeugt.')

    tmp=APP.with_name('app.py.1428.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.v1427_vor_1428_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp.replace(APP)
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1428_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        print('FEHLER:',e)
        raise SystemExit(1)
