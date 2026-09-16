from pathlib import Path
import datetime
import py_compile
import shutil

APP=Path(__file__).resolve().parent/'app.py'

POSAKTE_HELPER = r'''        def _position_record_store(folder):
            try:
                return _position_project_root(folder)/'.engbers_positionsakte.json'
            except Exception:
                return Path(folder)/'.engbers_positionsakte.json'

        def _position_record_key(folder,pos):
            try:
                base=_position_project_root(folder).resolve()
                mb=Path(folder).resolve()
                try: rel=str(mb.relative_to(base))
                except Exception: rel=str(mb)
                return rel.replace('\\','/').lower()+'|'+str(pos or '').strip().upper()
            except Exception:
                return str(pos or '').strip().upper()

        def _position_record_load(folder):
            try:
                import json
                store=_position_record_store(folder)
                if not store.exists(): return {'version':1,'positions':{}}
                data=json.loads(store.read_text(encoding='utf-8'))
                if not isinstance(data,dict): return {'version':1,'positions':{}}
                if not isinstance(data.get('positions'),dict): data['positions']={}
                return data
            except Exception:
                return {'version':1,'positions':{}}

        def _position_record_save(folder,data):
            try:
                import json
                store=_position_record_store(folder)
                tmp=store.with_name(store.name+'.tmp')
                tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                tmp.replace(store)
                return True
            except Exception:
                return False

        def _position_record_get(folder,pos):
            try:
                data=_position_record_load(folder)
                rec=data.get('positions',{}).get(_position_record_key(folder,pos),{})
                if not isinstance(rec,dict): rec={}
                files=rec.get('files',[])
                if not isinstance(files,list): files=[]
                return {'status':str(rec.get('status') or 'Offen'),'note':str(rec.get('note') or ''),'updated_at':str(rec.get('updated_at') or ''),'files':files}
            except Exception:
                return {'status':'Offen','note':'','updated_at':'','files':[]}

        def _position_record_update(folder,pos,**changes):
            try:
                import datetime as _dt
                data=_position_record_load(folder)
                key=_position_record_key(folder,pos)
                rec=data.setdefault('positions',{}).setdefault(key,{})
                if not isinstance(rec,dict): rec={}; data['positions'][key]=rec
                for k,v in changes.items(): rec[k]=v
                rec['updated_at']=_dt.datetime.now().isoformat(timespec='seconds')
                return _position_record_save(folder,data)
            except Exception:
                return False

        def _position_manual_position_files(folder,pos):
            try:
                base=_position_project_root(folder).resolve()
                rec=_position_record_get(folder,pos)
                out=[]
                for item in rec.get('files',[]):
                    if not isinstance(item,dict): continue
                    rel=str(item.get('path') or '').strip()
                    if not rel: continue
                    p=(base/rel).resolve()
                    try: p.relative_to(base)
                    except Exception: continue
                    if not p.exists() or not p.is_file(): continue
                    cat=str(item.get('category') or '').strip() or _position_category(p,rel)
                    try: ts=p.stat().st_mtime
                    except Exception: ts=0
                    try: shown=str(p.relative_to(base))
                    except Exception: shown=str(p)
                    out.append((900,ts,cat,p,shown+'  [manuell mit Position verknüpft]'))
                out.sort(key=lambda x:(x[0],x[1]),reverse=True)
                return out
            except Exception:
                return []

        def _position_link_file(folder,pos):
            try:
                from tkinter import filedialog, messagebox
                base=_position_project_root(folder).resolve()
                selected=filedialog.askopenfilename(
                    title=f'Datei mit Position {pos} verknüpfen',
                    initialdir=str(base),
                    filetypes=[('Projektdateien','*.pdf *.doc *.docx *.xls *.xlsx *.xlsm *.dwg *.dxf *.ifc *.jpg *.jpeg *.png *.txt *.zip'),('Alle Dateien','*.*')],
                )
                if not selected: return False
                p=Path(selected).resolve()
                try: rel=p.relative_to(base)
                except Exception:
                    messagebox.showwarning('Positionsakte','Bitte eine Datei innerhalb des aktuellen Projektordners auswählen.')
                    return False
                rec=_position_record_get(folder,pos)
                files=list(rec.get('files',[]))
                rels={str(x.get('path') or '').lower() for x in files if isinstance(x,dict)}
                relstr=str(rel)
                if relstr.lower() in rels:
                    messagebox.showinfo('Positionsakte','Diese Datei ist bereits mit der Position verknüpft.')
                    return False
                cat=_position_category(p,relstr)
                files.append({'path':relstr,'category':cat})
                if not _position_record_update(folder,pos,files=files):
                    messagebox.showwarning('Positionsakte','Die Dateiverknüpfung konnte nicht gespeichert werden.')
                    return False
                messagebox.showinfo('Positionsakte',f'Datei wurde mit Position {pos} verknüpft.\n\nKategorie: {cat}\n\nPosition bitte einmal erneut anklicken.')
                return True
            except Exception as exc:
                try:
                    from tkinter import messagebox
                    messagebox.showwarning('Positionsakte',f'Datei konnte nicht verknüpft werden:\n{exc}')
                except Exception: pass
                return False

        def _position_unlink_file(folder,pos):
            try:
                from tkinter import messagebox, simpledialog
                rec=_position_record_get(folder,pos)
                files=[x for x in rec.get('files',[]) if isinstance(x,dict) and str(x.get('path') or '').strip()]
                if not files:
                    messagebox.showinfo('Positionsakte','Für diese Position gibt es keine manuelle Dateiverknüpfung.')
                    return False
                if len(files)==1:
                    idx=0
                    if not messagebox.askyesno('Positionsakte',f'Diese Dateiverknüpfung entfernen?\n\n{files[0].get("path","")}'): return False
                else:
                    listing='\n'.join(f'{i+1}: {x.get("path","")}' for i,x in enumerate(files[:25]))
                    n=simpledialog.askinteger('Positionsakte','Welche Verknüpfung soll entfernt werden?\n\n'+listing,minvalue=1,maxvalue=min(len(files),25))
                    if not n: return False
                    idx=n-1
                removed=files.pop(idx)
                if not _position_record_update(folder,pos,files=files): return False
                messagebox.showinfo('Positionsakte',f'Verknüpfung entfernt:\n{removed.get("path","")}\n\nPosition bitte einmal erneut anklicken.')
                return True
            except Exception:
                return False

        def _position_set_status(folder,pos):
            try:
                from tkinter import simpledialog, messagebox
                current=_position_record_get(folder,pos).get('status') or 'Offen'
                options={1:'Offen',2:'In Bearbeitung',3:'Geprüft',4:'Änderung erforderlich',5:'Erledigt'}
                prompt='Bearbeitungsstatus für '+str(pos)+'\n\nAktuell: '+str(current)+'\n\n1 = Offen\n2 = In Bearbeitung\n3 = Geprüft\n4 = Änderung erforderlich\n5 = Erledigt'
                n=simpledialog.askinteger('Positionsstatus',prompt,minvalue=1,maxvalue=5)
                if not n: return False
                status=options[n]
                if not _position_record_update(folder,pos,status=status): return False
                messagebox.showinfo('Positionsstatus',f'Status wurde auf „{status}“ gesetzt.\n\nPosition bitte einmal erneut anklicken.')
                return True
            except Exception:
                return False

        def _position_edit_note(folder,pos):
            try:
                from tkinter import simpledialog, messagebox
                current=_position_record_get(folder,pos).get('note') or ''
                note=simpledialog.askstring('Positionsnotiz',f'Kurze Notiz zu Position {pos}:',initialvalue=current)
                if note is None: return False
                note=' '.join(str(note).split())[:500]
                if not _position_record_update(folder,pos,note=note): return False
                messagebox.showinfo('Positionsnotiz','Notiz wurde gespeichert.\n\nPosition bitte einmal erneut anklicken.')
                return True
            except Exception:
                return False
'''


def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    s=APP.read_text(encoding='utf-8')
    if 'APP_VERSION = "1.4.30"' in s:
        return 0
    if 'APP_VERSION = "1.4.29"' not in s:
        raise RuntimeError('Update 1.4.30 erwartet Projektzentrale 1.4.29. Es wurde nichts verändert.')
    original=s
    s=s.replace('APP_VERSION = "1.4.29"','APP_VERSION = "1.4.30"',1)

    marker='        def _position_context_plan_files(folder,pos):'
    if marker not in s:
        raise RuntimeError('1.4.30 Marker für Positionsakte-Helfer fehlt.')
    if 'def _position_record_store(folder)' not in s:
        s=s.replace(marker,POSAKTE_HELPER+'\n'+marker,1)

    old="""                matches.sort(key=lambda _h:((_h[0] if len(_h)>0 else 0),(_h[1] if len(_h)>1 else 0)),reverse=True)
                detail_text.insert('end',f'\\nVERKNÜPFTE PROJEKTDATEIEN ({len(matches)})\\n')
                _scope=_position_plan_scope(r.get('pos'))
"""
    new="""                for _hit in _position_manual_position_files(folder,r.get('pos')):
                    try:_key=str(Path(_hit[3]).resolve()).lower()
                    except Exception:_key=str(_hit[3]).lower()
                    _new_matches=[]
                    for _old_hit in matches:
                        try:_old_key=str(Path(_old_hit[3]).resolve()).lower()
                        except Exception:_old_key=str(_old_hit[3]).lower()
                        if _old_key!=_key: _new_matches.append(_old_hit)
                    matches=_new_matches
                    matches.append(_hit); _seen_files.add(_key)
                matches.sort(key=lambda _h:((_h[0] if len(_h)>0 else 0),(_h[1] if len(_h)>1 else 0)),reverse=True)

                _record=_position_record_get(folder,r.get('pos'))
                _status=_record.get('status') or 'Offen'
                _note=_record.get('note') or '—'
                detail_text.insert('end','\\nBEARBEITUNG\\n')
                detail_text.insert('end',f'Status: {_status}\\n')
                detail_text.insert('end',f'Notiz: {_note}\\n')
                _status_tag='posstatus_'+str(abs(hash((str(folder),str(r.get('pos'))))))
                detail_text.insert('end','• Status ändern … (Doppelklick)\\n',_status_tag)
                detail_text.tag_config(_status_tag,underline=True)
                detail_text.tag_bind(_status_tag,'<Double-1>',lambda _e,_f=folder,_p=r.get('pos'):_position_set_status(_f,_p))
                _note_tag='posnote_'+str(abs(hash((str(folder),str(r.get('pos'))))))
                detail_text.insert('end','• Notiz bearbeiten … (Doppelklick)\\n',_note_tag)
                detail_text.tag_config(_note_tag,underline=True)
                detail_text.tag_bind(_note_tag,'<Double-1>',lambda _e,_f=folder,_p=r.get('pos'):_position_edit_note(_f,_p))

                detail_text.insert('end',f'\\nVERKNÜPFTE PROJEKTDATEIEN ({len(matches)})\\n')
                _link_tag='posfile_link_'+str(abs(hash((str(folder),str(r.get('pos'))))))
                detail_text.insert('end','• Datei mit dieser Position verknüpfen … (Doppelklick)\\n',_link_tag)
                detail_text.tag_config(_link_tag,underline=True)
                detail_text.tag_bind(_link_tag,'<Double-1>',lambda _e,_f=folder,_p=r.get('pos'):_position_link_file(_f,_p))
                if _position_manual_position_files(folder,r.get('pos')):
                    _unlink_tag='posfile_unlink_'+str(abs(hash((str(folder),str(r.get('pos'))))))
                    detail_text.insert('end','• Manuelle Dateiverknüpfung entfernen … (Doppelklick)\\n',_unlink_tag)
                    detail_text.tag_config(_unlink_tag,underline=True)
                    detail_text.tag_bind(_unlink_tag,'<Double-1>',lambda _e,_f=folder,_p=r.get('pos'):_position_unlink_file(_f,_p))
                _scope=_position_plan_scope(r.get('pos'))
"""
    if old not in s:
        raise RuntimeError('1.4.30 Marker für Positionsakte-Anzeige fehlt.')
    s=s.replace(old,new,1)

    s=s.replace(
        'Hinweis 1.4.29: Positionspläne können pro Geschoss einmal manuell und dauerhaft zugeordnet werden. Die Zuordnung wird projektbezogen in .engbers_positionsplaene.json gespeichert und anschließend allen Positionen des Geschosses angeboten; sie kann auch wieder entfernt werden.',
        'Hinweis 1.4.30: Die Positionsakte speichert zusätzlich Bearbeitungsstatus, kurze Positionsnotiz und manuelle Dateiverknüpfungen je exakter mb-Position. Dateien bleiben an ihrem Originalort; gespeichert werden nur projektbezogene Verweise in .engbers_positionsakte.json.'
    )
    s=s.replace(
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb, Windows-Dateizuordnungen und Projektdateien werden read-only gelesen. Positionsakte 1.4.29 kann zusätzlich eine vom Benutzer bestätigte Positionsplan-Zuordnung als eigene Projektzentrale-Metadatei im Projektordner speichern; mb-Daten und Registry bleiben unverändert.',
        'Quelle: BSPos.mbdb, *.mbp, FEM/*.mbdb, Windows-Dateizuordnungen und Projektdateien werden read-only gelesen. Positionsakte 1.4.30 speichert Status, Notiz und manuelle Dateiverknüpfungen ausschließlich in einer eigenen Projektzentrale-Metadatei; mb-Daten und Registry bleiben unverändert.'
    )

    required=(
        'APP_VERSION = "1.4.30"',
        'def _position_record_store(folder)',
        "'.engbers_positionsakte.json'",
        'def _position_link_file(folder,pos)',
        'def _position_set_status(folder,pos)',
        'def _position_edit_note(folder,pos)',
        'Datei mit dieser Position verknüpfen … (Doppelklick)',
        'Status ändern … (Doppelklick)',
        'Notiz bearbeiten … (Doppelklick)',
        "for _hit in _position_manual_position_files(folder,r.get('pos'))",
        'def _position_assign_plan(folder,pos)',
    )
    if not all(x in s for x in required):
        raise RuntimeError('Patch-Ergebnis 1.4.30 unvollständig. Es wurde nichts verändert.')
    if s==original:
        raise RuntimeError('Keine Änderung erzeugt.')

    tmp=APP.with_name('app.py.1430.tmp')
    tmp.write_text(s,encoding='utf-8')
    py_compile.compile(str(tmp),doraise=True)
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bak=APP.with_name(f'app.py.v1429_vor_1430_{stamp}.bak')
    shutil.copy2(APP,bak)
    tmp.replace(APP)
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        try:(Path(__file__).resolve().parent/'patch_1430_error.txt').write_text(str(e),encoding='utf-8')
        except Exception:pass
        print('FEHLER:',e)
        raise SystemExit(1)
