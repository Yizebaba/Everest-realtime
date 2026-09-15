@echo off
cd /d E:\Everest-realtime
C:\Python314\python.exe -B -X utf8 monitor.py run --all --notify all --send
exit /b %errorlevel%
