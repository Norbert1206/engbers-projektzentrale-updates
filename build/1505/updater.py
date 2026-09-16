from pathlib import Path
import sys, json, shutil, subprocess, time, os


def _hidden_flags():
    return getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0


def main():
    if len(sys.argv) < 2:
        return
    marker = Path(sys.argv[1])
    if not marker.exists():
        return
    info = json.loads(marker.read_text(encoding='utf-8'))
    staged = Path(info['staged'])
    app_dir = Path(info['app_dir'])
    time.sleep(1.2)

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
    try:
        marker.unlink()
    except Exception:
        pass

    if os.name == 'nt':
        launcher = app_dir / 'pz_launcher.vbs'
        if launcher.exists():
            subprocess.Popen(['wscript.exe', '//B', str(launcher)], cwd=str(app_dir),
                             creationflags=_hidden_flags(), close_fds=True)
            return
        py = Path(sys.executable)
        pyw = py.with_name('pythonw.exe')
        exe = str(pyw if pyw.exists() else py)
        subprocess.Popen([exe, str(app_dir / 'app.py')], cwd=str(app_dir),
                         creationflags=_hidden_flags(), close_fds=True)
    else:
        subprocess.Popen([sys.executable, str(app_dir / 'app.py')], cwd=str(app_dir))


if __name__ == '__main__':
    main()
