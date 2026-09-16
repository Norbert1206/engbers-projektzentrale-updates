from pathlib import Path
import runpy
BASE=Path(__file__).resolve().parent
PATCH=BASE/'patch_1607.py'
if PATCH.exists():runpy.run_path(str(PATCH),run_name='__main__')
