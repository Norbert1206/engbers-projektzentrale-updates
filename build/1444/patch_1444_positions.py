def apply(s):
    if "win.title('Kategorie wählen')" not in s:
        start=s.find('        def _position_link_file(folder,pos):\n')
        end=s.find('        def _position_update_bearbeitung_display',start)
        if start<0 or end<0: raise RuntimeError('1.4.44: Positions-Dateiverknüpfung nicht gefunden.')
        new=r'''        def _position_link_file(folder,pos):
            try:
                from tkinter import filedialog, messagebox
                base=_position_project_root(folder).resolve()
                selected=filedialog.askopenfilename(title=f'Datei mit Position {pos} verknüpfen',initialdir=str(base),filetypes=[('Projektdateien','*.pdf *.doc *.docx *.xls *.xlsx *.xlsm *.dwg *.dxf *.ifc *.jpg *.jpeg *.png *.txt *.zip'),('Alle Dateien','*.*')])
                if not selected: return False
                p=Path(selected).resolve()
                try: rel=p.relative_to(base)
                except Exception:
                    messagebox.showwarning('Positionsakte','Bitte eine Datei innerhalb des aktuellen Projektordners auswählen.'); return False
                rec=_position_record_get(folder,pos); files=list(rec.get('files',[])); relstr=str(rel)
                if relstr.lower() in {str(x.get('path') or '').lower() for x in files if isinstance(x,dict)}:
                    messagebox.showinfo('Positionsakte','Diese Datei ist bereits mit der Position verknüpft.'); return False
                default_cat=_position_category(p,relstr); categories=('Prüfstatik','Pläne / CAD','Eigene Nachweise','Dokumente'); chosen={'value':None}
                win=tk.Toplevel(self); win.title('Kategorie wählen'); win.configure(bg=BG); win.transient(self); win.grab_set(); win.resizable(False,False)
                tk.Label(win,text=f'Datei mit Pos. {pos} verknüpfen',bg=BG,fg=INK,font=('Segoe UI Semibold',12)).pack(anchor='w',padx=20,pady=(18,4))
                tk.Label(win,text=p.name,bg=BG,fg=MUTED,font=('Segoe UI',9),wraplength=440,justify='left').pack(anchor='w',padx=20,pady=(0,12))
                def choose(cat): chosen['value']=cat; win.destroy()
                for cat in categories:
                    bg=ACCENT if cat==default_cat else '#e7e4dc'; fg='white' if cat==default_cat else INK
                    tk.Button(win,text=cat,command=lambda c=cat:choose(c),anchor='w',bg=bg,fg=fg,activebackground=bg,activeforeground=fg,bd=0,padx=14,pady=8,width=30).pack(fill='x',padx=20,pady=2)
                tk.Button(win,text='Abbrechen',command=win.destroy,bg=BG,fg=MUTED,bd=0,padx=14,pady=7).pack(anchor='e',padx=20,pady=(8,14))
                try:self.wait_window(win)
                except Exception:pass
                cat=chosen.get('value')
                if not cat:return False
                files.append({'path':relstr,'category':cat})
                if not _position_record_update(folder,pos,files=files):
                    messagebox.showwarning('Positionsakte','Die Dateiverknüpfung konnte nicht gespeichert werden.'); return False
                try:self.after_idle(position_selected)
                except Exception:pass
                return True
            except Exception as exc:
                try: messagebox.showwarning('Positionsakte',f'Datei konnte nicht verknüpft werden:\n{exc}')
                except Exception: pass
                return False

        def _position_unlink_file(folder,pos):
            try:
                from tkinter import messagebox, simpledialog
                rec=_position_record_get(folder,pos); files=[x for x in rec.get('files',[]) if isinstance(x,dict) and str(x.get('path') or '').strip()]
                if not files:
                    messagebox.showinfo('Positionsakte','Für diese Position gibt es keine manuelle Dateiverknüpfung.'); return False
                if len(files)==1:
                    idx=0
                    if not messagebox.askyesno('Positionsakte',f'Diese Dateiverknüpfung entfernen?\n\n{files[0].get("path","")}'): return False
                else:
                    listing='\n'.join(f'{i+1}: {x.get("path","")}' for i,x in enumerate(files[:25]))
                    n=simpledialog.askinteger('Positionsakte','Welche Verknüpfung soll entfernt werden?\n\n'+listing,minvalue=1,maxvalue=min(len(files),25))
                    if not n:return False
                    idx=n-1
                files.pop(idx)
                if not _position_record_update(folder,pos,files=files): return False
                try:self.after_idle(position_selected)
                except Exception:pass
                return True
            except Exception:return False

'''
        s=s[:start]+new+s[end:]
    if 'def _position_layout_1444()' not in s:
        marker='        # 1.4.35: Bearbeitungsstatus kompakt direkt hinter der Positionsspalte.\n'
        if marker not in s: raise RuntimeError('1.4.44: Statusspalten-Abschnitt nicht gefunden.')
        layout=r'''        def _position_layout_1444():
            try:
                cols=list(ptr.cget('columns'))
                if 'pz_bearbeitung' not in cols:return
                display=('Pos.','pz_bearbeitung','Bezeichnung','mb-Modul','mb-Kennwert') if current_project.get('folder') else ('mb-Projekt','Pos.','pz_bearbeitung','Bezeichnung','mb-Modul','mb-Kennwert')
                ptr.configure(displaycolumns=tuple(c for c in display if c in cols)); ptr.column('#0',width=112,minwidth=86,stretch=False,anchor='w')
                widths={'mb-Projekt':(92,78,False),'Pos.':(74,66,False),'pz_bearbeitung':(90,82,False),'Bezeichnung':(245,175,True),'mb-Modul':(72,64,False),'mb-Kennwert':(62,56,False)}
                for col,(w,m,st) in widths.items():
                    if col in cols:ptr.column(col,width=w,minwidth=m,stretch=st,anchor='w')
                ptr.heading('pz_bearbeitung',text='Status')
                try:ptr.xview_moveto(0)
                except Exception:pass
            except Exception:pass

'''
        s=s.replace(marker,layout+marker,1)
    old="""                        vals=list(ptr.item(iid,'values'))\n                        while len(vals)<=status_index:\n                            vals.append('')\n                        vals[status_index]=_position_status_display.get(status,status)\n                        ptr.item(iid,values=tuple(vals))\n"""
    new="""                        vals=list(ptr.item(iid,'values'))\n                        if len(vals)==len(cols)-1: vals.insert(status_index,'')\n                        while len(vals)<len(cols): vals.append('')\n                        vals[status_index]=_position_status_display.get(status,status)\n                        ptr.item(iid,values=tuple(vals))\n"""
    if old in s:s=s.replace(old,new,1)
    elif 'if len(vals)==len(cols)-1: vals.insert(status_index' not in s:raise RuntimeError('1.4.44: Statuswerte-Logik nicht gefunden.')
    if '_position_layout_1444()\n\n        try:\n            import tkinter as _tk' not in s:
        i=s.find('        # 1.4.35: Bearbeitungsstatus kompakt direkt hinter der Positionsspalte.\n'); needle="        except Exception:\n            pass\n\n        try:\n            import tkinter as _tk\n"; p=s.find(needle,i)
        if p<0:raise RuntimeError('1.4.44: Statuslayout-Ende nicht gefunden.')
        s=s[:p]+s[p:].replace(needle,"        except Exception:\n            pass\n\n        _position_layout_1444()\n\n        try:\n            import tkinter as _tk\n",1)
    old="""        def rebuild_positions(*_args):\n            keep=_position_status_current_key()\n            _rebuild_positions_1432_status(*_args)\n            _position_status_apply_to_tree()\n            _position_status_reselect(keep)\n"""
    new="""        def rebuild_positions(*_args):\n            keep=_position_status_current_key()\n            _rebuild_positions_1432_status(*_args)\n            _position_status_apply_to_tree()\n            _position_layout_1444()\n            _position_status_reselect(keep)\n"""
    if old in s:s=s.replace(old,new,1)
    elif '_position_layout_1444()\n            _position_status_reselect(keep)' not in s:raise RuntimeError('1.4.44: Positions-Rebuild nicht gefunden.')
    return s.replace("                    width=20,\n","                    width=17,\n",1)
