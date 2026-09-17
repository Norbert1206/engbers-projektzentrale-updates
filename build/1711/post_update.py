from pathlib import Path
import sys

base=Path(__file__).resolve().parent
app=base/'app.py'
mod=base/'wordforms_v1700.py'
text=app.read_text(encoding='utf-8') if app.exists() else ''
mt=mod.read_text(encoding='utf-8') if mod.exists() else ''
if 'APP_VERSION = "1.7.11"' not in text:
    raise SystemExit('1.7.11 post-check: Versionsnummer fehlt')
if 'PZ_WORD_FOCUS_BACKSTAGE_V1711' not in mt:
    raise SystemExit('1.7.11 post-check: Fokus-/Backstage-Fix fehlt')
print('Projektzentrale 1.7.11 post-check OK')
