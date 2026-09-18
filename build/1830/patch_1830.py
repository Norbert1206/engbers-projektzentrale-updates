from pathlib import Path
import py_compile, sys

ROOT=Path(sys.argv[1]).resolve()
APP=ROOT/"app.py"
POST=ROOT/"post_update.py"

def one(t,a,b,label):
    c=t.count(a)
    if c!=1:
        raise RuntimeError(f"{label}: {c}")
    return t.replace(a,b,1)

app=APP.read_text(encoding="utf-8")
app=one(app,'APP_VERSION = "1.8.29"','APP_VERSION = "1.8.30"',"app version")

old='''        rows=con.execute('SELECT id,ts,channel,sender,recipient,subject,attachment,original_path FROM comm WHERE project_id=? ORDER BY ts DESC',(self.project_id,)).fetchall()
        con.close()

        pan,b=self.panel(self.content,'Kommunikationsakte'); pan.pack(fill='both',expand=True)
        cols=('Zeit','Kanal','Von','An','Betreff / Thema','Anlage')
        tr=ttk.Treeview(b,columns=cols,show='headings',height=18)
        widths=[145,115,180,200,430,180]
        for i,c in enumerate(cols):
            tr.heading(c,text=c); tr.column(c,width=widths[i],anchor='w',stretch=(c=='Betreff / Thema'))
        pathmap={}
        for row in rows:
            iid=tr.insert('', 'end', values=(row['ts'],row['channel'],row['sender'],row['recipient'],row['subject'],row['attachment']))
            pathmap[iid]=str(row['original_path'] or '')
        sy=ttk.Scrollbar(b,orient='vertical',command=tr.yview); tr.configure(yscrollcommand=sy.set)
        tr.pack(side='left',fill='both',expand=True); sy.pack(side='right',fill='y')

        def open_comm(_evt=None):
            sel=tr.selection()
            if not sel:return
            p=pathmap.get(sel[0],'')
            if not p:return
            try:self.open_external_path(p)
            except Exception as exc:messagebox.showerror('Kommunikation',str(exc),parent=self)

        tr.bind('<Double-1>',open_comm); tr.bind('<Return>',open_comm)
'''

new='''        rows=list(con.execute('SELECT id,ts,channel,sender,recipient,subject,attachment,original_path FROM comm WHERE project_id=? ORDER BY ts DESC',(self.project_id,)).fetchall())
        con.close()

        filterbar=tk.Frame(self.content,bg=BG)
        filterbar.pack(fill='x',pady=(0,10))

        tk.Label(filterbar,text='FILTER',bg=BG,fg=MUTED,font=('Segoe UI',9,'bold')).pack(side='left',padx=(0,6))
        filter_var=tk.StringVar(value='Alle')
        filter_combo=ttk.Combobox(filterbar,textvariable=filter_var,state='readonly',width=15,values=('Alle','Nur Outlook','Eingang','Ausgang'))
        filter_combo.pack(side='left',padx=(0,14))

        tk.Label(filterbar,text='SUCHE PERSON / BETREFF',bg=BG,fg=MUTED,font=('Segoe UI',9,'bold')).pack(side='left',padx=(0,6))
        search_var=tk.StringVar()
        search_entry=tk.Entry(filterbar,textvariable=search_var,bd=1,relief='solid',font=('Segoe UI',10))
        search_entry.pack(side='left',fill='x',expand=True,ipady=5,padx=(0,8))

        status_var=tk.StringVar(value='')
        tk.Label(filterbar,textvariable=status_var,bg=BG,fg=MUTED,font=('Segoe UI',9)).pack(side='right',padx=(12,0))

        pan,b=self.panel(self.content,'Kommunikationsakte'); pan.pack(fill='both',expand=True)
        cols=('Zeit','Kanal','Von','An','Betreff / Thema','Anlage')
        tr=ttk.Treeview(b,columns=cols,show='headings',height=18)
        widths=[145,115,180,200,430,180]
        for i,c in enumerate(cols):
            tr.heading(c,text=c); tr.column(c,width=widths[i],anchor='w',stretch=(c=='Betreff / Thema'))

        pathmap={}

        def refill_comm():
            for iid in tr.get_children():
                tr.delete(iid)
            pathmap.clear()

            mode=filter_var.get()
            needle=search_var.get().strip().casefold()
            shown=0

            for row in rows:
                channel=str(row['channel'] or '')
                channel_cf=channel.casefold()

                if mode=='Nur Outlook' and not channel_cf.startswith('outlook'):
                    continue
                if mode=='Eingang' and 'eingang' not in channel_cf:
                    continue
                if mode=='Ausgang' and 'ausgang' not in channel_cf:
                    continue

                if needle:
                    haystack=' '.join([
                        str(row['sender'] or ''),
                        str(row['recipient'] or ''),
                        str(row['subject'] or ''),
                        str(row['attachment'] or ''),
                        channel,
                    ]).casefold()
                    if needle not in haystack:
                        continue

                iid=tr.insert('', 'end', values=(row['ts'],row['channel'],row['sender'],row['recipient'],row['subject'],row['attachment']))
                pathmap[iid]=str(row['original_path'] or '')
                shown+=1

            status_var.set(f'{shown} von {len(rows)} Einträgen')

        def clear_comm_filter():
            filter_var.set('Alle')
            search_var.set('')
            refill_comm()
            search_entry.focus_set()

        tk.Button(filterbar,text='ZURÜCKSETZEN',command=clear_comm_filter,bg='#e7e4dc',fg=INK,bd=0,padx=12,pady=6).pack(side='right',padx=(8,0))

        sy=ttk.Scrollbar(b,orient='vertical',command=tr.yview); tr.configure(yscrollcommand=sy.set)
        tr.pack(side='left',fill='both',expand=True); sy.pack(side='right',fill='y')

        filter_combo.bind('<<ComboboxSelected>>',lambda _evt: refill_comm())
        search_var.trace_add('write',lambda *_args: refill_comm())
        refill_comm()

        def open_comm(_evt=None):
            sel=tr.selection()
            if not sel:return
            p=pathmap.get(sel[0],'')
            if not p:return
            try:self.open_external_path(p)
            except Exception as exc:messagebox.showerror('Kommunikation',str(exc),parent=self)

        tr.bind('<Double-1>',open_comm); tr.bind('<Return>',open_comm)
'''

app=one(app,old,new,"communication filter block")
APP.write_text(app,encoding="utf-8")

post=POST.read_text(encoding="utf-8")
post=post.replace("update_1829_install.log","update_1830_install.log")
post=post.replace("update_1829_error.txt","update_1830_error.txt")
post=one(post,'APP_VERSION = "1.8.29"','APP_VERSION = "1.8.30"',"post version")
post=post.replace("OK: Update 1.8.29 erfolgreich installiert.","OK: Update 1.8.30 erfolgreich installiert.")
POST.write_text(post,encoding="utf-8")

for p in (APP,POST):
    py_compile.compile(str(p),doraise=True)

check=APP.read_text(encoding="utf-8")
for marker in ("Nur Outlook","SUCHE PERSON / BETREFF","ZURÜCKSETZEN","refill_comm"):
    if marker not in check:
        raise RuntimeError("1.8.30 marker fehlt: "+marker)

print("OK 1.8.30 communication filters")
