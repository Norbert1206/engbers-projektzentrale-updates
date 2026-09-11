from pathlib import Path
import sys, json, shutil, subprocess, time, os

def main():
    if len(sys.argv)<2: return
    marker=Path(sys.argv[1])
    if not marker.exists(): return
    info=json.loads(marker.read_text(encoding='utf-8'))
    staged=Path(info['staged']); app_dir=Path(info['app_dir'])
    time.sleep(1.5)
    protected={'data','project_files','backups'}
    for p in staged.rglob('*'):
        if not p.is_file(): continue
        rel=p.relative_to(staged)
        if rel.parts and rel.parts[0] in protected: continue
        dst=app_dir/rel; dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(p,dst)
    shutil.rmtree(staged,ignore_errors=True)
    try: marker.unlink()
    except Exception: pass
    start=app_dir/'START_PROJEKTZENTRALE.cmd'
    if os.name=='nt' and start.exists(): subprocess.Popen(['cmd','/c','start','',str(start)],cwd=str(app_dir),shell=False)
    else: subprocess.Popen([sys.executable,str(app_dir/'app.py')],cwd=str(app_dir))

if __name__=='__main__': main()
