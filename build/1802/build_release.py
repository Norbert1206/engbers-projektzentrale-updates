from pathlib import Path
import hashlib
import json
import zipfile

ROOT=Path(__file__).resolve().parents[2]
STABLE=ROOT/'stable'
STABLE.mkdir(exist_ok=True)
zip_path=STABLE/'Engbers_Projektzentrale_UPDATE_1_8_2_TINY.zip'
payload=[
    (ROOT/'build/1802/patch_1802.py','patch_1802.py'),
    (ROOT/'build/1802/post_update.py','post_update.py'),
]
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
    for src,dst in payload:
        z.write(src,dst)
with zipfile.ZipFile(zip_path) as z:
    assert z.testzip() is None
    assert set(z.namelist())=={'patch_1802.py','post_update.py'}
    assert not any(n.lower().endswith(('.png','.jpg','.jpeg','.pdf')) for n in z.namelist())
sha=hashlib.sha256(zip_path.read_bytes()).hexdigest()
manifest={
    'app':'Engbers Projektzentrale',
    'channel':'stable',
    'version':'1.8.2',
    'published_at':'2026-09-17',
    'min_bootstrap_version':'1.8.1',
    'package_url':'https://raw.githubusercontent.com/Norbert1206/engbers-projektzentrale-updates/main/stable/Engbers_Projektzentrale_UPDATE_1_8_2_TINY.zip?rev=1802-local-sasv-release-stamp',
    'package_format':'zip',
    'sha256':sha,
    'notes':'Version 1.8.2: saSV-Freigabeschritt mit lokalem Stempelprofil. Neue Buttons STEMPEL EINRICHTEN und FREIGEBEN & STEMPELN. Die echte Stempel/Unterschrift-Grafik bleibt ausschliesslich lokal unter LOCALAPPDATA und ist nicht Bestandteil des Update-Pakets. Das Word-Original bleibt beim finalen Stempeln unveraendert.',
    'update_available':True,
}
(STABLE/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('PACKAGE_SHA256='+sha)
