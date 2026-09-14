from pathlib import Path
import datetime
import py_compile
import shutil

APP=Path(__file__).resolve().parent/'app.py'


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.8"' in s:
        return 0
    if 'APP_VERSION = "1.4.7"' not in s:
        raise RuntimeError('Update 1.4.8 erwartet Projektzentrale 1.4.7. Es wurde nichts verändert.')

    original=s
    s=s.replace('APP_VERSION = "1.4.7"','APP_VERSION = "1.4.8"',1)

    # 1.4.7 verwendete an vier Stellen die alten Anzeigenamen der Row-Keys.
    # Seit dem universellen Reader 1.4.5 heißen sie desc/module/group/calc_status.
    replacements={
        "bez=str(r.get('bez') or '').strip() or '—'":
            "bez=str(r.get('bez') or r.get('desc') or '').strip() or '—'",
        "modul=str(r.get('modul') or '').strip() or '—'":
            "modul=str(r.get('modul') or r.get('module') or '').strip() or '—'",
        "status=(detail or {}).get('status',r.get('status','—'))":
            "status=(detail or {}).get('status') or r.get('calc_status') or r.get('status') or '—'",
        "gruppe=str(r.get('gruppe') or '').strip() or '—'":
            "gruppe=str(r.get('gruppe') or r.get('group') or '').strip() or '—'",
    }
    for old,new in replacements.items():
        if old not in s:
            raise RuntimeError(f'1.4.8 Marker fehlt: {old[:45]}')
        s=s.replace(old,new,1)

    # Technische Zusatzwerte ebenfalls kompatibel zu den generischen Reader-Keys lesen.
    old_extras="""                extras=[]\n                for key,label in (('art','Art'),('reihenfolge','Reihenfolge'),('ergebnis','mb-Ergebniskennwert'),('gesperrt','Gesperrt'),('file_refs','Dateireferenzen')):\n                    val=(detail or {}).get(key,r.get(key))\n                    if val not in (None,''):\n                        extras.append(f'{label}: {val}')\n"""
    new_extras="""                extras=[]\n                _extra_specs=(\n                    (('art','type'),'Art'),\n                    (('reihenfolge','order','row_order'),'Reihenfolge'),\n                    (('ergebnis','results'),'mb-Ergebniskennwert'),\n                    (('gesperrt','locked'),'Gesperrt'),\n                    (('file_refs',),'Dateireferenzen'),\n                )\n                for keys,label in _extra_specs:\n                    val=None\n                    for key in keys:\n                        if (detail or {}).get(key) not in (None,''):\n                            val=(detail or {}).get(key); break\n                        if r.get(key) not in (None,''):\n                            val=r.get(key); break\n                    if val not in (None,''):\n                        extras.append(f'{label}: {val}')\n"""
    if old_extras not in s:
        raise RuntimeError('1.4.8 Marker für technische Zusatzdaten fehlt.')
    s=s.replace(old_extras,new_extras,1)

    # Verknüpfte Projektdateien nicht mehr als flache Liste, sondern fachlich gruppiert anzeigen.
    old_matches="""                detail_text.insert('end',f'\\nVERKNÜPFTE PROJEKTDATEIEN ({len(matches)})\\n')\n                if matches:\n                    for _score,_ts,cat,p,rel in matches[:6]:\n                        n=_detail_add_link(detail_text,f'• {cat}: {rel}',p,n)\n                    if len(matches)>6:\n                        detail_text.insert('end',f'… {len(matches)-6} weitere Treffer\\n')\n                else:\n                    detail_text.insert('end','Noch keine Datei anhand der Positionsnummer eindeutig zugeordnet.\\n')\n"""
    new_matches="""                detail_text.insert('end',f'\\nVERKNÜPFTE PROJEKTDATEIEN ({len(matches)})\\n')\n                if matches:\n                    category_order=('Prüfstatik','Pläne / CAD','Eigene Nachweise','Dokumente')\n                    groups={k:[] for k in category_order}\n                    for hit in matches:\n                        groups.setdefault(hit[2],[]).append(hit)\n                    shown=0\n                    for cat in category_order:\n                        hits=groups.get(cat) or []\n                        if not hits: continue\n                        detail_text.insert('end',f'\\n{cat.upper()}\\n')\n                        for _score,_ts,_cat,p,rel in hits[:4]:\n                            n=_detail_add_link(detail_text,f'• {rel}',p,n); shown+=1\n                    remaining=max(0,len(matches)-shown)\n                    if remaining:\n                        detail_text.insert('end',f'… {remaining} weitere Treffer\\n')\n                else:\n                    detail_text.insert('end','Noch keine Datei anhand der Positionsnummer eindeutig zugeordnet.\\n')\n"""
    if old_matches not in s:
        raise RuntimeError('1.4.8 Marker für verknüpfte Projektdateien fehlt.')
    s=s.replace(old_matches,new_matches,1)

    s=s.replace(
        'Hinweis 1.4.7: Positionsakte kompakt: mb-Projekt und automatisch zugeordnete Projektdateien stehen oben und lassen sich per Doppelklick öffnen. Originaldateien bleiben read-only.',
        'Hinweis 1.4.8: Positionsakte 2.1: Modul, Fachgruppe und Status werden aus dem universellen mb-Reader korrekt übernommen; verknüpfte Projektdateien sind nach Prüfstatik, Plänen/CAD, eigenen Nachweisen und Dokumenten gruppiert. Alles read-only.'
    )
    s=s.replace(
        'Quelle: BSPos.mbdb wird je mb-Projekt automatisch gesucht · SQLite mode=ro. Positionsakte 1.4.7 zeigt direkte, rein lesende Verknüpfungen zum mb-Projekt und passenden Projektdateien.',
        'Quelle: BSPos.mbdb wird je mb-Projekt automatisch gesucht · SQLite mode=ro. Positionsakte 1.4.8 zeigt direkte, fachlich gruppierte Verknüpfungen zum mb-Projekt und passenden Projektdateien.'
    )

    required=(
        'APP_VERSION = "1.4.8"',
        "r.get('module')",
        "r.get('group')",
        "r.get('calc_status')",
        "category_order=('Prüfstatik','Pläne / CAD','Eigene Nachweise','Dokumente')",
    )
    if not all(x in s for x in required):
        raise RuntimeError('Patch-Ergebnis 1.4.8 unvollständig. Es wurde nichts verändert.')
    if s==original:
        raise RuntimeError('Keine Änderung erzeugt.')

    tmp=APP.with_name('app.py.148.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.v147_vor_148_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp.replace(APP)
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_148_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        print('FEHLER:',e)
        raise SystemExit(1)
