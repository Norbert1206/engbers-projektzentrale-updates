from pathlib import Path
import datetime
import py_compile
import shutil

APP=Path(__file__).resolve().parent/'app.py'

START_HELPER = r'''        _mb_windows_start_cache=None
        def _mb_windows_start_info():
            """Read Windows file associations for mb project/model files.

            This is deliberately diagnostic only. It does not start a model and
            does not write to the registry. The result tells us whether Windows/
            mb exposes a supported handler for .mbp and .mbdb on this machine.
            """
            global _mb_windows_start_cache
            if _mb_windows_start_cache is not None:
                return _mb_windows_start_cache
            result={
                'project_handler':'nicht registriert',
                'project_command':'',
                'model_handler':'nicht registriert',
                'model_command':'',
            }
            try:
                import winreg, re
                def _default(path):
                    try:
                        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,path) as k:
                            value,_=winreg.QueryValueEx(k,None)
                            return str(value or '').strip()
                    except Exception:
                        return ''
                def _command(ext):
                    progid=_default(ext)
                    candidates=[]
                    if progid:
                        candidates.append(progid+r'\shell\open\command')
                    candidates.append(ext+r'\shell\open\command')
                    for key in candidates:
                        cmd=_default(key)
                        if cmd:
                            return progid,cmd
                    return progid,''
                def _handler(cmd,progid):
                    if cmd:
                        m=re.match(r'^\s*"([^"]+\.exe)"|^\s*([^\s]+\.exe)',cmd,re.I)
                        if m:
                            try:return Path(m.group(1) or m.group(2)).name
                            except Exception:pass
                    return progid or 'nicht registriert'
                p_prog,p_cmd=_command('.mbp')
                m_prog,m_cmd=_command('.mbdb')
                result={
                    'project_handler':_handler(p_cmd,p_prog),
                    'project_command':p_cmd,
                    'model_handler':_handler(m_cmd,m_prog),
                    'model_command':m_cmd,
                }
            except Exception:
                pass
            _mb_windows_start_cache=result
            return result
'''


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.15"' in s:
        return 0
    if 'APP_VERSION = "1.4.14"' not in s:
        raise RuntimeError('Update 1.4.15 erwartet Projektzentrale 1.4.14. Es wurde nichts verändert.')
    original=s
    s=s.replace('APP_VERSION = "1.4.14"','APP_VERSION = "1.4.15"',1)

    marker='        def _detail_add_link(text,label,path,tag_index):'
    if marker not in s:
        raise RuntimeError('1.4.15 Marker für Positionsakte-Helfer fehlt.')
    if 'def _mb_windows_start_info' not in s:
        s=s.replace(marker,START_HELPER+'\n'+marker,1)

    old_meta="""                mb_model=_mb_model_for_position(folder,r)
                model_name=mb_model.get('name') or '—'
                model_id=mb_model.get('id') or ''
                model_source=mb_model.get('source') or '—'
                model_id_line=f'Modell-ID: {model_id}\\n' if model_id else ''
                detail_text.insert('end',f'Position: {posid}\\nBezeichnung: {bez}\\n\\nmb-Projekt: {projekt}\\nmb-Modul: {modul}\\nmb-Anwendung: {mb_app}\\nmb-Modell: {model_name}\\n{model_id_line}Modellquelle: {model_source}\\nFachgruppe: {gruppe}\\nBerechnungsstatus: {status}\\n')
"""
    new_meta="""                mb_model=_mb_model_for_position(folder,r)
                model_name=mb_model.get('name') or '—'
                model_id=mb_model.get('id') or ''
                model_source=mb_model.get('source') or '—'
                model_id_line=f'Modell-ID: {model_id}\\n' if model_id else ''
                start_info=_mb_windows_start_info()
                if str(mb_app).lower()=='microfe':
                    start_probe=f'Startprüfung Modell (.mbdb): {start_info.get("model_handler") or "nicht registriert"}\\n'
                else:
                    start_probe=f'Startprüfung Projekt (.mbp): {start_info.get("project_handler") or "nicht registriert"}\\n'
                detail_text.insert('end',f'Position: {posid}\\nBezeichnung: {bez}\\n\\nmb-Projekt: {projekt}\\nmb-Modul: {modul}\\nmb-Anwendung: {mb_app}\\nmb-Modell: {model_name}\\n{model_id_line}Modellquelle: {model_source}\\nFachgruppe: {gruppe}\\nBerechnungsstatus: {status}\\n{start_probe}')
"""
    if old_meta not in s:
        raise RuntimeError('1.4.15 Marker für Modellanzeige fehlt.')
    s=s.replace(old_meta,new_meta,1)

    s=s.replace(
        'Hinweis 1.4.14: MicroFe-Modellquellen werden weiterhin positionsgenau erkannt. Interne mb-Datei-IDs werden jetzt sauber als Modell-ID getrennt vom lesbaren Modellnamen angezeigt. Alles bleibt read-only.',
        'Hinweis 1.4.15: Zusätzlich wird read-only geprüft, welche Windows/mb-Dateizuordnung für Projektdateien (.mbp) und MicroFe-Modelldatenbanken (.mbdb) registriert ist. Damit kann der nächste Modellstart ohne geratenen Kommandozeilenparameter gebaut werden.'
    )
    s=s.replace(
        'Quelle: BSPos.mbdb, *.mbp und FEM/*.mbdb werden ausschließlich read-only gelesen. Positionsakte 1.4.14 trennt bei MicroFe lesbaren Modellnamen, interne Modell-ID und konkrete Modellquelle.',
        'Quelle: BSPos.mbdb, *.mbp und FEM/*.mbdb werden ausschließlich read-only gelesen. Positionsakte 1.4.15 ergänzt eine read-only Windows-Startdiagnose für .mbp/.mbdb; es werden keine Registry-Werte verändert.'
    )

    required=(
        'APP_VERSION = "1.4.15"',
        'def _mb_windows_start_info',
        "Startprüfung Modell (.mbdb)",
        "Startprüfung Projekt (.mbp)",
        'Modellquelle: {model_source}',
        'Startweg: ProjektManager → MicroFe',
        'def _mb_model_for_position',
    )
    if not all(x in s for x in required):
        raise RuntimeError('Patch-Ergebnis 1.4.15 unvollständig. Es wurde nichts verändert.')
    if s==original:
        raise RuntimeError('Keine Änderung erzeugt.')

    tmp=APP.with_name('app.py.1415.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.v1414_vor_1415_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp.replace(APP)
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1415_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        print('FEHLER:',e)
        raise SystemExit(1)
