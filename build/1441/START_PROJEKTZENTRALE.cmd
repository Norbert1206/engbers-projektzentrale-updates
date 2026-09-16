@echo off
cd /d "%~dp0"
if exist patch_1441.py (
  start /wait "" pythonw.exe patch_1441.py
)
start "" pythonw.exe app.py
exit
