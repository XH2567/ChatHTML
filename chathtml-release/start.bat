@echo off
cd /d "%~dp0"
echo === ChatHTML Server ===
echo Backend API:  http://127.0.0.1:8000/api
echo Frontend UI:  http://127.0.0.1:8000
echo.
chat-html.exe
pause
