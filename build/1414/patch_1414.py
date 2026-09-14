from pathlib import Path
import datetime
import py_compile
import shutil

APP=Path(__file__).resolve().parent/'app.py'


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.14"' in s:
        return 0
    if 'APP_VERSION = "1.4.13"' not in s:
        raise RuntimeError('Update 1.4.14 erwartet Projektzentrale 1.4.13. Es wurde nichts verändert.')
    original=s
    s=s.replace('APP_VERSION = "1.4.13"','APP_VERSION = "1.4.14"',1)

    # MicroFe databases use opaque internal filenames. Do not present that token
    # as if it were the human model name. Keep it visible as a separate Model-ID.
    old_micro="""                    if chosen is not None:
                        title=_db_title(chosen)
                        result={
                            'name':title or chosen.stem,
                            'source':str(chosen.relative_to(base)) if chosen.is_relative_to(base) else str(chosen),
                            'app':app,
                            'confidence':'position' if _db_has_position(chosen) else 'single',
                        }
"""
    new_micro="""                    if chosen is not None:
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
"""
    if old_micro not in s:
        raise RuntimeError('1.4.14 Marker für MicroFe-Modell fehlt.')
    s=s.replace(old_micro,new_micro,1)

    # Keep a stable ID field available for every result.
    s=s.replace("result={'name':'—','source':'—','app':app,'confidence':'fallback'}",
                "result={'name':'—','id':'','source':'—','app':app,'confidence':'fallback'}",1)
    s=s.replace("return {'name':'—','source':'—','app':'—','confidence':'error'}",
                "return {'name':'—','id':'','source':'—','app':'—','confidence':'error'}",1)

    old_bau="""                    result={
                        'name':title or fallback,
                        'source':str(source.relative_to(base)) if source is not None and source.is_relative_to(base) else (str(source) if source else '—'),
                        'app':app,
                        'confidence':'metadata' if title else 'container',
                    }
"""
    new_bau="""                    result={
                        'name':title or fallback,
                        'id':'',
                        'source':str(source.relative_to(base)) if source is not None and source.is_relative_to(base) else (str(source) if source else '—'),
                        'app':app,
                        'confidence':'metadata' if title else 'container',
                    }
"""
    if old_bau not in s:
        raise RuntimeError('1.4.14 Marker für BauStatik-Modell fehlt.')
    s=s.replace(old_bau,new_bau,1)

    old_meta="""                mb_model=_mb_model_for_position(folder,r)
                model_name=mb_model.get('name') or '—'
                model_source=mb_model.get('source') or '—'
                detail_text.insert('end',f'Position: {posid}\\nBezeichnung: {bez}\\n\\nmb-Projekt: {projekt}\\nmb-Modul: {modul}\\nmb-Anwendung: {mb_app}\\nmb-Modell: {model_name}\\nModellquelle: {model_source}\\nFachgruppe: {gruppe}\\nBerechnungsstatus: {status}\\n')
"""
    new_meta="""                mb_model=_mb_model_for_position(folder,r)
                model_name=mb_model.get('name') or '—'
                model_id=mb_model.get('id') or ''
                model_source=mb_model.get('source') or '—'
                model_id_line=f'Modell-ID: {model_id}\\n' if model_id else ''
                detail_text.insert('end',f'Position: {posid}\\nBezeichnung: {bez}\\n\\nmb-Projekt: {projekt}\\nmb-Modul: {modul}\\nmb-Anwendung: {mb_app}\\nmb-Modell: {model_name}\\n{model_id_line}Modellquelle: {model_source}\\nFachgruppe: {gruppe}\\nBerechnungsstatus: {status}\\n')
"""
    if old_meta not in s:
        raise RuntimeError('1.4.14 Marker für Modellanzeige fehlt.')
    s=s.replace(old_meta,new_meta,1)

    s=s.replace(
        'Hinweis 1.4.13: Positionsakte erkennt zusätzlich die konkrete mb-Modellquelle. MicroFe-Positionen werden der passenden FEM-Datenbank zugeordnet; BauStatik zeigt den Projekt-/Modellcontainer. Alle mb-Daten bleiben read-only.',
        'Hinweis 1.4.14: MicroFe-Modellquellen werden weiterhin positionsgenau erkannt. Interne mb-Datei-IDs werden jetzt sauber als Modell-ID getrennt vom lesbaren Modellnamen angezeigt. Alles bleibt read-only.'
    )
    s=s.replace(
        'Quelle: BSPos.mbdb, *.mbp und FEM/*.mbdb werden ausschließlich read-only gelesen. Positionsakte 1.4.13 zeigt Anwendung, Modellkennung und Modellquelle je Position; Dateizuordnung bleibt positionsgenau.',
        'Quelle: BSPos.mbdb, *.mbp und FEM/*.mbdb werden ausschließlich read-only gelesen. Positionsakte 1.4.14 trennt bei MicroFe lesbaren Modellnamen, interne Modell-ID und konkrete Modellquelle.'
    )

    required=(
        'APP_VERSION = "1.4.14"',
        "'name':title or 'MicroFe-Modell'",
        "'id':internal_id",
        "model_id_line=f'Modell-ID: {model_id}",
        'Modellquelle: {model_source}',
        'Startweg: ProjektManager → MicroFe',
        'def _mb_model_for_position',
    )
    if not all(x in s for x in required):
        raise RuntimeError('Patch-Ergebnis 1.4.14 unvollständig. Es wurde nichts verändert.')
    if s==original:
        raise RuntimeError('Keine Änderung erzeugt.')

    tmp=APP.with_name('app.py.1414.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.v1413_vor_1414_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp.replace(APP)
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1414_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        print('FEHLER:',e)
        raise SystemExit(1)
