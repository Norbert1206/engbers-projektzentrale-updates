from pathlib import Path
import ast
import datetime
import py_compile
import shutil
import traceback

APP = Path(__file__).resolve().parent / 'app.py'
VERSION_OLD = '1.5.4'
VERSION_NEW = '1.5.5'
MARKER = 'PZ_PROJECT_EXPLORER_QUEUE_V1505'


def _compile_text(text, name):
    p = APP.with_name(name)
    try:
        p.write_text(text, encoding='utf-8')
        py_compile.compile(str(p), doraise=True)
    finally:
        try: p.unlink()
        except Exception: pass


def _method_span(source, method_name):
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == 'App':
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == method_name:
                    start = sum(len(x) for x in lines[:child.lineno-1])
                    end = sum(len(x) for x in lines[:child.end_lineno])
                    return start, end
    raise RuntimeError(f'1.5.5: Methode {method_name} wurde nicht gefunden.')


def _replace_method(source, method_name, block):
    start, end = _method_span(source, method_name)
    return source[:start] + block.rstrip() + '\n\n' + source[end:]


PROJECT_EXPLORER_METHOD = r'''    def show_project_explorer(self):
        # PZ_PROJECT_EXPLORER_QUEUE_V1505
        # Dateisystem-I/O nur im Worker. Worker beruehrt Tkinter NICHT.
        # Ergebnisse kommen ueber Queue zurueck; Tk arbeitet ausschliesslich im Hauptthread.
        self.clear()
        r = self.project_row()
        sources = self._project_sources()
        self.titleblock(self.content, 'Projekt-Explorer', f"{r['number']} · {r['title']} · stabile Ordneransicht")
        self.program_starter_bar(self.content)

        import queue as _queue
        import threading as _threading
        import faulthandler as _faulthandler

        toolbar = tk.Frame(self.content, bg=BG)
        toolbar.pack(fill='x', pady=(0, 10))
        tk.Button(toolbar, text='+ PROJEKTORDNER VERKNÜPFEN', command=self._link_project_source,
                  bg=ACCENT, fg='white', bd=0, padx=12, pady=7).pack(side='left')
        tk.Label(toolbar, text=f"{len(sources)} Speicherort{'e' if len(sources) != 1 else ''}",
                 bg=BG, fg=MUTED).pack(side='left', padx=(10, 16))
        tk.Label(toolbar, text='Suche in geladenen Einträgen:', bg=BG, fg=MUTED).pack(side='left')
        search_var = tk.StringVar()
        search_entry = tk.Entry(toolbar, textvariable=search_var, width=28)
        search_entry.pack(side='left', padx=(5, 6), ipady=4)
        status_lbl = tk.Label(toolbar, text='', bg=BG, fg=MUTED, font=('Segoe UI', 8))
        status_lbl.pack(side='left', padx=(8, 0))

        pan, body = self.panel(self.content, 'Projektakte · Explorer')
        pan.pack(fill='both', expand=True)
        split = tk.PanedWindow(body, orient='horizontal', bg=PANEL, sashwidth=5, bd=0)
        split.pack(fill='both', expand=True)
        left = tk.Frame(split, bg=PANEL)
        right = tk.Frame(split, bg=PANEL, width=350)
        split.add(left, stretch='always')
        split.add(right, minsize=320)

        cols = ('Typ', 'Geändert', 'Größe', 'Pfad')
        tr = ttk.Treeview(left, columns=cols, show='tree headings', height=22)
        tr.heading('#0', text='Ordner / Datei')
        tr.column('#0', width=390, minwidth=240, stretch=True, anchor='w')
        for c, wid in (('Typ', 85), ('Geändert', 145), ('Größe', 90), ('Pfad', 520)):
            tr.heading(c, text=c)
            tr.column(c, width=wid, minwidth=70, stretch=(c == 'Pfad'), anchor='w')
        sy = ttk.Scrollbar(left, orient='vertical', command=tr.yview)
        sx = ttk.Scrollbar(left, orient='horizontal', command=tr.xview)
        tr.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        tr.grid(row=0, column=0, sticky='nsew')
        sy.grid(row=0, column=1, sticky='ns')
        sx.grid(row=1, column=0, sticky='ew')
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)

        pathmap = {}
        rootmap = {}
        sourcemap = {}
        isdirmap = {}
        mtimemap = {}
        sizemap = {}
        loaded = set()
        loading = set()
        load_token = {}
        dummy = '__PZ_DUMMY__'
        result_q = _queue.Queue()
        poll_scheduled = [False]
        generation = [0]

        def log_error(where):
            try:
                import traceback as _traceback
                p = Path(__file__).resolve().parent / 'project_explorer_error.txt'
                with p.open('a', encoding='utf-8') as f:
                    f.write('\n--- ' + datetime.datetime.now().isoformat() + ' · ' + where + ' ---\n')
                    f.write(_traceback.format_exc())
            except Exception:
                pass

        def dump_hang(tag):
            try:
                p = Path(__file__).resolve().parent / 'project_explorer_hang.log'
                with p.open('ab', buffering=0) as f:
                    f.write(('\n--- ' + datetime.datetime.now().isoformat() + ' · ' + tag + ' ---\n').encode('utf-8','replace'))
                    _faulthandler.dump_traceback(file=f, all_threads=True)
            except Exception:
                pass

        def arm_main_watchdog(tag, seconds=5.0):
            timer = _threading.Timer(seconds, lambda: dump_hang(tag))
            timer.daemon = True
            timer.start()
            return timer

        def fmt_changed(ts):
            try: return datetime.datetime.fromtimestamp(ts).strftime('%d.%m.%Y %H:%M') if ts else '—'
            except Exception: return '—'

        def fmt_size(size, is_dir):
            if is_dir: return '—'
            try: return self.human_size(size)
            except Exception: return '—'

        def selected(event=None):
            iid = ''
            try:
                if event is not None: iid = tr.identify_row(event.y)
            except Exception: iid = ''
            if not iid:
                try:
                    sel = tr.selection(); iid = sel[0] if sel else ''
                except Exception: iid = ''
            if iid:
                try: tr.selection_set(iid); tr.focus(iid)
                except Exception: pass
            return pathmap.get(iid), rootmap.get(iid), iid

        def insert_child(parent, root, info, src=None):
            pp = Path(info['path']); is_dir = bool(info.get('is_dir'))
            try: rel_text = str(pp.relative_to(root))
            except Exception: rel_text = pp.name
            typ = 'Ordner' if is_dir else (pp.suffix.upper().lstrip('.') or 'Datei')
            iid = tr.insert(parent, 'end', text=info.get('name') or pp.name,
                            values=(typ, fmt_changed(info.get('mtime',0)), fmt_size(info.get('size',0), is_dir), rel_text), open=False)
            pathmap[iid] = pp; rootmap[iid] = root; isdirmap[iid] = is_dir
            mtimemap[iid] = info.get('mtime',0); sizemap[iid] = info.get('size',0)
            if src is not None: sourcemap[iid] = src
            if is_dir: tr.insert(iid, 'end', text=dummy, values=('', '', '', ''))
            return iid

        def finish_apply(iid, token, items, error_text=''):
            if token != load_token.get(iid) or iid not in pathmap: return
            loading.discard(iid)
            try:
                for child in tr.get_children(iid):
                    if tr.item(child,'text') in (dummy, 'Wird geladen …'):
                        tr.delete(child)
            except Exception: pass
            if error_text:
                try:
                    tr.insert(iid, 'end', text='Ordner konnte nicht gelesen werden', values=('Hinweis','—','—',error_text))
                    status_lbl.configure(text='Ordner konnte nicht gelesen werden')
                except Exception: pass
                loaded.add(iid); return

            pos = [0]
            def batch():
                if token != load_token.get(iid) or iid not in pathmap: return
                watchdog = arm_main_watchdog('Treeview-Einfuegen blockiert: ' + str(pathmap.get(iid,'')), 5.0)
                try:
                    end = min(pos[0] + 80, len(items))
                    src = sourcemap.get(iid); root = rootmap.get(iid)
                    for info in items[pos[0]:end]: insert_child(iid, root, info, src)
                    pos[0] = end
                    watchdog.cancel()
                    if pos[0] < len(items): self.after(1, batch)
                    else:
                        loaded.add(iid)
                        status_lbl.configure(text=f'{len(items)} Einträge')
                except Exception:
                    try: watchdog.cancel()
                    except Exception: pass
                    log_error('finish_apply/batch')
            batch()

        def poll_results():
            poll_scheduled[0] = False
            try:
                while True:
                    iid, token, items, error_text = result_q.get_nowait()
                    finish_apply(iid, token, items, error_text)
            except _queue.Empty:
                pass
            except Exception:
                log_error('poll_results')
            if loading: schedule_poll()

        def schedule_poll():
            if poll_scheduled[0]: return
            poll_scheduled[0] = True
            try: self.after(50, poll_results)
            except Exception: poll_scheduled[0] = False

        def load_node_async(iid):
            if not iid or iid in loaded or iid in loading: return
            pp = pathmap.get(iid); root = rootmap.get(iid)
            if pp is None or root is None: loaded.add(iid); return
            if not bool(isdirmap.get(iid, False)): loaded.add(iid); return
            generation[0] += 1
            token = generation[0]; load_token[iid] = token; loading.add(iid)
            try:
                for child in tr.get_children(iid):
                    if tr.item(child,'text') == dummy: tr.item(child, text='Wird geladen …')
                status_lbl.configure(text='Ordner wird im Hintergrund gelesen …')
            except Exception: pass
            schedule_poll()

            def worker(path_text, target_iid, target_token):
                items=[]; error_text=''
                try:
                    import os as _os
                    with _os.scandir(path_text) as it:
                        for entry in it:
                            try: is_dir = entry.is_dir(follow_symlinks=False)
                            except Exception: is_dir = False
                            try:
                                st = entry.stat(follow_symlinks=False); mt, sz = st.st_mtime, st.st_size
                            except Exception: mt, sz = 0, 0
                            items.append({'path':entry.path, 'name':entry.name, 'is_dir':is_dir, 'mtime':mt, 'size':sz})
                    items.sort(key=lambda x:(not x['is_dir'], str(x['name']).casefold()))
                except Exception as exc:
                    error_text = repr(exc)
                try: result_q.put((target_iid, target_token, items, error_text))
                except Exception: pass

            _threading.Thread(target=worker, args=(str(pp), iid, token), name='PZ-Filesystem-Only', daemon=True).start()

            def slow_notice(expected_iid=iid, expected_token=token):
                if expected_iid in loading and load_token.get(expected_iid) == expected_token:
                    try: status_lbl.configure(text='Ordner reagiert langsam – Oberfläche bleibt bedienbar')
                    except Exception: pass
            try: self.after(8000, slow_notice)
            except Exception: pass

        def add_source(src, open_root=False):
            root = Path(src['path']); label = f"{src['kind']}: {src['label']}"
            iid = tr.insert('', 'end', text=label, values=('Speicherort','—','—',str(root)), open=open_root)
            pathmap[iid]=root; rootmap[iid]=root; sourcemap[iid]=src; isdirmap[iid]=True; mtimemap[iid]=0; sizemap[iid]=0
            tr.insert(iid, 'end', text=dummy, values=('', '', '', ''))
            if open_root: load_node_async(iid)
            return iid

        def render_normal():
            try:
                generation[0] += 1
                for iid in tr.get_children(''): tr.delete(iid)
                pathmap.clear(); rootmap.clear(); sourcemap.clear(); isdirmap.clear(); mtimemap.clear(); sizemap.clear()
                loaded.clear(); loading.clear(); load_token.clear()
                for idx, src in enumerate(sources): add_source(src, idx == 0)
                status_lbl.configure(text='')
            except Exception: log_error('render_normal')

        tk.Label(right, text='DATEI / ORDNER', bg=PANEL, fg=INK, font=('Segoe UI Semibold', 9)).pack(anchor='w', padx=12, pady=(0,8))
        detail = tk.Text(right, height=13, wrap='word', font=('Segoe UI',9), bg='#fbfaf6', fg=INK, bd=1, relief='solid')
        detail.pack(fill='both', expand=True, padx=12)
        btns=tk.Frame(right,bg=PANEL); btns.pack(fill='x',padx=12,pady=8)
        open_btn=tk.Button(btns,text='ÖFFNEN',bg=DARK,fg='white',bd=0,padx=10,pady=7); open_btn.pack(side='left')
        explorer_btn=tk.Button(btns,text='EXPLORER',bg='#e7e4dc',fg=INK,bd=0,padx=10,pady=7); explorer_btn.pack(side='left',padx=6)
        copy_btn=tk.Button(btns,text='PFAD KOPIEREN',bg='#e7e4dc',fg=INK,bd=0,padx=9,pady=7); copy_btn.pack(side='left')

        def refresh_detail(_evt=None):
            try:
                pp, root, iid = selected(); detail.configure(state='normal'); detail.delete('1.0','end')
                if not pp: detail.configure(state='disabled'); return
                try: rel = pp.relative_to(root)
                except Exception: rel = Path('.')
                is_dir = bool(isdirmap.get(iid, False))
                changed = fmt_changed(mtimemap.get(iid,0)); size = fmt_size(sizemap.get(iid,0), is_dir)
                detail.insert('1.0', f"Name: {pp.name}\nTyp: {'Ordner' if is_dir else (pp.suffix.upper() or 'Datei')}\n\nGeändert: {changed}\nGröße: {size}\n\nRelativer Pfad:\n{rel}\n\nOriginalpfad:\n{pp}")
                detail.configure(state='disabled')
            except Exception: log_error('refresh_detail')

        def open_selected(event=None):
            try:
                pp, root, iid = selected(event)
                if not pp: return 'break'
                if bool(isdirmap.get(iid, False)):
                    load_node_async(iid)
                    try: tr.item(iid, open=True)
                    except Exception: pass
                else: self.open_external_path(str(pp))
            except Exception: log_error('open_selected')
            return 'break'

        def show_in_explorer():
            try:
                pp,_,iid=selected()
                if not pp:return
                if os.name=='nt':
                    if bool(isdirmap.get(iid,False)): subprocess.Popen(['explorer.exe',str(pp)])
                    else: subprocess.Popen(['explorer.exe','/select,',str(pp)])
                else: self.open_external_path(str(pp))
            except Exception: log_error('show_in_explorer')

        def copy_path():
            try:
                pp,_,_=selected()
                if not pp:return
                self.clipboard_clear(); self.clipboard_append(str(pp)); self.update_idletasks()
            except Exception: log_error('copy_path')

        def on_tree_open(_evt=None):
            try: load_node_async(tr.focus())
            except Exception: log_error('on_tree_open')

        def do_search(_evt=None):
            q=search_var.get().strip().casefold()
            if not q: status_lbl.configure(text=''); return 'break'
            hits=[]
            for iid,pp in list(pathmap.items()):
                try:
                    if q in pp.name.casefold(): hits.append(iid)
                except Exception: pass
            if hits:
                iid=hits[0]; tr.selection_set(iid); tr.focus(iid); tr.see(iid); refresh_detail(); status_lbl.configure(text=f'{len(hits)} Treffer in geladenen Einträgen')
            else: status_lbl.configure(text='Kein Treffer in geladenen Einträgen')
            return 'break'

        def collapse_all():
            for iid in list(pathmap):
                try: tr.item(iid,open=False)
                except Exception: pass

        open_btn.configure(command=open_selected); explorer_btn.configure(command=show_in_explorer); copy_btn.configure(command=copy_path)
        tk.Button(toolbar,text='AKTUALISIEREN',command=render_normal,bg='#e7e4dc',fg=INK,bd=0,padx=10,pady=7).pack(side='right')
        tk.Button(toolbar,text='ZUKLAPPEN',command=collapse_all,bg='#e7e4dc',fg=INK,bd=0,padx=10,pady=7).pack(side='right',padx=6)

        menu=tk.Menu(self,tearoff=0)
        menu.add_command(label='Öffnen',command=open_selected); menu.add_command(label='Im Windows-Explorer zeigen',command=show_in_explorer); menu.add_separator(); menu.add_command(label='Pfad kopieren',command=copy_path)
        def popup(e):
            try:
                iid=tr.identify_row(e.y)
                if iid: tr.selection_set(iid); tr.focus(iid); menu.tk_popup(e.x_root,e.y_root)
            except Exception: log_error('popup')

        tr.bind('<<TreeviewOpen>>',on_tree_open); tr.bind('<Double-1>',open_selected); tr.bind('<Return>',open_selected)
        tr.bind('<<TreeviewSelect>>',refresh_detail); tr.bind('<Button-3>',popup); tr.bind('<F5>',lambda e:render_normal())
        tr.bind('<Control-c>',lambda e:(copy_path(),'break')[1]); search_entry.bind('<Return>',do_search); search_entry.bind('<Escape>',lambda e:search_var.set(''))
        render_normal()
'''


def main():
    if not APP.exists(): raise RuntimeError('1.5.5: app.py wurde nicht gefunden.')
    original = APP.read_text(encoding='utf-8')
    if f'APP_VERSION = "{VERSION_NEW}"' in original and MARKER in original: return 0
    if f'APP_VERSION = "{VERSION_OLD}"' not in original:
        raise RuntimeError('Update 1.5.5 erwartet Projektzentrale 1.5.4. Es wurde nichts verändert.')
    candidate = _replace_method(original, 'show_project_explorer', PROJECT_EXPLORER_METHOD)
    candidate = candidate.replace(f'APP_VERSION = "{VERSION_OLD}"', f'APP_VERSION = "{VERSION_NEW}"', 1)
    candidate = candidate.replace('Projektzentrale 1.5.4', 'Projektzentrale 1.5.5')
    for token in (MARKER, f'APP_VERSION = "{VERSION_NEW}"', 'PZ-Filesystem-Only'):
        if token not in candidate: raise RuntimeError('1.5.5: Sicherheitsprüfung fehlgeschlagen: '+token)
    _compile_text(candidate, 'app.py.1505.check')
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup=APP.with_name('app.py.vor_1_5_5_'+stamp+'.bak'); shutil.copy2(APP,backup)
    tmp=APP.with_name('app.py.1505.tmp'); tmp.write_text(candidate,encoding='utf-8'); py_compile.compile(str(tmp),doraise=True); tmp.replace(APP)
    APP.with_name('patch_1505_report.txt').write_text(
        'OK: Projektzentrale 1.5.5 installiert.\nDateisystem-I/O im Projekt-Explorer vollstaendig aus Tk-Hauptthread entfernt.\nWorker kommuniziert ausschliesslich ueber Queue; Hang-Waechter aktiviert.\nBackup: '+str(backup)+'\n', encoding='utf-8')
    return 0

if __name__=='__main__':
    try: raise SystemExit(main())
    except SystemExit: raise
    except Exception:
        try: APP.with_name('patch_1505_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        except Exception: pass
        raise
