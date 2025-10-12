@echo off
setlocal

REM 1) Activate your conda environment
CALL "C:\ProgramData\miniconda3\Scripts\activate.bat" youtube-uploader

REM 2) Go to your project folder
cd /d C:\Users\jack\Python-Apps\youtube-uploader

REM 3) Set the ENV variable
set "ENV=production"

REM 4) Enable MCP for XHS uploads
set "XHS_MCP_ENABLED=true"
set "XHS_MCP_SERVER_URL=http://192.168.1.9:18060/mcp"

REM 5) Run Python inside PowerShell so Tee-Object grabs both stdout+stderr
powershell -NoProfile -ExecutionPolicy Bypass -Command "& { python main.py --language zh 2>&1 | Tee-Object -FilePath 'script_output.log' -Append }"

REM 6) Deactivate your conda environment
CALL conda deactivate

endlocal