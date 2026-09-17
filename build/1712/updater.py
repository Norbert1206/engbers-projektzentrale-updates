from pathlib import Path
import sys, json, shutil, subprocess, time, os, traceback


def _hidden_flags():
    return getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0


def _pythonw():
    py = Path(sys.executable)
    pyw = py.with_name('pythonw.exe')
    return str(pyw if pyw.exists() else py)


def main():
    if len(sys.argv) < 2:
        return
    marker = Path(sys.argv[1])
    if not marker.exists():
        return
    info = json.loads(marker.read_text(encoding='utf-8'))
    staged = Path(info['staged'])
    app_dir = Path(info['app_dir'])
    log = app_dir / 'updater_install.log'
    time.sleep(1.5)
    try:
        protected = {'data', 'project_files', 'backups'}
        for p in staged.rglob('*'):
            if not p.is_file():
                continue
            rel = p.relative_to(staged)
            if rel.parts and rel.parts[0] in protected:
                continue
            dst = app_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)

        shutil.rmtree(staged, ignore_errors=True)
        try: marker.unlink()
        except Exception: pass

        post = app_dir / 'post_update.py'
        if post.exists():
            cp = subprocess.run([_pythonw(), str(post)], cwd=str(app_dir),
                                creationflags=_hidden_flags(), timeout=90)
            if cp.returncode != 0:
                raise RuntimeError(f'post_update.py lieferte Rueckgabecode {cp.returncode}')
            try: post.unlink()
            except Exception: pass

        log.write_text('OK: Update-Dateien kopiert und post_update erfolgreich ausgefuehrt.\n', encoding='utf-8')
    except Exception:
        try: log.write_text('FEHLER:\n' + traceback.format_exc(), encoding='utf-8')
        except Exception: pass

    if os.name == 'nt':
        launcher = app_dir / 'pz_launcher.vbs'
        if launcher.exists():
            subprocess.Popen(['wscript.exe', '//B', str(launcher)], cwd=str(app_dir),
                             creationflags=_hidden_flags(), close_fds=True)
            return
    subprocess.Popen([_pythonw(), str(app_dir / 'app.py')], cwd=str(app_dir),
                     creationflags=_hidden_flags(), close_fds=True)


if __name__ == '__main__':
    main()
