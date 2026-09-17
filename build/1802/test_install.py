from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]

MODULE='''from pathlib import Path\nimport os\nimport shutil\nimport tempfile\nimport subprocess\nimport datetime\nimport tkinter as tk\nfrom tkinter import ttk, messagebox\n\ndef open_wordforms(app):\n    w=None\n    tree=None\n    docs={}\n    status_lbl=None\n    INK='black'\n    ACCENT='gold'\n    DARK='black'\n    BG='white'\n    def open_original(event=None):\n        pass\n    def open_pdf():\n        messagebox.showinfo('Word-Bescheinigungen','Für die aktuelle Auswahl wurde noch keine PDF-Datei erzeugt.',parent=w)\n\n    tree.bind('<Double-1>',open_original)\n    foot=tk.Frame(w,bg=BG); foot.pack(fill='x',padx=22,pady=(0,16))\n    tk.Button(foot,text='WORD ÖFFNEN',command=open_original,bg='#e7e4dc',fg=INK,bd=0,padx=14,pady=9).pack(side='left')\n    tk.Button(foot,text='PDF ÖFFNEN',command=open_pdf,bg='#e7e4dc',fg=INK,bd=0,padx=14,pady=9).pack(side='left',padx=(8,0))\n    tk.Button(foot,text='SCHLIESSEN',command=w.destroy,bg='#e7e4dc',fg=INK,bd=0,padx=14,pady=9).pack(side='right')\n    tk.Button(foot,text='ALLE AUSFÜLLEN',command=lambda:None,bg=ACCENT,fg='white',bd=0,padx=16,pady=9).pack(side='right',padx=8)\n    tk.Button(foot,text='MARKIERTE AUSFÜLLEN',command=lambda:None,bg=DARK,fg='white',bd=0,padx=16,pady=9).pack(side='right')\n    return w\n'''

with tempfile.TemporaryDirectory() as td:
    d=Path(td)
    (d/'app.py').write_text('APP_VERSION = "1.8.1"\n',encoding='utf-8')
    (d/'wordforms_v1700.py').write_text(MODULE,encoding='utf-8')
    shutil.copy2(ROOT/'build/1802/patch_1802.py',d/'patch_1802.py')
    shutil.copy2(ROOT/'build/1802/post_update.py',d/'post_update.py')
    cp=subprocess.run([sys.executable,str(d/'post_update.py')],cwd=d,capture_output=True,text=True)
    if cp.returncode:
        print(cp.stdout)
        print(cp.stderr)
        err=d/'update_1802_error.txt'
        if err.exists(): print(err.read_text(encoding='utf-8'))
    assert cp.returncode==0
    app=(d/'app.py').read_text(encoding='utf-8')
    mod=(d/'wordforms_v1700.py').read_text(encoding='utf-8')
    assert 'APP_VERSION = "1.8.2"' in app
    for token in ('PZ_SASV_RELEASE_STAMP_V1802','STEMPEL EINRICHTEN','FREIGEBEN & STEMPELN','sasv_stempel_unterschrift.png','EngbersSasvStamp1802','III. Unterschrift','shape.Left=260.0f','shape.Width=190.0f','ExportAsFixedFormat'):
        assert token in mod,token
    assert 'from tkinter import ttk, messagebox, filedialog' in mod
    assert (d/'update_1802_install.log').exists()
print('1.8.2 installer test OK')
