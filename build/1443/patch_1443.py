from pathlib import Path
import datetime
import py_compile
import shutil

APP=Path(__file__).resolve().parent/'app.py'

SEARCH_LINE="        self.tree(frame,('Bereich','Treffer'),hits,[160,560])\n"

SEARCH_BLOCK="        # PZ_SEARCH_OPEN_V1443\n        result_tree=self.tree(frame,('Bereich','Treffer'),hits,[160,560])\n\n        def open_search_hit(event=None):\n            try:\n                iid=''\n                if event is not None:\n                    try: iid=result_tree.identify_row(event.y)\n                    except Exception: iid=''\n                if not iid:\n                    sel=result_tree.selection()\n                    if sel: iid=sel[0]\n                if not iid:\n                    return\n                result_tree.selection_set(iid)\n                vals=result_tree.item(iid,'values')\n                if len(vals)<2:\n                    return\n                area=str(vals[0]).strip()\n                target=str(vals[1]).strip()\n                if area!='Projekt' or not target:\n                    return\n\n                self.refresh_project_combo()\n                pid=self.project_map.get(target)\n                if pid is None:\n                    m=re.match(r'\\s*(\\d{2}-\\d{2,4})\\b',target)\n                    if m:\n                        number=m.group(1)\n                        for label,candidate_pid in self.project_map.items():\n                            if str(label).startswith(number):\n                                target=label\n                                pid=candidate_pid\n                                break\n                if pid is None:\n                    messagebox.showwarning('Projektsuche',\n                        f'Das Projekt konnte nicht geöffnet werden:\\n{target}',parent=w)\n                    return 'break'\n\n                active=None\n                for label,button in self.nav_buttons.items():\n                    try:\n                        if str(button.cget('bg')).lower()==str(DARK2).lower():\n                            active=label\n                            break\n                    except Exception:\n                        pass\n\n                self.project_id=pid\n                self.project_var.set(target)\n                w.destroy()\n\n                def finish_switch():\n                    if active and active in self.nav_buttons:\n                        try:\n                            self.nav_buttons[active].invoke()\n                            return\n                        except Exception:\n                            pass\n                    self.header.configure(text='Projektzentrale')\n                    self.show_dashboard()\n\n                self.after_idle(finish_switch)\n                return 'break'\n            except Exception as exc:\n                try:\n                    messagebox.showerror('Projektsuche',\n                        f'Projekt konnte nicht geöffnet werden:\\n{exc}',parent=w)\n                except Exception:\n                    pass\n                return 'break'\n\n        result_tree.bind('<Double-1>',open_search_hit)\n        result_tree.bind('<Return>',open_search_hit)\n"

def _compile_text(text,name):
    tmp=APP.with_name(name)
    try:
        tmp.write_text(text,encoding='utf-8')
        py_compile.compile(str(tmp),doraise=True)
    finally:
        try: tmp.unlink()
        except Exception: pass

def _patch_search(source):
    if 'PZ_SEARCH_OPEN_V1443' in source:
        return source, True
    if SEARCH_LINE not in source:
        return source, False
    return source.replace(SEARCH_LINE,SEARCH_BLOCK,1), True

def main():
    if not APP.exists():
        raise RuntimeError(f'Installation nicht gefunden: {APP}')
    original=APP.read_text(encoding='utf-8')

    if 'APP_VERSION = "1.4.43"' in original:
        return 0

    previous=None
    for version in ('1.4.42','1.4.41','1.4.40'):
        if f'APP_VERSION = "{version}"' in original:
            previous=version
            break
    if previous is None:
        raise RuntimeError('Update 1.4.43 erwartet Projektzentrale 1.4.40 bis 1.4.42. Es wurde nichts verändert.')

    candidate,changed=_patch_search(original)
    if not changed or 'PZ_SEARCH_OPEN_V1443' not in candidate:
        raise RuntimeError('Der reale Suchdialog aus 1.4.40 wurde nicht gefunden. Die installierte Version bleibt unverändert.')

    _compile_text(candidate,'app.py.1443.search.check')
    candidate=candidate.replace(f'APP_VERSION = "{previous}"','APP_VERSION = "1.4.43"',1)
    _compile_text(candidate,'app.py.1443.final.check')

    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup=APP.with_name(f'app.py.vor_1443_{stamp}.bak')
    shutil.copy2(APP,backup)
    tmp=APP.with_name('app.py.1443.tmp')
    tmp.write_text(candidate,encoding='utf-8')
    tmp.replace(APP)

    try:
        APP.with_name('patch_1443_report.txt').write_text(
            f'Ausgangsversion: {previous}\n'
            'Globale Suche: Ergebnis-Treeview gespeichert und Projekt-Doppelklick direkt gebunden.\n'
            'Projektwechsel: direkt über self.project_map / self.project_id.\n',
            encoding='utf-8'
        )
    except Exception:
        pass
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        try:
            (Path(__file__).resolve().parent/'patch_1443_error.txt').write_text(str(exc),encoding='utf-8')
        except Exception:
            pass
        raise SystemExit(1)
