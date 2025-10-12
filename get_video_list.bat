@echo off
REM Helper script to generate a list of video files for bulk upload
REM Run this on the Windows MCP server to get the list of videos
REM
REM Usage: get_video_list.bat [folder_path]
REM Example: get_video_list.bat "C:\Users\jack\Python-Apps\youtube-uploader\downloaded_videos"

setlocal

if "%~1"=="" (
    echo Usage: get_video_list.bat [folder_path]
    echo Example: get_video_list.bat "C:\Users\jack\Python-Apps\youtube-uploader\downloaded_videos"
    exit /b 1
)

set "FOLDER=%~1"

echo Scanning folder: %FOLDER%
echo.
echo Python list format:
echo =====================================
echo video_files = [

for %%F in ("%FOLDER%\*.mp4") do (
    echo     r"%%~fF",
)

echo ]
echo =====================================
echo.
echo Copy the list above and paste it into bulk_upload_xhs_mcp.py

endlocal

