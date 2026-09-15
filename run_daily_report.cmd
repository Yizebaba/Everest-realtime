@echo off
cd /d E:\Everest-realtime
rem Daily collection produces local per-source cards. It does not send a summary.
C:\Python314\python.exe -B -X utf8 monitor.py run --all --notify none
exit /b %errorlevel%
