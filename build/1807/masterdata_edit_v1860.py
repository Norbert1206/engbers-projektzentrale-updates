import json
import tkinter as tk
from tkinter import messagebox

import masterdata_v1604 as _md


MODULE_VERSION = '1.8.6'
MARKER = 'PZ_MASTERDATA_EDIT_V1860'


def open_masterdata_editor(app):
    db,now_iso,BG,PANEL,INK,MUTED,ACCENT,DARK=_md._base._env(app)
    _md._base._schema(db)
    data=_md._masterdata_row(app)
    project=app.project_row()

    w=tk.Toplevel(app)
    w.title('Projektstammdaten bearbeiten')
    w.geometry('1180x820')
    w.minsize(920,680)
    w.configure(bg=BG)
    w.transient(app)

    head=tk.Frame(w,bg=BG); head.pack(fill='x',padx=22,pady=(18,10))
    tk.Label(head,text='PROJEKTSTAMMDATEN BEARBEITEN',bg=BG,fg=INK,font=('Segoe UI Semibold',18)).pack(anchor='w')
    tk.Label(
        head,
        text='Erkannte Angaben sind Vorschläge. Änderungen gelten künftig für neue Ausgaben; bereits fertige Word- und PDF-Dateien werden nicht verändert.',
        bg=BG,fg=MUTED,justify='left',wraplength=1080,
    ).pack(anchor='w',pady=(5,0))

    canvas=tk.Canvas(w,bg=BG,highlightthickness=0)
    scrollbar=tk.Scrollbar(w,orient='vertical',command=canvas.yview)
    body=tk.Frame(canvas,bg=BG)
    body_id=canvas.create_window((0,0),window=body,anchor='nw')
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side='top',fill='both',expand=True,padx=(22,0),pady=(0,10))
    scrollbar.place(relx=1.0,x=-22,y=105,relheight=.75,anchor='ne')
    body.grid_columnconfigure(0,weight=1,uniform='cards')
    body.grid_columnconfigure(1,weight=1,uniform='cards')
    vars={}
    for idx,(title,fields) in enumerate(_md.GROUPS):
        card=_md._editable_card(body,title,fields,vars,PANEL,INK,MUTED,ACCENT)
        card.grid(
            row=idx//2,column=idx%2,sticky='nsew',
            padx=(0,7) if idx%2==0 else (7,0),pady=(0,10),
        )
    for key,var in vars.items():
        var.set(str(data.get(key,'') or ''))

    def resize(_event=None):
        canvas.configure(scrollregion=canvas.bbox('all'))
        canvas.itemconfigure(body_id,width=max(100,canvas.winfo_width()))
    body.bind('<Configure>',resize); canvas.bind('<Configure>',resize)

    note=tk.Label(
        w,
        text='Hinweis: Die Angaben zur Tragwerksplanung sind das zentrale Büroprofil und werden deshalb projektübergreifend verwendet.',
        bg=BG,fg=MUTED,anchor='w',justify='left',
    )
    note.pack(fill='x',padx=22)

    foot=tk.Frame(w,bg=BG); foot.pack(fill='x',padx=22,pady=(10,16))
    def save():
        values={key:var.get().strip() for key,var in vars.items()}
        con=db(); cursor=con.cursor()
        try:
            cursor.execute('INSERT OR IGNORE INTO project_masterdata(project_id) VALUES(?)',(app.project_id,))
            columns=[name for name,_label in _md.FIELDS]
            saved={name:values.get(name,'') for name in columns}
            try:
                row=cursor.execute('SELECT source_files FROM project_masterdata WHERE project_id=?',(app.project_id,)).fetchone()
                source_files=row['source_files'] if row and row['source_files'] else '[]'
            except Exception:
                source_files='[]'
            saved['source_files']=source_files
            saved['updated_at']=now_iso()
            update_columns=columns+['source_files','updated_at']
            cursor.execute(
                'UPDATE project_masterdata SET '+', '.join(name+'=?' for name in update_columns)+' WHERE project_id=?',
                tuple(saved.get(name,'') for name in update_columns)+(app.project_id,),
            )

            office_map={
                'name':'engineer_name','firm':'engineer_firm','street':'engineer_street',
                'zip':'engineer_zip','city':'engineer_city','phone':'engineer_phone','email':'engineer_email',
            }
            cursor.execute('INSERT OR IGNORE INTO office_profile(id) VALUES(1)')
            cursor.execute(
                'UPDATE office_profile SET '+', '.join(name+'=?' for name in office_map)+' WHERE id=1',
                tuple(values.get(source,'') for source in office_map.values()),
            )

            address=' '.join(
                part for part in (
                    values.get('project_street',''),
                    (values.get('project_zip','')+' '+values.get('project_city','')).strip(),
                ) if part
            ).strip()
            architect=values.get('architect_name','') or values.get('architect_firm','')
            cursor.execute(
                'UPDATE projects SET address=?,client=?,architect=? WHERE id=?',
                (
                    address or (project['address'] or ''),
                    values.get('client_name','') or (project['client'] or ''),
                    architect or (project['architect'] or ''),
                    app.project_id,
                ),
            )
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
        messagebox.showinfo(
            'Projektstammdaten',
            'Die Stammdaten wurden gespeichert.\n\nBereits fertige Dokumente wurden nicht verändert.',
            parent=w,
        )
        w.destroy()
        app.refresh_project_combo()
        app.show_project()

    tk.Button(foot,text='SPEICHERN',command=save,bg=ACCENT,fg='white',bd=0,padx=18,pady=9).pack(side='right')
    tk.Button(foot,text='ABBRECHEN',command=w.destroy,bg='#e7e4dc',fg=INK,bd=0,padx=18,pady=9).pack(side='right',padx=8)
    return w
