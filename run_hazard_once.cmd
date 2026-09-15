@echo off
cd /d E:\Everest-realtime
C:\Python314\python.exe -B -X utf8 monitor.py run --notify changed --send
exit /b %errorlevel%
