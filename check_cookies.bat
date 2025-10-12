@echo off
setlocal

REM 1) Activate your conda environment
CALL "C:\ProgramData\miniconda3\Scripts\activate.bat" youtube-uploader

REM 2) Go to your project folder
cd /d C:\Users\jack\Python-Apps\youtube-uploader

REM 3) Set the ENV variable
set "ENV=production"

REM 4) Run the cookie expiry checker with logging
powershell -NoProfile -ExecutionPolicy Bypass -Command "& { python check_cookie_expiry.py 2>&1 | Tee-Object -FilePath 'check_cookies_output.log' -Append }"

REM 5) Deactivate your conda environment
CALL conda deactivate

endlocal